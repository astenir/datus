"""Enterprise audit administration routes."""

from __future__ import annotations

import csv
import json
from io import StringIO
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from datus.api.auth.context import AppContext
from datus.api.enterprise.deps import get_audit_sink
from datus.api.enterprise.models import AuditEvent as CoreAuditEvent
from datus.api.models.base_models import Result
from datus_enterprise.audit import AuditEvent, audit_decision
from datus_enterprise.authorization import require_module

router = APIRouter(prefix="/api/v1", tags=["enterprise-audit"])

AdminAuditCtx = Annotated[AppContext, Depends(require_module("module.admin.audit"))]


class AuditLogEntry(BaseModel):
    """Sanitized audit log entry returned to admin callers."""

    user_id: str | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    decision: str
    reason: str | None = None
    request_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.get("/admin/audit-logs", response_model=Result[list[AuditLogEntry]], summary="List Audit Logs")
async def list_audit_logs(
    ctx: AdminAuditCtx,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    user_id: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    decision: str | None = None,
) -> Result[list[AuditLogEntry]]:
    """Query audit logs when the configured audit sink exposes a reader interface."""

    events, error = await _query_audit_events(
        ctx,
        operation="list_audit_logs",
        limit=limit,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        decision=decision,
    )
    if error is not None:
        return error

    entries = [_entry_from_event(event) for event in events]
    await _audit_query(ctx, operation="list_audit_logs", decision="allow", reason=None, count=len(entries))
    return Result(success=True, data=entries)


@router.get("/admin/audit-logs/export", response_model=None, summary="Export Audit Logs")
async def export_audit_logs(
    ctx: AdminAuditCtx,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    user_id: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    decision: str | None = None,
) -> Response | Result[dict]:
    """Export matching audit logs as a CSV file when the audit sink supports queries."""

    events, error = await _query_audit_events(
        ctx,
        operation="export_audit_logs",
        limit=limit,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        decision=decision,
    )
    if error is not None:
        return error

    await _audit_query(ctx, operation="export_audit_logs", decision="allow", reason=None, count=len(events))
    return Response(
        content=_events_to_csv(events),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="audit-logs.csv"'},
    )


async def _query_audit_events(
    ctx: AppContext,
    *,
    operation: str,
    limit: int,
    user_id: str | None,
    action: str | None,
    resource_type: str | None,
    resource_id: str | None,
    decision: str | None,
) -> tuple[list[CoreAuditEvent], Result[Any] | None]:
    sink = get_audit_sink()
    query_events = getattr(sink, "query_events", None)
    if not callable(query_events):
        await _audit_query(ctx, operation=operation, decision="deny", reason="audit query unavailable", count=None)
        return [], Result(
            success=False,
            errorCode="AUDIT_QUERY_UNAVAILABLE",
            errorMessage="The configured audit sink does not support audit log queries.",
        )

    try:
        events = await query_events(
            limit=limit,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            decision=decision,
        )
    except Exception:
        await _audit_query(ctx, operation=operation, decision="deny", reason="audit query failed", count=None)
        return [], Result(
            success=False,
            errorCode="AUDIT_QUERY_FAILED",
            errorMessage="Audit log query failed.",
        )

    return events[:limit], None


async def _audit_query(
    ctx: AppContext, *, operation: str, decision: str, reason: str | None, count: int | None
) -> None:
    metadata = {"operation": operation}
    if count is not None:
        metadata["count"] = count
    await audit_decision(
        ctx,
        AuditEvent(
            action="module.admin.audit",
            resource_type="audit_log",
            resource_id=None,
            decision=decision,
            reason=reason,
            metadata=metadata,
        ),
    )


def _entry_from_event(event: CoreAuditEvent) -> AuditLogEntry:
    return AuditLogEntry(
        user_id=event.user_id,
        action=event.action,
        resource_type=event.resource_type,
        resource_id=event.resource_id,
        decision=event.decision,
        reason=event.reason,
        request_id=event.request_id,
        metadata=dict(event.metadata),
    )


def _events_to_csv(events: list[CoreAuditEvent]) -> str:
    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
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
                "user_id": event.user_id,
                "action": event.action,
                "resource_type": event.resource_type,
                "resource_id": event.resource_id,
                "decision": event.decision,
                "reason": event.reason,
                "request_id": event.request_id,
                "metadata": json.dumps(event.metadata, sort_keys=True, ensure_ascii=False, default=str),
            }
        )
    return output.getvalue()
