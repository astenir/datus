"""
Stateless chat service — thin proxy over ChatTaskManager.

Each request assembles configuration and delegates to ChatTaskManager
for the actual agentic loop execution. Session management methods
read from disk each time (no in-memory state).
"""

import asyncio
import copy
import json
import os
import uuid
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, List, Optional

from datus.agent.node.chat_agentic_node import ChatAgenticNode
from datus.api.models.base_models import Result
from datus.api.models.cli_models import (
    ChatHistoryData,
    ChatSessionData,
    ChatSessionItemInfo,
    ChatSessionSubagentEvent,
    ChatSessionTerminalEvent,
    CompactSessionData,
    CompactSessionInput,
    IMessageContent,
    SSEErrorData,
    SSEEvent,
    SSEMessagePayload,
    StreamChatInput,
)
from datus.api.models.success_story_models import SuccessStorySource
from datus.api.services.action_sse_converter import action_to_history_sse_event
from datus.api.services.chat_admission import ChatCapacityError
from datus.api.services.chat_task_manager import (
    _is_visible_assistant_response,
    _remember_assistant_message,
    _should_include_final_response,
    _should_skip_duplicate_assistant_message,
)
from datus.configuration.agent_config import AgentConfig
from datus.models.session_manager import (
    SessionManager,
    extract_agent_from_session_id,
    session_matches_agent,
    session_scope_from_user_id,
)
from datus.schemas.action_history import ActionHistory, ActionRole, ActionStatus
from datus.utils.exceptions import DatusException, ErrorCode
from datus.utils.loggings import get_logger
from datus.utils.sql_utils import looks_like_sql_file_ref, read_workspace_sql_file
from datus.utils.time_utils import now_utc_iso

logger = get_logger(__name__)


