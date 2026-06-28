"""FastAPI dependencies for enterprise extension providers."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, NamedTuple, Optional

from fastapi import Depends, HTTPException, Request

from datus.api.auth.context import AppContext
from datus.api.enterprise.models import AuditEvent, ProjectionInput, ProjectionResult, ResourceRef
from datus.api.models.base_models import Result

if TYPE_CHECKING:
    from datus.api.services.datus_service import DatusService

_PLATFORM_STATUSES = {"active", "maintenance", "readonly"}


def get_authorization_provider():
    from datus.api.deps import get_enterprise_extensions

    return get_enterprise_extensions().authorization_provider


def get_audit_sink():
    from datus.api.deps import get_enterprise_extensions

    return get_enterprise_extensions().audit_sink


def get_artifact_acl_store():
    from datus.api.deps import get_enterprise_extensions

    return get_enterprise_extensions().artifact_acl_store


def get_config_projector():
    from datus.api.deps import get_enterprise_extensions

    return get_enterprise_extensions().config_projector


async def authorize(ctx: AppContext, *, action: str, resource: ResourceRef | None = None):
    provider = get_authorization_provider()
    return await provider.check(ctx, action, resource or ResourceRef(type="module"))


async def project_request_config(
    ctx: AppContext,
    base_config,
    *,
    operation: str,
    requested_datasource: str | None = None,
    requested_catalog: str | None = None,
    requested_database: str | None = None,
    requested_schema: str | None = None,
    metadata: dict | None = None,
) -> ProjectionResult:
    """Project a request-scoped AgentConfig clone through the configured provider."""

    result = await get_config_projector().project(
        ProjectionInput(
            ctx=ctx,
            base_config=base_config,
            operation=operation,
            requested_datasource=requested_datasource,
            requested_catalog=requested_catalog,
            requested_database=requested_database,
            requested_schema=requested_schema,
            metadata=metadata or {},
        )
    )
    if result.denied_reason:
        resource_id = requested_datasource or result.principal.get("datasource")
        await get_audit_sink().write(
            AuditEvent(
                user_id=ctx.user_id,
                action=operation,
                resource_type="datasource",
                resource_id=resource_id,
                decision="deny",
                reason=result.denied_reason,
            )
        )
        raise HTTPException(status_code=403, detail=result.denied_reason)
    return result


async def require_authorized_module(
    ctx: AppContext, permission_key: str, *, resource: ResourceRef | None = None
) -> None:
    """Raise 403 unless ``ctx`` can use ``permission_key``."""

    decision = await authorize(
        ctx,
        action=permission_key,
        resource=resource or ResourceRef(type="module", id=permission_key),
    )
    if decision.allowed:
        return

    await get_audit_sink().write(
        AuditEvent(
            user_id=ctx.user_id,
            action=permission_key,
            resource_type=(resource.type if resource else "module"),
            resource_id=(resource.id if resource else permission_key),
            decision="deny",
            reason=decision.reason,
        )
    )
    raise HTTPException(status_code=403, detail=decision.reason or "Permission denied.")


def current_platform_status() -> str:
    """Return the configured enterprise platform status."""

    raw_status = os.getenv("DATUS_PLATFORM_STATUS", "active").strip().lower()
    return raw_status if raw_status in _PLATFORM_STATUSES else "unknown"


async def enforce_platform_status(
    ctx: AppContext,
    *,
    operation: str,
    resource_type: str,
    resource_id: str | None = None,
    allowed_statuses: set[str] | None = None,
) -> None:
    """Fail closed for protected enterprise operations when the platform is not writable."""

    from datus.api.deps import get_enterprise_extensions

    extensions = get_enterprise_extensions()
    if not extensions.enabled:
        return

    status = current_platform_status()
    allowed = allowed_statuses or {"active"}
    if status in allowed:
        return

    reason = f"Platform status '{status}' does not allow operation '{operation}'."
    await extensions.audit_sink.write(
        AuditEvent(
            user_id=ctx.user_id,
            action="system.platform_status",
            resource_type=resource_type,
            resource_id=resource_id,
            decision="deny",
            reason=reason,
            metadata={"operation": operation, "platform_status": status},
        )
    )
    raise HTTPException(status_code=403, detail="PLATFORM_STATUS_FORBIDDEN")


def require_platform_active(
    *,
    operation: str,
    resource_type: str,
    resource_id: str | None = None,
):
    """FastAPI dependency for execution or mutation routes blocked outside active status."""

    from datus.api.deps import get_app_context, get_datus_service

    async def _dependency(request: Request, _service: object = Depends(get_datus_service)) -> None:
        ctx = get_app_context(request)
        await enforce_platform_status(
            ctx,
            operation=operation,
            resource_type=resource_type,
            resource_id=resource_id,
            allowed_statuses={"active"},
        )

    return _dependency


async def reject_in_enterprise_mode(
    ctx: AppContext,
    *,
    operation: str,
    resource_type: str,
    resource_id: str | None = None,
) -> None:
    """Reject legacy route surfaces that have no enterprise security chain yet."""

    from datus.api.deps import get_enterprise_extensions

    extensions = get_enterprise_extensions()
    if not extensions.enabled:
        return

    reason = f"Route operation '{operation}' is disabled in enterprise mode."
    await extensions.audit_sink.write(
        AuditEvent(
            user_id=ctx.user_id,
            action="system.route_disabled",
            resource_type=resource_type,
            resource_id=resource_id,
            decision="deny",
            reason=reason,
            metadata={"operation": operation},
        )
    )
    raise HTTPException(status_code=403, detail="ENTERPRISE_ROUTE_DISABLED")


def require_enterprise_route_disabled(
    *,
    operation: str,
    resource_type: str = "legacy_api",
    resource_id: str | None = None,
):
    """FastAPI dependency for API surfaces intentionally unavailable in enterprise mode."""

    from datus.api.deps import get_app_context, get_datus_service

    async def _dependency(request: Request, _service: object = Depends(get_datus_service)) -> None:
        from datus.api.deps import get_enterprise_extensions

        if not get_enterprise_extensions().enabled:
            return
        ctx = get_app_context(request)
        await reject_in_enterprise_mode(
            ctx,
            operation=operation,
            resource_type=resource_type,
            resource_id=resource_id,
        )

    return _dependency


class SessionAccess(NamedTuple):
    """Resolved session access decision for route handlers."""

    error: Optional[Result[dict]]
    user_id: str | None


async def authorize_session_access(
    svc: "DatusService",
    ctx: AppContext,
    session_id: str,
    *,
    action: str,
    require_existing_session: bool = False,
    allow_admin: bool = True,
) -> SessionAccess:
    """Return the disk-scope owner user id when ``ctx`` can access a session."""

    if not ctx.user_id:
        return SessionAccess(error=None, user_id=None)

    from datus.api.deps import get_enterprise_extensions

    extensions = get_enterprise_extensions()
    owner = None
    task = svc.task_manager.get_task(session_id)
    if task is not None:
        owner = getattr(task, "owner_user_id", None)
        if owner is None and extensions.enabled:
            await _audit_session_deny(ctx, session_id, action, "session owner missing")
            return SessionAccess(error=_session_error("SESSION_FORBIDDEN", "Session access denied"), user_id=None)

    if owner is None:
        owner = await extensions.session_owner_store.get_owner(svc.project_id, session_id)

    if owner is None:
        owns_scoped_session = svc.chat.session_exists(session_id, user_id=ctx.user_id)
        if owns_scoped_session:
            if extensions.enabled and extensions.session_body_store is not None:
                await _audit_session_deny(ctx, session_id, action, "session owner missing")
                if require_existing_session:
                    return SessionAccess(error=_session_error("RESOURCE_NOT_FOUND", "Session not found"), user_id=None)
                return SessionAccess(
                    error=_session_error("SESSION_FORBIDDEN", "Session access denied"),
                    user_id=None,
                )
            await extensions.session_owner_store.set_owner(svc.project_id, session_id, ctx.user_id)
            return SessionAccess(error=None, user_id=ctx.user_id)
        if require_existing_session and extensions.enabled:
            return SessionAccess(error=_session_error("RESOURCE_NOT_FOUND", "Session not found"), user_id=None)
        return SessionAccess(error=None, user_id=ctx.user_id)

    if owner == ctx.user_id:
        return SessionAccess(error=None, user_id=ctx.user_id)

    if allow_admin and await _can_administer_sessions(ctx, session_id):
        return SessionAccess(error=None, user_id=owner)

    await _audit_session_deny(ctx, session_id, action, "session owner mismatch")
    return SessionAccess(error=_session_error("SESSION_FORBIDDEN", "Session access denied"), user_id=None)


async def delete_session_owner(svc: "DatusService", session_id: str) -> None:
    """Delete session owner metadata for a removed session."""

    from datus.api.deps import get_enterprise_extensions

    await get_enterprise_extensions().session_owner_store.delete_owner(svc.project_id, session_id)


async def _can_administer_sessions(ctx: AppContext, session_id: str) -> bool:
    from datus.api.deps import get_enterprise_extensions

    extensions = get_enterprise_extensions()
    principal = getattr(ctx, "principal", None) or {}
    has_explicit_permissions = bool(ctx.permissions or principal.get("permissions"))
    if not extensions.enabled and not has_explicit_permissions:
        return False
    decision = await authorize(
        ctx,
        action="module.admin.sessions",
        resource=ResourceRef(type="session", id=session_id),
    )
    return decision.allowed


async def _audit_session_deny(ctx: AppContext, session_id: str, action: str, reason: str) -> None:
    await get_audit_sink().write(
        AuditEvent(
            user_id=ctx.user_id,
            action=f"session.{action}",
            resource_type="session",
            resource_id=session_id,
            decision="deny",
            reason=reason,
        )
    )


def _session_error(error_code: str, message: str) -> Result[dict]:
    return Result[dict](success=False, errorCode=error_code, errorMessage=message)


def require_module(permission_key: str):
    """FastAPI dependency factory for module permissions."""

    from datus.api.deps import get_app_context, get_datus_service

    async def _dependency(request: Request, _service: object = Depends(get_datus_service)) -> AppContext:
        ctx = get_app_context(request)
        await require_authorized_module(ctx, permission_key)
        return ctx

    return _dependency
