"""Tests for datus.api.services.chat_service — chat session management."""

import asyncio
import json
import os
import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from datus.api.models.cli_models import ChatSessionSubagentEvent, ChatSessionTerminalEvent
from datus.api.services.chat_admission import ChatCapacityError
from datus.api.services.chat_service import ChatService
from datus.api.services.chat_task_manager import ChatTaskManager
from datus.models.session_manager import SessionManager


@pytest.fixture
def chat_svc(real_agent_config):
    """Create ChatService with real config for reuse."""
    return ChatService(
        agent_config=real_agent_config,
        task_manager=ChatTaskManager(),
        project_id="test-proj",
    )


class TestChatServiceInit:
    """Tests for ChatService initialization."""

    def test_init_with_real_config(self, chat_svc, real_agent_config):
        """ChatService initializes with real agent config and task manager."""
        assert chat_svc.agent_config is real_agent_config
        assert isinstance(chat_svc._task_manager, ChatTaskManager)

    def test_init_stores_properties(self, real_agent_config):
        """ChatService stores agent_config and task_manager."""
        tm = ChatTaskManager()
        svc = ChatService(agent_config=real_agent_config, task_manager=tm, project_id="p1")
        assert svc.agent_config is real_agent_config
        assert svc._task_manager is tm

    def test_init_sets_session_dir(self, chat_svc, real_agent_config):
        """ChatService sets _session_dir from agent_config."""
        assert chat_svc._session_dir == real_agent_config.session_dir


class TestChatServiceSessionExists:
    """Tests for session_exists."""

    def test_nonexistent_session_returns_false(self, chat_svc):
        """session_exists returns False for unknown session."""
        assert chat_svc.session_exists("nonexistent-session-id") is False

    def test_session_check_uses_session_manager(self, chat_svc):
        """session_exists delegates to SessionManager.session_exists."""
        # Multiple non-existent calls should all return False
        assert chat_svc.session_exists("fake-a") is False
        assert chat_svc.session_exists("fake-b") is False


