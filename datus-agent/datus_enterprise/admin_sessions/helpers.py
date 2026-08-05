"""Shared non-route helpers for enterprise session administration."""

from __future__ import annotations

import asyncio
from typing import Any

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.deps import ServiceDep
from datus.api.models.base_models import Result
from datus.utils.loggings import get_logger
from datus_enterprise.admin_sessions.models import AdminSessionDetail, AdminSessionSummary
from datus_enterprise.audit import AuditEvent, audit_decision

logger = get_logger(__name__)


async def _list_owner_records(
    svc: ServiceDep,
    ctx: AppContext,
    *,
    user_id: str | None,
    limit: int | None = None,
    offset: int | None = None,
) -> tuple[list[dict[str, Any]], Result[Any] | None]:
    store = deps.get_enterprise_extensions().session_owner_store
    list_sessions_page = getattr(store, "list_sessions_page", None)
    if limit is not None and offset is not None and callable(list_sessions_page):
        try:
            return await list_sessions_page(
                svc.project_id,
                user_id,
                limit=limit,
                offset=offset,
            ), None
        except Exception:
            await _audit_session_mutation(
                ctx,
                session_id=None,
                operation="list_admin_sessions",
                decision="deny",
                reason="session list failed",
            )
            return [], _session_error("SESSION_LIST_FAILED", "Session list failed.")

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


async def _can_use_native_owner_page(
    svc: ServiceDep,
    *,
    user_id: str | None,
    state: str | None,
    search: str | None,
    task_snapshots: list[dict[str, Any]],
) -> bool:
    """Use a DB page only when runtime task merging cannot add extra rows."""

    store = deps.get_enterprise_extensions().session_owner_store
    if state is not None or (search or "").strip() or not callable(getattr(store, "list_sessions_page", None)):
        return False
    get_sessions = getattr(store, "get_sessions", None)
    if task_snapshots and not callable(get_sessions):
        return False

    try:
        session_ids = [str(task.get("session_id") or "") for task in task_snapshots]
        if any(not session_id for session_id in session_ids):
            return False
        owner_records = (
            {str(record.get("session_id") or ""): record for record in await get_sessions(svc.project_id, session_ids)}
            if task_snapshots
            else {}
        )
        for task in task_snapshots:
            session_id = str(task.get("session_id") or "")
            record = owner_records.get(session_id)
            if record is None:
                return False
            if not record.get("updated_at"):
                # A runtime task's created_at becomes the summary sort key when
                # legacy/local owner metadata has no persisted timestamp.
                return False
            owner_user_id = _optional_str(record.get("user_id") or record.get("owner_user_id"))
            if user_id is not None and owner_user_id != user_id:
                task_owner = _optional_str(task.get("owner_user_id"))
                if task_owner == user_id:
                    return False
    except Exception:
        return False
    return True


async def _merge_owner_records_and_tasks(
    svc: ServiceDep,
    records: list[dict[str, Any]],
    *,
    user_id: str | None,
    task_snapshots: list[dict[str, Any]] | None = None,
    include_runtime_only: bool = True,
) -> list[AdminSessionSummary]:
    by_session_id: dict[str, AdminSessionSummary] = {}
    snapshots_by_session_id = (
        {str(item["session_id"]): item for item in task_snapshots if item.get("session_id")}
        if task_snapshots is not None
        else {str(item["session_id"]): item for item in svc.task_manager.list_task_snapshots()}
    )

    for record in records:
        session_id = str(record.get("session_id") or "")
        if not session_id:
            continue
        owner_user_id = _optional_str(record.get("user_id") or record.get("owner_user_id"))
        task = snapshots_by_session_id.pop(session_id, None)
        by_session_id[session_id] = await _summary_from_record_and_task(
            svc,
            record,
            task,
            owner_user_id,
            check_disk=False,
        )

    if not include_runtime_only:
        return sorted(by_session_id.values(), key=lambda item: item.updated_at or item.created_at or "", reverse=True)

    for session_id, task in snapshots_by_session_id.items():
        owner_user_id = _optional_str(task.get("owner_user_id"))
        if user_id is not None and owner_user_id != user_id:
            continue
        by_session_id[session_id] = await _summary_from_record_and_task(
            svc,
            {"session_id": session_id, "user_id": owner_user_id},
            task,
            owner_user_id,
            check_disk=False,
        )

    return sorted(by_session_id.values(), key=lambda item: item.updated_at or item.created_at or "", reverse=True)


