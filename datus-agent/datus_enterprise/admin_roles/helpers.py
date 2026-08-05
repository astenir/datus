"""Shared non-route helpers for enterprise role administration."""

from __future__ import annotations

import re
from fnmatch import fnmatchcase
from typing import Any

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.constants import USER_ID_PATTERN
from datus.api.models.base_models import Result
from datus.utils.exceptions import DatusException, ErrorCode
from datus.utils.loggings import get_logger
from datus_enterprise.admin_roles.models import (
    MAX_PERMISSION_KEYS,
    AdminRoleSummary,
    AdminUserRolesSummary,
)
from datus_enterprise.audit import AuditEvent, audit_decision

logger = get_logger(__name__)
PERMISSION_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_*.-]+$")


def _role_matches_search(record: dict[str, Any], search: str | None) -> bool:
    query = (search or "").strip().casefold()
    if not query:
        return True
    values = [record.get("role_id"), record.get("name"), record.get("description"), *(record.get("permissions") or [])]
    return any(query in str(value or "").casefold() for value in values)


async def _list_role_users_after_delete_false(
    ctx: AppContext,
    store: Any,
    role_id: str,
    before: dict[str, Any],
) -> list[str] | Result[Any]:
    try:
        return await store.list_role_users(role_id)
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


async def _load_user_for_roles(ctx: AppContext, user_id: str, *, operation: str) -> dict[str, Any] | Result[Any]:
    try:
        user = await deps.get_enterprise_extensions().user_store.get_user(user_id)
    except Exception:
        await _audit_user_roles_mutation(
            ctx,
            user_id=user_id,
            operation=operation,
            decision="deny",
            reason="user read failed",
        )
        return _role_error("USER_READ_FAILED", "User read failed.")
    if user is None:
        await _audit_user_roles_mutation(
            ctx,
            user_id=user_id,
            operation=operation,
            decision="deny",
            reason="user not found",
        )
        return _role_error("RESOURCE_NOT_FOUND", "User not found.")
    return user


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


async def _audit_role_mutation_best_effort(
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
    try:
        await _audit_role_mutation(
            ctx,
            role_id=role_id,
            operation=operation,
            decision=decision,
            reason=reason,
            old_summary=old_summary,
            new_summary=new_summary,
            metadata=metadata,
        )
    except Exception as exc:
        logger.warning(
            "Admin role audit write failed for operation '%s' decision '%s': %s",
            operation,
            decision,
            exc,
        )


async def _audit_user_roles_mutation(
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
            action="module.admin.roles",
            resource_type="user_roles",
            resource_id=user_id,
            decision=decision,
            reason=reason,
            metadata=audit_metadata,
        ),
    )


async def _audit_user_roles_mutation_best_effort(
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
        await _audit_user_roles_mutation(
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
            "Admin user roles audit write failed for operation '%s' decision '%s': %s",
            operation,
            decision,
            exc,
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


def _user_roles_summary_for_audit(summary: AdminUserRolesSummary) -> dict[str, Any]:
    return {"user_id": summary.user_id, "role_ids": list(summary.role_ids)}


def _validate_user_id(user_id: str) -> str | None:
    candidate = user_id.strip()
    if candidate != user_id or not candidate or not USER_ID_PATTERN.fullmatch(user_id):
        return "Invalid user_id. Only letters, digits, underscore and hyphen are allowed."
    return None


def _validate_role_id(role_id: str) -> str | None:
    candidate = role_id.strip()
    if candidate != role_id or not candidate or not USER_ID_PATTERN.fullmatch(role_id):
        return "Invalid role_id. Only letters, digits, underscore and hyphen are allowed."
    return None


def _validate_role_ids(role_ids: list[str]) -> str | None:
    if len(role_ids) > MAX_PERMISSION_KEYS:
        return f"User role set cannot contain more than {MAX_PERMISSION_KEYS} role ids."
    for role_id in role_ids:
        if not isinstance(role_id, str):
            return "Role ids must be strings."
        invalid = _validate_role_id(role_id)
        if invalid is not None:
            return invalid
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


def _user_roles_validation_error_code(message: str) -> str:
    if "user_id" in message:
        return "USER_ID_INVALID"
    return "ROLE_ID_INVALID"


def _is_role_not_found_error(exc: Exception) -> bool:
    return (
        isinstance(exc, DatusException)
        and exc.code == ErrorCode.COMMON_FIELD_INVALID
        and "Role not found:" in exc.message
    )


def _normalized_permissions(permissions: list[str]) -> list[str]:
    return sorted({permission.strip() for permission in permissions if permission.strip()})


def _normalized_role_ids(role_ids: list[str]) -> list[str]:
    return sorted({role_id.strip() for role_id in role_ids if role_id.strip()})


def _actor_permissions(ctx: AppContext) -> list[str] | None:
    if ctx.is_admin:
        return None
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


def _permissions_not_grantable(ctx: AppContext, permissions: list[str]) -> list[str]:
    actor_permissions = _actor_permissions(ctx)
    if actor_permissions is None:
        return []
    return [
        permission
        for permission in permissions
        if not any(_permission_covers(permission, granted) for granted in actor_permissions)
    ]


def _permission_covers(requested: str, granted: str) -> bool:
    return granted == "*" or fnmatchcase(requested, granted)


def _required_str(value: str) -> str:
    return value.strip()


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _role_error(error_code: str, message: str) -> Result[Any]:
    return Result(success=False, errorCode=error_code, errorMessage=message)
