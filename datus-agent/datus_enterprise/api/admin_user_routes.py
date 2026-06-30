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
from datus.utils.loggings import get_logger
from datus_enterprise.audit import AuditEvent, audit_decision
from datus_enterprise.authorization import require_module

router = APIRouter(prefix="/api/v1", tags=["enterprise-users"])
logger = get_logger(__name__)

_require_admin_users = require_module("module.admin.users")
AdminUsersCtx = Annotated[AppContext, Depends(_require_admin_users)]


class UpsertAdminUserRequest(BaseModel):
    """Enterprise user metadata mutation."""

    display_name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    enabled: bool = True
    external_user_id: str | None = Field(default=None, max_length=200)
    department: str | None = Field(default=None, max_length=200)
    title: str | None = Field(default=None, max_length=200)
    last_seen_at: str | None = Field(default=None, max_length=100)


class AdminUserRoleSummary(BaseModel):
    """Sanitized role summary embedded in admin user details."""

    role_id: str
    name: str | None = None
    permissions: list[str] = Field(default_factory=list)
    built_in: bool = False


class AdminUserDatasourceGrantSummary(BaseModel):
    """Sanitized datasource grant summary embedded in admin user details."""

    subject_type: str
    subject_id: str
    datasource_key: str
    effect: str
    scope: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None


class AdminUserSummary(BaseModel):
    """Sanitized enterprise user metadata."""

    user_id: str
    display_name: str | None = None
    email: str | None = None
    enabled: bool
    external_user_id: str | None = None
    department: str | None = None
    title: str | None = None
    last_seen_at: str | None = None
    role_ids: list[str] = Field(default_factory=list)
    role_count: int = 0
    direct_datasource_grant_count: int = 0
    created_at: str | None = None
    updated_at: str | None = None


