"""Request-level AgentConfig projection for datasource-scoped execution."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from typing import Any, Dict, Optional

from datus.api.auth.context import AppContext
from datus.api.enterprise.models import ProjectionInput, ProjectionResult
from datus.configuration.agent_config import AgentConfig
from datus.utils.exceptions import DatusException, ErrorCode


@dataclass(frozen=True)
class ConfigProjection:
    """Projected request config and derived principal."""

    agent_config: AgentConfig
    principal: Dict[str, Any] = field(default_factory=dict)


class DatasourceGrantConfigProjector:
    """Project AgentConfig through request datasource grants.

    This projector is intended for enterprise-enabled deployments. Local mode
    should keep using ``PassthroughConfigProjector`` so no-auth development
    remains compatible.
    """

    async def project(self, request: ProjectionInput) -> ProjectionResult:
        projected = copy.deepcopy(request.base_config)
        configured_datasources = dict(getattr(projected.services, "datasources", {}) or {})
        allowed_grants = _allowed_datasource_grants(
            request.ctx.datasource_grants,
            operation=request.operation,
            configured_datasources=configured_datasources,
        )
        if not allowed_grants:
            return ProjectionResult(
                config=projected,
                principal=dict(request.ctx.principal or {}),
                datasource_grants={},
                denied_reason="No datasource grant available.",
            )

        requested_datasource = (request.requested_datasource or "").strip()
        if requested_datasource:
            if requested_datasource not in configured_datasources:
                raise DatusException(
                    ErrorCode.COMMON_FIELD_INVALID,
                    message=f"Datasource '{requested_datasource}' not found in services.datasources.",
                )
            if requested_datasource not in allowed_grants:
                return ProjectionResult(
                    config=projected,
                    principal=dict(request.ctx.principal or {}),
                    datasource_grants=allowed_grants,
                    denied_reason=f"Datasource '{requested_datasource}' is not authorized for this request.",
                )
            selected_datasource = requested_datasource
        else:
            selected_datasource = _select_default_datasource(projected, allowed_grants)
            if not selected_datasource:
                return ProjectionResult(
                    config=projected,
                    principal=dict(request.ctx.principal or {}),
                    datasource_grants=allowed_grants,
                    denied_reason="No authorized datasource is available for this request.",
                )

        denied_reason = _requested_scope_denial(
            allowed_grants[selected_datasource],
            request,
            selected_datasource=selected_datasource,
        )
        if denied_reason:
            return ProjectionResult(
                config=projected,
                principal=dict(request.ctx.principal or {}),
                datasource_grants=allowed_grants,
                denied_reason=denied_reason,
            )

        projected.services.datasources = {
            key: value for key, value in configured_datasources.items() if key in allowed_grants
        }
        projected.current_datasource = selected_datasource

        principal = dict(request.ctx.principal or {})
        principal["user_id"] = request.ctx.user_id
        principal["datasource"] = selected_datasource
        principal["allowed_datasources"] = sorted(allowed_grants)
        principal["datasource_grants"] = allowed_grants
        projected.principal = principal

        return ProjectionResult(
            config=projected,
            principal=principal,
            datasource_grants=allowed_grants,
        )


async def project_request_config(
    ctx: AppContext,
    agent_config: AgentConfig,
    *,
    requested_datasource: Optional[str] = None,
) -> ConfigProjection:
    """Clone ``agent_config`` and apply request-scoped datasource selection.

    This helper does not write ``.datus/config.yml`` and does not mutate the
    cached ``DatusService.agent_config``. The default implementation performs
    only shape-safe local projection; production enterprise deployments should
    layer datasource grants into this function.
    """

    projected = copy.deepcopy(agent_config)
    principal = dict(ctx.principal or {})
    if requested_datasource:
        if requested_datasource not in projected.services.datasources:
            raise DatusException(
                ErrorCode.COMMON_FIELD_INVALID,
                message=f"Datasource '{requested_datasource}' not found in services.datasources.",
            )
        projected.current_datasource = requested_datasource
        principal.setdefault("datasource", requested_datasource)
    projected.principal = principal
    return ConfigProjection(agent_config=projected, principal=principal)


def _allowed_datasource_grants(
    raw_grants: dict[str, Any],
    *,
    operation: str,
    configured_datasources: dict[str, Any],
) -> dict[str, Any]:
    allowed: dict[str, Any] = {}
    wildcard_grant = _normalize_grant((raw_grants or {}).get("*"))
    if wildcard_grant is not None and _grant_allows_operation(wildcard_grant, operation):
        for datasource_key in configured_datasources:
            allowed[datasource_key] = copy.deepcopy(wildcard_grant)

    for datasource_key, grant in (raw_grants or {}).items():
        if datasource_key == "*":
            continue
        if datasource_key not in configured_datasources:
            continue
        normalized = _normalize_grant(grant)
        if normalized is None:
            continue
        if not _grant_allows_operation(normalized, operation):
            continue
        allowed[datasource_key] = normalized
    return allowed


def _normalize_grant(grant: Any) -> dict[str, Any] | None:
    if grant is True:
        return {"effect": "allow"}
    if grant in (False, None):
        return None
    if not isinstance(grant, dict):
        return None
    effect = str(grant.get("effect", "allow")).strip().lower()
    if effect != "allow":
        return None
    normalized = dict(grant)
    normalized["effect"] = "allow"
    return normalized


def _grant_allows_operation(grant: dict[str, Any], operation: str) -> bool:
    if operation.startswith("catalog.") and grant.get("allow_catalog") is False:
        return False
    if not operation.startswith("catalog.") and grant.get("allow_sql") is False:
        return False
    return True


def _requested_scope_denial(
    grant: dict[str, Any],
    request: ProjectionInput,
    *,
    selected_datasource: str,
) -> str | None:
    checks = [
        ("catalogs", "catalog", request.requested_catalog),
        ("databases", "database", request.requested_database),
        ("schemas", "schema", request.requested_schema),
    ]
    for scope_key, label, value in checks:
        if _scope_allows(grant, scope_key, value):
            continue
        return f"Requested {label} '{value}' is not authorized for datasource '{selected_datasource}'."
    return None


def _scope_allows(grant: dict[str, Any], scope_key: str, value: str | None) -> bool:
    patterns = _scope_patterns(grant, scope_key)
    if patterns is None:
        return True
    requested_value = (value or "").strip()
    if not requested_value:
        return True
    if not patterns:
        return False
    return any(fnmatchcase(requested_value, pattern) for pattern in patterns)


def _scope_patterns(grant: dict[str, Any], scope_key: str) -> list[str] | None:
    if scope_key not in grant or grant.get(scope_key) is None:
        return None
    raw_patterns = grant[scope_key]
    if isinstance(raw_patterns, str):
        raw_patterns = [part.strip() for part in raw_patterns.split(",")]
    if not isinstance(raw_patterns, (list, tuple, set)):
        return []
    return [str(pattern).strip() for pattern in raw_patterns if str(pattern).strip()]


def _select_default_datasource(agent_config: AgentConfig, allowed_grants: dict[str, Any]) -> str | None:
    current_datasource = getattr(agent_config, "current_datasource", "") or ""
    if current_datasource in allowed_grants:
        return current_datasource
    default_datasource = getattr(agent_config.services, "default_datasource", None)
    if default_datasource in allowed_grants:
        return default_datasource
    return next((key for key in agent_config.services.datasources if key in allowed_grants), None)