async def _resolve_session_detail(svc: ServiceDep, session_id: str) -> AdminSessionDetail | None:
    store = deps.get_enterprise_extensions().session_owner_store
    record = await _get_owner_record(store, svc.project_id, session_id)
    owner = _optional_str((record or {}).get("user_id") or (record or {}).get("owner_user_id"))
    task = svc.task_manager.get_task_snapshot(session_id)
    if owner is None and task is None:
        return None

    summary = await _summary_from_record_and_task(
        svc,
        record or {"session_id": session_id, "user_id": owner},
        task,
        owner or _optional_str((task or {}).get("owner_user_id")),
    )
    return AdminSessionDetail(
        **summary.model_dump(),
        consumer_offset=int(task.get("consumer_offset") or 0) if task is not None else None,
        error=_optional_str(task.get("error")) if task is not None else None,
    )


async def _get_owner_record(store: Any, project_id: str, session_id: str) -> dict[str, Any] | None:
    """Return full owner metadata when the configured store supports it."""

    get_session = getattr(store, "get_session", None)
    if callable(get_session):
        record = await get_session(project_id, session_id)
        if record is not None:
            return record

    owner = await store.get_owner(project_id, session_id)
    if owner is None:
        return None
    return {"project_id": project_id, "session_id": session_id, "user_id": owner}


async def _resolve_session_detail_or_error(
    svc: ServiceDep,
    ctx: AppContext,
    session_id: str,
    *,
    operation: str,
) -> tuple[AdminSessionDetail | None, Result[Any] | None]:
    try:
        return await _resolve_session_detail(svc, session_id), None
    except Exception:
        await _audit_session_mutation(
            ctx,
            session_id=session_id,
            operation=operation,
            decision="deny",
            reason="session read failed",
        )
        return None, _session_error("SESSION_READ_FAILED", "Session read failed")


async def _summary_from_record_and_task(
    svc: ServiceDep,
    record: dict[str, Any],
    task: dict[str, Any] | None,
    owner_user_id: str | None,
    *,
    check_disk: bool = True,
) -> AdminSessionSummary:
    session_id = str(record["session_id"])
    exists_on_disk = None
    if check_disk and owner_user_id is not None:
        exists_on_disk = await _safe_session_exists(svc, session_id, owner_user_id)

    return AdminSessionSummary(
        session_id=session_id,
        owner_user_id=owner_user_id,
        status=str((task or {}).get("status") or "persisted"),
        is_running=bool((task or {}).get("is_running")),
        runtime_snapshot_available=task is not None,
        created_at=_optional_str(record.get("created_at") or (task or {}).get("created_at")),
        updated_at=_optional_str(record.get("updated_at") or (task or {}).get("created_at")),
        event_count=int(task.get("event_count") or 0) if task is not None else None,
        exists_on_disk=exists_on_disk,
    )


async def _safe_session_exists(svc: ServiceDep, session_id: str, owner_user_id: str) -> bool | None:
    try:
        return bool(await asyncio.to_thread(svc.chat.session_exists, session_id, user_id=owner_user_id))
    except Exception:
        return None


def _session_matches_search(summary: AdminSessionSummary, search: str | None) -> bool:
    query = (search or "").strip().casefold()
    if not query:
        return True
    values = (
        summary.session_id,
        summary.owner_user_id,
        summary.status,
        summary.event_count,
    )
    return any(query in str(value or "").casefold() for value in values)


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


async def _audit_session_mutation_best_effort(
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
    try:
        await _audit_session_mutation(
            ctx,
            session_id=session_id,
            operation=operation,
            decision=decision,
            reason=reason,
            old_summary=old_summary,
            new_summary=new_summary,
            metadata=metadata,
        )
    except Exception as exc:
        logger.warning(
            "Admin session audit write failed for operation '%s' decision '%s': %s",
            operation,
            decision,
            exc,
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
