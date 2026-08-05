"""Core local defaults and compatibility exports for enterprise stores."""

from __future__ import annotations

import copy
from fnmatch import fnmatchcase
from typing import Any

from datus.api.auth.context import AppContext
from datus.api.enterprise.models import AccessDecision, ProjectionInput, ProjectionResult, ResourceRef
from datus.utils.exceptions import DatusException, ErrorCode
from datus_enterprise.storage.local.stores import (
    InMemoryEnterpriseAgentStore,
    InMemoryEnterpriseDatasourceGrantStore,
    InMemoryEnterpriseQuotaStore,
    InMemoryEnterpriseRoleStore,
    InMemoryEnterpriseSecretStore,
    InMemoryEnterpriseUserStore,
    InMemorySessionOwnerStore,
    InMemoryUserDatasourceStore,
    InMemoryUserModelCredentialStore,
    NoopAuditSink,
    SqliteAuditSink,
    SqliteEnterpriseDatasourceGrantStore,
    SqliteEnterpriseRoleStore,
    SqliteEnterpriseUserStore,
    SqliteSessionOwnerStore,
    SqliteUserDatasourceStore,
    SqliteUserModelCredentialStore,
)


class LocalAuthorizationProvider:
    """Default authorization provider for local/open-source mode.

    Missing permissions mean local-compatible allow. If permissions are
    present, checks are evaluated against stable permission keys and glob
    patterns such as ``module.dashboard.*``.
    """

    async def check(self, ctx: AppContext, action: str, resource: ResourceRef) -> AccessDecision:  # noqa: ARG002
        permissions = _context_permissions(ctx)
        if permissions is None:
            return AccessDecision(allowed=True, reason="local-compatible allow")
        if _matches_permission(action, permissions):
            return AccessDecision(allowed=True, reason="permission matched")
        return AccessDecision(allowed=False, reason=f"missing permission {action}", code="PERMISSION_DENIED")

    async def allowed_datasources(self, ctx: AppContext) -> dict[str, Any]:
        return dict(ctx.datasource_grants or {})


class PassthroughConfigProjector:
    """Clone AgentConfig without applying enterprise datasource grants."""

    async def project(self, request: ProjectionInput) -> ProjectionResult:
        projected = copy.deepcopy(request.base_config)
        principal = dict(request.ctx.principal or {})
        if request.requested_datasource:
            if request.requested_datasource not in projected.services.datasources:
                raise DatusException(
                    ErrorCode.COMMON_FIELD_INVALID,
                    message=f"Datasource '{request.requested_datasource}' not found in services.datasources.",
                )
            projected.current_datasource = request.requested_datasource
            principal.setdefault("datasource", request.requested_datasource)
        projected.principal = principal
        return ProjectionResult(
            config=projected,
            principal=principal,
            datasource_grants=dict(request.ctx.datasource_grants or {}),
        )


def _context_permissions(ctx: AppContext) -> list[str] | None:
    if ctx.permissions:
        return sorted(ctx.permissions)
    raw = ctx.principal.get("permissions")
    if raw is None:
        return None
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, str)]
    return []


def _matches_permission(action: str, permissions: list[str]) -> bool:
    return any(permission == "*" or fnmatchcase(action, permission) for permission in permissions)


__all__ = [
    "LocalAuthorizationProvider",
    "PassthroughConfigProjector",
    "InMemoryEnterpriseAgentStore",
    "InMemoryEnterpriseDatasourceGrantStore",
    "InMemoryEnterpriseQuotaStore",
    "InMemoryEnterpriseRoleStore",
    "InMemoryEnterpriseSecretStore",
    "InMemoryEnterpriseUserStore",
    "InMemorySessionOwnerStore",
    "InMemoryUserDatasourceStore",
    "InMemoryUserModelCredentialStore",
    "NoopAuditSink",
    "SqliteAuditSink",
    "SqliteEnterpriseDatasourceGrantStore",
    "SqliteEnterpriseRoleStore",
    "SqliteEnterpriseUserStore",
    "SqliteSessionOwnerStore",
    "SqliteUserDatasourceStore",
    "SqliteUserModelCredentialStore",
]
