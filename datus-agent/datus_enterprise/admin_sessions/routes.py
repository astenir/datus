"""Enterprise session administration routes."""

from __future__ import annotations

import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.deps import ServiceDep
from datus.api.enterprise.deps import require_platform_active
from datus.api.models.base_models import Result
from datus_enterprise.admin_sessions.helpers import (
    _audit_session_mutation,
    _audit_session_mutation_best_effort,
    _can_use_native_owner_page,
    _list_owner_records,
    _merge_owner_records_and_tasks,
    _resolve_session_detail_or_error,
    _session_error,
    _session_matches_search,
    _summary_for_audit,
)
from datus_enterprise.admin_sessions.models import AdminSessionDetail, AdminSessionSummary
from datus_enterprise.api.admin_pagination import (
    ADMIN_LIST_DEFAULT_LIMIT,
    ADMIN_LIST_MAX_LIMIT,
    AdminListResult,
    paginate_admin_records,
)
from datus_enterprise.audit import AuditEvent, audit_decision
from datus_enterprise.authorization import require_module

router = APIRouter(prefix="/api/v1", tags=["enterprise-sessions"])
_require_admin_sessions = require_module("module.admin.sessions")
AdminSessionsCtx = Annotated[AppContext, Depends(_require_admin_sessions)]

_SESSION_IO_TIMEOUT = 15.0


@router.get(
    "/admin/sessions",
    response_model=AdminListResult[AdminSessionSummary],
    summary="List Admin Sessions",
    description="Admin-only session owner and runtime status list.",
    dependencies=[Depends(_require_admin_sessions)],
)
async def list_admin_sessions(
    svc: ServiceDep,
    ctx: AdminSessionsCtx,
    user_id: Annotated[str | None, Query(description="Optional owner user id filter")] = None,
    state: Annotated[str | None, Query(pattern="^(running|stopped)$")] = None,
    search: Annotated[str | None, Query(max_length=200, description="Search session fields.")] = None,
    limit: Annotated[int, Query(ge=1, le=ADMIN_LIST_MAX_LIMIT)] = ADMIN_LIST_DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdminListResult[AdminSessionSummary] | Result[Any]:
    """List sessions from the owner index and merge in active in-process tasks."""

    task_snapshots = list(svc.task_manager.list_task_snapshots())
    use_native_page = await _can_use_native_owner_page(
        svc,
        user_id=user_id,
        state=state,
        search=search,
        task_snapshots=task_snapshots,
    )
    records, error = await _list_owner_records(
        svc,
        ctx,
        user_id=user_id,
        limit=limit + 1 if use_native_page else None,
        offset=offset if use_native_page else None,
    )
    if error is not None:
        return error

    summaries = await _merge_owner_records_and_tasks(
        svc,
        records,
        user_id=user_id,
        task_snapshots=task_snapshots,
        include_runtime_only=not use_native_page,
    )
    summaries = [
        summary
        for summary in summaries
        if (state != "running" or summary.is_running)
        and (state != "stopped" or not summary.is_running)
        and _session_matches_search(summary, search)
    ]
    page = paginate_admin_records(
        summaries,
        limit=limit,
        offset=offset,
        records_are_offset=use_native_page,
    )
    await audit_decision(
        ctx,
        AuditEvent(
            action="module.admin.sessions",
            resource_type="session",
            resource_id=None,
            decision="allow",
            metadata={
                "operation": "list_admin_sessions",
                "count": len(page.data or []),
                "user_id": user_id,
                "offset": offset,
                "has_more": page.pagination.has_more,
            },
        ),
    )
    return page


@router.get(
    "/admin/sessions/{session_id}",
    response_model=Result[AdminSessionDetail],
    summary="Get Admin Session",
    description="Admin-only session owner and runtime status detail.",
    dependencies=[Depends(_require_admin_sessions)],
)
async def get_admin_session(
    session_id: str,
    svc: ServiceDep,
    ctx: AdminSessionsCtx,
) -> Result[AdminSessionDetail]:
    """Return bounded metadata for a known session."""

    detail, error = await _resolve_session_detail_or_error(svc, ctx, session_id, operation="get_admin_session")
    if error is not None:
        return error
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
    dependencies=[Depends(_require_admin_sessions)],
)
async def stop_admin_session(
    session_id: str,
    svc: ServiceDep,
    ctx: AdminSessionsCtx,
) -> Result[dict]:
    """Stop a running session without requiring the caller to own it."""

    before, error = await _resolve_session_detail_or_error(svc, ctx, session_id, operation="stop_admin_session")
    if error is not None:
        return error
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
    after, error = await _resolve_session_detail_or_error(svc, ctx, session_id, operation="stop_admin_session")
    if error is not None:
        return error
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

    await _audit_session_mutation_best_effort(
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
    dependencies=[
        Depends(_require_admin_sessions),
        Depends(require_platform_active(operation="admin.sessions.delete", resource_type="session")),
    ],
)
async def delete_admin_session(
    session_id: str,
    svc: ServiceDep,
    ctx: AdminSessionsCtx,
) -> Result[dict]:
    """Delete a session from its owner's disk scope and remove owner metadata."""

    before, error = await _resolve_session_detail_or_error(svc, ctx, session_id, operation="delete_admin_session")
    if error is not None:
        return error
    if before is None:
        await _audit_session_mutation(
            ctx,
            session_id=session_id,
            operation="delete_admin_session",
            decision="deny",
            reason="session not found",
        )
        return _session_error("RESOURCE_NOT_FOUND", "Session not found")

    if before.owner_user_id is None:
        await _audit_session_mutation(
            ctx,
            session_id=session_id,
            operation="delete_admin_session",
            decision="deny",
            reason="session owner unknown",
            old_summary=_summary_for_audit(before),
        )
        return _session_error("SESSION_OWNER_UNKNOWN", "Session owner is unknown.")

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

    try:
        await deps.get_enterprise_extensions().session_owner_store.delete_owner(svc.project_id, session_id)
    except Exception:
        await _audit_session_mutation(
            ctx,
            session_id=session_id,
            operation="delete_admin_session",
            decision="deny",
            reason="session owner delete failed",
            old_summary=_summary_for_audit(before),
        )
        return _session_error("SESSION_OWNER_DELETE_FAILED", "Session owner metadata delete failed.")

    await svc.task_manager.discard_task_snapshot(session_id)
    await _audit_session_mutation_best_effort(
        ctx,
        session_id=session_id,
        operation="delete_admin_session",
        decision="allow",
        old_summary=_summary_for_audit(before),
        new_summary={"deleted": True},
    )
    return Result(success=True, data={"session_id": session_id, "deleted": True})
