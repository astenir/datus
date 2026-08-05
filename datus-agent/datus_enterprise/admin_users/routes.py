"""Enterprise user administration routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.enterprise.deps import require_platform_active
from datus.api.models.base_models import Result
from datus_enterprise.admin_users.helpers import (
    _audit_user_mutation,
    _audit_user_mutation_best_effort,
    _deny_user_disable_if_protected,
    _detail_from_record,
    _list_summaries_from_records,
    _optional_str,
    _set_user_enabled,
    _summary_for_audit,
    _summary_from_record,
    _user_error,
    _user_matches_search,
    _validate_user_id,
)
from datus_enterprise.admin_users.models import (
    AdminUserDetail,
    AdminUserSummary,
    UpsertAdminUserRequest,
)
from datus_enterprise.api.admin_pagination import (
    ADMIN_LIST_DEFAULT_LIMIT,
    ADMIN_LIST_MAX_LIMIT,
    AdminListResult,
    paginate_admin_records,
)
from datus_enterprise.authorization import require_module

router = APIRouter(prefix="/api/v1", tags=["enterprise-users"])
_require_admin_users = require_module("module.admin.users")
AdminUsersCtx = Annotated[AppContext, Depends(_require_admin_users)]


@router.get("/admin/users", response_model=AdminListResult[AdminUserSummary], summary="List Admin Users")
async def list_admin_users(
    ctx: AdminUsersCtx,
    enabled: Annotated[bool | None, Query(description="Filter by enabled state.")] = None,
    search: Annotated[str | None, Query(max_length=200, description="Search user profile fields.")] = None,
    limit: Annotated[int, Query(ge=1, le=ADMIN_LIST_MAX_LIMIT)] = ADMIN_LIST_DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdminListResult[AdminUserSummary] | Result[Any]:
    """Return sanitized enterprise user metadata for admin workflows."""

    try:
        store = deps.get_enterprise_extensions().user_store
        list_page = getattr(store, "list_users_page", None)
        records_are_offset = callable(list_page)
        if records_are_offset:
            records = await list_page(
                enabled=enabled,
                search=search,
                limit=limit + 1,
                offset=offset,
            )
        else:
            records = await store.list_users(enabled=enabled)
            records = [record for record in records if _user_matches_search(record, search)]
    except Exception:
        await _audit_user_mutation(
            ctx,
            user_id=None,
            operation="list_admin_users",
            decision="deny",
            reason="user list failed",
        )
        return _user_error("USER_LIST_FAILED", "User list failed.")

    try:
        page = paginate_admin_records(
            records,
            limit=limit,
            offset=offset,
            records_are_offset=records_are_offset,
        )
        users = await _list_summaries_from_records(page.data or [])
    except Exception:
        await _audit_user_mutation(
            ctx,
            user_id=None,
            operation="list_admin_users",
            decision="deny",
            reason="user list enrichment failed",
        )
        return _user_error("USER_LIST_FAILED", "User list failed.")
    await _audit_user_mutation(
        ctx,
        user_id=None,
        operation="list_admin_users",
        decision="allow",
        metadata={"count": len(users), "enabled": enabled, "offset": offset, "has_more": page.pagination.has_more},
    )
    return AdminListResult(success=True, data=users, pagination=page.pagination)


@router.get("/admin/users/{user_id}", response_model=Result[AdminUserDetail], summary="Get Admin User")
async def get_admin_user(user_id: str, ctx: AdminUsersCtx) -> Result[AdminUserDetail]:
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

    try:
        detail = await _detail_from_record(record)
    except Exception:
        await _audit_user_mutation(
            ctx,
            user_id=user_id,
            operation="get_admin_user",
            decision="deny",
            reason="user read enrichment failed",
        )
        return _user_error("USER_READ_FAILED", "User read failed.")
    summary = _summary_from_record(record)
    await _audit_user_mutation(
        ctx,
        user_id=user_id,
        operation="get_admin_user",
        decision="allow",
        old_summary=_summary_for_audit(summary),
    )
    return Result(success=True, data=detail)


@router.put(
    "/admin/users/{user_id}",
    response_model=Result[AdminUserSummary],
    summary="Upsert Admin User",
    dependencies=[
        Depends(_require_admin_users),
        Depends(require_platform_active(operation="admin.users.upsert", resource_type="user")),
    ],
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

    if before is not None and bool(before.get("enabled", True)) and not body.enabled:
        blocked = await _deny_user_disable_if_protected(
            ctx,
            user_id=user_id,
            operation="upsert_admin_user",
            before=before,
        )
        if blocked is not None:
            return blocked

    try:
        record = await store.upsert_user(
            user_id=user_id,
            display_name=_optional_str(body.display_name),
            email=_optional_str(body.email),
            enabled=body.enabled,
            external_user_id=_optional_str(body.external_user_id),
            department=_optional_str(body.department),
            title=_optional_str(body.title),
            last_seen_at=_optional_str(body.last_seen_at),
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
    await _audit_user_mutation_best_effort(
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
    dependencies=[
        Depends(_require_admin_users),
        Depends(require_platform_active(operation="admin.users.disable", resource_type="user")),
    ],
)
async def disable_admin_user(user_id: str, ctx: AdminUsersCtx) -> Result[AdminUserSummary]:
    """Disable future requests from one enterprise user."""

    return await _set_user_enabled(ctx, user_id=user_id, enabled=False, operation="disable_admin_user")


@router.post(
    "/admin/users/{user_id}/enable",
    response_model=Result[AdminUserSummary],
    summary="Enable Admin User",
    dependencies=[
        Depends(_require_admin_users),
        Depends(require_platform_active(operation="admin.users.enable", resource_type="user")),
    ],
)
async def enable_admin_user(user_id: str, ctx: AdminUsersCtx) -> Result[AdminUserSummary]:
    """Enable future requests from one enterprise user."""

    return await _set_user_enabled(ctx, user_id=user_id, enabled=True, operation="enable_admin_user")
