"""FastAPI dependencies for enterprise extension providers."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from datus.api.auth.context import AppContext
from datus.api.enterprise.models import AuditEvent, ResourceRef


def get_authorization_provider():
    from datus.api.deps import get_enterprise_extensions

    return get_enterprise_extensions().authorization_provider


def get_audit_sink():
    from datus.api.deps import get_enterprise_extensions

    return get_enterprise_extensions().audit_sink


async def authorize(ctx: AppContext, *, action: str, resource: ResourceRef | None = None):
    provider = get_authorization_provider()
    return await provider.check(ctx, action, resource or ResourceRef(type="module"))


def require_module(permission_key: str):
    """FastAPI dependency factory for module permissions."""

    from datus.api.deps import get_app_context, get_datus_service

    async def _dependency(request: Request, _service: object = Depends(get_datus_service)) -> AppContext:
        ctx = get_app_context(request)
        decision = await authorize(ctx, action=permission_key, resource=ResourceRef(type="module", id=permission_key))
        if not decision.allowed:
            await get_audit_sink().write(
                AuditEvent(
                    user_id=ctx.user_id,
                    action=permission_key,
                    resource_type="module",
                    resource_id=permission_key,
                    decision="deny",
                    reason=decision.reason,
                )
            )
            raise HTTPException(status_code=403, detail=decision.reason or "Permission denied.")
        return ctx

    return _dependency
