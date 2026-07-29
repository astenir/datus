"""Downstream ChatService history, storage, and admission coverage."""

import asyncio
import json
import os
import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from datus.api.models.downstream import ChatSessionSubagentEvent, ChatSessionTerminalEvent
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


class TestChatServiceListSessions:
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
        svc._task_manager.list_task_snapshots = MagicMock(
            return_value=[
                {
                    "session_id": "s1",
                    "owner_user_id": "alice",
                    "status": "running",
                    "is_running": True,
                    "created_at": "2026-01-01T00:00:00Z",
                    "user_query": "older",
                }
            ]
        )

        with patch("datus.api.services.chat_service.SessionManager", side_effect=AssertionError("sync bridge used")):
            result = await svc.list_sessions_async(user_id="alice")

        assert result.success is True
        assert [item.session_id for item in result.data.sessions] == ["s2", "s1"]
        assert result.data.total_count == 2
        assert result.data.sessions[0].is_active is False
        assert result.data.sessions[1].is_active is True

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


class TestChatServiceGetHistory:
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

    def test_terminal_events_stay_with_their_turn_in_multi_turn_history(self, chat_svc):
        """Terminal outcomes render before later turns instead of collecting at the end."""
        session_id = "multi-turn-terminal-event-history"
        sm = SessionManager(session_dir=chat_svc._session_dir)
        sm.create_session(session_id)
        db_path = os.path.join(chat_svc._session_dir, f"{session_id}.db")
        rows = [
            ({"role": "user", "content": "first request"}, "2026-07-21T00:00:01"),
            ({"role": "user", "content": "second request"}, "2026-07-21T00:00:03"),
            (
                {
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "second answer"}],
                },
                "2026-07-21T00:00:04",
            ),
            ({"role": "user", "content": "third request"}, "2026-07-21T00:00:05"),
        ]
        with sqlite3.connect(db_path) as conn:
            conn.executemany(
                "INSERT INTO agent_messages (session_id, message_data, created_at) VALUES (?, ?, ?)",
                [(session_id, json.dumps(message), created_at) for message, created_at in rows],
            )

        first_error = ChatSessionTerminalEvent(
            event_id="run-1-terminal",
            event_type="error",
            error="first run failed",
            error_type="PROVIDER_FAILED",
            created_at="2026-07-21T00:00:02Z",
        )
        third_error = ChatSessionTerminalEvent(
            event_id="run-3-terminal",
            event_type="timeout",
            error="third run timed out",
            error_type="TIMEOUT",
            created_at="2026-07-21T00:00:06Z",
        )
        sm.append_terminal_event(session_id, first_error)
        sm.append_terminal_event(session_id, third_error)

        result = chat_svc.get_history(session_id)

        assert result.success is True
        terminal_ids = {first_error.event_id, third_error.event_id}
        markers = [
            message.message_id if message.message_id in terminal_ids else message.content[0].payload.get("content")
            for message in result.data.messages
        ]
        assert markers == [
            "first request",
            first_error.event_id,
            "second request",
            "second answer",
            "third request",
            third_error.event_id,
        ]

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
        parent_manager.create_session(parent_session_id)
        parent_db_path = os.path.join(chat_svc._session_dir, f"{parent_session_id}.db")
        with sqlite3.connect(parent_db_path) as conn:
            conn.execute(
                "INSERT INTO agent_messages (session_id, message_data, created_at) VALUES (?, ?, ?)",
                (
                    parent_session_id,
                    json.dumps({"role": "user", "content": "调用ask_metric问下基金"}),
                    "2026-07-22T14:46:13",
                ),
            )
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
    def _patched_sm(self):
        fake = MagicMock()
        fake.session_exists.return_value = False
        fake.list_sessions.return_value = []
        fake.get_session_messages.return_value = []
        return fake

    def test_get_session_info_passes_scope(self, chat_svc):
        fake = self._patched_sm()
        fake.get_session_info.return_value = {"exists": True, "total_tokens": 7}
        with patch("datus.api.services.chat_service.SessionManager", return_value=fake) as cls:
            result = chat_svc.get_session_info("sid", user_id="erin")
            cls.assert_called_once_with(session_dir=chat_svc._session_dir, scope="erin")

        assert result.success is True
        assert result.data == {"exists": True, "total_tokens": 7}


@pytest.mark.asyncio
class TestChatServiceStreamChat:
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
