"""Downstream chat-task limits and stateless buffer helpers."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal, Optional, TypeAlias

from datus.api.models.downstream import DashboardEditSession, ReportEditSession
from datus.schemas.action_history import ActionRole, ActionStatus
from datus.utils.loggings import get_logger
from datus.utils.time_utils import now_utc_iso

logger = get_logger(__name__)

WebFilesystemExecutor: TypeAlias = Literal["client", "server"]
ArtifactEditSession: TypeAlias = ReportEditSession | DashboardEditSession
REPORT_EDIT_SESSION_PREFIX = "report_edit__"
DASHBOARD_EDIT_SESSION_PREFIX = "dashboard_edit__"
ARTIFACT_EDIT_SESSION_TTL_SECONDS = 6 * 60 * 60


@dataclass(frozen=True)
class ChatBufferLimits:
    """Per-task in-memory SSE retention limits."""

    max_events: int = 5000
    max_bytes: int = 16 * 1024 * 1024
    completed_ttl_seconds: int = 300
    cleanup_interval_seconds: int = 60
    stop_grace_seconds: int = 5

    @classmethod
    def from_api_config(cls, api_config: dict[str, Any] | None) -> "ChatBufferLimits":
        raw = (api_config or {}).get("chat") or {}
        if not isinstance(raw, dict):
            raw = {}
        return cls(
            max_events=_positive_int(raw.get("max_buffer_events"), cls.max_events),
            max_bytes=_positive_int(raw.get("max_buffer_bytes"), cls.max_bytes),
            completed_ttl_seconds=_positive_int(raw.get("completed_task_ttl_seconds"), cls.completed_ttl_seconds),
            cleanup_interval_seconds=_positive_int(raw.get("cleanup_interval_seconds"), cls.cleanup_interval_seconds),
            stop_grace_seconds=_positive_int(raw.get("stop_grace_seconds"), cls.stop_grace_seconds),
        )


class EventBufferExpiredError(RuntimeError):
    """Raised when a resume cursor predates the bounded in-memory buffer."""


class EventBufferOverflowError(RuntimeError):
    """Raised when one SSE event exceeds the complete task buffer budget."""


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def initialize_chat_task_runtime(task, owner_user_id: Optional[str]) -> None:
    task.owner_user_id = owner_user_id
    task.event_sizes = []
    task.event_bytes = 0
    task.base_offset = 0
    task.completed_at = None
    task.admission_token = None
    task.run_id = uuid.uuid4().hex
    task.session_established = False
    task.terminal_event_persisted = False
    task.terminal_event_type = None
    task.stop_requested = False


def create_report_edit_session(
    sessions: dict[str, ArtifactEditSession],
    *,
    user_id: Optional[str],
    report_slug: str,
) -> ReportEditSession:
    purge_expired_artifact_edit_sessions(sessions)
    edit_session_id = uuid.uuid4().hex
    subagent_id = f"{REPORT_EDIT_SESSION_PREFIX}{edit_session_id}"
    session = ReportEditSession(
        edit_session_id=edit_session_id,
        subagent_id=subagent_id,
        artifact_type="report",
        artifact_slug=report_slug,
        owner_user_id=user_id,
        created_at=now_utc_iso(),
    )
    sessions[subagent_id] = session
    return session


def create_dashboard_edit_session(
    sessions: dict[str, ArtifactEditSession],
    *,
    user_id: Optional[str],
    dashboard_slug: str,
) -> DashboardEditSession:
    purge_expired_artifact_edit_sessions(sessions)
    edit_session_id = uuid.uuid4().hex
    subagent_id = f"{DASHBOARD_EDIT_SESSION_PREFIX}{edit_session_id}"
    session = DashboardEditSession(
        edit_session_id=edit_session_id,
        subagent_id=subagent_id,
        artifact_type="dashboard",
        artifact_slug=dashboard_slug,
        owner_user_id=user_id,
        created_at=now_utc_iso(),
    )
    sessions[subagent_id] = session
    return session


def get_artifact_edit_session(
    sessions: dict[str, ArtifactEditSession],
    subagent_id: Optional[str],
) -> Optional[ArtifactEditSession]:
    if not subagent_id:
        return None
    purge_expired_artifact_edit_sessions(sessions)
    return sessions.get(subagent_id)


def purge_expired_artifact_edit_sessions(sessions: dict[str, ArtifactEditSession]) -> None:
    if not sessions:
        return
    now = datetime.now(timezone.utc)
    expired: list[str] = []
    for subagent_id, session in sessions.items():
        try:
            created = datetime.fromisoformat(session.created_at.replace("Z", "+00:00"))
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
        except ValueError:
            expired.append(subagent_id)
            continue
        if (now - created).total_seconds() > ARTIFACT_EDIT_SESSION_TTL_SECONDS:
            expired.append(subagent_id)
    for subagent_id in expired:
        sessions.pop(subagent_id, None)


def terminal_outcome_from_action(
    action: Any,
) -> Optional[tuple[Literal["error", "cancelled", "timeout"], str, str]]:
    if getattr(action, "role", None) != ActionRole.ASSISTANT or getattr(action, "depth", 0) != 0:
        return None
    if getattr(action, "action_type", None) == "interrupted":
        detail = str(getattr(action, "messages", None) or "Execution interrupted by user")
        return ("cancelled", detail, "CHAT_CANCELLED")
    if getattr(action, "action_type", None) != "error" or getattr(action, "status", None) != ActionStatus.FAILED:
        return None

    output = action.output if isinstance(getattr(action, "output", None), dict) else {}
    detail = str(
        output.get("error")
        or output.get("error_message")
        or output.get("errorMessage")
        or getattr(action, "messages", None)
        or "Chat execution failed"
    )
    error_type = str(
        output.get("error_type") or output.get("error_code") or output.get("errorCode") or "CHAT_EXECUTION_ERROR"
    )
    return ("error", detail, error_type)


def trim_event_buffer(task, limits: ChatBufferLimits) -> None:
    """Trim old events in batches while keeping absolute resume cursors stable."""

    if len(task.events) <= limits.max_events and task.event_bytes <= limits.max_bytes:
        return

    target_events = max(1, int(limits.max_events * 0.8))
    target_bytes = max(1, int(limits.max_bytes * 0.8))
    remove_count = 0
    removed_bytes = 0
    remaining_bytes = task.event_bytes
    while remove_count < len(task.events) - 1 and (
        len(task.events) - remove_count > target_events or remaining_bytes > target_bytes
    ):
        size = task.event_sizes[remove_count]
        removed_bytes += size
        remaining_bytes -= size
        remove_count += 1

    if remove_count == 0:
        return
    del task.events[:remove_count]
    del task.event_sizes[:remove_count]
    task.event_bytes = max(0, task.event_bytes - removed_bytes)
    task.base_offset += remove_count
    logger.warning(
        "Trimmed %s buffered chat events for session=%s; earliest_cursor=%s retained_bytes=%s",
        remove_count,
        task.session_id,
        task.base_offset,
        task.event_bytes,
    )


def task_snapshot(task) -> dict[str, Any]:
    return {
        "session_id": task.session_id,
        "owner_user_id": task.owner_user_id,
        "status": task.status,
        "is_running": task.status == "running",
        "created_at": task.created_at.isoformat(),
        "event_count": len(task.events),
        "event_bytes": task.event_bytes,
        "earliest_event_cursor": task.base_offset,
        "consumer_offset": task.consumer_offset,
        "error": task.error,
    }
