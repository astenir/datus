"""Enterprise session administration routes."""

from __future__ import annotations

import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.deps import ServiceDep
from datus.api.models.base_models import Result
from datus_enterprise.audit import AuditEvent, audit_decision
from datus_enterprise.authorization import require_module

router = APIRouter(prefix="/api/v1", tags=["enterprise-sessions"])

AdminSessionsCtx = Annotated[AppContext, Depends(require_module("module.admin.sessions"))]

_SESSION_IO_TIMEOUT = 15.0


class AdminSessionSummary(BaseModel):
    """Bounded session metadata for admin views."""

    session_id: str
    owner_user_id: str | None = None
    status: str
    is_running: bool = False
    created_at: str | None = None
    updated_at: str | None = None
    event_count: int = 0
    exists_on_disk: bool | None = None


class AdminSessionDetail(AdminSessionSummary):
    """Detailed bounded session metadata for one session."""

    consumer_offset: int = 0
    error: str | None = None


@router.get(
    "/admin/sessions",
    response_model=Result[list[AdminSessionSummary]],
    summary="List Admin Sessions",
    description="Admin-only session owner and runtime status list.",
)
async def list_admin_sessions(
    svc: ServiceDep,
    ctx: AdminSessionsCtx,
    user_id: Annotated[str | None, Query(description="Optional owner user id filter")] = None,
) -> Result[list[AdminSessionSummary]]:
    """List sessions from the owner index and merge in active in-process tasks."""

    records, error = await _list_owner_records(svc, ctx, user_id=user_id)
    if error is not None:
        return error

    summaries = await _merge_owner_records_and_tasks(svc, records, user_id=user_id)
    await audit_decision(
        ctx,
        AuditEvent(
            action="module.admin.sessions",
            resource_type="session",
            resource_id=None,
            decision="allow",
            metadata={"operation": "list_admin_sessions", "count": len(summaries), "user_id": user_id},
        ),
    )
    return Result(success=True, data=summaries)


@router.get(
    "/admin/sessions/{session_id}",
    response_model=Result[AdminSessionDetail],
    summary="Get Admin Session",
    description="Admin-only session owner and runtime status detail.",
)
async def get_admin_session(
    session_id: str,
    svc: ServiceDep,
    ctx: AdminSessionsCtx,
) -> Result[AdminSessionDetail]:
    """Return bounded metadata for a known session."""

    detail = await _resolve_session_detail(svc, session_id)
    if detail is None:
        await _audit_session_mutation(
            ctx,
            session_id=session_id,
            operation="get_admin_session",
            decision="deny",
            reason="session not found",
        )
        return _session_error("RESOURCE_NOT_FOUND", "Session not found")

    await _audit_session_mutation(
        ctx,
        session_id=session_id,
        operation="get_admin_session",
        decision="allow",
        old_summary=_summary_for_audit(detail),
    )
    return Result(success=True, data=detail)


@router.post(
    "/admin/sessions/{session_id}/stop",
    response_model=Result[dict],
    summary="Stop Admin Session",
    description="Admin-only stop for a running session.",
)
async def stop_admin_session(
    session_id: str,
    svc: ServiceDep,
    ctx: AdminSessionsCtx,
) -> Result[dict]:
    """Stop a running session without requiring the caller to own it."""

    before = await _resolve_session_detail(svc, session_id)
    if before is None:
        await _audit_session_mutation(
            ctx,
            session_id=session_id,
            operation="stop_admin_session",
            decision="deny",
            reason="session not found",
        )
        return _session_error("RESOURCE_NOT_FOUND", "Session not found")

    stopped = await svc.task_manager.stop_task(session_id)
    after = await _resolve_session_detail(svc, session_id)
    if not stopped:
        await _audit_session_mutation(
            ctx,
            session_id=session_id,
            operation="stop_admin_session",
            decision="deny",
            reason="session not running",
            old_summary=_summary_for_audit(before),
            new_summary=_summary_for_audit(after),
            metadata={"stopped": False},
        )
        return _session_error("SESSION_NOT_RUNNING", f"Session {session_id} is not currently running")

    await _audit_session_mutation(
        ctx,
        session_id=session_id,
        operation="stop_admin_session",
        decision="allow",
        old_summary=_summary_for_audit(before),
        new_summary=_summary_for_audit(after),
        metadata={"stopped": stopped},
    )
    return Result(success=True, data={"session_id": session_id, "stopped": True})


