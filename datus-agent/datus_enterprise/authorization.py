"""Authorization helpers for enterprise route wrappers.

This package provides local-compatible defaults: if no permission list is
present in ``AppContext.principal``, access is allowed so existing no-auth
deployments keep working. Enterprise deployments should replace this with a
provider backed by RBAC metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
from typing import Optional

from fastapi import HTTPException

from datus.api.auth.context import AppContext
from datus.api.deps import AppContextDep


@dataclass(frozen=True)
class ResourceRef:
    """Resource being authorized."""

    type: str
    id: Optional[str] = None


@dataclass(frozen=True)
class AuthorizationDecision:
    """Authorization result."""

    allowed: bool
    reason: str = ""


class LocalAuthorizationProvider:
    """Default authorization provider for local-compatible mode."""

    async def check(
        self,
        ctx: AppContext,
        *,
        action: str,
        resource: Optional[ResourceRef] = None,  # noqa: ARG002
    ) -> AuthorizationDecision:
        permissions = _principal_permissions(ctx)
        if permissions is None:
            return AuthorizationDecision(allowed=True, reason="local-compatible allow")
        if _matches_permission(action, permissions):
            return AuthorizationDecision(allowed=True, reason="permission matched")
        return AuthorizationDecision(allowed=False, reason=f"missing permission {action}")


_authorization_provider: LocalAuthorizationProvider = LocalAuthorizationProvider()


def get_authorization_provider() -> LocalAuthorizationProvider:
    return _authorization_provider


async def authorize(
    ctx: AppContext,
    *,
    action: str,
    resource: Optional[ResourceRef] = None,
) -> AuthorizationDecision:
    return await get_authorization_provider().check(ctx, action=action, resource=resource)


def require_module(permission_key: str):
    """FastAPI dependency factory for module permissions."""

    async def _dependency(ctx: AppContextDep) -> AppContext:
        decision = await authorize(ctx, action=permission_key)
        if not decision.allowed:
            raise HTTPException(status_code=403, detail=decision.reason or "Permission denied.")
        return ctx

    return _dependency


def _principal_permissions(ctx: AppContext) -> Optional[list[str]]:
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
