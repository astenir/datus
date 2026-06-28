"""Enterprise user administration routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.constants import USER_ID_PATTERN
from datus.api.enterprise.deps import require_platform_active
from datus.api.models.base_models import Result
from datus_enterprise.audit import AuditEvent, audit_decision
from datus_enterprise.authorization import require_module

router = APIRouter(prefix="/api/v1", tags=["enterprise-users"])

AdminUsersCtx = Annotated[AppContext, Depends(require_module("module.admin.users"))]


class UpsertAdminUserRequest(BaseModel):
    """Enterprise user metadata mutation."""

    display_name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    enabled: bool = True


class AdminUserSummary(BaseModel):
    """Sanitized enterprise user metadata."""

    user_id: str
    display_name: str | None = None
    email: str | None = None
    enabled: bool
    created_at: str | None = None
    updated_at: str | None = None


@router.get("/admin/users", response_model=Result[list[AdminUserSummary]], summary="List Admin Users")
async def list_admin_users(
    ctx: AdminUsersCtx,
    enabled: Annotated[bool | None, Query(description="Filter by enabled state.")] = None,
) -> Result[list[AdminUserSummary]]:
    """Return sanitized enterprise user metadata for admin workflows."""

    try:
        records = await deps.get_enterprise_extensions().user_store.list_users(enabled=enabled)
    except Exception:
        await _audit_user_mutation(
            ctx,
            user_id=None,
            operation="list_admin_users",
            decision="deny",
            reason="user list failed",
        )
        return _user_error("USER_LIST_FAILED", "User list failed.")

    users = [_summary_from_record(record) for record in records]
    await _audit_user_mutation(
        ctx,
        user_id=None,
        operation="list_admin_users",
        decision="allow",
        metadata={"count": len(users), "enabled": enabled},
    )
    return Result(success=True, data=users)


@router.get("/admin/users/{user_id}", response_model=Result[AdminUserSummary], summary="Get Admin User")
async def get_admin_user(user_id: str, ctx: AdminUsersCtx) -> Result[AdminUserSummary]:
    """Return sanitized metadata for one enterprise user."""

    invalid = _validate_user_id(user_id)
    if invalid is not None:
        await _audit_user_mutation(ctx, user_id=user_id, operation="get_admin_user", decision="deny", reason=invalid)
        return _user_error("USER_ID_INVALID", invalid)

    try:
        record = await deps.get_enterprise_extensions().user_store.get_user(user_id)
    except Exception:
        await _audit_user_mutation(
            ctx,
            user_id=user_id,
            operation="get_admin_user",
            decision="deny",
            reason="user read failed",
        )
        return _user_error("USER_READ_FAILED", "User read failed.")
    if record is None:
        await _audit_user_mutation(
            ctx,
            user_id=user_id,
            operation="get_admin_user",
            decision="deny",
            reason="user not found",
        )
        return _user_error("RESOURCE_NOT_FOUND", "User not found.")

    summary = _summary_from_record(record)
    await _audit_user_mutation(
        ctx,
        user_id=user_id,
        operation="get_admin_user",
        decision="allow",
        old_summary=_summary_for_audit(summary),
    )
    return Result(success=True, data=summary)


@router.put(
    "/admin/users/{user_id}",
    response_model=Result[AdminUserSummary],
    summary="Upsert Admin User",
    dependencies=[Depends(require_platform_active(operation="admin.users.upsert", resource_type="user"))],
)
async def upsert_admin_user(
    user_id: str,
    body: UpsertAdminUserRequest,
    ctx: AdminUsersCtx,
) -> Result[AdminUserSummary]:
    """Create or replace sanitized enterprise user metadata."""

    invalid = _validate_user_id(user_id)
    if invalid is not None:
        await _audit_user_mutation(ctx, user_id=user_id, operation="upsert_admin_user", decision="deny", reason=invalid)
        return _user_error("USER_ID_INVALID", invalid)

    store = deps.get_enterprise_extensions().user_store
    try:
        before = await store.get_user(user_id)
    except Exception:
        await _audit_user_mutation(
            ctx,
            user_id=user_id,
            operation="upsert_admin_user",
            decision="deny",
            reason="user read failed",
        )
        return _user_error("USER_READ_FAILED", "User read failed.")
    try:
        record = await store.upsert_user(
            user_id=user_id,
            display_name=_optional_str(body.display_name),
            email=_optional_str(body.email),
            enabled=body.enabled,
        )
    except Exception:
        await _audit_user_mutation(
            ctx,
            user_id=user_id,
            operation="upsert_admin_user",
            decision="deny",
            reason="user upsert failed",
            old_summary=_summary_for_audit(_summary_from_record(before)) if before is not None else None,
        )
        return _user_error("USER_UPSERT_FAILED", "User upsert failed.")

    summary = _summary_from_record(record)
    await _audit_user_mutation(
        ctx,
        user_id=user_id,
        operation="upsert_admin_user",
        decision="allow",
        old_summary=_summary_for_audit(_summary_from_record(before)) if before is not None else None,
        new_summary=_summary_for_audit(summary),
    )
    return Result(success=True, data=summary)


@router.post(
    "/admin/users/{user_id}/disable",
    response_model=Result[AdminUserSummary],
    summary="Disable Admin User",
    dependencies=[Depends(require_platform_active(operation="admin.users.disable", resource_type="user"))],
)
async def disable_admin_user(user_id: str, ctx: AdminUsersCtx) -> Result[AdminUserSummary]:
    """Disable future requests from one enterprise user."""

    return await _set_user_enabled(ctx, user_id=user_id, enabled=False, operation="disable_admin_user")


@router.post(
    "/admin/users/{user_id}/enable",
    response_model=Result[AdminUserSummary],
    summary="Enable Admin User",
    dependencies=[Depends(require_platform_active(operation="admin.users.enable", resource_type="user"))],
)
async def enable_admin_user(user_id: str, ctx: AdminUsersCtx) -> Result[AdminUserSummary]:
    """Enable future requests from one enterprise user."""

    return await _set_user_enabled(ctx, user_id=user_id, enabled=True, operation="enable_admin_user")


async def _set_user_enabled(
    ctx: AppContext,
    *,
    user_id: str,
    enabled: bool,
    operation: str,
) -> Result[AdminUserSummary]:
    invalid = _validate_user_id(user_id)
    if invalid is not None:
        await _audit_user_mutation(ctx, user_id=user_id, operation=operation, decision="deny", reason=invalid)
        return _user_error("USER_ID_INVALID", invalid)

    store = deps.get_enterprise_extensions().user_store
    try:
        before = await store.get_user(user_id)
    except Exception:
        await _audit_user_mutation(ctx, user_id=user_id, operation=operation, decision="deny", reason="user read failed")
        return _user_error("USER_READ_FAILED", "User read failed.")
    if before is None:
        await _audit_user_mutation(ctx, user_id=user_id, operation=operation, decision="deny", reason="user not found")
        return _user_error("RESOURCE_NOT_FOUND", "User not found.")

    try:
        record = await store.set_user_enabled(user_id, enabled)
    except Exception:
        await _audit_user_mutation(
            ctx,
            user_id=user_id,
            operation=operation,
            decision="deny",
            reason="user update failed",
            old_summary=_summary_for_audit(_summary_from_record(before)),
        )
        return _user_error("USER_UPDATE_FAILED", "User update failed.")
    if record is None:
        await _audit_user_mutation(ctx, user_id=user_id, operation=operation, decision="deny", reason="user not found")
        return _user_error("RESOURCE_NOT_FOUND", "User not found.")

    summary = _summary_from_record(record)
    await _audit_user_mutation(
        ctx,
        user_id=user_id,
        operation=operation,
        decision="allow",
        old_summary=_summary_for_audit(_summary_from_record(before)),
        new_summary=_summary_for_audit(summary),
    )
    return Result(success=True, data=summary)


async def _audit_user_mutation(
    ctx: AppContext,
    *,
    user_id: str | None,
    operation: str,
    decision: str,
    reason: str | None = None,
    old_summary: dict[str, Any] | None = None,
    new_summary: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    audit_metadata = {"operation": operation}
    if old_summary is not None:
        audit_metadata["old"] = old_summary
    if new_summary is not None:
        audit_metadata["new"] = new_summary
    if metadata:
        audit_metadata.update(metadata)
    await audit_decision(
        ctx,
        AuditEvent(
            action="module.admin.users",
            resource_type="user",
            resource_id=user_id,
            decision=decision,
            reason=reason,
            metadata=audit_metadata,
        ),
    )


def _summary_from_record(record: dict[str, Any]) -> AdminUserSummary:
    return AdminUserSummary(
        user_id=str(record["user_id"]),
        display_name=_optional_str(record.get("display_name")),
        email=_optional_str(record.get("email")),
        enabled=bool(record.get("enabled", True)),
        created_at=_optional_str(record.get("created_at")),
        updated_at=_optional_str(record.get("updated_at")),
    )


def _summary_for_audit(summary: AdminUserSummary) -> dict[str, Any]:
    return {
        "user_id": summary.user_id,
        "display_name": summary.display_name,
        "email": summary.email,
        "enabled": summary.enabled,
    }


def _validate_user_id(user_id: str) -> str | None:
    candidate = user_id.strip()
    if candidate != user_id or not candidate or not USER_ID_PATTERN.fullmatch(user_id):
        return "Invalid user_id. Only letters, digits, underscore and hyphen are allowed."
    return None


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _user_error(error_code: str, message: str) -> Result[Any]:
    return Result(success=False, errorCode=error_code, errorMessage=message)