@router.delete(
    "/admin/sessions/{session_id}",
    response_model=Result[dict],
    summary="Delete Admin Session",
    description="Admin-only deletion for a session and its owner metadata.",
)
async def delete_admin_session(
    session_id: str,
    svc: ServiceDep,
    ctx: AdminSessionsCtx,
) -> Result[dict]:
    """Delete a session from its owner's disk scope and remove owner metadata."""

    before = await _resolve_session_detail(svc, session_id)
    if before is None:
        await _audit_session_mutation(
            ctx,
            session_id=session_id,
            operation="delete_admin_session",
            decision="deny",
            reason="session not found",
        )
        return _session_error("RESOURCE_NOT_FOUND", "Session not found")

    if before.is_running:
        await svc.task_manager.stop_task(session_id)
        await svc.task_manager.discard_task_snapshot(session_id, wait=True, timeout=_SESSION_IO_TIMEOUT)

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(svc.chat.delete_session, session_id, user_id=before.owner_user_id),
            timeout=_SESSION_IO_TIMEOUT,
        )
    except TimeoutError:
        await _audit_session_mutation(
            ctx,
            session_id=session_id,
            operation="delete_admin_session",
            decision="deny",
            reason="session delete timed out",
            old_summary=_summary_for_audit(before),
        )
        return _session_error("REQUEST_TIMEOUT", "Session delete timed out")

    if not result.success:
        await _audit_session_mutation(
            ctx,
            session_id=session_id,
            operation="delete_admin_session",
            decision="deny",
            reason=result.errorMessage or result.errorCode or "session delete failed",
            old_summary=_summary_for_audit(before),
        )
        return Result(success=False, errorCode=result.errorCode, errorMessage=result.errorMessage)

    await deps.get_enterprise_extensions().session_owner_store.delete_owner(svc.project_id, session_id)
    await svc.task_manager.discard_task_snapshot(session_id)
    await _audit_session_mutation(
        ctx,
        session_id=session_id,
        operation="delete_admin_session",
        decision="allow",
        old_summary=_summary_for_audit(before),
        new_summary={"deleted": True},
    )
    return Result(success=True, data={"session_id": session_id, "deleted": True})


async def _list_owner_records(
    svc: ServiceDep,
    ctx: AppContext,
    *,
    user_id: str | None,
) -> tuple[list[dict[str, Any]], Result[Any] | None]:
    store = deps.get_enterprise_extensions().session_owner_store
    list_sessions = getattr(store, "list_sessions", None)
    if callable(list_sessions):
        try:
            return await list_sessions(svc.project_id, user_id), None
        except Exception:
            await _audit_session_mutation(
                ctx,
                session_id=None,
                operation="list_admin_sessions",
                decision="deny",
                reason="session list failed",
            )
            return [], _session_error("SESSION_LIST_FAILED", "Session list failed.")

    if user_id is not None:
        try:
            session_ids = await store.list_session_ids(svc.project_id, user_id)
            return [
                {
                    "project_id": svc.project_id,
                    "session_id": session_id,
                    "user_id": user_id,
                    "created_at": None,
                    "updated_at": None,
                }
                for session_id in session_ids
            ], None
        except Exception:
            await _audit_session_mutation(
                ctx,
                session_id=None,
                operation="list_admin_sessions",
                decision="deny",
                reason="session list failed",
            )
            return [], _session_error("SESSION_LIST_FAILED", "Session list failed.")

    await _audit_session_mutation(
        ctx,
        session_id=None,
        operation="list_admin_sessions",
        decision="deny",
        reason="session owner store does not support admin listing",
    )
    return [], _session_error(
        "SESSION_LIST_UNAVAILABLE",
        "The configured session owner store does not support admin session listing.",
    )


