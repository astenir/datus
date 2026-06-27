"""Enterprise role administration routes."""

from __future__ import annotations

import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.constants import USER_ID_PATTERN
from datus.api.models.base_models import Result
from datus_enterprise.audit import AuditEvent, audit_decision
from datus_enterprise.authorization import require_module

router = APIRouter(prefix="/api/v1", tags=["enterprise-roles"])

AdminRolesCtx = Annotated[AppContext, Depends(require_module("module.admin.roles"))]

PERMISSION_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_*.-]+$")
MAX_PERMISSION_KEYS = 200


class UpsertAdminRoleRequest(BaseModel):
    """Enterprise role metadata and permission mutation."""

    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    permissions: list[str] = Field(default_factory=list, max_length=MAX_PERMISSION_KEYS)


class SetRolePermissionsRequest(BaseModel):
    """Enterprise role permission-set mutation."""

    permissions: list[str] = Field(default_factory=list, max_length=MAX_PERMISSION_KEYS)


class AdminRoleSummary(BaseModel):
    """Sanitized enterprise role metadata."""

    role_id: str
    name: str
    description: str | None = None
    permissions: list[str] = Field(default_factory=list)
    built_in: bool = False
    created_at: str | None = None
    updated_at: str | None = None


@router.get("/admin/roles", response_model=Result[list[AdminRoleSummary]], summary="List Admin Roles")
async def list_admin_roles(ctx: AdminRolesCtx) -> Result[list[AdminRoleSummary]]:
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

    roles = [_summary_from_record(record) for record in records]
    await _audit_role_mutation(
        ctx,
        role_id=None,
        operation="list_admin_roles",
        decision="allow",
        metadata={"count": len(roles)},
    )
    return Result(success=True, data=roles)


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


@router.put("/admin/roles/{role_id}", response_model=Result[AdminRoleSummary], summary="Upsert Admin Role")
async def upsert_admin_role(
    role_id: str,
    body: UpsertAdminRoleRequest,
    ctx: AdminRolesCtx,
) -> Result[AdminRoleSummary]:
    """Create or replace sanitized enterprise role metadata and permissions."""

    invalid = _validate_role_id(role_id) or _validate_role_name(body.name) or _validate_permissions(body.permissions)
    if invalid is not None:
        await _audit_role_mutation(ctx, role_id=role_id, operation="upsert_admin_role", decision="deny", reason=invalid)
        return _role_error(_validation_error_code(invalid), invalid)

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
            permissions=_normalized_permissions(body.permissions),
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
    await _audit_role_mutation(
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
)
async def set_admin_role_permissions(
    role_id: str,
    body: SetRolePermissionsRequest,
    ctx: AdminRolesCtx,
) -> Result[AdminRoleSummary]:
    """Replace one enterprise role permission set."""

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
        record = await store.set_role_permissions(role_id, _normalized_permissions(body.permissions))
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
    await _audit_role_mutation(
        ctx,
        role_id=role_id,
        operation="set_admin_role_permissions",
        decision="allow",
        old_summary=_summary_for_audit(_summary_from_record(before)),
        new_summary=_summary_for_audit(summary),
    )
    return Result(success=True, data=summary)


@router.delete("/admin/roles/{role_id}", response_model=Result[dict], summary="Delete Admin Role")
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
        await _audit_role_mutation(
            ctx,
            role_id=role_id,
            operation="delete_admin_role",
            decision="deny",
            reason="role not found",
        )
        return _role_error("RESOURCE_NOT_FOUND", "Role not found.")

    await _audit_role_mutation(
        ctx,
        role_id=role_id,
        operation="delete_admin_role",
        decision="allow",
        old_summary=_summary_for_audit(_summary_from_record(before)),
        new_summary={"deleted": True},
    )
    return Result(success=True, data={"role_id": role_id, "deleted": True})


async def _audit_role_mutation(
    ctx: AppContext,
    *,
    role_id: str | None,
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
            action="module.admin.roles",
            resource_type="role",
            resource_id=role_id,
            decision=decision,
            reason=reason,
            metadata=audit_metadata,
        ),
    )


def _summary_from_record(record: dict[str, Any]) -> AdminRoleSummary:
    return AdminRoleSummary(
        role_id=str(record["role_id"]),
        name=str(record["name"]),
        description=_optional_str(record.get("description")),
        permissions=_normalized_permissions(record.get("permissions") or []),
        built_in=bool(record.get("built_in")),
        created_at=_optional_str(record.get("created_at")),
        updated_at=_optional_str(record.get("updated_at")),
    )


def _summary_for_audit(summary: AdminRoleSummary) -> dict[str, Any]:
    return {
        "role_id": summary.role_id,
        "name": summary.name,
        "description": summary.description,
        "permissions": list(summary.permissions),
        "built_in": summary.built_in,
    }


def _validate_role_id(role_id: str) -> str | None:
    candidate = role_id.strip()
    if candidate != role_id or not candidate or not USER_ID_PATTERN.fullmatch(role_id):
        return "Invalid role_id. Only letters, digits, underscore and hyphen are allowed."
    return None


def _validate_role_name(name: str) -> str | None:
    if not name.strip():
        return "Invalid role name. Role name cannot be empty."
    return None


def _validate_permissions(permissions: list[str]) -> str | None:
    if len(permissions) > MAX_PERMISSION_KEYS:
        return f"Role permission set cannot contain more than {MAX_PERMISSION_KEYS} keys."
    for permission in permissions:
        if not isinstance(permission, str):
            return "Permission keys must be strings."
        candidate = permission.strip()
        if (
            candidate != permission
            or not candidate
            or len(candidate) > 128
            or not PERMISSION_KEY_PATTERN.fullmatch(candidate)
        ):
            return "Invalid permission key. Only letters, digits, underscore, hyphen, dot and wildcard are allowed."
    return None


def _validation_error_code(message: str) -> str:
    if "role_id" in message:
        return "ROLE_ID_INVALID"
    if "role name" in message:
        return "ROLE_NAME_INVALID"
    return "ROLE_PERMISSION_INVALID"


def _normalized_permissions(permissions: list[str]) -> list[str]:
    return sorted({permission.strip() for permission in permissions if permission.strip()})


def _required_str(value: str) -> str:
    return value.strip()


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _role_error(error_code: str, message: str) -> Result[Any]:
    return Result(success=False, errorCode=error_code, errorMessage=message)
