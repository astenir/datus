"""Downstream chat-task limits and stateless buffer helpers."""

import asyncio
import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal, Optional, Type, TypeAlias

from datus.agent.node.mcp_failure_actions_downstream import is_mcp_connection_failure_action
from datus.api.models.downstream import (
    ChatSessionTerminalEvent,
    ChatSessionToolExecutionEvent,
    DashboardEditSession,
    ReportEditSession,
)
from datus.configuration.agent_config import AgentConfig
from datus.models.session_manager import SessionManager, session_scope_from_user_id
from datus.schemas.action_history import ActionRole, ActionStatus
from datus.utils.loggings import get_logger
from datus.utils.path_manager import get_path_manager
from datus.utils.time_utils import now_utc_iso, to_utc_iso

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
    stream_delta_batch_interval_ms: int = 50
    stream_delta_batch_chars: int = 1024
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
            stream_delta_batch_interval_ms=_positive_int(
                raw.get("stream_delta_batch_interval_ms"), cls.stream_delta_batch_interval_ms
            ),
            stream_delta_batch_chars=_positive_int(raw.get("stream_delta_batch_chars"), cls.stream_delta_batch_chars),
            completed_ttl_seconds=_positive_int(raw.get("completed_task_ttl_seconds"), cls.completed_ttl_seconds),
            cleanup_interval_seconds=_positive_int(raw.get("cleanup_interval_seconds"), cls.cleanup_interval_seconds),
            stop_grace_seconds=_positive_int(raw.get("stop_grace_seconds"), cls.stop_grace_seconds),
        )


class EventBufferExpiredError(RuntimeError):
    """Raised when a resume cursor predates the bounded in-memory buffer."""


class EventBufferOverflowError(RuntimeError):
    """Raised when one SSE event exceeds the complete task buffer budget."""


async def prepare_chat_request_config(
    agent_config: AgentConfig,
    *,
    project_id: str,
    session_body_store: Any,
    artifact_acl_store: Any,
    enterprise_enabled: bool,
    user_id: Optional[str],
    principal: Optional[dict[str, Any]],
) -> None:
    """Attach downstream request state to an already cloned agent config."""

    if session_body_store is not None:
        agent_config._session_body_store = session_body_store
        agent_config._session_project_id = project_id
    agent_config.principal = dict(principal or {})
    agent_config._request_user_id = user_id
    agent_config._artifact_acl_store = artifact_acl_store
    agent_config._enterprise_enabled = enterprise_enabled
    agent_config._business_datasource_read_only = enterprise_enabled
    agent_config._protect_artifact_filesystem = enterprise_enabled
    if enterprise_enabled and not user_id:
        raise ValueError("AUTH_REQUIRED")
    if enterprise_enabled:
        from datus_enterprise.workspace import prepare_user_workspace

        workspace_root = await asyncio.to_thread(prepare_user_workspace, agent_config, user_id or "")
        agent_config._request_workspace_root = str(workspace_root)


async def persist_terminal_event(
    *,
    task: Any,
    agent_config: AgentConfig,
    user_id: Optional[str],
    event_type: Literal["error", "cancelled", "timeout"],
    error: str,
    error_type: str,
    project_id: str,
    session_body_store: Any,
    session_manager_type: Type[SessionManager] = SessionManager,
) -> None:
    """Best-effort persistence for established-session display outcomes."""

    if not task.session_established or task.terminal_event_persisted:
        return

    terminal_event = ChatSessionTerminalEvent(
        event_id=f"{task.run_id}-terminal",
        event_type=event_type,
        error=error,
        error_type=error_type,
    )
    base_dir = getattr(agent_config, "session_dir", None) or str(
        get_path_manager(agent_config=agent_config).sessions_dir
    )
    session_manager = session_manager_type(
        session_dir=base_dir,
        scope=session_scope_from_user_id(user_id),
        agent_config=agent_config,
        project_id=project_id,
        body_store=session_body_store,
    )
    try:
        await session_manager.append_terminal_event_async(task.session_id, terminal_event)
    except Exception:
        logger.warning(
            "Failed to persist terminal chat event for session %s",
            task.session_id,
            exc_info=True,
        )
        return
    task.terminal_event_persisted = True
    task.terminal_event_type = event_type


async def persist_tool_execution_event(
    *,
    task: Any,
    action: Any,
    agent_config: AgentConfig,
    user_id: Optional[str],
    project_id: str,
    session_body_store: Any,
    session_manager_type: Type[SessionManager] = SessionManager,
) -> None:
    """Best-effort persistence of measured tool timing for canonical history."""

    if not task.session_established or action.role != ActionRole.TOOL or action.status == ActionStatus.PROCESSING:
        return
    is_mcp_failure = is_mcp_connection_failure_action(action)
    start_time = action.start_time
    end_time = action.end_time
    if is_mcp_failure:
        # MCP connection failures are synthetic display actions. They do not
        # come from an SDK function_call_output, so there is no measured end
        # timestamp to attach to the in-memory action. Keep a zero-duration
        # sidecar event so canonical history can restore the failure card.
        if start_time is None and end_time is None:
            start_time = end_time = datetime.now(timezone.utc)
        elif start_time is None:
            start_time = end_time
        elif end_time is None:
            end_time = start_time
    elif start_time is None or end_time is None:
        return
    try:
        duration = (end_time - start_time).total_seconds()
    except (OverflowError, TypeError):
        return
    if not math.isfinite(duration) or duration < 0:
        return
    started_at = to_utc_iso(start_time)
    completed_at = to_utc_iso(end_time)
    if not started_at or not completed_at:
        return

    call_tool_id = action.action_id.removeprefix("complete_")
    tool_name = None
    error = None
    summary = None
    if is_mcp_failure:
        action_input = action.input if isinstance(action.input, dict) else {}
        tool_name = str(action_input.get("function_name") or action.action_type)
        action_output = action.output if isinstance(action.output, dict) else {}
        error_value = action_output.get("error")
        if isinstance(error_value, str) and error_value.strip():
            error = error_value.strip()
        summary_value = action_output.get("summary")
        if isinstance(summary_value, str) and summary_value.strip():
            summary = summary_value.strip()

    tool_event = ChatSessionToolExecutionEvent(
        event_id=f"{task.run_id}-tool-{call_tool_id}",
        call_tool_id=call_tool_id,
        duration=duration,
        started_at=started_at,
        completed_at=completed_at,
        depth=max(int(getattr(action, "depth", 0) or 0), 0),
        parent_action_id=getattr(action, "parent_action_id", None),
        tool_name=tool_name,
        error=error,
        summary=summary,
        created_at=completed_at,
    )
    base_dir = getattr(agent_config, "session_dir", None) or str(
        get_path_manager(agent_config=agent_config).sessions_dir
    )
    session_manager = session_manager_type(
        session_dir=base_dir,
        scope=session_scope_from_user_id(user_id),
        agent_config=agent_config,
        project_id=project_id,
        body_store=session_body_store,
    )
    try:
        await session_manager.append_tool_execution_event_async(task.session_id, tool_event)
    except Exception:
        logger.warning(
            "Failed to persist tool execution event for session %s and call %s",
            task.session_id,
            call_tool_id,
            exc_info=True,
        )


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
        "user_query": getattr(task, "user_query", None),
    }
