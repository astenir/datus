"""Enterprise audit administration routes."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from io import StringIO
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from datus.api.auth.context import AppContext
from datus.api.enterprise.deps import get_audit_sink
from datus.api.enterprise.models import AuditEvent as CoreAuditEvent
from datus.api.models.base_models import Result
from datus.utils.csv_utils import sanitize_csv_field
from datus.utils.loggings import get_logger
from datus_enterprise.audit import AuditEvent, audit_decision
from datus_enterprise.authorization import require_module
from datus_enterprise.quota import consume_enterprise_quota

router = APIRouter(prefix="/api/v1", tags=["enterprise-audit"])
logger = get_logger(__name__)

AdminAuditCtx = Annotated[AppContext, Depends(require_module("module.admin.audit"))]
AdminAuditExportCtx = Annotated[AppContext, Depends(require_module("module.admin.audit.export"))]


class AuditLogEntry(BaseModel):
    """Sanitized audit log entry returned to admin callers."""

    id: int | None = None
    created_at: str | None = None
    user_id: str | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    decision: str
    reason: str | None = None
    request_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditLogPage(BaseModel):
    """Cursor-paginated audit log page."""

    entries: list[AuditLogEntry]
    limit: int
    before_id: int | None = None
    next_before_id: int | None = None
    has_more: bool


@router.get("/admin/audit-logs", response_model=Result[AuditLogPage], summary="List Audit Logs")
async def list_audit_logs(
    ctx: AdminAuditCtx,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    before_id: Annotated[int | None, Query(ge=1)] = None,
    user_id: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    decision: str | None = None,
    request_id: str | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
) -> Result[AuditLogPage]:
    """Query audit logs when the configured audit sink exposes a reader interface."""

    events, has_more, error = await _query_audit_events(
        ctx,
        operation="list_audit_logs",
        limit=limit,
        before_id=before_id,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        decision=decision,
        request_id=request_id,
        created_after=_datetime_param(created_after),
        created_before=_datetime_param(created_before),
    )
    if error is not None:
        return error

    entries = [_entry_from_event(event) for event in events]
    page = AuditLogPage(
        entries=entries,
        limit=limit,
        before_id=before_id,
        next_before_id=_next_before_id(entries, has_more),
        has_more=has_more,
    )
    await _audit_query(
        ctx,
        operation="list_audit_logs",
        decision="allow",
        reason=None,
        count=len(entries),
        metadata={
            "before_id": before_id,
            "next_before_id": page.next_before_id,
            "has_more": has_more,
            "request_id": request_id,
            "created_after": _datetime_param(created_after),
            "created_before": _datetime_param(created_before),
        },
    )
    return Result(success=True, data=page)


@router.get("/admin/audit-logs/export", response_model=None, summary="Export Audit Logs")
async def export_audit_logs(
    ctx: AdminAuditExportCtx,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    before_id: Annotated[int | None, Query(ge=1)] = None,
    user_id: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    decision: str | None = None,
    request_id: str | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
) -> Response | Result[dict]:
    """Export matching audit logs as a CSV file when the audit sink supports queries."""

    query_events, error = await _audit_query_reader(
        ctx,
        operation="export_audit_logs",
        audit_action="module.admin.audit.export",
    )
    if error is not None:
        return error

    quota_error = await consume_enterprise_quota(
        ctx,
        resource="admin.audit.export",
        amount=1,
        resource_type="audit_log",
        resource_id=None,
        metadata={
            "operation": "export_audit_logs",
            "limit": limit,
            "before_id": before_id,
            "user_id": user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "decision": decision,
            "request_id": request_id,
            "created_after": _datetime_param(created_after),
            "created_before": _datetime_param(created_before),
        },
    )
    if quota_error is not None:
        return quota_error

    events, _, error = await _query_audit_events(
        ctx,
        operation="export_audit_logs",
        audit_action="module.admin.audit.export",
        query_events=query_events,
        limit=limit,
        before_id=before_id,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        decision=decision,
        request_id=request_id,
        created_after=_datetime_param(created_after),
        created_before=_datetime_param(created_before),
    )
    if error is not None:
        return error

    await _audit_query(
        ctx,
        operation="export_audit_logs",
        action="module.admin.audit.export",
        decision="allow",
        reason=None,
        count=len(events),
        metadata={
            "before_id": before_id,
            "request_id": request_id,
            "created_after": _datetime_param(created_after),
            "created_before": _datetime_param(created_before),
        },
    )
    return Response(
        content=_events_to_csv(events),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="audit-logs.csv"'},
    )


async def _audit_query_reader(
    ctx: AppContext,
    *,
    operation: str,
    audit_action: str,
) -> tuple[Any, Result[Any] | None]:
    sink = get_audit_sink()
    query_events = getattr(sink, "query_events", None)
    if callable(query_events):
        return query_events, None

    await _audit_query(
        ctx,
        operation=operation,
        action=audit_action,
        decision="deny",
        reason="audit query unavailable",
        count=None,
    )
    return None, Result(
        success=False,
        errorCode="AUDIT_QUERY_UNAVAILABLE",
        errorMessage="The configured audit sink does not support audit log queries.",
    )


async def _query_audit_events(
    ctx: AppContext,
    *,
    operation: str,
    audit_action: str = "module.admin.audit",
    query_events: Any | None = None,
    limit: int,
    before_id: int | None,
    user_id: str | None,
    action: str | None,
    resource_type: str | None,
    resource_id: str | None,
    decision: str | None,
    request_id: str | None,
    created_after: str | None,
    created_before: str | None,
) -> tuple[list[CoreAuditEvent], bool, Result[Any] | None]:
    if query_events is None:
        query_events, error = await _audit_query_reader(
            ctx,
            operation=operation,
            audit_action=audit_action,
        )
        if error is not None:
            return [], False, error

    try:
        events = await query_events(
            limit=limit + 1,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            decision=decision,
            request_id=request_id,
            before_id=before_id,
            created_after=created_after,
            created_before=created_before,
        )
    except Exception:
        await _audit_query(
            ctx,
            operation=operation,
            action=audit_action,
            decision="deny",
            reason="audit query failed",
            count=None,
        )
        return (
            [],
            False,
            Result(
                success=False,
                errorCode="AUDIT_QUERY_FAILED",
                errorMessage="Audit log query failed.",
            ),
        )

    return events[:limit], len(events) > limit, None


async def _audit_query(
    ctx: AppContext,
    *,
    operation: str,
    action: str = "module.admin.audit",
    decision: str,
    reason: str | None,
    count: int | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    audit_metadata = {"operation": operation}
    if count is not None:
        audit_metadata["count"] = count
    if metadata:
        audit_metadata.update({key: value for key, value in metadata.items() if value is not None})
    try:
        await audit_decision(
            ctx,
            AuditEvent(
                action=action,
                resource_type="audit_log",
                resource_id=None,
                decision=decision,
                reason=reason,
                metadata=audit_metadata,
            ),
        )
    except Exception:
        logger.warning("Admin audit query audit write failed for operation=%s", operation, exc_info=True)


def _entry_from_event(event: CoreAuditEvent) -> AuditLogEntry:
    return AuditLogEntry(
        id=event.id,
        created_at=event.created_at,
        user_id=event.user_id,
        action=event.action,
        resource_type=event.resource_type,
        resource_id=event.resource_id,
        decision=event.decision,
        reason=event.reason,
        request_id=event.request_id,
        metadata=dict(event.metadata),
    )


def _next_before_id(entries: list[AuditLogEntry], has_more: bool) -> int | None:
    if not has_more or not entries:
        return None
    return entries[-1].id


def _datetime_param(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _events_to_csv(events: list[CoreAuditEvent]) -> str:
    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "id",
            "created_at",
            "user_id",
            "action",
            "resource_type",
            "resource_id",
            "decision",
            "reason",
            "request_id",
            "metadata",
        ],
    )
    writer.writeheader()
    for event in events:
        writer.writerow(
            {
                "id": _csv_cell(event.id),
                "created_at": _csv_cell(event.created_at),
                "user_id": _csv_cell(event.user_id),
                "action": _csv_cell(event.action),
                "resource_type": _csv_cell(event.resource_type),
                "resource_id": _csv_cell(event.resource_id),
                "decision": _csv_cell(event.decision),
                "reason": _csv_cell(event.reason),
                "request_id": _csv_cell(event.request_id),
                "metadata": _csv_cell(json.dumps(event.metadata, sort_keys=True, ensure_ascii=False, default=str)),
            }
        )
    return output.getvalue()


def _csv_cell(value: Any) -> str | None:
    return sanitize_csv_field(value)