class AdminUserDetail(AdminUserSummary):
    """Detailed enterprise user metadata for one admin user profile."""

    roles: list[AdminUserRoleSummary] = Field(default_factory=list)
    effective_permissions: list[str] = Field(default_factory=list)
    direct_datasource_grants: list[AdminUserDatasourceGrantSummary] = Field(default_factory=list)
    role_datasource_grants: list[AdminUserDatasourceGrantSummary] = Field(default_factory=list)
    role_datasource_grant_count: int = 0
    effective_datasource_grant_count: int = 0


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

    try:
        users = await _list_summaries_from_records(records)
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
        metadata={"count": len(users), "enabled": enabled},
    )
    return Result(success=True, data=users)


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
        await _audit_user_mutation(
            ctx, user_id=user_id, operation=operation, decision="deny", reason="user read failed"
        )
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
    await _audit_user_mutation_best_effort(
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


async def _audit_user_mutation_best_effort(
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
    try:
        await _audit_user_mutation(
            ctx,
            user_id=user_id,
            operation=operation,
            decision=decision,
            reason=reason,
            old_summary=old_summary,
            new_summary=new_summary,
            metadata=metadata,
        )
    except Exception as exc:
        logger.warning(
            "Admin user audit write failed for operation '%s' decision '%s': %s",
            operation,
            decision,
            exc,
        )


def _summary_from_record(record: dict[str, Any]) -> AdminUserSummary:
    return AdminUserSummary(
        user_id=str(record["user_id"]),
        display_name=_optional_str(record.get("display_name")),
        email=_optional_str(record.get("email")),
        enabled=bool(record.get("enabled", True)),
        external_user_id=_optional_str(record.get("external_user_id")),
        department=_optional_str(record.get("department")),
        title=_optional_str(record.get("title")),
        last_seen_at=_optional_str(record.get("last_seen_at")),
        created_at=_optional_str(record.get("created_at")),
        updated_at=_optional_str(record.get("updated_at")),
    )


async def _list_summaries_from_records(records: list[dict[str, Any]]) -> list[AdminUserSummary]:
    summaries = [_summary_from_record(record) for record in records]
    extensions = deps.get_enterprise_extensions()
    direct_grants = await extensions.datasource_grant_store.list_grants(subject_type="user")
    direct_grant_counts: dict[str, int] = {}
    for grant in direct_grants:
        subject_id = _optional_str(grant.get("subject_id"))
        if subject_id is None:
            continue
        direct_grant_counts[subject_id] = direct_grant_counts.get(subject_id, 0) + 1

    for summary in summaries:
        role_ids = sorted(await extensions.role_store.list_user_roles(summary.user_id))
        summary.role_ids = role_ids
        summary.role_count = len(role_ids)
        summary.direct_datasource_grant_count = direct_grant_counts.get(summary.user_id, 0)
    return summaries


async def _detail_from_record(record: dict[str, Any]) -> AdminUserDetail:
    summary = _summary_from_record(record)
    extensions = deps.get_enterprise_extensions()
    role_ids = sorted(await extensions.role_store.list_user_roles(summary.user_id))
    role_records = {str(role["role_id"]): role for role in await extensions.role_store.list_roles()}
    roles = [_role_summary_from_record(role_records.get(role_id), role_id=role_id) for role_id in role_ids]
    direct_grant_records = await extensions.datasource_grant_store.list_grants(
        subject_type="user",
        subject_id=summary.user_id,
    )
    role_grant_records: list[dict[str, Any]] = []
    for role_id in role_ids:
        role_grant_records.extend(
            await extensions.datasource_grant_store.list_grants(subject_type="role", subject_id=role_id)
        )

    direct_grants = [_datasource_grant_summary_from_record(record) for record in direct_grant_records]
    role_grants = [_datasource_grant_summary_from_record(record) for record in role_grant_records]
    effective_grant_keys = {
        str(grant["datasource_key"])
        for grant in [*direct_grant_records, *role_grant_records]
        if grant.get("datasource_key") is not None
    }
    permissions = sorted({permission for role in roles for permission in role.permissions})

    return AdminUserDetail(
        user_id=summary.user_id,
        display_name=summary.display_name,
        email=summary.email,
        enabled=summary.enabled,
        external_user_id=summary.external_user_id,
        department=summary.department,
        title=summary.title,
        last_seen_at=summary.last_seen_at,
        role_ids=role_ids,
        role_count=len(role_ids),
        direct_datasource_grant_count=len(direct_grants),
        created_at=summary.created_at,
        updated_at=summary.updated_at,
        roles=roles,
        effective_permissions=permissions,
        direct_datasource_grants=direct_grants,
        role_datasource_grants=role_grants,
        role_datasource_grant_count=len(role_grants),
        effective_datasource_grant_count=len(effective_grant_keys),
    )


def _role_summary_from_record(record: dict[str, Any] | None, *, role_id: str) -> AdminUserRoleSummary:
    if record is None:
        return AdminUserRoleSummary(role_id=role_id)
    return AdminUserRoleSummary(
        role_id=str(record["role_id"]),
        name=_optional_str(record.get("name")),
        permissions=sorted({str(permission) for permission in record.get("permissions") or [] if str(permission)}),
        built_in=bool(record.get("built_in", False)),
    )


def _datasource_grant_summary_from_record(record: dict[str, Any]) -> AdminUserDatasourceGrantSummary:
    scope = record.get("scope")
    return AdminUserDatasourceGrantSummary(
        subject_type=str(record["subject_type"]),
        subject_id=str(record["subject_id"]),
        datasource_key=str(record["datasource_key"]),
        effect=str(record.get("effect") or "allow"),
        scope=dict(scope) if isinstance(scope, dict) else {},
        created_at=_optional_str(record.get("created_at")),
        updated_at=_optional_str(record.get("updated_at")),
    )


def _summary_for_audit(summary: AdminUserSummary) -> dict[str, Any]:
    return {
        "user_id": summary.user_id,
        "display_name": summary.display_name,
        "email": summary.email,
        "enabled": summary.enabled,
        "external_user_id": summary.external_user_id,
        "department": summary.department,
        "title": summary.title,
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