class TestChatServiceListSessions:
    """Tests for list_sessions."""

    def test_list_sessions_empty(self, chat_svc):
        """list_sessions returns empty list when no sessions exist."""
        result = chat_svc.list_sessions()
        assert result.success is True
        assert result.data.sessions == []

    def test_list_sessions_returns_total_count(self, chat_svc):
        """list_sessions data includes total_count field."""
        result = chat_svc.list_sessions()
        assert result.data.total_count == 0

    def test_list_sessions_with_created_session(self, chat_svc):
        """list_sessions detects a session created via SessionManager."""
        sm = SessionManager(session_dir=chat_svc._session_dir)
        session = sm.create_session("test-list-session")
        asyncio.run(session.add_items([{"role": "user", "content": "Hello"}]))

        result = chat_svc.list_sessions()
        assert result.success is True
        assert result.data.total_count >= 1
        session_ids = [s.session_id for s in result.data.sessions]
        assert "test-list-session" in session_ids

    def test_list_sessions_filters_by_subagent_id(self, chat_svc):
        """subagent_id='gen_metrics' keeps only sessions whose prefix matches."""
        sm = SessionManager(session_dir=chat_svc._session_dir)
        sm.create_session("chat_session_a")
        sm.create_session("gen_metrics_session_a")
        sm.create_session("gen_metrics_session_b")

        result = chat_svc.list_sessions(subagent_id="gen_metrics")
        assert result.success is True
        session_ids = {s.session_id for s in result.data.sessions}
        assert session_ids == {"gen_metrics_session_a", "gen_metrics_session_b"}

    def test_list_sessions_filter_chat_includes_legacy(self, chat_svc):
        """subagent_id='chat' returns chat-prefixed and legacy (no-prefix) ids, but not subagents."""
        sm = SessionManager(session_dir=chat_svc._session_dir)
        sm.create_session("chat_session_a")
        sm.create_session("legacy-id-1")
        sm.create_session("gen_metrics_session_a")

        result = chat_svc.list_sessions(subagent_id="chat")
        assert result.success is True
        session_ids = {s.session_id for s in result.data.sessions}
        assert session_ids == {"chat_session_a", "legacy-id-1"}

    def test_list_sessions_no_filter_returns_all(self, chat_svc):
        """subagent_id=None returns sessions for every agent."""
        sm = SessionManager(session_dir=chat_svc._session_dir)
        sm.create_session("chat_session_a")
        sm.create_session("gen_metrics_session_a")

        result = chat_svc.list_sessions()
        assert result.success is True
        session_ids = {s.session_id for s in result.data.sessions}
        assert {"chat_session_a", "gen_metrics_session_a"} <= session_ids

    def test_list_sessions_timestamps_use_iso_z_format(self, chat_svc):
        """created_at / last_updated must be ISO-8601 UTC with 'Z' suffix.

        Regression guard: previously these fields were emitted as bare SQLite
        ``YYYY-MM-DD HH:MM:SS`` strings (no timezone), so clients could not
        convert them to local time correctly.
        """
        import os
        import re
        import sqlite3
        from datetime import datetime

        # Build a session DB with explicit naive UTC timestamps in agent_sessions
        # and one user message, mirroring the schema OpenAI Agents SDK creates.
        session_id = "ts-format-session"
        db_path = os.path.join(chat_svc._session_dir, f"{session_id}.db")
        os.makedirs(chat_svc._session_dir, exist_ok=True)
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "CREATE TABLE agent_sessions ("
                "session_id TEXT PRIMARY KEY, "
                "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
                "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
            )
            conn.execute(
                "CREATE TABLE agent_messages ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "session_id TEXT NOT NULL, "
                "message_data TEXT NOT NULL, "
                "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
            )
            conn.execute(
                "INSERT INTO agent_sessions (session_id, created_at, updated_at) "
                "VALUES (?, '2026-04-30 12:34:56', '2026-04-30 12:35:10')",
                (session_id,),
            )
            conn.execute(
                "INSERT INTO agent_messages (session_id, message_data, created_at) "
                "VALUES (?, ?, '2026-04-30 12:34:56')",
                (session_id, '{"role": "user", "content": "Hi"}'),
            )

        result = chat_svc.list_sessions()
        target = next(s for s in result.data.sessions if s.session_id == session_id)

        assert target.created_at == "2026-04-30T12:34:56Z"
        assert target.last_updated == "2026-04-30T12:35:10Z"
        iso_z_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        assert iso_z_pattern.match(target.created_at), target.created_at
        assert iso_z_pattern.match(target.last_updated), target.last_updated
        # And they must round-trip through fromisoformat as aware UTC datetimes.
        from datetime import timezone

        parsed = datetime.fromisoformat(target.created_at.replace("Z", "+00:00"))
        assert parsed == datetime(2026, 4, 30, 12, 34, 56, tzinfo=timezone.utc)

    @pytest.mark.asyncio
    async def test_list_sessions_async_uses_body_store_directly(self, real_agent_config):
        """PG body-store API reads must not go through SessionManager.run_async bridges."""

        class BodyStore:
            async def list_session_ids(self, **kwargs):
                assert kwargs == {"project_id": "project-1", "scope": "alice"}
                return ["s2", "s1"]

            async def get_session_info(self, **kwargs):
                if kwargs["session_id"] == "s2":
                    return {
                        "exists": True,
                        "created_at": "2026-01-02T00:00:00Z",
                        "updated_at": "2026-01-02T00:01:00Z",
                        "first_user_message": "newer",
                        "message_count": 2,
                        "total_tokens": 20,
                    }
                return {
                    "exists": True,
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:01:00Z",
                    "first_user_message": "older",
                    "message_count": 1,
                    "total_tokens": 10,
                }

        svc = ChatService(
            agent_config=real_agent_config,
            task_manager=ChatTaskManager(),
            project_id="project-1",
            session_body_store=BodyStore(),
        )

        with patch("datus.api.services.chat_service.SessionManager", side_effect=AssertionError("sync bridge used")):
            result = await svc.list_sessions_async(user_id="alice")

        assert result.success is True
        assert [item.session_id for item in result.data.sessions] == ["s2", "s1"]
        assert result.data.total_count == 2

    @pytest.mark.asyncio
    async def test_delete_session_async_uses_body_store_directly(self, real_agent_config):
        """PG body-store deletes must stay on the caller event loop."""

        class BodyStore:
            def __init__(self):
                self.deleted = []

            async def session_exists(self, **kwargs):
                assert kwargs == {"project_id": "project-1", "scope": "alice", "session_id": "s1"}
                return True

            async def delete_session(self, **kwargs):
                self.deleted.append(kwargs)

        body_store = BodyStore()
        svc = ChatService(
            agent_config=real_agent_config,
            task_manager=ChatTaskManager(),
            project_id="project-1",
            session_body_store=body_store,
        )

        with patch("datus.api.services.chat_service.SessionManager", side_effect=AssertionError("sync bridge used")):
            result = await svc.delete_session_async("s1", user_id="alice")

        assert result.success is True
        assert body_store.deleted == [{"project_id": "project-1", "scope": "alice", "session_id": "s1"}]


class TestChatServiceDeleteSession:
    """Tests for delete_session."""

    def test_delete_nonexistent_session_succeeds(self, chat_svc):
        """delete_session for unknown session succeeds (no-op)."""
        result = chat_svc.delete_session("nonexistent-session")
        assert result.success is True

    def test_delete_existing_session(self, chat_svc):
        """delete_session removes existing session."""
        sm = SessionManager(session_dir=chat_svc._session_dir)
        sm.create_session("to-delete")

        result = chat_svc.delete_session("to-delete")
        assert result.success is True
        assert chat_svc.session_exists("to-delete") is False


