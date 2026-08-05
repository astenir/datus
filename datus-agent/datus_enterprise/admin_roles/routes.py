"""Enterprise role administration routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.enterprise.deps import require_platform_active
from datus.api.models.base_models import Result
from datus_enterprise.admin_roles.helpers import (
    _audit_role_mutation,
    _audit_role_mutation_best_effort,
    _audit_user_roles_mutation,
    _audit_user_roles_mutation_best_effort,
    _is_role_not_found_error,
    _list_role_users_after_delete_false,
    _load_user_for_roles,
    _normalized_permissions,
    _normalized_role_ids,
    _optional_str,
    _permissions_not_grantable,
    _required_str,
    _role_error,
    _role_matches_search,
    _summary_for_audit,
    _summary_from_record,
    _user_roles_summary_for_audit,
    _user_roles_validation_error_code,
    _validate_permissions,
    _validate_role_id,
    _validate_role_ids,
    _validate_role_name,
    _validate_user_id,
    _validation_error_code,
)
from datus_enterprise.admin_roles.models import (
    AdminRoleSummary,
    AdminUserRolesSummary,
    SetRolePermissionsRequest,
    SetUserRolesRequest,
    UpsertAdminRoleRequest,
)
from datus_enterprise.api.admin_pagination import (
    ADMIN_LIST_DEFAULT_LIMIT,
    ADMIN_LIST_MAX_LIMIT,
    AdminListResult,
    paginate_admin_records,
)
from datus_enterprise.authorization import require_module

router = APIRouter(prefix="/api/v1", tags=["enterprise-roles"])
_require_admin_roles = require_module("module.admin.roles")
AdminRolesCtx = Annotated[AppContext, Depends(_require_admin_roles)]

@router.get("/admin/roles", response_model=AdminListResult[AdminRoleSummary], summary="List Admin Roles")
async def list_admin_roles(
    ctx: AdminRolesCtx,
    built_in: Annotated[bool | None, Query(description="Filter by built-in state.")] = None,
    search: Annotated[str | None, Query(max_length=200, description="Search role fields and permissions.")] = None,
    limit: Annotated[int, Query(ge=1, le=ADMIN_LIST_MAX_LIMIT)] = ADMIN_LIST_DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdminListResult[AdminRoleSummary] | Result[Any]:
    """Return sanitized enterprise role metadata for admin workflows."""

    try:
        records = await deps.get_enterprise_extensions().role_store.list_roles()
    except Exception:
        await _audit_role_mutation(
            ctx,
            role_id=None,
            operation="list_admin_roles",
            decision="deny",
            reason="role list failed",
        )
        return _role_error("ROLE_LIST_FAILED", "Role list failed.")

    roles = [
        _summary_from_record(record)
        for record in records
        if (built_in is None or bool(record.get("built_in", False)) is built_in)
        and _role_matches_search(record, search)
    ]
    page = paginate_admin_records(roles, limit=limit, offset=offset)
    await _audit_role_mutation(
        ctx,
        role_id=None,
        operation="list_admin_roles",
        decision="allow",
        metadata={
            "count": len(page.data or []),
            "built_in": built_in,
            "offset": offset,
            "has_more": page.pagination.has_more,
        },
    )
    return page


@router.get("/admin/roles/{role_id}", response_model=Result[AdminRoleSummary], summary="Get Admin Role")
async def get_admin_role(role_id: str, ctx: AdminRolesCtx) -> Result[AdminRoleSummary]:
    """Return sanitized metadata for one enterprise role."""

    invalid = _validate_role_id(role_id)
    if invalid is not None:
        await _audit_role_mutation(ctx, role_id=role_id, operation="get_admin_role", decision="deny", reason=invalid)
        return _role_error("ROLE_ID_INVALID", invalid)

    try:
        record = await deps.get_enterprise_extensions().role_store.get_role(role_id)
    except Exception:
        await _audit_role_mutation(
            ctx,
            role_id=role_id,
            operation="get_admin_role",
            decision="deny",
            reason="role read failed",
        )
        return _role_error("ROLE_READ_FAILED", "Role read failed.")
    if record is None:
        await _audit_role_mutation(
            ctx,
            role_id=role_id,
            operation="get_admin_role",
            decision="deny",
            reason="role not found",
        )
        return _role_error("RESOURCE_NOT_FOUND", "Role not found.")

    summary = _summary_from_record(record)
    await _audit_role_mutation(
        ctx,
        role_id=role_id,
        operation="get_admin_role",
        decision="allow",
        old_summary=_summary_for_audit(summary),
    )
    return Result(success=True, data=summary)


@router.put(
    "/admin/roles/{role_id}",
    response_model=Result[AdminRoleSummary],
    summary="Upsert Admin Role",
    dependencies=[
        Depends(_require_admin_roles),
        Depends(require_platform_active(operation="admin.roles.upsert", resource_type="role")),
    ],
)
async def upsert_admin_role(
    role_id: str,
    body: UpsertAdminRoleRequest,
    ctx: AdminRolesCtx,
) -> Result[AdminRoleSummary]:
    """Create or replace sanitized enterprise role metadata and permissions."""

    normalized_permissions = _normalized_permissions(body.permissions)
    invalid = _validate_role_id(role_id) or _validate_role_name(body.name) or _validate_permissions(body.permissions)
    if invalid is not None:
        await _audit_role_mutation(ctx, role_id=role_id, operation="upsert_admin_role", decision="deny", reason=invalid)
        return _role_error(_validation_error_code(invalid), invalid)
    not_grantable = _permissions_not_grantable(ctx, normalized_permissions)
    if not_grantable:
        await _audit_role_mutation(
            ctx,
            role_id=role_id,
            operation="upsert_admin_role",
            decision="deny",
            reason="permission grant exceeds actor permissions",
            metadata={"permissions": not_grantable},
        )
        return _role_error("ROLE_PERMISSION_FORBIDDEN", "Cannot grant permissions that the actor does not have.")

    store = deps.get_enterprise_extensions().role_store
    try:
        before = await store.get_role(role_id)
    except Exception:
        await _audit_role_mutation(
            ctx,
            role_id=role_id,
            operation="upsert_admin_role",
            decision="deny",
            reason="role read failed",
        )
        return _role_error("ROLE_READ_FAILED", "Role read failed.")

    try:
        record = await store.upsert_role(
            role_id=role_id,
            name=_required_str(body.name),
            description=_optional_str(body.description),
            permissions=normalized_permissions,
            built_in=bool((before or {}).get("built_in")),
        )
    except Exception:
        await _audit_role_mutation(
            ctx,
            role_id=role_id,
            operation="upsert_admin_role",
            decision="deny",
            reason="role upsert failed",
            old_summary=_summary_for_audit(_summary_from_record(before)) if before is not None else None,
        )
        return _role_error("ROLE_UPSERT_FAILED", "Role upsert failed.")

    summary = _summary_from_record(record)
    await _audit_role_mutation_best_effort(
        ctx,
        role_id=role_id,
        operation="upsert_admin_role",
        decision="allow",
        old_summary=_summary_for_audit(_summary_from_record(before)) if before is not None else None,
        new_summary=_summary_for_audit(summary),
    )
    return Result(success=True, data=summary)


@router.put(
    "/admin/roles/{role_id}/permissions",
    response_model=Result[AdminRoleSummary],
    summary="Set Admin Role Permissions",
    dependencies=[
        Depends(_require_admin_roles),
        Depends(require_platform_active(operation="admin.roles.permissions.update", resource_type="role")),
    ],
)
async def set_admin_role_permissions(
    role_id: str,
    body: SetRolePermissionsRequest,
    ctx: AdminRolesCtx,
) -> Result[AdminRoleSummary]:
    """Replace one enterprise role permission set."""

    normalized_permissions = _normalized_permissions(body.permissions)
    invalid = _validate_role_id(role_id) or _validate_permissions(body.permissions)
    if invalid is not None:
        await _audit_role_mutation(
            ctx,
            role_id=role_id,
            operation="set_admin_role_permissions",
            decision="deny",
            reason=invalid,
        )
        return _role_error(_validation_error_code(invalid), invalid)
    not_grantable = _permissions_not_grantable(ctx, normalized_permissions)
    if not_grantable:
        await _audit_role_mutation(
            ctx,
            role_id=role_id,
            operation="set_admin_role_permissions",
            decision="deny",
            reason="permission grant exceeds actor permissions",
            metadata={"permissions": not_grantable},
        )
        return _role_error("ROLE_PERMISSION_FORBIDDEN", "Cannot grant permissions that the actor does not have.")

    store = deps.get_enterprise_extensions().role_store
    try:
        before = await store.get_role(role_id)
    except Exception:
        await _audit_role_mutation(
            ctx,
            role_id=role_id,
            operation="set_admin_role_permissions",
            decision="deny",
            reason="role read failed",
        )
        return _role_error("ROLE_READ_FAILED", "Role read failed.")
    if before is None:
        await _audit_role_mutation(
            ctx,
            role_id=role_id,
            operation="set_admin_role_permissions",
            decision="deny",
            reason="role not found",
        )
        return _role_error("RESOURCE_NOT_FOUND", "Role not found.")

    try:
        record = await store.set_role_permissions(role_id, normalized_permissions)
    except Exception:
        await _audit_role_mutation(
            ctx,
            role_id=role_id,
            operation="set_admin_role_permissions",
            decision="deny",
            reason="role update failed",
            old_summary=_summary_for_audit(_summary_from_record(before)),
        )
        return _role_error("ROLE_UPDATE_FAILED", "Role update failed.")
    if record is None:
        await _audit_role_mutation(
            ctx,
            role_id=role_id,
            operation="set_admin_role_permissions",
            decision="deny",
            reason="role not found",
        )
        return _role_error("RESOURCE_NOT_FOUND", "Role not found.")

    summary = _summary_from_record(record)
    await _audit_role_mutation_best_effort(
        ctx,
        role_id=role_id,
        operation="set_admin_role_permissions",
        decision="allow",
        old_summary=_summary_for_audit(_summary_from_record(before)),
        new_summary=_summary_for_audit(summary),
    )
    return Result(success=True, data=summary)


@router.get(
    "/admin/users/{user_id}/roles",
    response_model=Result[AdminUserRolesSummary],
    summary="Get Admin User Roles",
)
async def get_admin_user_roles(user_id: str, ctx: AdminRolesCtx) -> Result[AdminUserRolesSummary]:
    """Return role ids assigned to one enterprise user."""

    invalid = _validate_user_id(user_id)
    if invalid is not None:
        await _audit_user_roles_mutation(
            ctx, user_id=user_id, operation="get_admin_user_roles", decision="deny", reason=invalid
        )
        return _role_error("USER_ID_INVALID", invalid)

    user = await _load_user_for_roles(ctx, user_id, operation="get_admin_user_roles")
    if isinstance(user, Result):
        return user

    try:
        role_ids = await deps.get_enterprise_extensions().role_store.list_user_roles(user_id)
    except Exception:
        await _audit_user_roles_mutation(
            ctx,
            user_id=user_id,
            operation="get_admin_user_roles",
            decision="deny",
            reason="user roles read failed",
        )
        return _role_error("USER_ROLES_READ_FAILED", "User roles read failed.")

    summary = AdminUserRolesSummary(user_id=user_id, role_ids=role_ids)
    await _audit_user_roles_mutation(
        ctx,
        user_id=user_id,
        operation="get_admin_user_roles",
        decision="allow",
        old_summary=_user_roles_summary_for_audit(summary),
    )
    return Result(success=True, data=summary)


@router.put(
    "/admin/users/{user_id}/roles",
    response_model=Result[AdminUserRolesSummary],
    summary="Set Admin User Roles",
    dependencies=[
        Depends(_require_admin_roles),
        Depends(require_platform_active(operation="admin.users.roles.update", resource_type="user")),
    ],
)
async def set_admin_user_roles(
    user_id: str,
    body: SetUserRolesRequest,
    ctx: AdminRolesCtx,
) -> Result[AdminUserRolesSummary]:
    """Replace role ids assigned to one enterprise user."""

    invalid = _validate_user_id(user_id) or _validate_role_ids(body.role_ids)
    if invalid is not None:
        await _audit_user_roles_mutation(
            ctx, user_id=user_id, operation="set_admin_user_roles", decision="deny", reason=invalid
        )
        return _role_error(_user_roles_validation_error_code(invalid), invalid)

    user = await _load_user_for_roles(ctx, user_id, operation="set_admin_user_roles")
    if isinstance(user, Result):
        return user

    store = deps.get_enterprise_extensions().role_store
    normalized_role_ids = _normalized_role_ids(body.role_ids)
    try:
        before = await store.list_user_roles(user_id)
    except Exception:
        await _audit_user_roles_mutation(
            ctx,
            user_id=user_id,
            operation="set_admin_user_roles",
            decision="deny",
            reason="user roles read failed",
        )
        return _role_error("USER_ROLES_READ_FAILED", "User roles read failed.")

    assigned_permissions: set[str] = set()
    for role_id in normalized_role_ids:
        try:
            role = await store.get_role(role_id)
        except Exception:
            await _audit_user_roles_mutation(
                ctx,
                user_id=user_id,
                operation="set_admin_user_roles",
                decision="deny",
                reason="role read failed",
                old_summary={"user_id": user_id, "role_ids": before},
                metadata={"role_id": role_id},
            )
            return _role_error("ROLE_READ_FAILED", "Role read failed.")
        if role is None:
            await _audit_user_roles_mutation(
                ctx,
                user_id=user_id,
                operation="set_admin_user_roles",
                decision="deny",
                reason="role not found",
                old_summary={"user_id": user_id, "role_ids": before},
                metadata={"role_id": role_id},
            )
            return _role_error("RESOURCE_NOT_FOUND", f"Role not found: {role_id}.")
        assigned_permissions.update(_normalized_permissions(role.get("permissions") or []))

    not_grantable = _permissions_not_grantable(ctx, sorted(assigned_permissions))
    if not_grantable:
        await _audit_user_roles_mutation(
            ctx,
            user_id=user_id,
            operation="set_admin_user_roles",
            decision="deny",
            reason="role assignment exceeds actor permissions",
            old_summary={"user_id": user_id, "role_ids": before},
            metadata={"permissions": not_grantable},
        )
        return _role_error("USER_ROLES_FORBIDDEN", "Cannot assign roles with permissions that the actor does not have.")

    try:
        role_ids = await store.set_user_roles(user_id, normalized_role_ids)
    except Exception as exc:
        if _is_role_not_found_error(exc):
            await _audit_user_roles_mutation(
                ctx,
                user_id=user_id,
                operation="set_admin_user_roles",
                decision="deny",
                reason="role not found",
                old_summary={"user_id": user_id, "role_ids": before},
            )
            return _role_error("RESOURCE_NOT_FOUND", "Role not found.")
        await _audit_user_roles_mutation(
            ctx,
            user_id=user_id,
            operation="set_admin_user_roles",
            decision="deny",
            reason="user roles update failed",
            old_summary={"user_id": user_id, "role_ids": before},
        )
        return _role_error("USER_ROLES_UPDATE_FAILED", "User roles update failed.")

    summary = AdminUserRolesSummary(user_id=user_id, role_ids=role_ids)
    await _audit_user_roles_mutation_best_effort(
        ctx,
        user_id=user_id,
        operation="set_admin_user_roles",
        decision="allow",
        old_summary={"user_id": user_id, "role_ids": before},
        new_summary=_user_roles_summary_for_audit(summary),
    )
    return Result(success=True, data=summary)


@router.delete(
    "/admin/roles/{role_id}",
    response_model=Result[dict],
    summary="Delete Admin Role",
    dependencies=[
        Depends(_require_admin_roles),
        Depends(require_platform_active(operation="admin.roles.delete", resource_type="role")),
    ],
)
async def delete_admin_role(role_id: str, ctx: AdminRolesCtx) -> Result[dict]:
    """Delete one enterprise role record and its permission set."""

    invalid = _validate_role_id(role_id)
    if invalid is not None:
        await _audit_role_mutation(ctx, role_id=role_id, operation="delete_admin_role", decision="deny", reason=invalid)
        return _role_error("ROLE_ID_INVALID", invalid)

    store = deps.get_enterprise_extensions().role_store
    try:
        before = await store.get_role(role_id)
    except Exception:
        await _audit_role_mutation(
            ctx,
            role_id=role_id,
            operation="delete_admin_role",
            decision="deny",
            reason="role read failed",
        )
        return _role_error("ROLE_READ_FAILED", "Role read failed.")
    if before is None:
        await _audit_role_mutation(
            ctx,
            role_id=role_id,
            operation="delete_admin_role",
            decision="deny",
            reason="role not found",
        )
        return _role_error("RESOURCE_NOT_FOUND", "Role not found.")
    if bool(before.get("built_in")):
        await _audit_role_mutation(
            ctx,
            role_id=role_id,
            operation="delete_admin_role",
            decision="deny",
            reason="built-in role cannot be deleted",
            old_summary=_summary_for_audit(_summary_from_record(before)),
        )
        return _role_error("ROLE_DELETE_FORBIDDEN", "Built-in role cannot be deleted.")

    try:
        assigned_users = await store.list_role_users(role_id)
    except Exception:
        await _audit_role_mutation(
            ctx,
            role_id=role_id,
            operation="delete_admin_role",
            decision="deny",
            reason="role bindings read failed",
            old_summary=_summary_for_audit(_summary_from_record(before)),
        )
        return _role_error("ROLE_BINDINGS_READ_FAILED", "Role bindings read failed.")
    if assigned_users:
        await _audit_role_mutation(
            ctx,
            role_id=role_id,
            operation="delete_admin_role",
            decision="deny",
            reason="role has assigned users",
            old_summary=_summary_for_audit(_summary_from_record(before)),
            metadata={"assigned_user_count": len(assigned_users), "assigned_user_ids": assigned_users[:10]},
        )
        return _role_error("ROLE_DELETE_FORBIDDEN", "Role has assigned users.")

    try:
        deleted = await store.delete_role(role_id)
    except Exception:
        await _audit_role_mutation(
            ctx,
            role_id=role_id,
            operation="delete_admin_role",
            decision="deny",
            reason="role delete failed",
            old_summary=_summary_for_audit(_summary_from_record(before)),
        )
        return _role_error("ROLE_DELETE_FAILED", "Role delete failed.")
    if not deleted:
        assigned_users = await _list_role_users_after_delete_false(ctx, store, role_id, before)
        if isinstance(assigned_users, Result):
            return assigned_users
        if assigned_users:
            await _audit_role_mutation(
                ctx,
                role_id=role_id,
                operation="delete_admin_role",
                decision="deny",
                reason="role has assigned users",
                old_summary=_summary_for_audit(_summary_from_record(before)),
                metadata={"assigned_user_count": len(assigned_users), "assigned_user_ids": assigned_users[:10]},
            )
            return _role_error("ROLE_DELETE_FORBIDDEN", "Role has assigned users.")
        await _audit_role_mutation(
            ctx,
            role_id=role_id,
            operation="delete_admin_role",
            decision="deny",
            reason="role not found",
        )
        return _role_error("RESOURCE_NOT_FOUND", "Role not found.")

    await _audit_role_mutation_best_effort(
        ctx,
        role_id=role_id,
        operation="delete_admin_role",
        decision="allow",
        old_summary=_summary_for_audit(_summary_from_record(before)),
        new_summary={"deleted": True},
    )
    return Result(success=True, data={"role_id": role_id, "deleted": True})
