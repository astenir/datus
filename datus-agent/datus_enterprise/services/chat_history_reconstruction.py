"""Canonical enterprise Chat history reconstruction."""

import asyncio
import json
import os
import uuid
from typing import Any, Dict, List, Optional

from datus.agent.node.mcp_failure_actions_downstream import is_mcp_connection_tool_name
from datus.api.models.base_models import Result
from datus.api.models.cli_models import (
    AtContextData,
    ChatHistoryData,
    IMessageContent,
    SSEMessagePayload,
)
from datus.api.models.downstream import (
    ChatSessionSubagentEvent,
    ChatSessionTerminalEvent,
    ChatSessionToolExecutionEvent,
)
from datus.api.services.action_sse_converter import action_to_history_sse_event
from datus.api.services.chat_task_manager import (
    _is_visible_assistant_response,
    _remember_assistant_message,
    _should_include_final_response,
    _should_skip_duplicate_assistant_message,
)
from datus.cli.manual_exec import exec_to_markdown
from datus.models.session_manager import (
    SessionManager,
    session_scope_from_user_id,
)
from datus.schemas.action_history import ActionHistory, ActionRole, ActionStatus
from datus.utils.loggings import get_logger
from datus.utils.time_utils import now_utc_iso, to_utc_iso

logger = get_logger(__name__)