class SuccessStorySourceError(ValueError):
    """Stable source-resolution failure surfaced by the success-story route."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code

if TYPE_CHECKING:
    from datus.api.enterprise.protocols import SessionBodyStore


class ChatService:
    """Thin service that delegates chat execution to ChatTaskManager.

    Owned by DatusService. Session management methods read from disk.
    """

    def __init__(
        self,
        agent_config: AgentConfig,
        task_manager=None,
        project_id: Optional[str] = None,
        session_body_store: Optional["SessionBodyStore"] = None,
    ) -> None:
        self.agent_config = agent_config
        self._task_manager = task_manager
        self._project_id = project_id or getattr(agent_config, "_session_project_id", None) or "default"
        self._session_body_store = session_body_store

        # Session directory: {home}/sessions — must match agent's path_manager.sessions_dir
        self._session_dir = self.agent_config.session_dir

    # ------------------------------------------------------------------
    # Streaming chat (thin proxy)
    # ------------------------------------------------------------------

    async def stream_chat(
        self,
        request: StreamChatInput,
        sub_agent_id: Optional[str] = None,
        user_id: Optional[str] = None,
        principal: Optional[Dict[str, Any]] = None,
        agent_config: Optional[AgentConfig] = None,
    ) -> AsyncGenerator[SSEEvent, None]:
        """Start a background chat task and yield SSE events."""
        task_manager = self._task_manager
        active_config = agent_config or self.agent_config
        try:
            task = await task_manager.start_chat(
                active_config,
                request,
                sub_agent_id=sub_agent_id,
                user_id=user_id,
                principal=principal,
            )
        except ChatCapacityError as e:
            yield SSEEvent(
                id=1,
                event="error",
                data=SSEErrorData(error=str(e), error_type="CHAT_CAPACITY_EXCEEDED", session_id=request.session_id),
                timestamp=now_utc_iso(),
            )
            return
        except (ValueError, DatusException) as e:
            error_code = e.code.name if isinstance(e, DatusException) else ErrorCode.COMMON_VALIDATION_FAILED.name
            yield SSEEvent(
                id=1,
                event="error",
                data=SSEErrorData(error=str(e), error_type=error_code, session_id=request.session_id),
                timestamp=now_utc_iso(),
            )
            return
        except Exception as e:
            logger.error("Failed to start chat stream for session %s: %s", request.session_id, e, exc_info=True)
            yield SSEEvent(
                id=1,
                event="error",
                data=SSEErrorData(error=str(e), error_type="CHAT_START_FAILED", session_id=request.session_id),
                timestamp=now_utc_iso(),
            )
            return
        async for event in task_manager.consume_events(task):
            yield event

    # ------------------------------------------------------------------
    # Session management (stateless — reads from disk each time)
    # ------------------------------------------------------------------

    def session_exists(self, session_id: str, user_id: Optional[str] = None) -> bool:
        """Check if a session exists on disk."""
        session_mgr = self._session_manager(user_id)
        return session_mgr.session_exists(session_id)

    async def session_exists_async(self, session_id: str, user_id: Optional[str] = None) -> bool:
        """Check if a session exists without crossing event loops for async body stores."""
        if self._session_body_store is None:
            return await asyncio.to_thread(self.session_exists, session_id, user_id=user_id)

        scope = session_scope_from_user_id(user_id)
        return bool(
            await self._session_body_store.session_exists(
                project_id=self._project_id,
                scope=scope,
                session_id=session_id,
            )
        )

    def list_sessions(
        self,
        user_id: Optional[str] = None,
        subagent_id: Optional[str] = None,
    ) -> Result[ChatSessionData]:
        """List chat sessions from disk, optionally filtered by agent.

        When ``subagent_id`` is ``None`` every session for *user_id* is
        returned. When set, only sessions whose id prefix encodes that agent
        are returned; the sentinel ``"chat"`` selects the default chat agent
        (including legacy prefix-less sessions).
        """
        try:
            session_mgr = self._session_manager(user_id)
            all_ids = session_mgr.list_sessions()
            if subagent_id is not None:
                all_ids = [sid for sid in all_ids if session_matches_agent(sid, subagent_id)]
            sessions = []

            for sid in all_ids:
                try:
                    info = session_mgr.get_session_info(sid)
                    if not info.get("exists", False):
                        continue
                    created_at = info.get("created_at") or ""
                    last_updated = info.get("updated_at") or info.get("file_modified_iso") or created_at
                    sessions.append(
                        ChatSessionItemInfo(
                            user_query=info.get("first_user_message"),
                            session_id=sid,
                            created_at=created_at,
                            last_updated=last_updated,
                            total_turns=info.get("message_count", 0),
                            token_count=info.get("total_tokens", 0),
                            last_sql_queries=[],
                            is_active=False,
                        )
                    )
                except Exception as e:
                    logger.warning(f"Failed to read session {sid}: {e}")

            sessions.sort(key=lambda x: x.last_updated or x.created_at, reverse=True)
            return Result[ChatSessionData](
                success=True,
                data=ChatSessionData(
                    sessions=sessions,
                    total_count=len(sessions),
                ),
            )

        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            return Result[ChatSessionData](success=False, errorCode="SESSION_LIST_ERROR", errorMessage=str(e))

    async def list_sessions_async(
        self,
        user_id: Optional[str] = None,
        subagent_id: Optional[str] = None,
    ) -> Result[ChatSessionData]:
        """List chat sessions without using sync async bridges for async body stores."""
        if self._session_body_store is None:
            return await asyncio.to_thread(self.list_sessions, user_id=user_id, subagent_id=subagent_id)

        scope = session_scope_from_user_id(user_id)
        try:
            all_ids = await self._session_body_store.list_session_ids(
                project_id=self._project_id,
                scope=scope,
            )
            if subagent_id is not None:
                all_ids = [sid for sid in all_ids if session_matches_agent(sid, subagent_id)]

            sessions = []
            for sid in all_ids:
                try:
                    info = await self._session_body_store.get_session_info(
                        project_id=self._project_id,
                        scope=scope,
                        session_id=sid,
                    )
                    if not info.get("exists", False):
                        continue
                    created_at = info.get("created_at") or ""
                    last_updated = info.get("updated_at") or info.get("file_modified_iso") or created_at
                    sessions.append(
                        ChatSessionItemInfo(
                            user_query=info.get("first_user_message"),
                            session_id=sid,
                            created_at=created_at,
                            last_updated=last_updated,
                            total_turns=info.get("message_count", 0),
                            token_count=info.get("total_tokens", 0),
                            last_sql_queries=[],
                            is_active=False,
                        )
                    )
                except Exception as e:
                    logger.warning(f"Failed to read session {sid}: {e}")

            sessions.sort(key=lambda x: x.last_updated or x.created_at, reverse=True)
            return Result[ChatSessionData](
                success=True,
                data=ChatSessionData(
                    sessions=sessions,
                    total_count=len(sessions),
                ),
            )
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            return Result[ChatSessionData](success=False, errorCode="SESSION_LIST_ERROR", errorMessage=str(e))

    def delete_session(self, session_id: str, user_id: Optional[str] = None) -> Result[ChatSessionData]:
        """Delete a session from disk."""
        try:
            session_mgr = self._session_manager(user_id)
            if session_mgr.session_exists(session_id):
                session_mgr.delete_session(session_id)

            return Result[ChatSessionData](
                success=True,
                data=ChatSessionData(
                    session_id=session_id,
                    created_at="",
                    last_updated=now_utc_iso(),
                    total_turns=0,
                    token_count=0,
                    last_sql_queries=[],
                    is_active=False,
                ),
            )
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return Result[ChatSessionData](success=False, errorCode="SESSION_DELETE_ERROR", errorMessage=str(e))

    async def delete_session_async(self, session_id: str, user_id: Optional[str] = None) -> Result[ChatSessionData]:
        """Delete a session without using sync async bridges for async body stores."""
        if self._session_body_store is None:
            return await asyncio.to_thread(self.delete_session, session_id, user_id=user_id)

        try:
            scope = session_scope_from_user_id(user_id)
            if await self._session_body_store.session_exists(
                project_id=self._project_id,
                scope=scope,
                session_id=session_id,
            ):
                await self._session_body_store.delete_session(
                    project_id=self._project_id,
                    scope=scope,
                    session_id=session_id,
                )

            return Result[ChatSessionData](
                success=True,
                data=ChatSessionData(
                    session_id=session_id,
                    created_at="",
                    last_updated=now_utc_iso(),
                    total_turns=0,
                    token_count=0,
                    last_sql_queries=[],
                    is_active=False,
                ),
            )
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return Result[ChatSessionData](success=False, errorCode="SESSION_DELETE_ERROR", errorMessage=str(e))

    def get_session_info(self, session_id: str, user_id: Optional[str] = None) -> Result[Dict[str, Any]]:
        """Get scoped metadata for a chat session."""
        try:
            session_mgr = self._session_manager(user_id)
            return Result[Dict[str, Any]](success=True, data=session_mgr.get_session_info(session_id))
        except Exception as e:
            logger.error(f"Failed to get session info for {session_id}: {e}")
            return Result[Dict[str, Any]](success=False, errorCode="SESSION_INFO_ERROR", errorMessage=str(e))

    async def compact_session(
        self, request: CompactSessionInput, user_id: Optional[str] = None
    ) -> Result[CompactSessionData]:
        """Compact a session by loading it into a temporary node and running compaction."""
        session_id = request.session_id
        try:
            # Create a temporary ChatAgenticNode to load the session
            node = ChatAgenticNode(
                node_id=session_id,
                description="Temporary node for compaction",
                node_type="chat",
                input_data=None,
                agent_config=self._agent_config_for_session_body_store(),
                tools=None,
                scope=session_scope_from_user_id(user_id),
                session_id=session_id,
            )

            # Load the existing SQLite session so _session is populated
            node._get_or_create_session()

            old_tokens = await node._count_session_tokens()
            # The public ``compact`` API replaces the legacy ``_manual_compact``
            # entrypoint. Pass ``mode="major"`` because the API surface is the
            # equivalent of an explicit ``/compact`` invocation — it always
            # wants the LLM summarization path, never the rule-based minor
            # archive pass (which runs autonomously inside the agent loop).
            result = await node.compact(mode="major", reason="api_request")

            if not result.get("success", False):
                return Result[CompactSessionData](
                    success=True,
                    data=CompactSessionData(session_id=session_id, success=False, error="Compact failed"),
                )

            summary_token = result.get("summary_token") or 0
            if not summary_token:
                # major-compact payload now reports ``summary`` / ``history_jsonl``
                # and may omit ``summary_token`` when the upstream LLM does not
                # surface ``output_tokens``. Fall back to a 4-char-per-token
                # estimate over the summary text so the metrics remain
                # directionally correct instead of silently zeroing out.
                summary_text = result.get("summary") or ""
                summary_token = max(len(summary_text) // 4, 0)
            return Result[CompactSessionData](
                success=True,
                data=CompactSessionData(
                    session_id=session_id,
                    success=True,
                    new_token_count=summary_token,
                    tokens_saved=old_tokens - summary_token,
                    compression_ratio=str(summary_token / old_tokens if old_tokens > 0 else 0),
                ),
            )

        except Exception as e:
            logger.error(f"Failed to compact session {session_id}: {e}")
            return Result[CompactSessionData](success=False, errorCode="SESSION_COMPACT_ERROR", errorMessage=str(e))

    def get_history(self, session_id: str, user_id: Optional[str] = None) -> Result[ChatHistoryData]:
        """Get chat history messages for a session."""
        try:
            # Use SessionManager to get messages from SQLite
            session_manager = self._session_manager(user_id)
            raw_messages = session_manager.get_session_messages(session_id)
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
            )

        except Exception as e:
            logger.error(f"Failed to get history for session {session_id}: {e}")
            return Result[ChatHistoryData](
                success=False,
                errorCode="SESSION_HISTORY_ERROR",
                errorMessage=f"Failed to get session history: {str(e)}",
            )

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
            except Exception:
                logger.warning("Failed to load display sidecar events for session %s", session_id, exc_info=True)
                terminal_events = []
                subagent_events = []
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
            )
        except Exception as e:
            logger.error(f"Failed to get history for session {session_id}: {e}")
            return Result[ChatHistoryData](
                success=False,
                errorCode="SESSION_HISTORY_ERROR",
                errorMessage=f"Failed to get session history: {str(e)}",
            )

    async def resolve_success_story_source_async(
        self,
        session_id: str,
        call_tool_id: str,
        *,
        user_id: Optional[str] = None,
        session_link: Optional[str] = None,
    ) -> SuccessStorySource:
        """Resolve a trusted successful SQL call from root or nested history."""
        try:
            raw_messages, subagent_messages, child_session_ids = await self._load_success_story_history_async(
                session_id,
                user_id=user_id,
            )
        except Exception as exc:
            logger.warning("Failed to load success-story source history for %s", session_id, exc_info=True)
            raise SuccessStorySourceError(
                "SUCCESS_STORY_SOURCE_NOT_FOUND",
                "The SQL execution could not be found in this session.",
            ) from exc

        root_match = self._find_success_story_action(raw_messages, call_tool_id)
        if root_match is not None:
            question, start_action, completion_action = root_match
            return self._success_story_source_from_actions(
                session_id=session_id,
                call_tool_id=call_tool_id,
                question=question,
                subagent_name=extract_agent_from_session_id(session_id),
                start_action=start_action,
                completion_action=completion_action,
                session_link=session_link,
            )

        root_questions = self._root_questions_by_task(raw_messages)
        for parent_call_id, child_messages in subagent_messages.items():
            nested_match = self._find_success_story_action(child_messages, call_tool_id)
            if nested_match is None:
                continue
            _, start_action, completion_action = nested_match
            child_session_id = child_session_ids.get(parent_call_id, "")
            return self._success_story_source_from_actions(
                session_id=session_id,
                call_tool_id=call_tool_id,
                question=root_questions.get(parent_call_id, ""),
                subagent_name=extract_agent_from_session_id(child_session_id),
                start_action=start_action,
                completion_action=completion_action,
                session_link=session_link,
            )

        raise SuccessStorySourceError(
            "SUCCESS_STORY_SOURCE_NOT_FOUND",
            "The SQL execution could not be found in this session.",
        )

    async def _load_success_story_history_async(
        self,
        session_id: str,
        *,
        user_id: Optional[str],
    ) -> tuple[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]], Dict[str, str]]:
        if self._session_body_store is None:
            return await asyncio.to_thread(self._load_success_story_history, session_id, user_id=user_id)

        raw_rows = await self._session_body_store.get_session_messages(
            project_id=self._project_id,
            scope=session_scope_from_user_id(user_id),
            session_id=session_id,
        )
        raw_messages = SessionManager._message_rows_to_raw_messages(raw_rows)
        try:
            terminal_rows = await self._session_body_store.get_session_terminal_events(
                project_id=self._project_id,
                scope=session_scope_from_user_id(user_id),
                session_id=session_id,
            )
            subagent_events = SessionManager._validate_subagent_events(terminal_rows, session_id=session_id)
        except Exception:
            logger.warning("Failed to load sub-agent sidecars for session %s", session_id, exc_info=True)
            subagent_events = []
        history_messages = self._with_subagent_anchors(raw_messages, subagent_events)
        child_session_ids = self._task_subagent_session_ids(history_messages, subagent_events)
        subagent_messages = await self._load_nested_subagent_messages_async(
            session_id,
            user_id,
            history_messages,
            subagent_events=subagent_events,
        )
        return history_messages, subagent_messages, child_session_ids

    def _load_success_story_history(
        self,
        session_id: str,
        *,
        user_id: Optional[str],
    ) -> tuple[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]], Dict[str, str]]:
        session_manager = self._session_manager(user_id)
        raw_messages = session_manager.get_session_messages(session_id)
        try:
            subagent_events = session_manager.get_subagent_events(session_id)
        except Exception:
            logger.warning("Failed to load sub-agent sidecars for session %s", session_id, exc_info=True)
            subagent_events = []
        history_messages = self._with_subagent_anchors(raw_messages, subagent_events)
        child_session_ids = self._task_subagent_session_ids(history_messages, subagent_events)
        subagent_messages = self._load_nested_subagent_messages(
            session_id,
            history_messages,
            session_manager=session_manager,
            subagent_events=subagent_events,
        )
        return history_messages, subagent_messages, child_session_ids

    @classmethod
    def _find_success_story_action(
        cls,
        raw_messages: List[Dict[str, Any]],
        call_tool_id: str,
    ) -> Optional[tuple[str, ActionHistory, Optional[ActionHistory]]]:
        latest_question = ""
        start_action: Optional[ActionHistory] = None
        start_question = ""
        completion_action: Optional[ActionHistory] = None
        for message in raw_messages:
            if message.get("role") == "user":
                latest_question = cls._message_text(message.get("content"))
                continue
            for action in message.get("actions", []):
                if action.role != ActionRole.TOOL:
                    continue
                if action.action_id == call_tool_id and action.status == ActionStatus.PROCESSING:
                    start_action = action
                    start_question = latest_question
                elif action.action_id in {f"complete_{call_tool_id}", call_tool_id} and action.status != ActionStatus.PROCESSING:
                    completion_action = action

        if start_action is None:
            return None
        return start_question, start_action, completion_action

    @classmethod
    def _root_questions_by_task(cls, raw_messages: List[Dict[str, Any]]) -> Dict[str, str]:
        latest_question = ""
        questions: Dict[str, str] = {}
        for message in raw_messages:
            if message.get("role") == "user":
                latest_question = cls._message_text(message.get("content"))
                continue
            for action in message.get("actions", []):
                if (
                    action.role == ActionRole.TOOL
                    and action.action_type == "task"
                    and action.status == ActionStatus.PROCESSING
                ):
                    questions[action.action_id] = latest_question
        return questions

    def _success_story_source_from_actions(
        self,
        *,
        session_id: str,
        call_tool_id: str,
        question: str,
        subagent_name: str,
        start_action: ActionHistory,
        completion_action: Optional[ActionHistory],
        session_link: Optional[str],
    ) -> SuccessStorySource:
        function_name, arguments = self._action_function(start_action)
        if not self._is_sql_execution_tool(function_name):
            raise SuccessStorySourceError(
                "SUCCESS_STORY_SOURCE_NOT_FOUND",
                "The selected tool call is not a SQL execution.",
            )
        if completion_action is None or not self._tool_completion_succeeded(completion_action):
            raise SuccessStorySourceError(
                "SUCCESS_STORY_NOT_SUCCESSFUL",
                "Only a successfully completed SQL execution can be saved.",
            )

        sql = arguments.get("sql")
        if not isinstance(sql, str) or not sql.strip():
            _, completion_arguments = self._action_function(completion_action)
            sql = completion_arguments.get("sql")
        if not isinstance(sql, str) or not sql.strip():
            raise SuccessStorySourceError(
                "SUCCESS_STORY_SOURCE_NOT_FOUND",
                "The executed SQL could not be recovered from session history.",
            )
        sql = sql.strip()
        if looks_like_sql_file_ref(sql):
            try:
                sql = read_workspace_sql_file(sql, self.agent_config.project_root).strip()
            except (OSError, ValueError) as exc:
                raise SuccessStorySourceError(
                    "SUCCESS_STORY_SOURCE_NOT_FOUND",
                    "The executed SQL file is no longer available.",
                ) from exc

        datasource_id = self._success_story_datasource_from_actions(start_action, completion_action)

        if not question.strip():
            raise SuccessStorySourceError(
                "SUCCESS_STORY_SOURCE_NOT_FOUND",
                "The source question could not be recovered from session history.",
            )
        return SuccessStorySource(
            session_id=session_id,
            call_tool_id=call_tool_id,
            question=question.strip(),
            sql=sql,
            datasource_id=datasource_id,
            subagent_name=subagent_name or "chat",
            session_link=session_link,
        )

    @classmethod
    def _success_story_datasource_from_actions(
        cls,
        start_action: ActionHistory,
        completion_action: ActionHistory,
    ) -> str:
        datasource_ids = set()
        for action in (start_action, completion_action):
            _, arguments = cls._action_function(action)
            for key in ("datasource", "datasource_id", "datasource_name"):
                value = arguments.get(key)
                if isinstance(value, str) and value.strip():
                    datasource_ids.add(value.strip())

        if not datasource_ids:
            raise SuccessStorySourceError(
                "SUCCESS_STORY_DATASOURCE_NOT_FOUND",
                "The datasource used by this SQL execution could not be recovered from session history.",
            )
        if len(datasource_ids) > 1:
            raise SuccessStorySourceError(
                "SUCCESS_STORY_DATASOURCE_CONFLICT",
                "The SQL execution contains conflicting datasource identifiers.",
            )
        return datasource_ids.pop()

    @staticmethod
    def _action_function(action: ActionHistory) -> tuple[str, Dict[str, Any]]:
        if not isinstance(action.input, dict):
            return "", {}
        function_name = str(action.input.get("function_name") or action.action_type or "")
        arguments = action.input.get("arguments", {})
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except (TypeError, ValueError):
                arguments = {}
        return function_name, arguments if isinstance(arguments, dict) else {}

    @staticmethod
    def _is_sql_execution_tool(function_name: str) -> bool:
        normalized = function_name.strip().lower()
        return normalized in {"execute_sql", "read_query"} or normalized.endswith((".execute_sql", ".read_query"))

    @staticmethod
    def _tool_completion_succeeded(action: ActionHistory) -> bool:
        if action.status != ActionStatus.SUCCESS:
            return False
        candidates = [action.output]
        if isinstance(action.output, dict):
            candidates.append(action.output.get("raw_output"))
        for candidate in candidates:
            if isinstance(candidate, str):
                try:
                    candidate = json.loads(candidate)
                except (TypeError, ValueError):
                    continue
            if not isinstance(candidate, dict):
                continue
            if candidate.get("success") in (0, False) or candidate.get("error"):
                return False
        return True

    @staticmethod
    def _message_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            return ""
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)

    def _history_result_from_raw_messages(
        self,
        session_id: str,
        raw_messages: List[Dict[str, Any]],
        *,
        terminal_events: Optional[List[ChatSessionTerminalEvent]] = None,
        subagent_messages: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    ) -> Result[ChatHistoryData]:
        if not raw_messages and not terminal_events:
            return Result[ChatHistoryData](success=True, data=ChatHistoryData())

        logger.info(f"Retrieved {len(raw_messages)} messages for session {session_id}")
        sse_messages, _ = self._history_payloads_from_raw_messages(
            raw_messages,
            subagent_messages=subagent_messages,
        )

        for terminal_event in terminal_events or []:
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
                )
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
    ) -> tuple[List[SSEMessagePayload], int]:
        sse_messages: List[SSEMessagePayload] = []
        task_completions = {
            action.action_id.removeprefix("complete_"): action
            for msg in raw_messages
            for action in msg.get("actions", [])
            if action.role == ActionRole.TOOL
            and action.action_type == "task"
            and action.status != ActionStatus.PROCESSING
        }

        for msg in raw_messages:
            role = msg.get("role", "")
            if role == "user":
                content = msg.get("content", "")
                if content:
                    sse_messages.append(
                        SSEMessagePayload(
                            message_id=str(uuid.uuid4()),
                            role="user",
                            content=[IMessageContent(type="markdown", payload={"content": content})],
                            depth=depth,
                            parent_action_id=parent_action_id,
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
                                )
                                sse_messages.extend(child_payloads)
                                completion = task_completions.get(action.action_id)
                                if completion is not None:
                                    sse_messages.append(
                                        self._subagent_completion_history_payload(
                                            action,
                                            completion,
                                            child_raw_messages,
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
    def _subagent_completion_history_payload(
        task_action: ActionHistory,
        completion_action: ActionHistory,
        child_raw_messages: List[Dict[str, Any]],
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
        duration = 0.0
        if task_action.start_time and completion_action.end_time:
            duration = (completion_action.end_time - task_action.start_time).total_seconds()

        payload: Dict[str, Any] = {
            "subagentType": subagent_type,
            "toolCount": tool_count,
            "duration": duration,
        }
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

    def _session_manager(self, user_id: Optional[str]) -> SessionManager:
        scope = session_scope_from_user_id(user_id)
        if self._session_body_store is None:
            return SessionManager(session_dir=self._session_dir, scope=scope)

        return SessionManager(
            session_dir=self._session_dir,
            scope=scope,
            agent_config=self.agent_config,
            project_id=self._project_id,
            body_store=self._session_body_store,
        )

    def _agent_config_for_session_body_store(self) -> AgentConfig:
        if self._session_body_store is None:
            return self.agent_config

        agent_config = copy.copy(self.agent_config)
        agent_config._session_body_store = self._session_body_store
        agent_config._session_project_id = self._project_id
        return agent_config
