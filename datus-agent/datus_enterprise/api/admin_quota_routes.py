"""Enterprise quota administration routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.constants import USER_ID_PATTERN
from datus.api.enterprise.deps import require_platform_active
from datus.api.models.base_models import Result
from datus.utils.loggings import get_logger
from datus_enterprise.api.admin_pagination import (
    ADMIN_LIST_DEFAULT_LIMIT,
    ADMIN_LIST_MAX_LIMIT,
    AdminListResult,
    paginate_admin_records,
)
from datus_enterprise.audit import AuditEvent, audit_decision
from datus_enterprise.authorization import require_module

router = APIRouter(prefix="/api/v1", tags=["enterprise-quotas"])
logger = get_logger(__name__)

_require_admin_quotas = require_module("module.admin.quotas")
AdminQuotasCtx = Annotated[AppContext, Depends(_require_admin_quotas)]

SUBJECT_TYPES = {"global", "role", "user"}
MAX_RESOURCE_LENGTH = 120
MAX_LIMIT = 10**12
MAX_WINDOW_SECONDS = 366 * 24 * 60 * 60


class UpsertQuotaRequest(BaseModel):
    """Enterprise quota metadata mutation."""

    subject_type: Any
    subject_id: Any = None
    resource: Any
    limit: Any
    window_seconds: Any = Field(default=86400)
    enabled: Any = True


class AdminQuotaSummary(BaseModel):
    """Sanitized enterprise quota metadata."""

    subject_type: str
    subject_id: str
    resource: str
    limit: int
    window_seconds: int
    enabled: bool
    created_at: str | None = None
    updated_at: str | None = None


class AdminUsageSummary(BaseModel):
    """Sanitized enterprise quota usage summary."""

    subject_type: str
    subject_id: str
    resource: str
    used: int = 0
    window_start: str | None = None
    window_seconds: int | None = None
    updated_at: str | None = None


@router.get("/admin/quotas", response_model=AdminListResult[AdminQuotaSummary], summary="List Admin Quotas")
async def list_admin_quotas(
    ctx: AdminQuotasCtx,
    subject_type: Annotated[str | None, Query(description="Filter by subject type: global, user, or role.")] = None,
    subject_id: Annotated[str | None, Query(description="Filter by subject id.")] = None,
    resource: Annotated[str | None, Query(description="Filter by quota resource key.")] = None,
    enabled: Annotated[bool | None, Query(description="Filter by enabled state.")] = None,
    search: Annotated[str | None, Query(max_length=200, description="Search quota fields.")] = None,
    limit: Annotated[int, Query(ge=1, le=ADMIN_LIST_MAX_LIMIT)] = ADMIN_LIST_DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdminListResult[AdminQuotaSummary] | Result[Any]:
    """Return configured enterprise quota metadata."""

    invalid = _validate_optional_filters(subject_type=subject_type, subject_id=subject_id, resource=resource)
    if invalid is not None:
        await _audit_quota(
            ctx,
            operation="list_admin_quotas",
            decision="deny",
            reason=invalid,
            metadata={"subject_type": subject_type, "subject_id": subject_id, "resource": resource},
        )
        return _quota_error("QUOTA_FILTER_INVALID", invalid)

    store = deps.get_enterprise_extensions().quota_store
    if store is None:
        await _audit_quota(ctx, operation="list_admin_quotas", decision="deny", reason="quota store unavailable")
        return _quota_error("QUOTA_STORE_UNAVAILABLE", "Quota store is not configured.")

    try:
        records = await store.list_quotas(subject_type=subject_type, subject_id=subject_id, resource=resource)
    except Exception:
        await _audit_quota(ctx, operation="list_admin_quotas", decision="deny", reason="quota list failed")
        return _quota_error("QUOTA_LIST_FAILED", "Quota list failed.")

    quotas = [
        _quota_summary_from_record(record)
        for record in records
        if (enabled is None or bool(record.get("enabled", True)) is enabled)
        and _quota_record_matches_search(record, search)
    ]
    page = paginate_admin_records(quotas, limit=limit, offset=offset)
    await _audit_quota(
        ctx,
        operation="list_admin_quotas",
        decision="allow",
        metadata={
            "count": len(page.data or []),
            "subject_type": subject_type,
            "subject_id": subject_id,
            "resource": resource,
            "enabled": enabled,
            "offset": offset,
            "has_more": page.pagination.has_more,
        },
    )
    return page


@router.put(
    "/admin/quotas",
    response_model=Result[AdminQuotaSummary],
    summary="Upsert Admin Quota",
    dependencies=[
        Depends(_require_admin_quotas),
        Depends(require_platform_active(operation="admin.quotas.upsert", resource_type="quota")),
    ],
)
async def upsert_admin_quota(body: UpsertQuotaRequest, ctx: AdminQuotasCtx) -> Result[AdminQuotaSummary]:
    """Create or replace one enterprise quota metadata record."""

    normalized = _normalize_quota_request(body)
    if isinstance(normalized, str):
        await _audit_quota(ctx, operation="upsert_admin_quota", decision="deny", reason=normalized)
        return _quota_error(_quota_validation_error_code(normalized), normalized)

    store = deps.get_enterprise_extensions().quota_store
    if store is None:
        await _audit_quota(ctx, operation="upsert_admin_quota", decision="deny", reason="quota store unavailable")
        return _quota_error("QUOTA_STORE_UNAVAILABLE", "Quota store is not configured.")

    old_summary = None
    try:
        old_records = await store.list_quotas(
            subject_type=normalized["subject_type"],
            subject_id=normalized["subject_id"],
            resource=normalized["resource"],
        )
        if old_records:
            old_summary = _quota_summary_for_audit(_quota_summary_from_record(old_records[0]))
        record = await store.put_quota(**normalized)
    except Exception:
        await _audit_quota(
            ctx,
            operation="upsert_admin_quota",
            decision="deny",
            reason="quota upsert failed",
            resource_id=_quota_resource_id(normalized),
        )
        return _quota_error("QUOTA_UPSERT_FAILED", "Quota upsert failed.")

    summary = _quota_summary_from_record(record)
    await _audit_quota_best_effort(
        ctx,
        operation="upsert_admin_quota",
        decision="allow",
        resource_id=_quota_resource_id(normalized),
        old_summary=old_summary,
        new_summary=_quota_summary_for_audit(summary),
    )
    return Result(success=True, data=summary)


@router.delete(
    "/admin/quotas/{subject_type}/{subject_id}/{resource}",
    response_model=Result[dict[str, bool]],
    summary="Delete Admin Quota",
    dependencies=[
        Depends(_require_admin_quotas),
        Depends(require_platform_active(operation="admin.quotas.delete", resource_type="quota")),
    ],
)
async def delete_admin_quota(
    subject_type: Annotated[str, Path(description="Quota subject type: global, user, or role.")],
    subject_id: Annotated[str, Path(description="Quota subject id, or * for global quotas.")],
    resource: Annotated[str, Path(description="Quota resource key.")],
    ctx: AdminQuotasCtx,
) -> Result[dict[str, bool]]:
    """Delete one enterprise quota metadata record and its current usage counters."""

    normalized = _normalize_quota_identity(subject_type=subject_type, subject_id=subject_id, resource=resource)
    if isinstance(normalized, str):
        await _audit_quota(ctx, operation="delete_admin_quota", decision="deny", reason=normalized)
        return _quota_error(_quota_validation_error_code(normalized), normalized)

    store = deps.get_enterprise_extensions().quota_store
    if store is None:
        await _audit_quota(ctx, operation="delete_admin_quota", decision="deny", reason="quota store unavailable")
        return _quota_error("QUOTA_STORE_UNAVAILABLE", "Quota store is not configured.")

    old_summary = None
    try:
        old_records = await store.list_quotas(
            subject_type=normalized["subject_type"],
            subject_id=normalized["subject_id"],
            resource=normalized["resource"],
        )
        if old_records:
            old_summary = _quota_summary_for_audit(_quota_summary_from_record(old_records[0]))
        deleted = await store.delete_quota(**normalized)
    except Exception:
        await _audit_quota(
            ctx,
            operation="delete_admin_quota",
            decision="deny",
            reason="quota delete failed",
            resource_id=_quota_resource_id(normalized),
        )
        return _quota_error("QUOTA_DELETE_FAILED", "Quota delete failed.")

    if not deleted:
        await _audit_quota(
            ctx,
            operation="delete_admin_quota",
            decision="deny",
            reason="quota not found",
            resource_id=_quota_resource_id(normalized),
        )
        return _quota_error("QUOTA_NOT_FOUND", "Quota not found.")

    await _audit_quota_best_effort(
        ctx,
        operation="delete_admin_quota",
        decision="allow",
        resource_id=_quota_resource_id(normalized),
        old_summary=old_summary,
        metadata={"deleted": True},
    )
    return Result(success=True, data={"deleted": True})


@router.get("/admin/usage", response_model=AdminListResult[AdminUsageSummary], summary="List Admin Usage")
async def list_admin_usage(
    ctx: AdminQuotasCtx,
    subject_type: Annotated[str | None, Query(description="Filter by subject type: global, user, or role.")] = None,
    subject_id: Annotated[str | None, Query(description="Filter by subject id.")] = None,
    resource: Annotated[str | None, Query(description="Filter by quota resource key.")] = None,
    search: Annotated[str | None, Query(max_length=200, description="Search usage fields.")] = None,
    limit: Annotated[int, Query(ge=1, le=ADMIN_LIST_MAX_LIMIT)] = ADMIN_LIST_DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdminListResult[AdminUsageSummary] | Result[Any]:
    """Return enterprise usage summaries for quota administration."""

    invalid = _validate_optional_filters(subject_type=subject_type, subject_id=subject_id, resource=resource)
    if invalid is not None:
        await _audit_quota(
            ctx,
            operation="list_admin_usage",
            decision="deny",
            reason=invalid,
            metadata={"subject_type": subject_type, "subject_id": subject_id, "resource": resource},
        )
        return _quota_error("QUOTA_FILTER_INVALID", invalid)

    store = deps.get_enterprise_extensions().quota_store
    if store is None:
        await _audit_quota(ctx, operation="list_admin_usage", decision="deny", reason="quota store unavailable")
        return _quota_error("QUOTA_STORE_UNAVAILABLE", "Quota store is not configured.")

    try:
        records = await store.list_usage(subject_type=subject_type, subject_id=subject_id, resource=resource)
    except Exception:
        await _audit_quota(ctx, operation="list_admin_usage", decision="deny", reason="usage list failed")
        return _quota_error("USAGE_LIST_FAILED", "Usage list failed.")

    usage = [_usage_summary_from_record(record) for record in records if _quota_record_matches_search(record, search)]
    page = paginate_admin_records(usage, limit=limit, offset=offset)
    await _audit_quota(
        ctx,
        operation="list_admin_usage",
        decision="allow",
        metadata={
            "count": len(page.data or []),
            "subject_type": subject_type,
            "subject_id": subject_id,
            "resource": resource,
            "offset": offset,
            "has_more": page.pagination.has_more,
        },
    )
    return page


def _quota_record_matches_search(record: dict[str, Any], search: str | None) -> bool:
    query = (search or "").strip().casefold()
    if not query:
        return True
    return any(
        query in str(record.get(field) or "").casefold()
        for field in ("subject_type", "subject_id", "resource", "limit", "limit_value", "window_seconds", "used")
    )


def _normalize_quota_request(body: UpsertQuotaRequest) -> dict[str, Any] | str:
    subject_type = str(body.subject_type or "").strip()
    if subject_type not in SUBJECT_TYPES:
        return "Quota subject_type must be global, user, or role."
    subject_id = _normalize_subject_id(subject_type, body.subject_id)
    if subject_id is None:
        return "Quota subject_id is invalid."
    resource = _normalize_resource(body.resource)
    if resource is None:
        return "Quota resource is invalid."
    limit = _normalize_positive_int(body.limit, max_value=MAX_LIMIT)
    if limit is None:
        return "Quota limit must be a positive integer."
    window_seconds = _normalize_positive_int(body.window_seconds, max_value=MAX_WINDOW_SECONDS)
    if window_seconds is None:
        return "Quota window_seconds must be a positive integer."
    if not isinstance(body.enabled, bool):
        return "Quota enabled must be a boolean."
    return {
        "subject_type": subject_type,
        "subject_id": subject_id,
        "resource": resource,
        "limit": limit,
        "window_seconds": window_seconds,
        "enabled": body.enabled,
    }


def _validate_optional_filters(
    *,
    subject_type: str | None = None,
    subject_id: str | None = None,
    resource: str | None = None,
) -> str | None:
    normalized_subject_type = None
    if subject_type is not None:
        normalized_subject_type = subject_type.strip()
        if normalized_subject_type not in SUBJECT_TYPES:
            return "Quota subject_type must be global, user, or role."
    if subject_id is not None:
        if normalized_subject_type is None:
            return "Quota subject_type is required when subject_id is provided."
        if _normalize_subject_id(normalized_subject_type, subject_id) is None:
            return "Quota subject_id is invalid."
    if resource is not None and _normalize_resource(resource) is None:
        return "Quota resource is invalid."
    return None


def _normalize_quota_identity(*, subject_type: Any, subject_id: Any, resource: Any) -> dict[str, str] | str:
    normalized_subject_type = str(subject_type or "").strip()
    if normalized_subject_type not in SUBJECT_TYPES:
        return "Quota subject_type must be global, user, or role."
    if normalized_subject_type == "global" and str(subject_id or "").strip() != "*":
        return "Quota subject_id is invalid."
    normalized_subject_id = _normalize_subject_id(normalized_subject_type, subject_id)
    if normalized_subject_id is None:
        return "Quota subject_id is invalid."
    normalized_resource = _normalize_resource(resource)
    if normalized_resource is None:
        return "Quota resource is invalid."
    return {
        "subject_type": normalized_subject_type,
        "subject_id": normalized_subject_id,
        "resource": normalized_resource,
    }


def _normalize_subject_id(subject_type: str, raw_subject_id: Any) -> str | None:
    if subject_type == "global":
        return "*"
    if not isinstance(raw_subject_id, str):
        return None
    candidate = raw_subject_id.strip()
    if candidate != raw_subject_id or not candidate or not USER_ID_PATTERN.fullmatch(candidate):
        return None
    return candidate


def _normalize_resource(raw_resource: Any) -> str | None:
    if not isinstance(raw_resource, str):
        return None
    resource = raw_resource.strip()
    if resource != raw_resource or not resource or len(resource) > MAX_RESOURCE_LENGTH:
        return None
    if not USER_ID_PATTERN.fullmatch(resource.replace(".", "_").replace(":", "_")):
        return None
    return resource


def _normalize_positive_int(value: Any, *, max_value: int) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        candidate = value
    elif isinstance(value, str) and value.isdecimal():
        candidate = int(value)
    else:
        return None
    if candidate <= 0 or candidate > max_value:
        return None
    return candidate


def _quota_summary_from_record(record: dict[str, Any]) -> AdminQuotaSummary:
    return AdminQuotaSummary(
        subject_type=str(record.get("subject_type") or ""),
        subject_id=str(record.get("subject_id") or ""),
        resource=str(record.get("resource") or ""),
        limit=int(record.get("limit") or 0),
        window_seconds=int(record.get("window_seconds") or 0),
        enabled=bool(record.get("enabled")),
        created_at=_optional_str(record.get("created_at")),
        updated_at=_optional_str(record.get("updated_at")),
    )


def _usage_summary_from_record(record: dict[str, Any]) -> AdminUsageSummary:
    return AdminUsageSummary(
        subject_type=str(record.get("subject_type") or ""),
        subject_id=str(record.get("subject_id") or ""),
        resource=str(record.get("resource") or ""),
        used=int(record.get("used") or 0),
        window_start=_optional_str(record.get("window_start")),
        window_seconds=_optional_int(record.get("window_seconds")),
        updated_at=_optional_str(record.get("updated_at")),
    )


def _quota_summary_for_audit(summary: AdminQuotaSummary) -> dict[str, Any]:
    return {
        "subject_type": summary.subject_type,
        "subject_id": summary.subject_id,
        "resource": summary.resource,
        "limit": summary.limit,
        "window_seconds": summary.window_seconds,
        "enabled": summary.enabled,
    }


def _quota_resource_id(record: dict[str, Any]) -> str:
    return f"{record['subject_type']}:{record['subject_id']}:{record['resource']}"


async def _audit_quota(
    ctx: AppContext,
    *,
    operation: str,
    decision: str,
    reason: str | None = None,
    resource_id: str | None = None,
    old_summary: dict[str, Any] | None = None,
    new_summary: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    event_metadata = {"operation": operation}
    if metadata:
        event_metadata.update(metadata)
    if old_summary is not None:
        event_metadata["old_summary"] = old_summary
    if new_summary is not None:
        event_metadata["new_summary"] = new_summary
    await audit_decision(
        ctx,
        AuditEvent(
            action="module.admin.quotas",
            resource_type="quota",
            resource_id=resource_id,
            decision=decision,
            reason=reason,
            metadata=event_metadata,
        ),
    )


async def _audit_quota_best_effort(
    ctx: AppContext,
    *,
    operation: str,
    decision: str,
    reason: str | None = None,
    resource_id: str | None = None,
    old_summary: dict[str, Any] | None = None,
    new_summary: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    try:
        await _audit_quota(
            ctx,
            operation=operation,
            decision=decision,
            reason=reason,
            resource_id=resource_id,
            old_summary=old_summary,
            new_summary=new_summary,
            metadata=metadata,
        )
    except Exception as exc:
        logger.warning(
            "Admin quota audit write failed for operation '%s' decision '%s': %s",
            operation,
            decision,
            exc,
        )


def _quota_error(code: str, message: str) -> Result:
    return Result(success=False, errorCode=code, errorMessage=message)


def _quota_validation_error_code(message: str) -> str:
    if "subject_type" in message or "subject_id" in message:
        return "QUOTA_SUBJECT_INVALID"
    if "resource" in message:
        return "QUOTA_RESOURCE_INVALID"
    if "limit" in message:
        return "QUOTA_LIMIT_INVALID"
    if "window_seconds" in message:
        return "QUOTA_WINDOW_INVALID"
    if "enabled" in message:
        return "QUOTA_ENABLED_INVALID"
    return "QUOTA_INVALID"


def _optional_str(value: Any) -> str | None:
    return str(value) if value is not None else None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)
