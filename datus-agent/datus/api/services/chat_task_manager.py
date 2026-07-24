"""
Chat Task Manager — decouples the agentic loop into background asyncio.Tasks.

The agentic loop runs in a background Task, writing SSE events to a buffer.
SSE endpoints consume events from the buffer via ``consume_events``.
Disconnecting a client does **not** cancel the background computation;
the client can reconnect and resume from where it left off.
"""

import asyncio
import copy
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, List, Literal, Optional

from datus.agent.node.agentic_node import AgenticNode
from datus.api.models.cli_models import (
    ChatSessionTerminalEvent,
    IMessageContent,
    SSEDataType,
    SSEEndData,
    SSEErrorData,
    SSEEvent,
    SSEMessageData,
    SSEMessagePayload,
    SSEPingData,
    SSESessionData,
    SSEUsageData,
    StreamChatInput,
)
from datus.api.models.dashboard_models import DashboardEditSession
from datus.api.models.report_models import ReportEditSession
from datus.api.services.action_sse_converter import action_to_sse_event
from datus.cli.autocomplete import AtReferenceCompleter
from datus.configuration.agent_config import AgentConfig
from datus.models.session_manager import SessionManager, session_scope_from_user_id
from datus.schemas.action_history import ActionHistoryManager, ActionRole, ActionStatus
from datus.schemas.node_models import Metric, ReferenceSql, TableSchema
from datus.tools.proxy.proxy_tool import apply_proxy_tools
from datus.utils.loggings import get_logger
from datus.utils.path_manager import get_path_manager, set_current_path_manager
from datus.utils.time_utils import now_utc_iso
from datus.utils.trace_context import build_chat_trace_context, reset_trace_context, set_trace_context

logger = get_logger(__name__)

if TYPE_CHECKING:
    from datus.api.enterprise.protocols import ArtifactAclStore, SessionBodyStore, SessionOwnerStore
    from datus.api.services.chat_admission import ChatAdmissionController

HEARTBEAT_INTERVAL = 10  # seconds
REPORT_EDIT_SESSION_PREFIX = "report_edit__"
DASHBOARD_EDIT_SESSION_PREFIX = "dashboard_edit__"
ARTIFACT_EDIT_SESSION_TTL_SECONDS = 6 * 60 * 60
ArtifactEditSession = ReportEditSession | DashboardEditSession


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


def is_thinking_only_content(content_items) -> bool:
    """Return True if all content items are thinking chunks (i.e. a delta message).

    Used by both the SSE coalescing logic and the bridge outbound conversion
    to avoid duplicating the detection heuristic.
    """
    return bool(content_items) and all(getattr(item, "type", "") == "thinking" for item in content_items)


def _is_stream_delta(event: SSEEvent) -> bool:
    """Return True if *event* is a consecutive-mergeable text delta."""
    if event.event != "message":
        return False
    data = event.data
    if not isinstance(data, SSEMessageData):
        return False
    if data.type not in (SSEDataType.CREATE_MESSAGE, SSEDataType.APPEND_MESSAGE):
        return False
    content_types = {getattr(item, "type", "") for item in data.payload.content}
    return bool(content_types) and content_types <= {"thinking", "markdown"} and len(content_types) == 1


def _delta_message_id(event: SSEEvent) -> str:
    """Extract the message_id from a text-delta event.

    Callers must ensure *event* passes ``_is_stream_delta`` first.
    """
    data = event.data
    if isinstance(data, SSEMessageData):
        return data.payload.message_id
    return ""


def _delta_content_type(event: SSEEvent) -> str:
    data = event.data
    if isinstance(data, SSEMessageData) and data.payload.content:
        return data.payload.content[0].type
    return ""


def _has_visible_content(event: SSEEvent) -> bool:
    if event.event != "message" or not isinstance(event.data, SSEMessageData):
        return False
    return any(bool(getattr(item, "payload", {}).get("content")) for item in event.data.payload.content)


def _assistant_content_fingerprint(event: SSEEvent) -> str:
    if event.event != "message" or not isinstance(event.data, SSEMessageData):
        return ""
    if event.data.payload.role != "assistant":
        return ""
    parts = []
    for item in event.data.payload.content:
        if item.type not in {"markdown", "thinking", "code"}:
            continue
        payload = getattr(item, "payload", {}) or {}
        content = payload.get("content")
        if content:
            parts.append(str(content).strip())
    return "\n".join(part for part in parts if part)


def _should_skip_duplicate_assistant_message(
    action,
    event: SSEEvent,
    seen_fingerprints: set[str],
) -> bool:
    if action.role != ActionRole.ASSISTANT or action.status != ActionStatus.SUCCESS:
        return False
    if action.action_type == "thinking_delta":
        return False
    if event.event != "message" or not isinstance(event.data, SSEMessageData):
        return False
    if event.data.type != SSEDataType.CREATE_MESSAGE:
        return False
    fingerprint = _assistant_content_fingerprint(event)
    return bool(fingerprint and fingerprint in seen_fingerprints)


def _remember_assistant_message(event: SSEEvent, seen_fingerprints: set[str]) -> None:
    fingerprint = _assistant_content_fingerprint(event)
    if fingerprint:
        seen_fingerprints.add(fingerprint)


def _should_include_final_response(action, assistant_response_sent: bool) -> bool:
    """Return True for top-level wrapper responses that should be rendered.

    Sub-agent actions are forwarded with ``depth > 0``. Their own
    ``*_response`` wrappers must stay inside the tool/sub-agent transcript and
    must not become the top-level assistant bubble.
    """
    return (
        action.role == ActionRole.ASSISTANT
        and action.status == ActionStatus.SUCCESS
        and getattr(action, "depth", 0) == 0
        and bool(action.action_type)
        and action.action_type.endswith("_response")
        and not assistant_response_sent
    )