async def _merge_owner_records_and_tasks(
    svc: ServiceDep,
    records: list[dict[str, Any]],
    *,
    user_id: str | None,
) -> list[AdminSessionSummary]:
    by_session_id: dict[str, AdminSessionSummary] = {}
    task_snapshots = {str(item["session_id"]): item for item in svc.task_manager.list_task_snapshots()}

    for record in records:
        session_id = str(record.get("session_id") or "")
        if not session_id:
            continue
        owner_user_id = _optional_str(record.get("user_id") or record.get("owner_user_id"))
        task = task_snapshots.pop(session_id, None)
        by_session_id[session_id] = await _summary_from_record_and_task(svc, record, task, owner_user_id)

    for session_id, task in task_snapshots.items():
        owner_user_id = _optional_str(task.get("owner_user_id"))
        if user_id is not None and owner_user_id != user_id:
            continue
        by_session_id[session_id] = await _summary_from_record_and_task(
            svc,
            {"session_id": session_id, "user_id": owner_user_id},
            task,
            owner_user_id,
        )

    return sorted(by_session_id.values(), key=lambda item: item.updated_at or item.created_at or "", reverse=True)


async def _resolve_session_detail(svc: ServiceDep, session_id: str) -> AdminSessionDetail | None:
    store = deps.get_enterprise_extensions().session_owner_store
    owner = await store.get_owner(svc.project_id, session_id)
    task = svc.task_manager.get_task_snapshot(session_id)
    if owner is None and task is None:
        return None

    summary = await _summary_from_record_and_task(
        svc,
        {"session_id": session_id, "user_id": owner},
        task,
        owner or _optional_str((task or {}).get("owner_user_id")),
    )
    return AdminSessionDetail(
        **summary.model_dump(),
        consumer_offset=int((task or {}).get("consumer_offset") or 0),
        error=_optional_str((task or {}).get("error")),
    )


async def _summary_from_record_and_task(
    svc: ServiceDep,
    record: dict[str, Any],
    task: dict[str, Any] | None,
    owner_user_id: str | None,
) -> AdminSessionSummary:
    session_id = str(record["session_id"])
    exists_on_disk = None
    if owner_user_id is not None:
        exists_on_disk = await _safe_session_exists(svc, session_id, owner_user_id)

    return AdminSessionSummary(
        session_id=session_id,
        owner_user_id=owner_user_id,
        status=str((task or {}).get("status") or "persisted"),
        is_running=bool((task or {}).get("is_running")),
        created_at=_optional_str((task or {}).get("created_at") or record.get("created_at")),
        updated_at=_optional_str(record.get("updated_at") or (task or {}).get("created_at")),
        event_count=int((task or {}).get("event_count") or 0),
        exists_on_disk=exists_on_disk,
    )


async def _safe_session_exists(svc: ServiceDep, session_id: str, owner_user_id: str) -> bool:
    try:
        return bool(await asyncio.to_thread(svc.chat.session_exists, session_id, user_id=owner_user_id))
    except Exception:
        return False


async def _audit_session_mutation(
    ctx: AppContext,
    *,
    session_id: str | None,
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
            action="module.admin.sessions",
            resource_type="session",
            resource_id=session_id,
            decision=decision,
            reason=reason,
            metadata=audit_metadata,
        ),
    )


def _summary_for_audit(summary: AdminSessionSummary | None) -> dict[str, Any] | None:
    if summary is None:
        return None
    return {
        "session_id": summary.session_id,
        "owner_user_id": summary.owner_user_id,
        "status": summary.status,
        "is_running": summary.is_running,
        "exists_on_disk": summary.exists_on_disk,
    }


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _session_error(error_code: str, message: str) -> Result[Any]:
    return Result(success=False, errorCode=error_code, errorMessage=message)
