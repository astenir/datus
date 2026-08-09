"""Request-level AgentConfig projection for datasource-scoped execution."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from typing import Any, Dict, Optional

from datus.api.auth.context import AppContext
from datus.api.enterprise.models import ProjectionInput, ProjectionResult
from datus.configuration.agent_config import AgentConfig
from datus.utils.datasource_scope import datasource_field_order, datasource_scope_matches, grant_uses_tree_scope
from datus.utils.exceptions import DatusException, ErrorCode
from datus_enterprise.personal_datasources import (
    datasource_id_from_key,
    datasource_record_to_db_config,
    personal_datasource_key,
    personal_datasource_options,
    validate_personal_datasource_policy,
)


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
        personal_grants: dict[str, Any] = {}
        personal_options = personal_datasource_options(projected)
        personal_datasource_denied_keys: set[str] = set()
        if request.ctx.user_id and personal_options["enabled"]:
            personal_datasources = await _load_personal_datasources(request.ctx.user_id)
            for record in personal_datasources:
                datasource_key = personal_datasource_key(str(record["id"]))
                if datasource_key in configured_datasources:
                    continue
                if not record.get("enabled"):
                    personal_datasource_denied_keys.add(datasource_key)
                    continue
                try:
                    validate_personal_datasource_policy(
                        projected,
                        datasource_type=str(record.get("type") or ""),
                        host=str(record.get("host") or ""),
                    )
                except DatusException:
                    personal_datasource_denied_keys.add(datasource_key)
                    continue
                configured_datasources[datasource_key] = datasource_record_to_db_config(record)
                personal_grants[datasource_key] = {
                    "effect": "allow",
                    "allow_catalog": True,
                    "allow_sql": True,
                    "owner": "user",
                }
        requested_datasource = (request.requested_datasource or "").strip()
        if requested_datasource in personal_datasource_denied_keys:
            return ProjectionResult(
                config=projected,
                principal=dict(request.ctx.principal or {}),
                datasource_grants={},
                denied_reason=f"Datasource '{requested_datasource}' is not authorized for this request.",
            )
        if (
            requested_datasource
            and request.ctx.user_id
            and datasource_id_from_key(requested_datasource) is not None
            and requested_datasource not in configured_datasources
            and not personal_options["enabled"]
        ):
            return ProjectionResult(
                config=projected,
                principal=dict(request.ctx.principal or {}),
                datasource_grants={},
                denied_reason="Personal datasources are not enabled.",
            )
        allowed_grants = _allowed_datasource_grants(
            request.ctx.datasource_grants,
            operation=request.operation,
            configured_datasources=configured_datasources,
        )
        allowed_grants.update(personal_grants)
        if not allowed_grants:
            return ProjectionResult(
                config=projected,
                principal=dict(request.ctx.principal or {}),
                datasource_grants={},
                denied_reason="No datasource grant available.",
            )

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
            datasource_type=str(getattr(configured_datasources[selected_datasource], "type", "") or ""),
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
        await _touch_personal_datasource_if_needed(request.ctx.user_id, selected_datasource)

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


async def _load_personal_datasources(user_id: str) -> list[dict[str, Any]]:
    from datus.api import deps

    return await deps.get_enterprise_extensions().user_datasource_store.list_datasources(user_id)


async def _touch_personal_datasource_if_needed(user_id: str | None, datasource_key: str) -> None:
    datasource_id = datasource_id_from_key(datasource_key)
    if not user_id or datasource_id is None:
        return
    from datus.api import deps

    await deps.get_enterprise_extensions().user_datasource_store.touch_datasource_used(user_id, datasource_id)


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
    datasource_type: str = "",
) -> str | None:
    field_order = datasource_field_order(datasource_type)
    requested_coordinate = {
        "catalog": (request.requested_catalog or "").strip(),
        "database": (request.requested_database or "").strip(),
        "schema": (request.requested_schema or "").strip(),
        "table": "",
    }
    requested_field = next(
        (field for field in ("schema", "database", "catalog") if requested_coordinate[field] and field in field_order),
        None,
    )
    if requested_field and grant_uses_tree_scope(grant, field_order):
        if datasource_scope_matches(
            grant,
            coordinate=requested_coordinate,
            target_field=requested_field,
            field_order=field_order,
        ):
            return None
        return (
            f"Requested {requested_field} '{requested_coordinate[requested_field]}' is not authorized "
            f"for datasource '{selected_datasource}'."
        )

    checks = [
        ("catalogs", "catalog", [request.requested_catalog]),
        ("databases", "database", [request.requested_database]),
        ("schemas", "schema", _requested_schema_scope_candidates(request)),
    ]
    for scope_key, label, values in checks:
        if _scope_allows(grant, scope_key, values):
            continue
        value = next((candidate for candidate in values if candidate), None)
        return f"Requested {label} '{value}' is not authorized for datasource '{selected_datasource}'."
    return None


def _scope_allows(grant: dict[str, Any], scope_key: str, values: list[str | None]) -> bool:
    patterns = _scope_patterns(grant, scope_key)
    if patterns is None:
        return True
    candidates = [str(value).strip() for value in values if str(value or "").strip()]
    if not candidates:
        return True
    if not patterns:
        return False
    return any(fnmatchcase(value, pattern) for value in candidates for pattern in patterns)


def _scope_patterns(grant: dict[str, Any], scope_key: str) -> list[str] | None:
    if scope_key not in grant or grant.get(scope_key) is None:
        return None
    raw_patterns = grant[scope_key]
    if isinstance(raw_patterns, str):
        raw_patterns = [part.strip() for part in raw_patterns.split(",")]
    if not isinstance(raw_patterns, (list, tuple, set)):
        return []
    patterns = [str(pattern).strip() for pattern in raw_patterns if str(pattern).strip()]
    return patterns or None


def _requested_schema_scope_candidates(request: ProjectionInput) -> list[str | None]:
    schema = (request.requested_schema or "").strip()
    database = (request.requested_database or "").strip()
    catalog = (request.requested_catalog or "").strip()
    candidates: list[str | None] = [schema or None]
    if database and schema:
        candidates.append(f"{database}.{schema}")
    if catalog and schema:
        candidates.append(f"{catalog}.{schema}")
    if catalog and database and schema:
        candidates.append(f"{catalog}.{database}.{schema}")
    return candidates


def _select_default_datasource(agent_config: AgentConfig, allowed_grants: dict[str, Any]) -> str | None:
    current_datasource = getattr(agent_config, "current_datasource", "") or ""
    if current_datasource in allowed_grants:
        return current_datasource
    default_datasource = getattr(agent_config.services, "default_datasource", None)
    if default_datasource in allowed_grants:
        return default_datasource
    return next((key for key in agent_config.services.datasources if key in allowed_grants), None)