def _is_visible_assistant_response(action, event: SSEEvent, *, tool_result_seen: bool) -> bool:
    """Return True when an action already emitted user-visible assistant text.

    Model providers do not agree on whether final text appears as ``response``,
    ``message`` or a completed thinking chunk. For web de-duping we care about
    the observable SSE message: after a tool result, any visible assistant text
    means the wrapper ``chat_response`` would duplicate it.
    """
    if action.role != ActionRole.ASSISTANT or action.status != ActionStatus.SUCCESS:
        return False
    if (
        not action.action_type
        or action.action_type in {"thinking", "thinking_delta", "response_delta"}
        or action.action_type.endswith("_response")
    ):
        return False
    if not _has_visible_content(event):
        return False
    output = action.output if isinstance(action.output, dict) else {}
    return tool_result_seen or output.get("is_thinking") is not True


def _coalesce_deltas(events: list[SSEEvent]) -> list[SSEEvent]:
    """Merge consecutive text deltas for the same message and content type.

    Non-delta events pass through unchanged and break any ongoing run of deltas.
    A change in ``message_id`` between adjacent deltas also breaks the run so
    that deltas from different logical messages are never merged together.
    """
    if not events:
        return []

    result: list[SSEEvent] = []
    run_start: int | None = None  # index of first delta in the current run
    run_msg_id: str = ""  # message_id of the current run
    run_content_type: str = ""

    for i, ev in enumerate(events):
        if _is_stream_delta(ev):
            msg_id = _delta_message_id(ev)
            content_type = _delta_content_type(ev)
            if run_start is None:
                run_start = i
                run_msg_id = msg_id
                run_content_type = content_type
            elif msg_id != run_msg_id or content_type != run_content_type:
                # Different message or presentation — start a separate run.
                result.append(_merge_delta_run(events[run_start:i]))
                run_start = i
                run_msg_id = msg_id
                run_content_type = content_type
        else:
            # Flush any accumulated delta run before emitting this non-delta
            if run_start is not None:
                result.append(_merge_delta_run(events[run_start:i]))
                run_start = None
            result.append(ev)

    # Flush trailing delta run
    if run_start is not None:
        result.append(_merge_delta_run(events[run_start:]))

    return result


def _merge_delta_run(run: list[SSEEvent]) -> SSEEvent:
    """Merge a non-empty run of homogeneous text-delta events."""
    if len(run) == 1:
        return run[0]

    first = run[0]
    # Concatenate the text from content[0].payload["content"] of each event
    parts: list[str] = []
    for ev in run:
        data = ev.data
        if not isinstance(data, SSEMessageData):  # guaranteed by caller; guard for safety
            continue
        for item in data.payload.content:
            parts.append(item.payload.get("content", ""))

    merged_content_items = copy.deepcopy(first.data.payload.content)  # type: ignore[union-attr]
    # Replace the first item's text with the concatenated text
    if merged_content_items:
        merged_content_items[0].payload["content"] = "".join(parts)
        # Keep only one content item for the merged event
        merged_content_items = merged_content_items[:1]

    merged_payload = copy.deepcopy(first.data.payload)  # type: ignore[union-attr]
    merged_payload.content = merged_content_items
    merged_data = SSEMessageData(type=first.data.type, payload=merged_payload)  # type: ignore[union-attr]

    return SSEEvent(
        id=first.id,
        event=first.event,
        data=merged_data,
        timestamp=first.timestamp,
    )