class TestChatServiceGetHistory:
    """Tests for get_history."""

    def test_get_history_nonexistent_session_returns_empty(self, chat_svc):
        """get_history for unknown session returns empty messages."""
        result = chat_svc.get_history("nonexistent-session")
        assert result.success is True
        assert result.data.messages == []

    def test_get_history_empty_session_returns_success(self, chat_svc):
        """get_history for empty session returns success with empty messages."""
        sm = SessionManager(session_dir=chat_svc._session_dir)
        sm.create_session("empty-hist")

        result = chat_svc.get_history("empty-hist")
        assert result.success is True

    def test_history_keeps_provider_reasoning_separate_from_final_answer(self, chat_svc):
        """Reasoning rebuilds as thinking while assistant output rebuilds as markdown."""
        import json
        import os
        import sqlite3

        session_id = "history-reasoning-and-answer"
        response_id = "response-123"
        sm = SessionManager(session_dir=chat_svc._session_dir)
        sm.create_session(session_id)
        db_path = os.path.join(chat_svc._session_dir, f"{session_id}.db")
        rows = [
            (
                json.dumps({"role": "user", "content": "Which model are you?"}),
                "2026-01-01T00:00:00",
            ),
            (
                json.dumps(
                    {
                        "type": "reasoning",
                        "summary": [{"type": "summary_text", "text": "Identify the active model."}],
                        "provider_data": {"response_id": response_id},
                    }
                ),
                "2026-01-01T00:00:01",
            ),
            (
                json.dumps(
                    {
                        "role": "assistant",
                        "type": "message",
                        "content": [{"type": "output_text", "text": "I am the configured model."}],
                        "provider_data": {"response_id": response_id},
                    }
                ),
                "2026-01-01T00:00:02",
            ),
        ]
        with sqlite3.connect(db_path) as conn:
            conn.executemany(
                "INSERT INTO agent_messages (session_id, message_data, created_at) VALUES (?, ?, ?)",
                [(session_id, data, created_at) for data, created_at in rows],
            )

        result = chat_svc.get_history(session_id)

        assert result.success is True
        assistant_messages = [message for message in result.data.messages if message.role == "assistant"]
        assert [message.message_id for message in assistant_messages] == [
            f"{response_id}:reasoning",
            f"{response_id}:response",
        ]
        assert [message.content[0].type for message in assistant_messages] == ["thinking", "markdown"]
        assert assistant_messages[0].content[0].payload["content"] == "Identify the active model."
        assert assistant_messages[1].content[0].payload["content"] == "I am the configured model."

    def test_history_rebuilds_anthropic_thinking_block_separately(self, chat_svc):
        """Claude-native thinking content rebuilds beside its normal text answer."""
        import json
        import os
        import sqlite3

        session_id = "history-anthropic-reasoning-and-answer"
        response_id = "claude-response-123"
        sm = SessionManager(session_dir=chat_svc._session_dir)
        sm.create_session(session_id)
        db_path = os.path.join(chat_svc._session_dir, f"{session_id}.db")
        message = {
            "id": response_id,
            "role": "assistant",
            "content": [
                {"type": "thinking", "thinking": "Check the requested identity."},
                {"type": "text", "text": "I am the configured Claude model."},
            ],
        }
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "INSERT INTO agent_messages (session_id, message_data, created_at) VALUES (?, ?, ?)",
                (session_id, json.dumps(message), "2026-01-01T00:00:01"),
            )

        result = chat_svc.get_history(session_id)

        assert result.success is True
        assistant_messages = [message for message in result.data.messages if message.role == "assistant"]
        assert [message.message_id for message in assistant_messages] == [
            f"{response_id}:reasoning",
            f"{response_id}:response",
        ]
        assert [message.content[0].type for message in assistant_messages] == ["thinking", "markdown"]
        assert assistant_messages[0].content[0].payload["content"] == "Check the requested identity."
        assert assistant_messages[1].content[0].payload["content"] == "I am the configured Claude model."

    def test_terminal_events_are_idempotent_and_do_not_enter_model_context(self, chat_svc):
        """Display-only terminal outcomes survive reload without polluting SDK messages."""
        session_id = "terminal-event-history"
        sm = SessionManager(session_dir=chat_svc._session_dir)
        session = sm.create_session(session_id)
        event = ChatSessionTerminalEvent(
            event_id="run-1-terminal",
            event_type="error",
            error="provider failed after the stream started",
            error_type="PROVIDER_FAILED",
            created_at="2026-07-21T00:00:00Z",
        )

        sm.append_terminal_event(session_id, event)
        sm.append_terminal_event(session_id, event)

        result = chat_svc.get_history(session_id)
        terminal_messages = [message for message in result.data.messages if message.message_id == event.event_id]
        assert len(terminal_messages) == 1
        assert terminal_messages[0].role == "system"
        assert terminal_messages[0].content[0].type == "error"
        assert terminal_messages[0].content[0].payload["error_type"] == "PROVIDER_FAILED"
        assert asyncio.run(session.get_items()) == []

    def test_get_history_renders_ask_user_as_read_only_summary(self, chat_svc):
        """Persisted ask_user tool calls render as history summaries, not live controls."""
        import json
        import os
        import sqlite3

        session_id = "history-ask-user-summary"
        sm = SessionManager(session_dir=chat_svc._session_dir)
        sm.create_session(session_id)
        db_path = os.path.join(chat_svc._session_dir, f"{session_id}.db")
        question_args = {
            "questions": [
                {
                    "title": "County",
                    "question": "Which county?",
                    "options": ["Los Angeles", "San Francisco"],
                }
            ]
        }
        answer_result = [{"question": "Which county?", "answer": "Los Angeles"}]

        rows = [
            (json.dumps({"role": "user", "content": "Ask me for a county"}), "2026-01-01T00:00:00"),
            (
                json.dumps(
                    {
                        "type": "function_call",
                        "call_id": "call_ask_user",
                        "name": "ask_user",
                        "arguments": json.dumps(question_args),
                    }
                ),
                "2026-01-01T00:00:01",
            ),
            (
                json.dumps(
                    {
                        "type": "function_call_output",
                        "call_id": "call_ask_user",
                        "output": json.dumps({"success": 1, "result": json.dumps(answer_result)}),
                    }
                ),
                "2026-01-01T00:00:02",
            ),
            (
                json.dumps(
                    {
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "Great, I will use Los Angeles."}],
                    }
                ),
                "2026-01-01T00:00:03",
            ),
        ]
        with sqlite3.connect(db_path) as conn:
            conn.executemany(
                "INSERT INTO agent_messages (session_id, message_data, created_at) VALUES (?, ?, ?)",
                [(session_id, data, created_at) for data, created_at in rows],
            )

        result = chat_svc.get_history(session_id)

        assert result.success is True
        content_types = [content.type for message in result.data.messages for content in message.content]
        assert "interaction-summary" in content_types
        assert "user-interaction" not in content_types
        summary = next(
            content
            for message in result.data.messages
            for content in message.content
            if content.type == "interaction-summary"
        )
        assert "interactionKey" not in summary.payload
        assert summary.payload["requests"][0]["content"] == "Which county?"
        assert summary.payload["answers"][0]["answer"] == "Los Angeles"

    def test_get_history_restores_nested_subagent_messages(self, chat_svc):
        """Canonical history restores the child messages streamed under task()."""
        parent_session_id = "chat_session_parent_history"
        child_session_id = "gen_sql_session_child_history"
        parent_call_id = "task-call-1"

        parent_manager = SessionManager(session_dir=chat_svc._session_dir)
        parent_manager.create_session(parent_session_id)
        parent_db_path = os.path.join(chat_svc._session_dir, f"{parent_session_id}.db")
        parent_rows = [
            ({"role": "user", "content": "Delegate schema inspection"}, "2026-01-01T00:00:00"),
            (
                {
                    "type": "function_call",
                    "call_id": parent_call_id,
                    "name": "task",
                    "arguments": json.dumps({"type": "gen_sql", "prompt": "Inspect orders"}),
                },
                "2026-01-01T00:00:01",
            ),
            (
                {
                    "type": "function_call_output",
                    "call_id": parent_call_id,
                    "output": json.dumps(
                        {
                            "success": 1,
                            "result": {"response": "Inspection complete", "session_id": child_session_id},
                        }
                    ),
                },
                "2026-01-01T00:00:05",
            ),
        ]
        with sqlite3.connect(parent_db_path) as conn:
            conn.executemany(
                "INSERT INTO agent_messages (session_id, message_data, created_at) VALUES (?, ?, ?)",
                [(parent_session_id, json.dumps(message), created_at) for message, created_at in parent_rows],
            )
        parent_manager.append_subagent_event(
            parent_session_id,
            ChatSessionSubagentEvent(
                event_id=f"subagent-{parent_call_id}",
                parent_action_id=parent_call_id,
                child_session_id=child_session_id,
                subagent_type="gen_sql",
                arguments={"type": "gen_sql", "prompt": "Inspect orders"},
                created_at="2026-01-01T00:00:01Z",
            ),
        )

        child_dir = os.path.join(chat_svc._session_dir, parent_session_id)
        child_manager = SessionManager(session_dir=child_dir)
        child_manager.create_session(child_session_id)
        child_db_path = os.path.join(child_dir, f"{child_session_id}.db")
        child_rows = [
            ({"role": "user", "content": "Inspect orders"}, "2026-01-01T00:00:01"),
            (
                {
                    "type": "function_call",
                    "call_id": "child-tool-call-1",
                    "name": "list_tables",
                    "arguments": json.dumps({"schema": "public"}),
                },
                "2026-01-01T00:00:02",
            ),
            (
                {
                    "type": "function_call_output",
                    "call_id": "child-tool-call-1",
                    "output": json.dumps({"success": 1, "result": ["orders"]}),
                },
                "2026-01-01T00:00:03",
            ),
            (
                {
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "The orders table is available."}],
                },
                "2026-01-01T00:00:04",
            ),
        ]
        with sqlite3.connect(child_db_path) as conn:
            conn.executemany(
                "INSERT INTO agent_messages (session_id, message_data, created_at) VALUES (?, ?, ?)",
                [(child_session_id, json.dumps(message), created_at) for message, created_at in child_rows],
            )

        result = chat_svc.get_history(parent_session_id)

        assert result.success is True
        child_messages = [
            message
            for message in result.data.messages
            if message.depth == 1 and message.parent_action_id == parent_call_id
        ]
        assert child_messages
        top_level_task_calls = [
            content
            for message in result.data.messages
            if message.depth == 0
            for content in message.content
            if content.type == "call-tool" and content.payload.get("toolName") == "task"
        ]
        assert len(top_level_task_calls) == 1
        child_content_types = [content.type for message in child_messages for content in message.content]
        assert "call-tool" in child_content_types
        assert "call-tool-result" in child_content_types
        assert "subagent-complete" in child_content_types
        assert any(
            content.payload.get("content") == "Inspect orders"
            for message in child_messages
            for content in message.content
        )
        assert any(
            content.payload.get("content") == "The orders table is available."
            for message in child_messages
            for content in message.content
        )
        completion = next(
            content for message in child_messages for content in message.content if content.type == "subagent-complete"
        )
        assert completion.payload["subagentType"] == "gen_sql"
        assert completion.payload["toolCount"] == 1

    def test_get_history_restores_interrupted_subagent_from_sidecar(self, chat_svc):
        """A delegation sidecar anchors child history before task() returns."""
        parent_session_id = "chat_session_parent_cancelled"
        child_session_id = "ask_metrics_session_child_cancelled"
        parent_call_id = "task-call-cancelled"

        parent_manager = SessionManager(session_dir=chat_svc._session_dir)
        parent_session = parent_manager.create_session(parent_session_id)
        asyncio.run(parent_session.add_items([{"role": "user", "content": "调用ask_metric问下基金"}]))
        parent_manager.append_terminal_event(
            parent_session_id,
            ChatSessionTerminalEvent(
                event_id="run-cancelled-terminal",
                event_type="cancelled",
                error="本轮对话已停止。已完成的内容仍会保留，你可以继续发送新的消息。",
                error_type="CHAT_CANCELLED",
                created_at="2026-07-22T14:46:18Z",
            ),
        )
        delegation_event = ChatSessionSubagentEvent(
            event_id=f"subagent-{parent_call_id}",
            parent_action_id=parent_call_id,
            child_session_id=child_session_id,
            subagent_type="ask_metrics",
            arguments={
                "type": "ask_metrics",
                "prompt": "问下基金",
                "description": "查询基金指标",
            },
            created_at="2026-07-22T14:46:15Z",
        )
        parent_manager.append_subagent_event(parent_session_id, delegation_event)
        parent_manager.append_subagent_event(parent_session_id, delegation_event)

        child_dir = os.path.join(chat_svc._session_dir, parent_session_id)
        child_manager = SessionManager(session_dir=child_dir)
        child_manager.create_session(child_session_id)
        child_db_path = os.path.join(child_dir, f"{child_session_id}.db")
        child_rows = [
            ({"role": "user", "content": "问下基金"}, "2026-07-22T14:46:15"),
            (
                {
                    "type": "function_call",
                    "call_id": "child-list-metrics",
                    "name": "list_metrics",
                    "arguments": json.dumps({}),
                },
                "2026-07-22T14:46:17",
            ),
            (
                {
                    "type": "function_call_output",
                    "call_id": "child-list-metrics",
                    "output": json.dumps({"success": 1, "result": ["基金规模", "基金收益率"]}),
                },
                "2026-07-22T14:46:17",
            ),
        ]
        with sqlite3.connect(child_db_path) as conn:
            conn.executemany(
                "INSERT INTO agent_messages (session_id, message_data, created_at) VALUES (?, ?, ?)",
                [(child_session_id, json.dumps(message), created_at) for message, created_at in child_rows],
            )

        result = chat_svc.get_history(parent_session_id)

        assert result.success is True
        top_level_types = [
            content.type for message in result.data.messages if message.depth == 0 for content in message.content
        ]
        assert "call-tool" in top_level_types
        child_messages = [
            message
            for message in result.data.messages
            if message.depth == 1 and message.parent_action_id == parent_call_id
        ]
        child_content_types = [content.type for message in child_messages for content in message.content]
        assert "call-tool" in child_content_types
        assert "call-tool-result" in child_content_types
        assert any(
            content.payload.get("toolName") == "list_metrics"
            for message in child_messages
            for content in message.content
            if isinstance(content.payload, dict)
        )
        assert result.data.messages[-1].content[0].payload["error_type"] == "CHAT_CANCELLED"

    @pytest.mark.asyncio
    async def test_get_history_async_restores_nested_subagent_scope(self, real_agent_config):
        """Async body stores load child history from the parent-scoped session."""
        parent_session_id = "chat_session_parent_async"
        child_session_id = "gen_sql_session_child_async"
        parent_call_id = "task-call-async"
        parent_rows = [
            {
                "message_data": json.dumps(
                    {
                        "type": "function_call",
                        "call_id": parent_call_id,
                        "name": "task",
                        "arguments": json.dumps({"type": "gen_sql", "prompt": "Inspect orders"}),
                    }
                ),
                "created_at": "2026-01-01T00:00:01",
            },
            {
                "message_data": json.dumps(
                    {
                        "type": "function_call_output",
                        "call_id": parent_call_id,
                        "output": json.dumps({"success": 1, "result": {"session_id": child_session_id}}),
                    }
                ),
                "created_at": "2026-01-01T00:00:04",
            },
        ]
        child_rows = [
            {
                "message_data": json.dumps({"role": "user", "content": "Inspect orders"}),
                "created_at": "2026-01-01T00:00:01",
            },
            {
                "message_data": json.dumps(
                    {
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "Child response"}],
                    }
                ),
                "created_at": "2026-01-01T00:00:03",
            },
        ]

        class BodyStore:
            def __init__(self):
                self.message_calls = []

            async def get_session_messages(self, **kwargs):
                self.message_calls.append(kwargs)
                if kwargs["scope"] == "alice":
                    return parent_rows
                if kwargs["scope"] == f"alice__{parent_session_id}":
                    return child_rows
                return []

            async def get_session_terminal_events(self, **kwargs):
                return []

        body_store = BodyStore()
        svc = ChatService(
            agent_config=real_agent_config,
            task_manager=ChatTaskManager(),
            project_id="project-1",
            session_body_store=body_store,
        )

        with patch("datus.api.services.chat_service.SessionManager", wraps=SessionManager) as session_manager:
            result = await svc.get_history_async(parent_session_id, user_id="alice")

        assert result.success is True
        assert session_manager.call_count == 0
        assert {
            "project_id": "project-1",
            "scope": f"alice__{parent_session_id}",
            "session_id": child_session_id,
        } in body_store.message_calls
        child_messages = [
            message
            for message in result.data.messages
            if message.depth == 1 and message.parent_action_id == parent_call_id
        ]
        assert any(
            content.payload.get("content") == "Child response"
            for message in child_messages
            for content in message.content
        )

    @pytest.mark.asyncio
    async def test_get_history_async_restores_interrupted_subagent_from_sidecar(self, real_agent_config):
        """Async enterprise history uses the sidecar child link without a sync bridge."""
        parent_session_id = "chat_session_parent_cancelled_async"
        child_session_id = "ask_metrics_session_child_cancelled_async"
        parent_call_id = "task-call-cancelled-async"
        parent_rows = [
            {
                "message_data": json.dumps({"role": "user", "content": "调用ask_metric问下基金"}),
                "created_at": "2026-07-22T14:46:13",
            }
        ]
        child_rows = [
            {
                "message_data": json.dumps({"role": "user", "content": "问下基金"}),
                "created_at": "2026-07-22T14:46:15",
            },
            {
                "message_data": json.dumps(
                    {
                        "id": "reasoning-child-1",
                        "type": "reasoning",
                        "summary": [
                            {
                                "type": "summary_text",
                                "text": "先查看有哪些可用的基金指标。",
                            }
                        ],
                    }
                ),
                "created_at": "2026-07-22T14:46:16",
            },
            {
                "message_data": json.dumps(
                    {
                        "type": "function_call",
                        "call_id": "child-list-metrics-async",
                        "name": "list_metrics",
                        "arguments": json.dumps({}),
                    }
                ),
                "created_at": "2026-07-22T14:46:17",
            },
            {
                "message_data": json.dumps(
                    {
                        "type": "function_call_output",
                        "call_id": "child-list-metrics-async",
                        "output": json.dumps({"success": 1, "result": ["基金规模"]}),
                    }
                ),
                "created_at": "2026-07-22T14:46:17",
            },
        ]
        sidecar_rows = [
            {
                "event_id": f"subagent-{parent_call_id}",
                "event_type": "subagent",
                "parent_action_id": parent_call_id,
                "child_session_id": child_session_id,
                "subagent_type": "ask_metrics",
                "arguments": {
                    "type": "ask_metrics",
                    "prompt": "问下基金",
                    "description": "查询基金指标",
                },
                "created_at": "2026-07-22T14:46:15Z",
            },
            {
                "event_id": "run-cancelled-async-terminal",
                "event_type": "cancelled",
                "error": "本轮对话已停止。已完成的内容仍会保留，你可以继续发送新的消息。",
                "error_type": "CHAT_CANCELLED",
                "created_at": "2026-07-22T14:46:18Z",
            },
        ]

        class BodyStore:
            def __init__(self):
                self.message_calls = []

            async def get_session_messages(self, **kwargs):
                self.message_calls.append(kwargs)
                if kwargs["scope"] == "alice":
                    return parent_rows
                if kwargs["scope"] == parent_session_id:
                    return child_rows
                return []

            async def get_session_terminal_events(self, **kwargs):
                assert kwargs == {
                    "project_id": "project-1",
                    "scope": "alice",
                    "session_id": parent_session_id,
                }
                return sidecar_rows

        body_store = BodyStore()
        svc = ChatService(
            agent_config=real_agent_config,
            task_manager=ChatTaskManager(),
            project_id="project-1",
            session_body_store=body_store,
        )

        with patch("datus.api.services.chat_service.SessionManager", wraps=SessionManager) as session_manager:
            result = await svc.get_history_async(parent_session_id, user_id="alice")

        assert result.success is True
        assert session_manager.call_count == 0
        assert {
            "project_id": "project-1",
            "scope": f"alice__{parent_session_id}",
            "session_id": child_session_id,
        } in body_store.message_calls
        assert {
            "project_id": "project-1",
            "scope": parent_session_id,
            "session_id": child_session_id,
        } in body_store.message_calls
        child_messages = [
            message
            for message in result.data.messages
            if message.depth == 1 and message.parent_action_id == parent_call_id
        ]
        child_content_types = [content.type for message in child_messages for content in message.content]
        assert "thinking" in child_content_types
        assert "call-tool" in child_content_types
        assert "call-tool-result" in child_content_types
        assert any(
            content.payload.get("content") == "先查看有哪些可用的基金指标。"
            for message in child_messages
            for content in message.content
            if content.type == "thinking"
        )
        assert result.data.messages[-1].content[0].payload["error_type"] == "CHAT_CANCELLED"

    def test_terminal_sidecar_failure_does_not_hide_sdk_history(self, chat_svc):
        """The additive sidecar must not become a new availability dependency."""
        fake = MagicMock()
        fake.get_session_messages.return_value = [{"role": "user", "content": "kept message"}]
        fake.get_terminal_events.side_effect = RuntimeError("sidecar unavailable")

        with patch.object(chat_svc, "_session_manager", return_value=fake):
            result = chat_svc.get_history("sidecar-degraded")

        assert result.success is True
        assert len(result.data.messages) == 1
        assert result.data.messages[0].role == "user"
        assert result.data.messages[0].content[0].payload["content"] == "kept message"


