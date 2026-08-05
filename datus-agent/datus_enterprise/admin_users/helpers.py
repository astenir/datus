"""Shared non-route helpers for enterprise user administration."""

from __future__ import annotations

import asyncio
from typing import Any

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.constants import USER_ID_PATTERN
from datus.api.models.base_models import Result
from datus.utils.loggings import get_logger
from datus_enterprise.admin_users.models import (
    AdminUserDatasourceGrantSummary,
    AdminUserDetail,
    AdminUserRoleSummary,
    AdminUserSummary,
)
from datus_enterprise.audit import AuditEvent, audit_decision

logger = get_logger(__name__)


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

    if not enabled:
        blocked = await _deny_user_disable_if_protected(ctx, user_id=user_id, operation=operation, before=before)
        if blocked is not None:
            return blocked

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


async def _deny_user_disable_if_protected(
    ctx: AppContext,
    *,
    user_id: str,
    operation: str,
    before: dict[str, Any],
) -> Result[AdminUserSummary] | None:
    before_summary = _summary_from_record(before)
    if ctx.user_id == user_id:
        await _audit_user_mutation(
            ctx,
            user_id=user_id,
            operation=operation,
            decision="deny",
            reason="cannot disable current user",
            old_summary=_summary_for_audit(before_summary),
        )
        return _user_error("USER_DISABLE_SELF_FORBIDDEN", "Cannot disable the current user.")

    try:
        detail = await _detail_from_record(before)
    except Exception:
        await _audit_user_mutation(
            ctx,
            user_id=user_id,
            operation=operation,
            decision="deny",
            reason="user admin permissions read failed",
            old_summary=_summary_for_audit(before_summary),
        )
        return _user_error("USER_READ_FAILED", "User read failed.")
    if _has_enterprise_admin_access(detail):
        await _audit_user_mutation(
            ctx,
            user_id=user_id,
            operation=operation,
            decision="deny",
            reason="cannot disable enterprise administrator",
            old_summary=_summary_for_audit(before_summary),
        )
        return _user_error("USER_DISABLE_ADMIN_FORBIDDEN", "Cannot disable an enterprise administrator.")
    return None


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
    if not summaries:
        return []

    extensions = deps.get_enterprise_extensions()
    user_ids = [summary.user_id for summary in summaries]
    count_grants = getattr(extensions.datasource_grant_store, "count_grants_by_subjects", None)
    if callable(count_grants):
        direct_grant_counts = await count_grants(subject_type="user", subject_ids=user_ids)
    else:
        grant_groups = await asyncio.gather(
            *(
                extensions.datasource_grant_store.list_grants(subject_type="user", subject_id=user_id)
                for user_id in user_ids
            )
        )
        direct_grant_counts = {user_id: len(grants) for user_id, grants in zip(user_ids, grant_groups, strict=True)}

    role_id_groups = await asyncio.gather(
        *(extensions.role_store.list_user_roles(summary.user_id) for summary in summaries)
    )
    for summary, role_ids_for_user in zip(summaries, role_id_groups, strict=True):
        role_ids = sorted(role_ids_for_user)
        summary.role_ids = role_ids
        summary.role_count = len(role_ids)
        summary.direct_datasource_grant_count = direct_grant_counts.get(summary.user_id, 0)
    return summaries


def _user_matches_search(record: dict[str, Any], search: str | None) -> bool:
    query = (search or "").strip().casefold()
    if not query:
        return True
    return any(
        query in str(record.get(field) or "").casefold()
        for field in ("user_id", "display_name", "email", "external_user_id", "department", "title")
    )


def _has_enterprise_admin_access(detail: AdminUserDetail) -> bool:
    if "enterprise_admin" in detail.role_ids or "local_admin" in detail.role_ids:
        return True
    return any(_is_enterprise_admin_permission(permission) for permission in detail.effective_permissions)


def _is_enterprise_admin_permission(permission: str) -> bool:
    normalized = permission.strip()
    return (
        normalized == "*"
        or normalized == "module.*"
        or normalized == "module.admin"
        or normalized == "module.admin.*"
        or normalized.startswith("module.admin.")
    )


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