def _fill_database_context(
    agent_config: Optional[AgentConfig],
    catalog: Optional[str] = None,
    database: Optional[str] = None,
    schema: Optional[str] = None,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Resolve API database context without changing the active datasource."""
    config = None
    if agent_config is not None:
        try:
            config = agent_config.current_db_config()
        except Exception:
            config = None

    def first_string(*values):
        for value in values:
            if isinstance(value, str) and value:
                return value
        return None

    return (
        first_string(catalog, getattr(config, "catalog", None)),
        first_string(database, getattr(config, "database", None)),
        first_string(schema, getattr(config, "schema", None)),
    )


class ChatTask:
    """Represents a single running agentic loop."""

    def __init__(self, session_id: str, asyncio_task: asyncio.Task, owner_user_id: Optional[str] = None):
        self.session_id = session_id
        self.asyncio_task = asyncio_task
        self.owner_user_id = owner_user_id
        self.node: Optional[AgenticNode] = None
        self.events: list[SSEEvent] = []
        self.event_sizes: list[int] = []
        self.event_bytes: int = 0
        self.base_offset: int = 0
        self.status: str = "running"  # running | completed | error | cancelled
        self.condition = asyncio.Condition()
        self.created_at = datetime.now()
        self.completed_at: Optional[datetime] = None
        self.error: Optional[str] = None
        self.consumer_offset: int = 0
        self.admission_token = None
        self.run_id = uuid.uuid4().hex
        self.session_established = False
        self.terminal_event_persisted = False
        self.terminal_event_type: Optional[str] = None
        self.stop_requested = False


class ChatTaskManager:
    """Per-project manager for active chat tasks.

    Owned by DatusService — one instance per cached project.
    """

    def __init__(
        self,
        default_source: Optional[str] = None,
        default_interactive: bool = True,
        stream_thinking: bool = False,
        project_id: str = "default",
        session_owner_store: Optional["SessionOwnerStore"] = None,
        session_body_store: Optional["SessionBodyStore"] = None,
        artifact_acl_store: Optional["ArtifactAclStore"] = None,
        enterprise_enabled: bool = False,
        chat_admission: Optional["ChatAdmissionController"] = None,
        buffer_limits: Optional[ChatBufferLimits] = None,
    ) -> None:
        self._tasks: Dict[str, ChatTask] = {}
        self._completed_tasks: Dict[str, ChatTask] = {}
        self._discarded_task_ids: set[int] = set()
        self._default_source = default_source
        self._default_interactive = default_interactive
        self._stream_thinking = stream_thinking
        self._project_id = project_id
        self._session_owner_store = session_owner_store
        self._session_body_store = session_body_store
        self._artifact_acl_store = artifact_acl_store
        self._enterprise_enabled = enterprise_enabled
        self._chat_admission = chat_admission
        self._buffer_limits = buffer_limits or ChatBufferLimits()
        self._cleanup_handle: Optional[asyncio.TimerHandle] = None
        self._supports_artifact_edit_sessions = True
        self._supports_report_edit_sessions = True
        self._artifact_edit_sessions: Dict[str, ArtifactEditSession] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_report_edit_session(self, *, user_id: Optional[str], report_slug: str) -> ReportEditSession:
        """Register a process-local edit session locked to one report slug.

        Chat/SSE task state is already process-local in the current trial
        boundary. This registry follows the same sticky-session requirement
        instead of writing ephemeral agent definitions into shared config.
        """

        self._purge_expired_artifact_edit_sessions()
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
        self._artifact_edit_sessions[subagent_id] = session
        return session

    def get_report_edit_session(self, subagent_id: Optional[str]) -> Optional[ReportEditSession]:
        """Return a live report edit session by its chat subagent id."""

        session = self.get_artifact_edit_session(subagent_id)
        if isinstance(session, ReportEditSession):
            return session
        return None

    def create_dashboard_edit_session(self, *, user_id: Optional[str], dashboard_slug: str) -> DashboardEditSession:
        """Register a process-local edit session locked to one dashboard slug."""

        self._purge_expired_artifact_edit_sessions()
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
        self._artifact_edit_sessions[subagent_id] = session
        return session

    def get_artifact_edit_session(self, subagent_id: Optional[str]) -> Optional[ArtifactEditSession]:
        """Return a live report/dashboard edit session by its chat subagent id."""

        if not subagent_id:
            return None
        self._purge_expired_artifact_edit_sessions()
        return self._artifact_edit_sessions.get(subagent_id)

    def _purge_expired_artifact_edit_sessions(self) -> None:
        if not self._artifact_edit_sessions:
            return
        now = datetime.now(timezone.utc)
        expired: list[str] = []
        for subagent_id, session in self._artifact_edit_sessions.items():
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
            self._artifact_edit_sessions.pop(subagent_id, None)

    async def start_chat(
        self,
        agent_config: AgentConfig,
        request: StreamChatInput,
        sub_agent_id: Optional[str] = None,
        user_id: Optional[str] = None,
        principal: Optional[Dict[str, Any]] = None,
    ) -> ChatTask:
        """Create a background task for the agentic loop.
            :param sub_agent_id: builtin name or custom sub-agent DB ID
        Raises ``ValueError`` if a task is already running for the session.
        """
        # Clone config to avoid cross-request mutation of shared AgentConfig
        agent_config = copy.deepcopy(agent_config)
        if self._session_body_store is not None:
            agent_config._session_body_store = self._session_body_store
            agent_config._session_project_id = self._project_id
        agent_config.principal = dict(principal or {})
        agent_config._request_user_id = user_id
        agent_config._artifact_acl_store = self._artifact_acl_store
        agent_config._enterprise_enabled = self._enterprise_enabled
        agent_config._protect_artifact_filesystem = self._enterprise_enabled
        if self._enterprise_enabled and not user_id:
            raise ValueError("AUTH_REQUIRED")
        if self._enterprise_enabled:
            from datus_enterprise.workspace import prepare_user_workspace

            workspace_root = await asyncio.to_thread(prepare_user_workspace, agent_config, user_id or "")
            agent_config._request_workspace_root = str(workspace_root)
        # API surface has no interactive broker to confirm EXTERNAL file
        # access, so force filesystem strict mode — every node constructed
        # below reads this flag via AgenticNode._resolve_filesystem_strict().
        agent_config.filesystem_strict = True
        # Enterprise requests never receive a server-side BashTool: changing
        # cwd is not a filesystem sandbox. Remote front-ends (vscode/web) also
        # own their own shell and keep the same hardening in local mode.
        effective_source = request.source or self._default_source
        if self._enterprise_enabled or effective_source in ("vscode", "web"):
            agent_config.bash_tool_enabled = False
        # Stash the resolved source on the cloned config so downstream nodes
        # can adapt prompt-side hints to the front-end (e.g. vscode renders
        # the literal "." for the SQL files root because the IDE owns its own
        # workspace path).
        agent_config._client_source = effective_source
        # Per-request response language override. Empty / None keeps the
        # yaml-level ``agent.language`` default intact.
        if request.language:
            agent_config.language = request.language
        if request.model:
            provider, _, model_id = request.model.partition("/")
            if not model_id:
                raise ValueError(f"Invalid model format '{request.model}': expected 'provider/model_id'")
            if provider == "custom":
                agent_config.set_active_custom(model_id, persist=False)
            else:
                agent_config.set_active_provider_model(provider, model_id, persist=False)
        # Per-request datasource override (e.g. an IM channel pinned to a datasource).
        # Switches the connection profile; the setter validates it exists in config.
        if request.datasource:
            agent_config.current_datasource = request.datasource
        request.catalog, request.database, request.db_schema = _fill_database_context(
            agent_config,
            catalog=request.catalog,
            database=request.database,
            schema=request.db_schema,
        )
        agent_name = sub_agent_id or "chat"
        safe_name = agent_name.replace(" ", "_")
        session_id = request.session_id or f"{safe_name}_session_{str(uuid.uuid4())[:8]}"
        SessionManager._validate_session_id(session_id)
        request.session_id = session_id

        if session_id in self._tasks:
            raise ValueError(f"A task is already running for session {session_id}")

        admission_token = None
        if self._chat_admission is not None:
            admission_token = await self._chat_admission.acquire(project_id=self._project_id, user_id=user_id)
        if session_id in self._tasks:
            if self._chat_admission is not None:
                await self._chat_admission.release(admission_token)
            raise ValueError(f"A task is already running for session {session_id}")

        # Placeholder — asyncio_task set immediately after
        task = ChatTask(session_id=session_id, asyncio_task=None, owner_user_id=user_id)  # type: ignore[arg-type]
        task.admission_token = admission_token
        self._tasks[session_id] = task
        try:
            if user_id and self._session_owner_store is not None:
                await self._session_owner_store.set_owner(self._project_id, session_id, user_id)
        except Exception:
            self._tasks.pop(session_id, None)
            if self._chat_admission is not None:
                await self._chat_admission.release(admission_token)
            raise

        asyncio_task = asyncio.create_task(
            self._run_loop(
                task,
                agent_config,
                request,
                sub_agent_id=sub_agent_id,
                user_id=user_id,
            )
        )
        task.asyncio_task = asyncio_task
        return task

    async def stop_task(self, session_id: str) -> bool:
        """Stop a running task by interrupting its node."""
        task = self._tasks.get(session_id)
        if not task:
            return False
        task.stop_requested = True

        if task.node:
            try:
                task.node.interrupt_controller.interrupt()
                logger.info(f"Interrupted running task: {session_id}")
                if task.session_established:
                    try:
                        await asyncio.wait_for(
                            asyncio.shield(task.asyncio_task),
                            timeout=self._buffer_limits.stop_grace_seconds,
                        )
                    except asyncio.CancelledError:
                        if not task.asyncio_task.cancelled():
                            raise
                    except TimeoutError:
                        logger.warning(
                            "Chat task did not stop within %ss; cancelling task: %s",
                            self._buffer_limits.stop_grace_seconds,
                            session_id,
                        )
                        task.asyncio_task.cancel()
                        await asyncio.gather(task.asyncio_task, return_exceptions=True)
                    except Exception:
                        logger.debug("Stopped chat task finished with an error: %s", session_id, exc_info=True)
                    return True
            except Exception as e:
                logger.error(f"Failed to interrupt task {session_id}: {e}")

        # Before the session event is established there is no durable chat run
        # to interrupt gracefully. Cancellation here intentionally remains
        # process-local and does not create a terminal history event.
        if task.asyncio_task and not task.asyncio_task.done():
            task.asyncio_task.cancel()
            logger.info(f"Cancelled asyncio task: {session_id}")
            return True

        return False

    def has_active_tasks(self) -> bool:
        """Return True if any task is still running."""
        return any(t.status == "running" for t in self._tasks.values())

    def get_task(self, session_id: str) -> Optional[ChatTask]:
        return self._tasks.get(session_id) or self._completed_tasks.get(session_id)

    def get_task_snapshot(self, session_id: str) -> dict[str, Any] | None:
        """Return a bounded metadata snapshot for admin/session APIs."""

        task = self.get_task(session_id)
        return self._task_snapshot(task) if task is not None else None

    def list_task_snapshots(self) -> list[dict[str, Any]]:
        """Return bounded metadata snapshots for known in-process tasks."""

        snapshots = [self._task_snapshot(task) for task in self._tasks.values()]
        snapshots.extend(
            self._task_snapshot(task)
            for session_id, task in self._completed_tasks.items()
            if session_id not in self._tasks
        )
        return sorted(snapshots, key=lambda item: str(item.get("created_at") or ""), reverse=True)

    async def discard_task_snapshot(self, session_id: str, *, wait: bool = False, timeout: float = 5.0) -> bool:
        """Remove active/completed task metadata for a deleted session."""

        active_task = self._tasks.get(session_id)
        completed_task = self._completed_tasks.get(session_id)
        if active_task is not None:
            self._discarded_task_ids.add(id(active_task))
        had_task = active_task is not None or completed_task is not None

        if wait and active_task is not None and active_task.asyncio_task is not None:
            try:
                await asyncio.wait_for(active_task.asyncio_task, timeout=timeout)
            except asyncio.CancelledError:
                if not active_task.asyncio_task.cancelled():
                    raise
            except asyncio.TimeoutError:
                pass
            except Exception:
                logger.debug("Deleted session task finished with an error: %s", session_id, exc_info=True)

        if self._tasks.get(session_id) is active_task:
            self._tasks.pop(session_id, None)
        current_completed_task = self._completed_tasks.get(session_id)
        if current_completed_task is active_task or current_completed_task is completed_task:
            self._completed_tasks.pop(session_id, None)
        return had_task

    async def consume_events(self, task: ChatTask, start_from: Optional[int] = None) -> AsyncGenerator[SSEEvent, None]:
        """Yield events from *task*'s buffer.

        If *start_from* is ``None``, resume from the last recorded
        ``consumer_offset`` — but back up by one event so the client
        can safely re-process the last event it may not have fully handled.
        """
        if start_from is not None:
            cursor = start_from
        else:
            cursor = max(task.consumer_offset - 1, 0)

        while True:
            ping_event = None
            async with task.condition:
                if cursor < task.base_offset:
                    raise EventBufferExpiredError(
                        f"Requested event cursor {cursor} expired; earliest available cursor is {task.base_offset}."
                    )
                local_cursor = cursor - task.base_offset
                while local_cursor >= len(task.events) and task.status == "running":
                    try:
                        await asyncio.wait_for(task.condition.wait(), timeout=HEARTBEAT_INTERVAL)
                    except asyncio.TimeoutError:
                        local_cursor = cursor - task.base_offset
                        if local_cursor >= len(task.events) and task.status == "running":
                            ping_event = SSEEvent(
                                id=-1,
                                event="ping",
                                data=SSEPingData(),
                                timestamp=now_utc_iso(),
                            )
                            break  # exit inner loop so ping can be yielded
                    if cursor < task.base_offset:
                        raise EventBufferExpiredError(
                            f"Requested event cursor {cursor} expired; earliest available cursor is {task.base_offset}."
                        )
                    local_cursor = cursor - task.base_offset
                new_events = task.events[local_cursor:]
                is_done = task.status != "running"

            # Yield outside the lock to avoid blocking producers
            if ping_event is not None:
                yield ping_event

            coalesced = _coalesce_deltas(new_events)
            for event in coalesced:
                yield event
            cursor += len(new_events)
            task.consumer_offset = cursor

            if is_done and cursor >= task.base_offset + len(task.events):
                break

    async def wait_all_tasks(self) -> None:
        """Wait for all running tasks to finish without cancelling them."""
        pending = [t.asyncio_task for t in self._tasks.values() if t.asyncio_task and not t.asyncio_task.done()]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    async def shutdown(self) -> None:
        """Cancel every running task (called at application shutdown)."""
        for task in list(self._tasks.values()):
            if task.asyncio_task and not task.asyncio_task.done():
                task.asyncio_task.cancel()
        pending = [t.asyncio_task for t in self._tasks.values() if t.asyncio_task and not t.asyncio_task.done()]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        self._tasks.clear()
        self._completed_tasks.clear()
        if self._cleanup_handle is not None:
            self._cleanup_handle.cancel()
            self._cleanup_handle = None

    # ------------------------------------------------------------------
    # Background loop (full agentic loop implementation)
    # ------------------------------------------------------------------

    async def _persist_terminal_event(
        self,
        *,
        task: ChatTask,
        agent_config: AgentConfig,
        user_id: Optional[str],
        event_type: Literal["error", "cancelled", "timeout"],
        error: str,
        error_type: str,
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
        session_manager = SessionManager(
            session_dir=base_dir,
            scope=session_scope_from_user_id(user_id),
            agent_config=agent_config,
            project_id=self._project_id,
            body_store=self._session_body_store,
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

    @staticmethod
    def _terminal_outcome_from_action(
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

    async def _run_loop(
        self,
        task: ChatTask,
        agent_config: AgentConfig,
        request: StreamChatInput,
        sub_agent_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> None:
        """Execute the full agentic loop, pushing SSE events to the task buffer."""
        session_id = task.session_id
        event_id = 0
        trace_token = None

        # Pin the path manager into this task's context. Required when the caller
        # dispatched us from a thread that never inherited AgentConfig's ContextVar
        # (e.g. gateway bridge dispatching from an IM SDK worker thread via
        # ``asyncio.run_coroutine_threadsafe``); otherwise downstream stores fall
        # back to ``get_path_manager()`` and get an empty project_name.
        set_current_path_manager(agent_config.path_manager)

        try:
            start_time = datetime.now()

            # 1. Create node.
            #    Runs in thread pool because setup_tools() triggers synchronous
            #    operations (psycopg ConnectionPool creation, PG DDL for table
            #    creation via get_storage()) that would freeze the event loop.
            interactive_enabled = request.interactive if request.interactive is not None else self._default_interactive
            feedback_session_id: Optional[str] = None
            if sub_agent_id == "feedback" and request.source_session_id and self._session_body_store is not None:
                base_dir = getattr(agent_config, "session_dir", None) or str(
                    get_path_manager(agent_config=agent_config).sessions_dir
                )
                sm = SessionManager(
                    session_dir=base_dir,
                    scope=session_scope_from_user_id(user_id),
                    agent_config=agent_config,
                    project_id=self._project_id,
                    body_store=self._session_body_store,
                )
                feedback_session_id = await sm.copy_session_async(request.source_session_id, "feedback")

            def _init_node():
                # Feedback runs triggered with a source_session_id pre-copy the
                # source conversation into a fresh feedback session file BEFORE
                # node construction. The node then opens that cloned id directly
                # — no post-construction mutation needed.
                local_feedback_session_id = feedback_session_id
                if sub_agent_id == "feedback" and request.source_session_id and self._session_body_store is None:
                    base_dir = getattr(agent_config, "session_dir", None) or str(
                        get_path_manager(agent_config=agent_config).sessions_dir
                    )
                    sm = SessionManager(
                        session_dir=base_dir,
                        scope=session_scope_from_user_id(user_id),
                        agent_config=agent_config,
                        project_id=self._project_id,
                        body_store=self._session_body_store,
                    )
                    local_feedback_session_id = sm.copy_session(request.source_session_id, "feedback")

                return self._create_node(
                    agent_config,
                    subagent_id=sub_agent_id,
                    node_id=session_id,
                    user_id=user_id,
                    interactive=interactive_enabled,
                    session_id=local_feedback_session_id,
                )

            node = await asyncio.to_thread(_init_node)
            task.node = node
            trace_token = set_trace_context(
                build_chat_trace_context(
                    session_id=session_id,
                    llm_session_id=node.session_id,
                    node_name=node.get_node_name() if hasattr(node, "get_node_name") else None,
                    subagent_id=sub_agent_id,
                    user_id=user_id,
                    datasource=agent_config.current_datasource,
                    source_session_id=request.source_session_id,
                    source=request.source or self._default_source,
                    model=request.model,
                    agent_home=agent_config.home,
                )
            )

            # Per-request permission profile override. We deliberately do
            # NOT mutate ``agent_config.active_profile_name`` here because
            # the AgentConfig instance is shared across concurrent SaaS
            # users; rewriting it on one request would leak the new profile
            # to every other in-flight or future request. Instead we
            # switch the freshly created node's PermissionManager in
            # place — it is scoped to this request only.
            self._apply_permission_mode_override(node, agent_config, request.permission_mode)
            from datus.agent.tool_policy import apply_agent_runtime_policy

            apply_agent_runtime_policy(node)

            await self._push_event(
                task,
                SSEEvent(
                    id=event_id,
                    event="session",
                    data=SSESessionData(
                        session_id=session_id,
                        llm_session_id=node.session_id,
                    ),
                    timestamp=now_utc_iso(),
                ),
            )
            task.session_established = True
            event_id += 1
            event_id = await self._push_degraded_capability_warnings(task, node, event_id)

            # 3. Resolve @-references
            at_tables, at_metrics, at_sqls = self._resolve_at_context(
                agent_config, request.table_paths, request.metric_paths, request.sql_paths
            )

            # 4. Build typed input and assign to node
            node_input = self._create_node_input(
                user_message=request.message,
                current_node=node,
                at_tables=at_tables,
                at_metrics=at_metrics,
                at_sqls=at_sqls,
                catalog=request.catalog,
                database=request.database,
                db_schema=request.db_schema,
                plan_mode=request.plan_mode or False,
                source_session_id=request.source_session_id,
            )
            node.input = node_input

            # 5. Replace filesystem tools with proxy if applicable.
            # ``apply_proxy_tools`` consults ``_FS_DEPENDENT_NODES`` and the
            # node's ``tool_registry`` to leave filesystem tools un-proxied
            # for nodes that author server-side artifacts (e.g.
            # ``gen_visual_report`` writing ``render/*.jsx``). No isinstance
            # guard is needed here.
            effective_source = request.source or self._default_source
            if effective_source == "vscode":
                apply_proxy_tools(node, ["filesystem_tools.*"])
            elif effective_source == "web":
                apply_proxy_tools(node, ["write_file", "edit_file", "delete_file"])
            elif effective_source:
                logger.warning("Unsupported source '%s'; skipping proxy shortcut", effective_source)

            # 6. Execute streaming
            action_history = ActionHistoryManager()
            action_count = 0
            seen_delta_action_ids: set[str] = set()
            assistant_response_sent = False
            tool_result_seen = False
            seen_assistant_message_fingerprints: set[str] = set()

            async for action in node.execute_stream_with_interactions(action_history):
                action_count += 1

                # Convert action to SSE
                # Per-request stream_response overrides the server-level --stream flag
                effective_stream = (
                    request.stream_response if request.stream_response is not None else self._stream_thinking
                )

                is_first_delta = True
                if action.action_type in {"thinking_delta", "response_delta"}:
                    is_first_delta = action.action_id not in seen_delta_action_ids
                    seen_delta_action_ids.add(action.action_id)

                # finalize_progress actions reuse the same id across stages
                # so the SSE wire emits CREATE then UPDATE_MESSAGE; we mark
                # everything past the first emission as an update.
                is_finalize_progress_update = False
                if action.action_type == "finalize_progress":
                    is_finalize_progress_update = action.action_id in seen_delta_action_ids
                    seen_delta_action_ids.add(action.action_id)

                is_update = is_finalize_progress_update or (
                    effective_stream
                    and action.action_type in {"response", "thinking"}
                    and isinstance(action.output, dict)
                    and action.action_id in seen_delta_action_ids
                )

                sse = action_to_sse_event(
                    action,
                    event_id,
                    action.action_id,
                    stream_thinking=effective_stream,
                    is_first_delta=is_first_delta,
                    is_update=bool(is_update),
                    include_final_response=_should_include_final_response(action, assistant_response_sent),
                )
                terminal_outcome = self._terminal_outcome_from_action(action)
                if terminal_outcome is not None:
                    terminal_type, terminal_error, terminal_error_type = terminal_outcome
                    await self._persist_terminal_event(
                        task=task,
                        agent_config=agent_config,
                        user_id=user_id,
                        event_type=terminal_type,
                        error=terminal_error,
                        error_type=terminal_error_type,
                    )
                if sse:
                    # Per-LLM-call usage event: the converter has no access
                    # to the service-level session ids, so we stamp them
                    # here before fan-out. Skip the assistant-message dedup
                    # path entirely since usage carries no rendered text.
                    if sse.event == "usage" and isinstance(sse.data, SSEUsageData):
                        sse.data.session_id = session_id
                        # Only main-agent usage (depth==0) belongs to this
                        # node's LLM session. Sub-agent usage (depth>0) keeps the
                        # sub-agent session id stamped by the converter so the
                        # consumer can attribute it to the right session instead
                        # of mislabelling it as the parent's.
                        if sse.data.depth == 0:
                            sse.data.llm_session_id = node.session_id
                        await self._push_event(task, sse)
                        event_id += 1
                        continue
                    if _should_skip_duplicate_assistant_message(
                        action,
                        sse,
                        seen_assistant_message_fingerprints,
                    ):
                        continue
                    await self._push_event(task, sse)
                    event_id += 1
                    _remember_assistant_message(sse, seen_assistant_message_fingerprints)
                    if _is_visible_assistant_response(action, sse, tool_result_seen=tool_result_seen):
                        assistant_response_sent = True
                    if action.role == ActionRole.TOOL and action.status != ActionStatus.PROCESSING:
                        tool_result_seen = True

            # 7. End event
            token_kwargs: dict = {}
            try:
                turn_usage = await node.get_last_turn_usage()
                if turn_usage:
                    token_kwargs = {
                        "requests": turn_usage.requests,
                        "input_tokens": turn_usage.input_tokens,
                        "output_tokens": turn_usage.output_tokens,
                        "total_tokens": turn_usage.total_tokens,
                        "cached_tokens": turn_usage.cached_tokens,
                        "session_total_tokens": turn_usage.session_total_tokens,
                        "context_length": turn_usage.context_length,
                    }
            except Exception:
                logger.debug("Failed to extract turn token usage for end event", exc_info=True)

            await self._push_event(
                task,
                SSEEvent(
                    id=event_id,
                    event="end",
                    data=SSEEndData(
                        session_id=session_id,
                        llm_session_id=node.session_id,
                        total_events=event_id,
                        action_count=action_count,
                        duration=(datetime.now() - start_time).total_seconds(),
                        **token_kwargs,
                    ),
                    timestamp=now_utc_iso(),
                ),
            )
            event_id += 1

            if task.terminal_event_type == "cancelled":
                task.status = "cancelled"
            elif task.terminal_event_type in {"error", "timeout"}:
                task.status = "error"
            else:
                task.status = "completed"

        except asyncio.CancelledError:
            if task.stop_requested:
                await self._persist_terminal_event(
                    task=task,
                    agent_config=agent_config,
                    user_id=user_id,
                    event_type="cancelled",
                    error="Execution stopped by user",
                    error_type="CHAT_CANCELLED",
                )
            task.status = "cancelled"

        except Exception as e:
            logger.error(f"Chat task error for session {session_id}: {e}")
            task.status = "error"
            task.error = str(e)
            is_timeout = isinstance(e, TimeoutError)
            await self._persist_terminal_event(
                task=task,
                agent_config=agent_config,
                user_id=user_id,
                event_type="timeout" if is_timeout else "error",
                error=str(e),
                error_type="TIMEOUT" if is_timeout else type(e).__name__,
            )
            await self._push_event(
                task,
                SSEEvent(
                    id=event_id,
                    event="error",
                    data=SSEErrorData(
                        error=str(e),
                        error_type=type(e).__name__,
                        session_id=session_id,
                        llm_session_id=task.node.session_id if task.node else None,
                    ),
                    timestamp=now_utc_iso(),
                ),
            )
            event_id += 1

        finally:
            if trace_token is not None:
                reset_trace_context(trace_token)
            async with task.condition:
                task.condition.notify_all()
            task.completed_at = datetime.now()
            self._release_task_slot(session_id, task)
            if self._chat_admission is not None:
                await self._chat_admission.release(task.admission_token)

    async def _push_event(self, task: ChatTask, event: SSEEvent) -> None:
        """Append an event to the task buffer and notify consumers."""
        event_size = len(event.model_dump_json().encode("utf-8"))
        logger.debug("Pushing event id=%s type=%s bytes=%s", event.id, event.event, event_size)
        if event.event != "error" and event_size > self._buffer_limits.max_bytes:
            raise EventBufferOverflowError(
                f"Chat event exceeded the {self._buffer_limits.max_bytes}-byte buffer limit."
            )
        async with task.condition:
            task.events.append(event)
            task.event_sizes.append(event_size)
            task.event_bytes += event_size
            self._trim_event_buffer(task)
            task.condition.notify_all()

    def _trim_event_buffer(self, task: ChatTask) -> None:
        """Trim old events in batches while keeping absolute resume cursors stable."""

        limits = self._buffer_limits
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

    def _schedule_completed_cleanup(self) -> None:
        if self._cleanup_handle is not None and not self._cleanup_handle.cancelled():
            return
        loop = asyncio.get_running_loop()
        self._cleanup_handle = loop.call_later(
            self._buffer_limits.cleanup_interval_seconds,
            self._run_scheduled_cleanup,
        )

    def _run_scheduled_cleanup(self) -> None:
        self._cleanup_handle = None
        self._purge_expired_completed()
        if self._completed_tasks:
            self._schedule_completed_cleanup()

    def _purge_expired_completed(self) -> None:
        """Remove completed tasks after their configured resume TTL."""
        now = datetime.now()
        expired = [
            sid
            for sid, t in self._completed_tasks.items()
            if (now - (t.completed_at or t.created_at)).total_seconds() > self._buffer_limits.completed_ttl_seconds
        ]
        for sid in expired:
            self._completed_tasks.pop(sid, None)

    def _release_task_slot(self, session_id: str, task: ChatTask) -> None:
        """Release task tracking only when this task still owns the slot."""

        owns_active_slot = self._tasks.get(session_id) is task
        if owns_active_slot:
            self._tasks.pop(session_id, None)

        task_was_discarded = id(task) in self._discarded_task_ids
        if task_was_discarded:
            self._discarded_task_ids.discard(id(task))
            if self._completed_tasks.get(session_id) is task:
                self._completed_tasks.pop(session_id, None)
            return

        if owns_active_slot:
            # Keep completed task for resume within TTL.
            task.node = None
            self._completed_tasks[session_id] = task
            self._purge_expired_completed()
            self._schedule_completed_cleanup()

    def _task_snapshot(self, task: ChatTask) -> dict[str, Any]:
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

    # ------------------------------------------------------------------
    # Node factory
    # ------------------------------------------------------------------

    def _create_node(
        self,
        agent_config: AgentConfig,
        subagent_id: Optional[str],
        node_id: str,
        user_id: Optional[str] = None,
        interactive: bool = True,
        session_id: Optional[str] = None,
    ) -> AgenticNode:
        """Create a fresh AgenticNode based on subagent_id (builtin name or custom DB ID).

        Delegates dispatch to :func:`datus.agent.node.node_factory.create_interactive_node`
        so the API path matches the CLI exactly: every built-in sub_agent is wired to
        its dedicated AgenticNode subclass, and custom sub_agents honour their
        ``node_class`` field (``gen_report`` / ``gen_table`` / ``gen_dashboard`` /
        ``scheduler`` / ``gen_skill`` / ``explore``) instead of always falling back
        to ``GenSQLAgenticNode``.

        ``user_id`` is propagated as the node ``scope`` so that session files
        are isolated per user under ``{session_dir}/{user_id}/``. ``session_id``
        becomes the on-disk session identifier (defaults to ``node_id``); the
        feedback flow passes a pre-copied id so the new node opens the cloned
        session file directly instead of mutating ``node.session_id`` later.
        """
        from datus.agent.node.node_factory import create_interactive_node

        execution_mode: Literal["interactive", "workflow"] = "interactive" if interactive else "workflow"

        # ``agentic_nodes`` is keyed by sanitized node_name; the API receives the
        # custom sub_agent's UUID under the "id" field. Translate UUID -> name so
        # the factory's ``_resolve_node_class_type`` can look up node_class and
        # downstream tools can resolve scoped_context via sub_agent_config().
        node_name = subagent_id
        if subagent_id:
            for key, entry in (agent_config.agentic_nodes or {}).items():
                entry_id = entry.get("id") if isinstance(entry, dict) else getattr(entry, "id", None)
                if entry_id == subagent_id:
                    node_name = key
                    break

        return create_interactive_node(
            subagent_name=node_name,
            agent_config=agent_config,
            scope=session_scope_from_user_id(user_id),
            execution_mode=execution_mode,
            node_id=node_id,
            session_id=session_id if session_id is not None else node_id,
        )

    # ------------------------------------------------------------------
    # Per-request permission profile override
    # ------------------------------------------------------------------

    def _apply_permission_mode_override(
        self,
        node: AgenticNode,
        agent_config: AgentConfig,
        permission_mode: Optional[str],
    ) -> None:
        """Apply a per-request permission profile to the freshly created node.

        Switches ``node.permission_manager`` to ``permission_mode`` without
        touching ``agent_config.active_profile_name`` — the AgentConfig is
        shared by every concurrent request in the SaaS deployment, so
        mutating it would leak the override across users. The CLI's
        ``/profile`` flow can still mutate the global field because it
        owns the process exclusively; this API path cannot.

        No-ops when ``permission_mode`` is falsy, the node has no
        ``permission_manager`` (e.g. workflow nodes that skip the skill
        setup), or the requested profile already matches the active one.
        Failure handling is split deliberately:

        * Building ``user_overrides`` from ``agent.yml`` fails closed —
          raises so the outer ``_run_loop`` aborts the turn and emits an
          SSE error. Silently dropping malformed user rules would apply
          the bare profile base, which can be **broader** than the
          operator-configured posture (e.g. yaml had an explicit DENY
          we'd lose), so the safe move is to refuse the switch loudly.
        * ``switch_profile`` failures (unknown profile, malformed merge
          result) are logged and swallowed because at that point the
          node still has its original, server-default profile installed.
        """
        permission_manager = getattr(node, "permission_manager", None)
        if permission_manager is None:
            return
        if not permission_mode:
            return
        target_mode = permission_mode
        if getattr(permission_manager, "active_profile", None) == target_mode:
            return

        from datus.tools.permission.profiles import build_user_overrides

        raw_permissions = getattr(agent_config, "_raw_permissions", {}) or {}
        raw_user = {k: v for k, v in raw_permissions.items() if k != "profile"}
        try:
            user_overrides = build_user_overrides(target_mode, raw_user)
        except Exception as exc:
            logger.error(
                "Cannot build user overrides for permission_mode=%r from agent.yml: %s; "
                "refusing to switch profile to avoid broadening permissions beyond the "
                "operator-configured rules",
                target_mode,
                exc,
                exc_info=True,
            )
            raise RuntimeError(
                f"Failed to apply permission_mode={target_mode!r}: agent.yml permissions.rules is malformed ({exc})"
            ) from exc

        try:
            permission_manager.switch_profile(target_mode, user_overrides=user_overrides)
        except Exception as e:
            logger.error(
                "Failed to switch permission profile to %r for session=%s: %s",
                target_mode,
                getattr(node, "session_id", None),
                e,
            )
            return

        logger.info(
            "Applied per-request permission profile %r for session=%s",
            target_mode,
            getattr(node, "session_id", None),
        )

    # ------------------------------------------------------------------
    # Node input factory
    # ------------------------------------------------------------------

    def _create_node_input(
        self,
        user_message: str,
        current_node: AgenticNode,
        at_tables: List[TableSchema],
        at_metrics: List[Metric],
        at_sqls: List[ReferenceSql],
        catalog: Optional[str] = None,
        database: Optional[str] = None,
        db_schema: Optional[str] = None,
        plan_mode: bool = False,
        source_session_id: Optional[str] = None,
    ):
        """Create node input based on node type.

        Delegates to :func:`datus.agent.node.node_factory.create_node_input` so
        the API path covers every AgenticNode subclass the CLI knows about
        (GenReport / Explore / SkillCreator / GenTable / GenJob in addition to
        the GenSQL / Semantic / SqlSummary / Feedback / Chat branches).
        """
        from datus.agent.node.node_factory import create_node_input

        node_agent_config = getattr(current_node, "agent_config", None)
        if not isinstance(node_agent_config, AgentConfig):
            node_agent_config = None
        catalog, database, db_schema = _fill_database_context(
            node_agent_config,
            catalog=catalog,
            database=database,
            schema=db_schema,
        )

        return create_node_input(
            user_message=user_message,
            node=current_node,
            catalog=catalog,
            database=database,
            db_schema=db_schema,
            at_tables=at_tables,
            at_metrics=at_metrics,
            at_sqls=at_sqls,
            prompt_language="en",
            plan_mode=plan_mode,
            source_session_id=source_session_id,
        )

    # ------------------------------------------------------------------
    # @ reference resolution
    # ------------------------------------------------------------------

    async def _push_degraded_capability_warnings(self, task: ChatTask, node: AgenticNode, event_id: int) -> int:
        degraded = getattr(node, "degraded_capabilities", {}) or {}
        warnings = list(dict.fromkeys(str(message) for message in degraded.values() if str(message).strip()))
        if not warnings:
            return event_id

        await self._push_event(
            task,
            SSEEvent(
                id=event_id,
                event="message",
                data=SSEMessageData(
                    type=SSEDataType.CREATE_MESSAGE,
                    payload=SSEMessagePayload(
                        message_id=f"capability-degraded-{uuid.uuid4().hex[:8]}",
                        role="assistant",
                        content=[
                            IMessageContent(
                                type="markdown",
                                payload={"content": "\n\n".join(warnings)},
                            )
                        ],
                    ),
                ),
                timestamp=now_utc_iso(),
            ),
        )
        return event_id + 1

    def _resolve_at_context(
        self,
        agent_config: AgentConfig,
        table_paths: Optional[List[str]],
        metric_paths: Optional[List[str]],
        sql_paths: Optional[List[str]],
    ) -> tuple[List[TableSchema], List[Metric], List[ReferenceSql]]:
        """Resolve @-reference paths to typed objects using a fresh completer."""
        try:
            completer = AtReferenceCompleter(agent_config)
            completer.reload_data()
        except Exception as exc:
            logger.warning("Failed to resolve @ references; continuing without context references: %s", exc)
            return [], [], []

        tables: List[TableSchema] = []
        for path in table_paths or []:
            try:
                entry = completer.table_completer.flatten_data.get(path)
                if entry:
                    tables.append(TableSchema.from_dict(entry))
            except Exception as e:
                logger.warning(f"Failed to resolve table path '{path}': {e}")

        metrics: List[Metric] = []
        for path in metric_paths or []:
            try:
                entry = completer.metric_completer.flatten_data.get(path)
                if entry:
                    metrics.append(Metric.from_dict(entry))
            except Exception as e:
                logger.warning(f"Failed to resolve metric path '{path}': {e}")

        sqls: List[ReferenceSql] = []
        for path in sql_paths or []:
            try:
                entry = completer.sql_completer.flatten_data.get(path)
                if entry:
                    sqls.append(ReferenceSql.from_dict(entry))
            except Exception as e:
                logger.warning(f"Failed to resolve sql path '{path}': {e}")

        return tables, metrics, sqls