class TestChatServiceScopePropagation:
    """user_id is propagated as SessionManager.scope for isolation."""

    def _patched_sm(self):
        fake = MagicMock()
        fake.session_exists.return_value = False
        fake.list_sessions.return_value = []
        fake.get_session_messages.return_value = []
        return fake

    def test_session_exists_passes_scope(self, chat_svc):
        fake = self._patched_sm()
        with patch("datus.api.services.chat_service.SessionManager", return_value=fake) as cls:
            chat_svc.session_exists("sid", user_id="alice")
            cls.assert_called_once_with(session_dir=chat_svc._session_dir, scope="alice")

    def test_list_sessions_passes_scope(self, chat_svc):
        fake = self._patched_sm()
        with patch("datus.api.services.chat_service.SessionManager", return_value=fake) as cls:
            chat_svc.list_sessions(user_id="bob")
            cls.assert_called_once_with(session_dir=chat_svc._session_dir, scope="bob")

    def test_delete_session_passes_scope(self, chat_svc):
        fake = self._patched_sm()
        with patch("datus.api.services.chat_service.SessionManager", return_value=fake) as cls:
            chat_svc.delete_session("sid", user_id="carol")
            cls.assert_called_once_with(session_dir=chat_svc._session_dir, scope="carol")

    def test_get_history_passes_scope(self, chat_svc):
        fake = self._patched_sm()
        with patch("datus.api.services.chat_service.SessionManager", return_value=fake) as cls:
            chat_svc.get_history("sid", user_id="dave")
            cls.assert_called_once_with(session_dir=chat_svc._session_dir, scope="dave")

    def test_get_session_info_passes_scope(self, chat_svc):
        fake = self._patched_sm()
        fake.get_session_info.return_value = {"exists": True, "total_tokens": 7}
        with patch("datus.api.services.chat_service.SessionManager", return_value=fake) as cls:
            result = chat_svc.get_session_info("sid", user_id="erin")
            cls.assert_called_once_with(session_dir=chat_svc._session_dir, scope="erin")

        assert result.success is True
        assert result.data == {"exists": True, "total_tokens": 7}

    def test_none_user_id_falls_back_to_default_scope(self, chat_svc):
        fake = self._patched_sm()
        with patch("datus.api.services.chat_service.SessionManager", return_value=fake) as cls:
            chat_svc.list_sessions()
            cls.assert_called_once_with(session_dir=chat_svc._session_dir, scope=None)


