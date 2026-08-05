"""Trusted Success Story source resolution from canonical Chat history."""

import asyncio
import json
from typing import Any, Dict, List, Optional

from datus.api.models.downstream import (
    SuccessStorySource,
)
from datus.models.session_manager import (
    SessionManager,
    extract_agent_from_session_id,
    session_scope_from_user_id,
)
from datus.schemas.action_history import ActionHistory, ActionRole, ActionStatus
from datus.utils.loggings import get_logger
from datus.utils.sql_utils import looks_like_sql_file_ref, read_workspace_sql_file

logger = get_logger(__name__)


class SuccessStorySourceError(ValueError):
    """Stable source-resolution failure surfaced by the success-story route."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class EnterpriseSuccessStorySourceMixin:
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
                elif (
                    action.action_id in {f"complete_{call_tool_id}", call_tool_id}
                    and action.status != ActionStatus.PROCESSING
                ):
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