class EnterpriseChatHistoryMixin:
    async def get_history_async(self, session_id: str, user_id: Optional[str] = None) -> Result[ChatHistoryData]:
        """Get chat history without using sync async bridges for async body stores."""
        if self._session_body_store is None:
            return await asyncio.to_thread(self.get_history, session_id, user_id=user_id)

        try:
            raw_messages = await self._session_body_store.get_session_messages(
                project_id=self._project_id,
                scope=session_scope_from_user_id(user_id),
                session_id=session_id,
            )
            raw_messages = SessionManager._message_rows_to_raw_messages(raw_messages)
            try:
                terminal_rows = await self._session_body_store.get_session_terminal_events(
                    project_id=self._project_id,
                    scope=session_scope_from_user_id(user_id),
                    session_id=session_id,
                )
                terminal_events = SessionManager._validate_terminal_events(terminal_rows, session_id=session_id)
                subagent_events = SessionManager._validate_subagent_events(terminal_rows, session_id=session_id)
                tool_execution_events = SessionManager._validate_tool_execution_events(
                    terminal_rows, session_id=session_id
                )
            except Exception:
                logger.warning("Failed to load display sidecar events for session %s", session_id, exc_info=True)
                terminal_events = []
                subagent_events = []
                tool_execution_events = []
            history_messages = self._with_subagent_anchors(raw_messages, subagent_events)
            subagent_messages = await self._load_nested_subagent_messages_async(
                session_id,
                user_id,
                history_messages,
                subagent_events=subagent_events,
            )
            return self._history_result_from_raw_messages(
                session_id,
                history_messages,
                terminal_events=terminal_events,
                subagent_messages=subagent_messages,
                tool_execution_events=tool_execution_events,
            )
        except Exception as e:
            logger.error(f"Failed to get history for session {session_id}: {e}")
            return Result[ChatHistoryData](
                success=False,
                errorCode="SESSION_HISTORY_ERROR",
                errorMessage=f"Failed to get session history: {str(e)}",
            )

    def _history_result_from_session_manager(
        self,
        session_id: str,
        raw_messages: List[Dict[str, Any]],
        session_manager: SessionManager,
    ) -> Result[ChatHistoryData]:
        try:
            terminal_events = session_manager.get_terminal_events(session_id)
        except Exception:
            logger.warning("Failed to load terminal events for session %s", session_id, exc_info=True)
            terminal_events = []
        try:
            subagent_events = session_manager.get_subagent_events(session_id)
        except Exception:
            logger.warning("Failed to load sub-agent events for session %s", session_id, exc_info=True)
            subagent_events = []
        try:
            tool_execution_events = session_manager.get_tool_execution_events(session_id)
        except Exception:
            logger.warning("Failed to load tool execution events for session %s", session_id, exc_info=True)
            tool_execution_events = []
        history_messages = self._with_subagent_anchors(raw_messages, subagent_events)
        subagent_messages = self._load_nested_subagent_messages(
            session_id,
            history_messages,
            session_manager=session_manager,
            subagent_events=subagent_events,
        )
        return self._history_result_from_raw_messages(
            session_id,
            history_messages,
            terminal_events=terminal_events,
            subagent_messages=subagent_messages,
            tool_execution_events=tool_execution_events,
        )

    def _history_result_from_raw_messages(
        self,
        session_id: str,
        raw_messages: List[Dict[str, Any]],
        *,
        terminal_events: Optional[List[ChatSessionTerminalEvent]] = None,
        subagent_messages: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        tool_execution_events: Optional[List[ChatSessionToolExecutionEvent]] = None,
    ) -> Result[ChatHistoryData]:
        top_level_mcp_failures = self._mcp_connection_failure_events(
            tool_execution_events or [], depth=0, parent_action_id=None
        )
        if not raw_messages and not terminal_events and not top_level_mcp_failures:
            return Result[ChatHistoryData](success=True, data=ChatHistoryData())

        logger.info(f"Retrieved {len(raw_messages)} messages for session {session_id}")
        display_messages = self._with_terminal_event_markers(raw_messages, terminal_events or [])
        sse_messages, _ = self._history_payloads_from_raw_messages(
            display_messages,
            subagent_messages=subagent_messages,
            tool_execution_events={event.call_tool_id: event for event in tool_execution_events or []},
        )
        logger.info(f"Retrieved {len(sse_messages)} messages for session {session_id}")
        return Result[ChatHistoryData](success=True, data=ChatHistoryData(messages=sse_messages))

    def _history_payloads_from_raw_messages(
        self,
        raw_messages: List[Dict[str, Any]],
        *,
        event_id: int = 0,
        depth: int = 0,
        parent_action_id: Optional[str] = None,
        subagent_messages: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        tool_execution_events: Optional[Dict[str, ChatSessionToolExecutionEvent]] = None,
    ) -> tuple[List[SSEMessagePayload], int]:
        display_messages = self._with_mcp_connection_failure_actions(
            raw_messages,
            list((tool_execution_events or {}).values()),
            depth=depth,
            parent_action_id=parent_action_id,
        )
        sse_messages: List[SSEMessagePayload] = []
        task_completions = {
            action.action_id.removeprefix("complete_"): action
            for msg in display_messages
            for action in msg.get("actions", [])
            if action.role == ActionRole.TOOL
            and action.action_type == "task"
            and action.status != ActionStatus.PROCESSING
        }

        for msg in display_messages:
            terminal_event = msg.get("_terminal_event")
            if isinstance(terminal_event, ChatSessionTerminalEvent):
                sse_messages.append(
                    SSEMessagePayload(
                        message_id=terminal_event.event_id,
                        role="system",
                        content=[
                            IMessageContent(
                                type="error",
                                payload={
                                    "error": terminal_event.error,
                                    "error_type": terminal_event.error_type,
                                    "event_type": terminal_event.event_type,
                                    "created_at": terminal_event.created_at,
                                },
                            )
                        ],
                        depth=depth,
                        parent_action_id=parent_action_id,
                    )
                )
                event_id += 1
                continue

            role = msg.get("role", "")
            if role == "user":
                content = msg.get("content", "")
                if content:
                    content = exec_to_markdown(content)
                    at_context_raw = msg.get("at_context")
                    at_context = None
                    if isinstance(at_context_raw, dict):
                        at_context = AtContextData(
                            table_paths=at_context_raw.get("table_paths") or [],
                            metric_paths=at_context_raw.get("metric_paths") or [],
                            sql_paths=at_context_raw.get("sql_paths") or [],
                            knowledge_paths=at_context_raw.get("knowledge_paths") or [],
                        )
                    sse_messages.append(
                        SSEMessagePayload(
                            message_id=str(uuid.uuid4()),
                            role="user",
                            content=[IMessageContent(type="markdown", payload={"content": content})],
                            depth=depth,
                            parent_action_id=parent_action_id,
                            at_context=at_context,
                        )
                    )
                    event_id += 1
            elif role == "assistant":
                if "actions" in msg:
                    messages = msg["actions"]
                    assistant_response_seen = False
                    tool_result_seen = False
                    seen_assistant_message_fingerprints: set[str] = set()
                    for action in messages:
                        include_final_response = _should_include_final_response(action, assistant_response_seen)
                        sse_event = action_to_history_sse_event(
                            action,
                            event_id,
                            action.action_id,
                            include_user_message=True,
                            include_final_response=include_final_response,
                        )
                        if sse_event:
                            if _should_skip_duplicate_assistant_message(
                                action,
                                sse_event,
                                seen_assistant_message_fingerprints,
                            ):
                                continue
                            payload = sse_event.data.payload
                            if action.role == ActionRole.TOOL and action.status != ActionStatus.PROCESSING:
                                call_tool_id = action.action_id.removeprefix("complete_")
                                timing = (tool_execution_events or {}).get(call_tool_id)
                                if timing is not None:
                                    for content in payload.content:
                                        if content.type == "call-tool-result":
                                            content.payload["duration"] = timing.duration
                            if parent_action_id is not None:
                                payload.depth = depth
                                payload.parent_action_id = parent_action_id
                            sse_messages.append(payload)
                            event_id += 1
                            _remember_assistant_message(sse_event, seen_assistant_message_fingerprints)
                            if _is_visible_assistant_response(action, sse_event, tool_result_seen=tool_result_seen):
                                assistant_response_seen = True
                            if action.role == ActionRole.TOOL and action.status != ActionStatus.PROCESSING:
                                tool_result_seen = True
                        if (
                            action.role == ActionRole.TOOL
                            and action.action_type == "task"
                            and action.status == ActionStatus.PROCESSING
                        ):
                            child_raw_messages = (subagent_messages or {}).get(action.action_id)
                            if child_raw_messages is not None:
                                child_payloads, event_id = self._history_payloads_from_raw_messages(
                                    child_raw_messages,
                                    event_id=event_id,
                                    depth=1,
                                    parent_action_id=action.action_id,
                                    tool_execution_events=tool_execution_events,
                                )
                                sse_messages.extend(child_payloads)
                                completion = task_completions.get(action.action_id)
                                if completion is not None:
                                    task_timing = (tool_execution_events or {}).get(action.action_id)
                                    sse_messages.append(
                                        self._subagent_completion_history_payload(
                                            action,
                                            completion,
                                            child_raw_messages,
                                            duration=task_timing.duration if task_timing is not None else None,
                                        )
                                    )
                                    event_id += 1
                elif msg.get("content"):
                    sse_messages.append(
                        SSEMessagePayload(
                            message_id=str(uuid.uuid4()),
                            role="assistant",
                            content=[IMessageContent(type="markdown", payload={"content": msg["content"]})],
                            depth=depth,
                            parent_action_id=parent_action_id,
                        )
                    )
                    event_id += 1

        return sse_messages, event_id

    @staticmethod
    def _mcp_connection_failure_events(
        tool_execution_events: List[ChatSessionToolExecutionEvent],
        *,
        depth: int,
        parent_action_id: Optional[str],
    ) -> List[ChatSessionToolExecutionEvent]:
        return [
            event
            for event in tool_execution_events
            if is_mcp_connection_tool_name(event.tool_name)
            and bool(event.error)
            and event.depth == depth
            and (event.parent_action_id or None) == (parent_action_id or None)
        ]

    @classmethod
    def _with_mcp_connection_failure_actions(
        cls,
        raw_messages: List[Dict[str, Any]],
        tool_execution_events: List[ChatSessionToolExecutionEvent],
        *,
        depth: int,
        parent_action_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Restore MCP connection failures that never entered SDK history."""
        missing_events = cls._mcp_connection_failure_events(
            tool_execution_events,
            depth=depth,
            parent_action_id=parent_action_id,
        )
        if not missing_events:
            return raw_messages

        canonical_action_ids = {
            action.action_id
            for message in raw_messages
            for action in message.get("actions", [])
            if getattr(action, "action_id", None)
        }
        messages = list(raw_messages)

        for event in sorted(
            missing_events,
            key=lambda item: (to_utc_iso(item.created_at) or item.created_at, item.event_id),
        ):
            call_tool_id = event.call_tool_id.removeprefix("complete_")
            if call_tool_id in canonical_action_ids or f"complete_{call_tool_id}" in canonical_action_ids:
                continue

            tool_name = event.tool_name
            if not is_mcp_connection_tool_name(tool_name):
                continue
            server_name = tool_name[len("mcp.") : -len(".connect")]
            created_at = to_utc_iso(event.created_at) or now_utc_iso()
            started_at = to_utc_iso(event.started_at) or created_at
            completed_at = to_utc_iso(event.completed_at) or started_at
            input_data = {
                "function_name": tool_name,
                "arguments": {},
                "server_name": server_name,
            }
            start_action = ActionHistory(
                action_id=call_tool_id,
                role=ActionRole.TOOL,
                messages=f"Tool call: {tool_name}",
                action_type=tool_name,
                input=input_data,
                output=None,
                status=ActionStatus.PROCESSING,
                start_time=started_at,
                depth=event.depth,
                parent_action_id=event.parent_action_id,
            )
            result_action = ActionHistory(
                action_id=f"complete_{call_tool_id}",
                role=ActionRole.TOOL,
                messages=f"Tool result: {tool_name}",
                action_type=tool_name,
                input=input_data,
                output={
                    "error": event.error,
                    "summary": event.summary
                    or f"MCP Server '{server_name}' connection failed; the Agent continued without it.",
                },
                status=ActionStatus.FAILED,
                start_time=started_at,
                end_time=completed_at,
                depth=event.depth,
                parent_action_id=event.parent_action_id,
            )
            synthetic_message = {
                "role": "assistant",
                "content": "",
                "timestamp": created_at,
                "created_at": created_at,
                "actions": [start_action, result_action],
            }

            preceding_user_indexes = [
                index
                for index, message in enumerate(messages)
                if message.get("role") == "user"
                and (
                    not created_at
                    or not (message_time := to_utc_iso(message.get("created_at") or message.get("timestamp")))
                    or message_time <= created_at
                )
            ]
            if not preceding_user_indexes:
                preceding_user_indexes = [
                    index for index, message in enumerate(messages) if message.get("role") == "user"
                ]
            insertion_index = preceding_user_indexes[-1] + 1 if preceding_user_indexes else len(messages)
            while insertion_index < len(messages):
                message = messages[insertion_index]
                message_time = to_utc_iso(message.get("created_at") or message.get("timestamp"))
                if message.get("role") == "assistant" and (
                    not created_at or not message_time or message_time <= created_at
                ):
                    insertion_index += 1
                    continue
                break
            messages.insert(insertion_index, synthetic_message)
            canonical_action_ids.update({call_tool_id, f"complete_{call_tool_id}"})

        return messages

    @staticmethod
    def _subagent_completion_history_payload(
        task_action: ActionHistory,
        completion_action: ActionHistory,
        child_raw_messages: List[Dict[str, Any]],
        *,
        duration: Optional[float] = None,
    ) -> SSEMessagePayload:
        arguments = task_action.input.get("arguments", {}) if isinstance(task_action.input, dict) else {}
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {}
        subagent_type = arguments.get("type", "unknown") if isinstance(arguments, dict) else "unknown"
        tool_count = sum(
            1
            for msg in child_raw_messages
            for action in msg.get("actions", [])
            if action.role == ActionRole.TOOL and action.status == ActionStatus.PROCESSING
        )
        payload: Dict[str, Any] = {
            "subagentType": subagent_type,
            "toolCount": tool_count,
        }
        if duration is not None:
            payload["duration"] = duration
        output = completion_action.output if isinstance(completion_action.output, dict) else {}
        if output.get("success") in (0, False) and output.get("error"):
            payload["error"] = output["error"]

        return SSEMessagePayload(
            message_id=str(uuid.uuid4()),
            role="assistant",
            content=[IMessageContent(type="subagent-complete", payload=payload)],
            depth=1,
            parent_action_id=task_action.action_id,
        )

    @staticmethod
    def _with_terminal_event_markers(
        raw_messages: List[Dict[str, Any]],
        terminal_events: List[ChatSessionTerminalEvent],
    ) -> List[Dict[str, Any]]:
        """Place display-only terminal outcomes before later conversation turns."""
        if not terminal_events:
            return raw_messages

        messages = list(raw_messages)
        ordered_events = sorted(
            terminal_events,
            key=lambda event: (to_utc_iso(event.created_at) or event.created_at, event.event_id),
        )
        for event in ordered_events:
            event_time = to_utc_iso(event.created_at)
            insertion_index = len(messages)
            if event_time:
                for index, message in enumerate(messages):
                    message_time = to_utc_iso(message.get("created_at") or message.get("timestamp"))
                    if message_time and message_time > event_time:
                        insertion_index = index
                        break
            messages.insert(
                insertion_index,
                {
                    "role": "system",
                    "timestamp": event.created_at,
                    "created_at": event.created_at,
                    "_terminal_event": event,
                },
            )

        return messages

    @staticmethod
    def _with_subagent_anchors(
        raw_messages: List[Dict[str, Any]],
        subagent_events: List[ChatSessionSubagentEvent],
    ) -> List[Dict[str, Any]]:
        """Add display-only task calls that never reached canonical SDK history."""
        canonical_task_ids = {
            action.action_id
            for msg in raw_messages
            for action in msg.get("actions", [])
            if action.role == ActionRole.TOOL
            and action.action_type == "task"
            and action.status == ActionStatus.PROCESSING
        }
        missing_events = [event for event in subagent_events if event.parent_action_id not in canonical_task_ids]
        if not missing_events:
            return raw_messages

        messages = list(raw_messages)
        for event in sorted(missing_events, key=lambda item: item.created_at):
            task_action = ActionHistory(
                action_id=event.parent_action_id,
                role=ActionRole.TOOL,
                messages="Tool call: task",
                action_type="task",
                input={
                    "function_name": "task",
                    "arguments": json.dumps(event.arguments, ensure_ascii=False),
                },
                output=None,
                status=ActionStatus.PROCESSING,
                start_time=event.created_at,
            )
            synthetic_message = {
                "role": "assistant",
                "content": "",
                "timestamp": event.created_at,
                "created_at": event.created_at,
                "actions": [task_action],
            }
            preceding_user_indexes = [
                index
                for index, message in enumerate(messages)
                if message.get("role") == "user"
                and str(message.get("created_at") or message.get("timestamp") or "") <= event.created_at
            ]
            if not preceding_user_indexes:
                preceding_user_indexes = [
                    index for index, message in enumerate(messages) if message.get("role") == "user"
                ]
            insertion_index = preceding_user_indexes[-1] + 1 if preceding_user_indexes else len(messages)
            while (
                insertion_index < len(messages)
                and messages[insertion_index].get("role") == "assistant"
                and str(messages[insertion_index].get("created_at") or messages[insertion_index].get("timestamp") or "")
                <= event.created_at
            ):
                insertion_index += 1
            messages.insert(insertion_index, synthetic_message)

        return messages

    @staticmethod
    def _task_subagent_session_ids(
        raw_messages: List[Dict[str, Any]],
        subagent_events: Optional[List[ChatSessionSubagentEvent]] = None,
    ) -> Dict[str, str]:
        processing_task_ids: set[str] = set()
        completed_tasks = []
        for msg in raw_messages:
            for action in msg.get("actions", []):
                if action.role != ActionRole.TOOL or action.action_type != "task":
                    continue
                if action.status == ActionStatus.PROCESSING:
                    processing_task_ids.add(action.action_id)
                    continue
                completed_tasks.append(action)

        session_ids: Dict[str, str] = {}
        for event in subagent_events or []:
            try:
                session_ids[event.parent_action_id] = SessionManager._validate_session_id(event.child_session_id)
            except ValueError:
                logger.warning(
                    "Ignoring invalid nested sub-agent session id for task %s",
                    event.parent_action_id,
                )
        for action in completed_tasks:
            call_id = action.action_id.removeprefix("complete_")
            if call_id not in processing_task_ids or not isinstance(action.output, dict):
                continue
            result = action.output.get("result")
            candidate = action.output.get("session_id")
            if not candidate and isinstance(result, dict):
                candidate = result.get("session_id")
            if not isinstance(candidate, str) or not candidate:
                continue
            try:
                session_ids[call_id] = SessionManager._validate_session_id(candidate)
            except ValueError:
                logger.warning("Ignoring invalid nested sub-agent session id for task %s", call_id)
        return session_ids

    def _load_nested_subagent_messages(
        self,
        parent_session_id: str,
        raw_messages: List[Dict[str, Any]],
        *,
        session_manager: SessionManager,
        subagent_events: Optional[List[ChatSessionSubagentEvent]] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        task_session_ids = self._task_subagent_session_ids(raw_messages, subagent_events)
        if not task_session_ids:
            return {}

        SessionManager._validate_session_id(parent_session_id)
        child_cache: Dict[str, List[Dict[str, Any]]] = {}
        messages_by_call_id: Dict[str, List[Dict[str, Any]]] = {}
        for call_id, child_session_id in task_session_ids.items():
            try:
                if child_session_id not in child_cache:
                    nested_dirs = [os.path.join(session_manager.session_dir, parent_session_id)]
                    legacy_nested_dir = os.path.join(self._session_dir, parent_session_id)
                    if legacy_nested_dir not in nested_dirs:
                        nested_dirs.append(legacy_nested_dir)
                    child_messages: List[Dict[str, Any]] = []
                    for nested_dir in nested_dirs:
                        child_manager = SessionManager(session_dir=nested_dir)
                        child_messages = child_manager.get_session_messages(child_session_id)
                        if child_messages:
                            break
                    child_cache[child_session_id] = child_messages
                messages_by_call_id[call_id] = child_cache[child_session_id]
            except Exception:
                logger.warning(
                    "Failed to load nested sub-agent history for parent %s task %s",
                    parent_session_id,
                    call_id,
                    exc_info=True,
                )
        return messages_by_call_id

    async def _load_nested_subagent_messages_async(
        self,
        parent_session_id: str,
        user_id: Optional[str],
        raw_messages: List[Dict[str, Any]],
        *,
        subagent_events: Optional[List[ChatSessionSubagentEvent]] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        task_session_ids = self._task_subagent_session_ids(raw_messages, subagent_events)
        if not task_session_ids or self._session_body_store is None:
            return {}

        SessionManager._validate_session_id(parent_session_id)
        user_scope = session_scope_from_user_id(user_id)
        parent_scope = session_scope_from_user_id(parent_session_id)
        nested_scope = "__".join(part for part in (user_scope, parent_scope) if part)
        candidate_scopes = [nested_scope or None]
        legacy_scope = parent_scope or None
        if legacy_scope not in candidate_scopes:
            candidate_scopes.append(legacy_scope)
        child_cache: Dict[str, List[Dict[str, Any]]] = {}
        messages_by_call_id: Dict[str, List[Dict[str, Any]]] = {}
        for call_id, child_session_id in task_session_ids.items():
            try:
                if child_session_id not in child_cache:
                    message_rows = []
                    for child_scope in candidate_scopes:
                        message_rows = await self._session_body_store.get_session_messages(
                            project_id=self._project_id,
                            scope=child_scope,
                            session_id=child_session_id,
                        )
                        if message_rows:
                            break
                    child_cache[child_session_id] = SessionManager._message_rows_to_raw_messages(message_rows)
                messages_by_call_id[call_id] = child_cache[child_session_id]
            except Exception:
                logger.warning(
                    "Failed to load nested sub-agent history for parent %s task %s",
                    parent_session_id,
                    call_id,
                    exc_info=True,
                )
        return messages_by_call_id