@pytest.mark.asyncio
class TestChatServiceCompactSession:
    """Tests for compact_session."""

    async def test_compact_nonexistent_session(self, real_agent_config, mock_llm_create):
        """compact_session auto-creates and compacts a fresh empty session — the call must
        never raise, and the typed Result must round-trip the requested session_id."""
        from datus.api.models.cli_models import CompactSessionInput

        svc = ChatService(
            agent_config=real_agent_config,
            task_manager=ChatTaskManager(),
            project_id="test-proj",
        )
        request = CompactSessionInput(session_id="nonexistent")
        result = await svc.compact_session(request)

        assert result.success is True
        assert result.data.session_id == "nonexistent"

    async def test_compact_persists_summary_into_session(self, real_agent_config, mock_llm_create):
        """End-to-end: compact must keep the .db alive and write a
        user-marker + assistant-summary pair back into the same session.

        This is the regression coverage for the original bug where compact
        deleted the .db and stored the summary only in the discarded node's
        memory, so UI history reads got an empty session and the next
        chat turn had no summary context.
        """
        from datus.api.models.cli_models import CompactSessionInput

        svc = ChatService(
            agent_config=real_agent_config,
            task_manager=ChatTaskManager(),
            project_id="test-proj",
        )

        # Route the mock LLM's session manager to the real on-disk session_dir
        # so that ChatAgenticNode._get_or_create_session loads the same .db
        # we pre-populate below.
        real_sm = SessionManager(session_dir=svc._session_dir)
        mock_llm_create._session_manager = real_sm

        # Pre-create a real chat session with two Q/A pairs.
        session_id = "chat_session_compact_test"
        seeded = real_sm.create_session(session_id)
        await seeded.add_items(
            [
                {"role": "user", "content": "What tables are there?"},
                {"role": "assistant", "content": [{"type": "output_text", "text": "Tables: schools, frpm"}]},
                {"role": "user", "content": "Describe schools."},
                {"role": "assistant", "content": [{"type": "output_text", "text": "schools has cols a, b, c"}]},
            ]
        )

        # Patch the mock LLM's generate_with_tools to return a deterministic
        # summary for the summarization prompt issued inside _manual_compact.
        from unittest.mock import AsyncMock as _AsyncMock

        mock_llm_create.generate_with_tools = _AsyncMock(
            return_value={"content": "Summary of conversation", "usage": {"output_tokens": 42}}
        )

        request = CompactSessionInput(session_id=session_id)
        result = await svc.compact_session(request)

        assert result.success is True
        assert result.data.success is True

        # The .db file must still exist — compact no longer deletes it.
        import os

        db_path = os.path.join(svc._session_dir, f"{session_id}.db")
        assert os.path.exists(db_path), "Session .db must be preserved after compact"

        # Re-open the session via a fresh SessionManager to bypass any
        # in-memory caches and verify on-disk state.
        verify_sm = SessionManager(session_dir=svc._session_dir)
        verify_session = verify_sm.get_session(session_id)
        items = await verify_session.get_items()

        # After the compact refactor, the session contains a single assistant
        # message carrying the summary + a JSONL recovery pointer appended by
        # the host. Storing as ``assistant`` (not ``user``) makes the next
        # turn see the summary as a prior assistant utterance — the natural
        # shape for "I summarized previously, now answer the next question",
        # and avoids /chat/history rendering a phantom user message.
        assert len(items) == 1
        assert items[0]["role"] == "assistant"
        content_blocks = items[0]["content"]
        assert isinstance(content_blocks, list) and len(content_blocks) == 1
        assert content_blocks[0]["type"] == "output_text"
        body = content_blocks[0]["text"]
        assert "Summary of conversation" in body


@pytest.mark.asyncio
class TestChatServiceStreamChat:
    """Tests for stream_chat."""

    async def test_stream_chat_produces_events(self, real_agent_config, mock_llm_create):
        """stream_chat yields SSE events from the task manager."""
        from datus.api.models.cli_models import StreamChatInput

        svc = ChatService(
            agent_config=real_agent_config,
            task_manager=ChatTaskManager(),
            project_id="test-proj",
        )
        request = StreamChatInput(message="hello", session_id="stream-test")
        events = []
        async for event in svc.stream_chat(request):
            events.append(event)
            if len(events) > 5:
                break
        assert len(events) >= 1
        assert events[0].event == "session"

    async def test_stream_chat_capacity_rejection_yields_typed_error(self, real_agent_config):
        """Admission failures are stable SSE errors instead of broken streams."""
        from datus.api.models.cli_models import StreamChatInput

        task_manager = MagicMock()
        task_manager.start_chat = AsyncMock(side_effect=ChatCapacityError(scope="worker", limit=1))
        svc = ChatService(agent_config=real_agent_config, task_manager=task_manager, project_id="test-proj")

        request = StreamChatInput(message="hello", session_id="capacity-rejected")
        events = [event async for event in svc.stream_chat(request, user_id="alice")]

        assert len(events) == 1
        assert events[0].event == "error"
        assert events[0].data.error_type == "CHAT_CAPACITY_EXCEEDED"
        assert events[0].data.session_id == "capacity-rejected"
        task_manager.consume_events.assert_not_called()

    async def test_stream_chat_duplicate_session_yields_error(self, real_agent_config, mock_llm_create):
        """stream_chat for duplicate session_id yields error event."""
        from datus.api.models.cli_models import StreamChatInput

        tm = ChatTaskManager()
        svc = ChatService(agent_config=real_agent_config, task_manager=tm, project_id="test-proj")

        release_first_task = asyncio.Event()

        class BlockingNode:
            """Keep the first task running so duplicate-session handling is deterministic."""

            def __init__(self, session_id: str):
                self.session_id = session_id

            async def execute_stream_with_interactions(self, action_history):
                if False:
                    yield None
                await release_first_task.wait()

            async def get_last_turn_usage(self):
                return None

        # Mock _create_node to avoid real storage initialization and keep the task active.
        with patch.object(tm, "_create_node", return_value=BlockingNode("dup-stream")):
            request1 = StreamChatInput(message="first", session_id="dup-stream")
            stream1 = svc.stream_chat(request1)
            stream2 = None
            try:
                first_event = await asyncio.wait_for(anext(stream1), timeout=2)
                assert first_event.event == "session"
                assert "dup-stream" in tm._tasks

                request2 = StreamChatInput(message="second", session_id="dup-stream")
                stream2 = svc.stream_chat(request2)
                duplicate_event = await asyncio.wait_for(anext(stream2), timeout=2)
                assert duplicate_event.event == "error"
            finally:
                release_first_task.set()
                await stream1.aclose()
                if stream2 is not None:
                    await stream2.aclose()
                await tm.shutdown()

    async def test_stream_chat_owner_store_failure_yields_error(self, real_agent_config):
        """New-session owner-store failures must be returned as SSE errors, not uncaught generator errors."""
        from datus.api.models.cli_models import StreamChatInput

        class FailingOwnerStore:
            async def set_owner(self, project_id, session_id, user_id):
                raise RuntimeError("owner store unavailable")

        tm = ChatTaskManager(project_id="project-1", session_owner_store=FailingOwnerStore())
        svc = ChatService(agent_config=real_agent_config, task_manager=tm, project_id="project-1")

        request = StreamChatInput(message="hello", session_id="new-session")
        events = [event async for event in svc.stream_chat(request, user_id="alice")]

        assert len(events) == 1
        assert events[0].event == "error"
        assert events[0].data.session_id == "new-session"
        assert events[0].data.error_type == "CHAT_START_FAILED"
        assert "owner store unavailable" in events[0].data.error
        assert tm._tasks == {}
