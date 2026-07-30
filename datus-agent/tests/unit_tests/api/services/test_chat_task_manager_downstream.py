"""Downstream ChatTaskManager owner, terminal, and enterprise coverage."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from datus.api.services.chat_task_manager import ChatTask, ChatTaskManager


class TestApplyPermissionModeOverride:
    def _make_agent_config(self, raw_permissions=None):
        from types import SimpleNamespace

        return SimpleNamespace(
            active_profile_name="normal",
            _raw_permissions=raw_permissions or {},
        )

    def _make_node(self, current_profile="normal", switch_side_effect=None):
        node = MagicMock()
        node.session_id = "sess-x"
        if current_profile is None:
            node.permission_manager = None
            return node
        pm = MagicMock()
        pm.active_profile = current_profile
        if switch_side_effect is not None:
            pm.switch_profile.side_effect = switch_side_effect
        node.permission_manager = pm
        return node

    def test_legacy_agent_permission_ceiling_does_not_clamp_request_profile(self):
        """Persisted pre-migration runtime policy must not override an authorized request."""
        manager = ChatTaskManager()
        node = self._make_node(current_profile="normal")
        node.node_config = {"runtime_policy": {"max_permission_mode": "normal"}}

        manager._apply_permission_mode_override(node, self._make_agent_config(), "dangerous")

        node.permission_manager.switch_profile.assert_called_once_with("dangerous", user_overrides=None)


class TestChatTaskManagerBehavior:
    @pytest.mark.asyncio
    async def test_completed_tool_timing_is_persisted_for_history(self, real_agent_config):
        from datus.models.session_manager import SessionManager
        from datus.schemas.action_history import ActionHistory, ActionRole, ActionStatus
        from datus_enterprise.services.chat_task_runtime import persist_tool_execution_event

        session_id = "durable-tool-timing"
        manager = SessionManager(session_dir=real_agent_config.session_dir)
        manager.create_session(session_id)
        task = ChatTask(session_id=session_id, asyncio_task=MagicMock())
        task.session_established = True
        task.run_id = "run-1"
        start = datetime(2026, 1, 1, 12, 0, 0, 125000)
        action = ActionHistory(
            action_id="complete_tool-call-1",
            role=ActionRole.TOOL,
            action_type="list_tables",
            status=ActionStatus.SUCCESS,
            input={"function_name": "list_tables", "arguments": {}},
            output={"success": 1, "result": ["orders"]},
            start_time=start,
            end_time=start + timedelta(seconds=0.375),
            depth=1,
            parent_action_id="task-call-1",
        )

        await persist_tool_execution_event(
            task=task,
            action=action,
            agent_config=real_agent_config,
            user_id=None,
            project_id="test-proj",
            session_body_store=None,
        )

        [event] = manager.get_tool_execution_events(session_id)
        assert event.call_tool_id == "tool-call-1"
        assert event.duration == 0.375
        assert event.depth == 1
        assert event.parent_action_id == "task-call-1"

    @pytest.mark.asyncio
    async def test_established_stream_error_is_durable_in_fresh_history(self, real_agent_config):
        """A terminal SSE error must survive destruction of in-memory task state."""
        from datus.api.models.cli_models import StreamChatInput
        from datus.api.services.chat_service import ChatService
        from datus.models.session_manager import SessionManager

        session_id = "durable-terminal-error"
        SessionManager(session_dir=real_agent_config.session_dir).create_session(session_id)

        class FailingNode:
            session_id = "llm-durable-terminal-error"

            def get_node_name(self):
                return "chat"

            async def execute_stream_with_interactions(self, action_history_manager):
                if False:
                    yield None
                raise RuntimeError("provider stream failed")

        manager = ChatTaskManager(project_id="test-proj")
        manager._create_node = lambda *args, **kwargs: FailingNode()  # type: ignore[method-assign]
        task = ChatTask(session_id=session_id, asyncio_task=MagicMock())

        await manager._run_loop(
            task,
            real_agent_config,
            StreamChatInput(message="hello", session_id=session_id),
        )

        live_error = next(event for event in task.events if event.event == "error")
        assert live_error.data.error_type == "RuntimeError"
        assert live_error.data.error == "provider stream failed"

        history_service = ChatService(
            agent_config=real_agent_config,
            task_manager=ChatTaskManager(),
            project_id="test-proj",
        )
        history = history_service.get_history(session_id)
        history_error = next(
            content for message in history.data.messages for content in message.content if content.type == "error"
        )
        assert history_error.payload["error_type"] == live_error.data.error_type
        assert history_error.payload["error"] == live_error.data.error

        sdk_items = await SessionManager(session_dir=real_agent_config.session_dir).get_session(session_id).get_items()
        assert sdk_items == []

    @pytest.mark.asyncio
    async def test_permission_denial_action_is_durable_with_stable_error_type(self, real_agent_config):
        """Expected tool-policy denials retain their safe detail and stable code."""
        from datus.api.models.cli_models import StreamChatInput
        from datus.api.services.chat_service import ChatService
        from datus.models.session_manager import SessionManager
        from datus.schemas.action_history import ActionHistory, ActionRole, ActionStatus

        session_id = "durable-permission-denial"
        error = (
            "权限受限：当前 Agent 或会话的工具策略不允许直接修改文件。"
            "write_file 已被“普通”权限模式拦截，换路径或重试不会绕过限制。"
            "请联系管理员核对该 Agent 的工具策略。"
        )
        SessionManager(session_dir=real_agent_config.session_dir).create_session(session_id)

        class PermissionDeniedNode:
            session_id = "llm-durable-permission-denial"

            def get_node_name(self):
                return "chat"

            async def execute_stream_with_interactions(self, action_history_manager):
                yield ActionHistory(
                    action_id="permission-denied-action",
                    role=ActionRole.ASSISTANT,
                    action_type="error",
                    messages=f"chat interaction failed: {error}",
                    input={},
                    output={"success": False, "error": error, "error_type": "PERMISSION_DENIED"},
                    status=ActionStatus.FAILED,
                )

            async def get_last_turn_usage(self):
                return None

        manager = ChatTaskManager(project_id="test-proj")
        manager._create_node = lambda *args, **kwargs: PermissionDeniedNode()  # type: ignore[method-assign]
        task = ChatTask(session_id=session_id, asyncio_task=MagicMock())

        await manager._run_loop(
            task,
            real_agent_config,
            StreamChatInput(message="create a file", session_id=session_id),
        )

        assert task.status == "error"
        history = ChatService(
            agent_config=real_agent_config,
            task_manager=ChatTaskManager(),
            project_id="test-proj",
        ).get_history(session_id)
        history_error = next(
            content for message in history.data.messages for content in message.content if content.type == "error"
        )
        assert history_error.payload["error_type"] == "PERMISSION_DENIED"
        assert history_error.payload["error"] == error

    @pytest.mark.asyncio
    async def test_interrupted_action_is_durable_in_fresh_history(self, real_agent_config):
        """A graceful user stop is restored as a cancelled terminal block."""
        from datus.api.models.cli_models import StreamChatInput
        from datus.api.services.chat_service import ChatService
        from datus.models.session_manager import SessionManager
        from datus.schemas.action_history import ActionHistory, ActionRole, ActionStatus

        session_id = "durable-terminal-cancelled"
        SessionManager(session_dir=real_agent_config.session_dir).create_session(session_id)

        class InterruptedNode:
            session_id = "llm-durable-terminal-cancelled"

            def get_node_name(self):
                return "chat"

            async def execute_stream_with_interactions(self, action_history_manager):
                yield ActionHistory(
                    action_id="interrupted-action",
                    role=ActionRole.ASSISTANT,
                    action_type="interrupted",
                    messages="Execution interrupted by user",
                    input={},
                    output=None,
                    status=ActionStatus.SUCCESS,
                )

            async def get_last_turn_usage(self):
                return None

        manager = ChatTaskManager(project_id="test-proj")
        manager._create_node = lambda *args, **kwargs: InterruptedNode()  # type: ignore[method-assign]
        task = ChatTask(session_id=session_id, asyncio_task=MagicMock())

        await manager._run_loop(
            task,
            real_agent_config,
            StreamChatInput(message="hello", session_id=session_id),
        )

        assert task.status == "cancelled"
        history = ChatService(
            agent_config=real_agent_config,
            task_manager=ChatTaskManager(),
            project_id="test-proj",
        ).get_history(session_id)
        history_error = next(
            content for message in history.data.messages for content in message.content if content.type == "error"
        )
        assert history_error.payload["event_type"] == "cancelled"
        assert history_error.payload["error_type"] == "CHAT_CANCELLED"

    @pytest.mark.asyncio
    async def test_discard_timeout_finalizer_does_not_remove_reused_session(self):
        """A discarded old task must not clean up a later task with the same session ID."""

        manager = ChatTaskManager()
        old_asyncio_task = asyncio.create_task(asyncio.sleep(10))
        old_task = ChatTask(session_id="reuse-session", asyncio_task=old_asyncio_task)
        manager._tasks["reuse-session"] = old_task

        discarded = await manager.discard_task_snapshot("reuse-session", wait=True, timeout=0.001)
        assert discarded is True
        assert manager._tasks == {}

        new_task = ChatTask(session_id="reuse-session", asyncio_task=MagicMock())
        manager._tasks["reuse-session"] = new_task

        old_task.status = "cancelled"
        manager._release_task_slot("reuse-session", old_task)

        assert manager._tasks["reuse-session"] is new_task
        assert manager._completed_tasks.get("reuse-session") is not old_task
        assert id(old_task) not in manager._discarded_task_ids

        await asyncio.gather(old_asyncio_task, return_exceptions=True)

    @pytest.mark.asyncio
    async def test_discard_wait_does_not_remove_reused_completed_session(self, monkeypatch):
        """Stale discard cleanup must not remove a newer completed task snapshot."""

        from datus.api.services import chat_task_manager as ctm

        manager = ChatTaskManager()
        old_task = ChatTask(session_id="reuse-session", asyncio_task=MagicMock())
        new_task = ChatTask(session_id="reuse-session", asyncio_task=MagicMock())
        manager._tasks["reuse-session"] = old_task

        async def fake_wait_for(awaitable, timeout):
            manager._release_task_slot("reuse-session", old_task)
            manager._tasks["reuse-session"] = new_task
            manager._release_task_slot("reuse-session", new_task)

        monkeypatch.setattr(ctm.asyncio, "wait_for", fake_wait_for)

        discarded = await manager.discard_task_snapshot("reuse-session", wait=True, timeout=0.001)

        assert discarded is True
        assert manager._tasks == {}
        assert manager._completed_tasks["reuse-session"] is new_task
        assert manager._completed_tasks["reuse-session"] is not old_task
        assert id(old_task) not in manager._discarded_task_ids


@pytest.mark.asyncio
class TestStartChat:
    async def test_start_chat_owner_store_failure_removes_placeholder_task(self, real_agent_config):
        """A failed owner write must not leave an uncancellable running placeholder."""
        from datus.api.models.cli_models import StreamChatInput

        class FailingOwnerStore:
            async def set_owner(self, project_id, session_id, user_id):
                raise RuntimeError("owner store unavailable")

        manager = ChatTaskManager(project_id="project-1", session_owner_store=FailingOwnerStore())
        request = StreamChatInput(message="hello", session_id="owned-session")

        with pytest.raises(RuntimeError, match="owner store unavailable"):
            await manager.start_chat(real_agent_config, request, user_id="alice")

        assert manager._tasks == {}

    async def test_start_chat_records_task_owner(self, real_agent_config, monkeypatch):
        """start_chat stores raw owner metadata before the background loop runs."""
        from datus.api.enterprise.defaults import InMemorySessionOwnerStore
        from datus.api.models.cli_models import StreamChatInput

        async def fake_run_loop(self, task, agent_config, request, **kwargs):
            task.status = "completed"

        monkeypatch.setattr(ChatTaskManager, "_run_loop", fake_run_loop)
        owner_store = InMemorySessionOwnerStore()
        manager = ChatTaskManager(project_id="project-1", session_owner_store=owner_store)
        request = StreamChatInput(message="hello", session_id="owned-session")

        task = await manager.start_chat(real_agent_config, request, user_id="alice@example.com")
        await task.asyncio_task

        assert task.owner_user_id == "alice@example.com"
        assert await owner_store.get_owner("project-1", "owned-session") == "alice@example.com"

    async def test_start_chat_rejects_invalid_session_id_before_owner_write(self, real_agent_config):
        from datus.api.enterprise.defaults import InMemorySessionOwnerStore
        from datus.api.models.cli_models import StreamChatInput

        owner_store = InMemorySessionOwnerStore()
        manager = ChatTaskManager(project_id="project-1", session_owner_store=owner_store)
        request = StreamChatInput(message="hello", session_id="bad/session")

        with pytest.raises(ValueError, match="Invalid session ID"):
            await manager.start_chat(real_agent_config, request, user_id="alice")

        assert manager._tasks == {}
        assert await owner_store.list_sessions("project-1") == []

    async def test_stop_established_task_waits_for_graceful_interrupt(self):
        """Established tasks get a chance to emit their durable interrupted action."""
        manager = ChatTaskManager()
        interrupted = asyncio.Event()
        running = asyncio.create_task(interrupted.wait())
        task = ChatTask(session_id="graceful-stop", asyncio_task=running)
        task.session_established = True
        task.node = MagicMock()
        task.node.interrupt_controller.interrupt.side_effect = interrupted.set
        manager._tasks[task.session_id] = task

        assert await manager.stop_task(task.session_id) is True
        assert running.done() is True
        assert running.cancelled() is False
        task.node.interrupt_controller.interrupt.assert_called_once()


class TestStartChatLanguageOverride:
    @pytest.mark.asyncio
    async def test_session_body_store_is_added_only_to_cloned_config(self, real_agent_config, monkeypatch):
        from datus.api.models.cli_models import StreamChatInput

        captured = {}

        async def fake_run_loop(self, task, agent_config, request, **kwargs):
            captured["agent_config"] = agent_config

        body_store = object()
        monkeypatch.setattr(ChatTaskManager, "_run_loop", fake_run_loop)
        manager = ChatTaskManager(project_id="enterprise", session_body_store=body_store)
        request = StreamChatInput(message="hi")

        task = await manager.start_chat(real_agent_config, request)
        await task.asyncio_task

        assert captured["agent_config"]._session_body_store is body_store
        assert captured["agent_config"]._session_project_id == "enterprise"
        assert getattr(real_agent_config, "_session_body_store", None) is None
        assert getattr(real_agent_config, "_session_project_id", None) is None


class TestStartChatRemoteSourceHardening:
    @pytest.mark.asyncio
    async def test_enterprise_no_source_disables_bash_tool(self, real_agent_config, monkeypatch):
        from datus.api.models.cli_models import StreamChatInput

        real_agent_config.bash_tool_enabled = True
        captured = {}

        async def fake_run_loop(self, task, agent_config, request, **kwargs):
            captured["agent_config"] = agent_config

        monkeypatch.setattr(ChatTaskManager, "_run_loop", fake_run_loop)
        manager = ChatTaskManager(enterprise_enabled=True)
        request = StreamChatInput(message="hi", session_id="enterprise-no-source")
        task = await manager.start_chat(real_agent_config, request, user_id="alice")
        await task.asyncio_task

        assert captured["agent_config"].bash_tool_enabled is False
        assert captured["agent_config"]._request_workspace_root.startswith(
            str(real_agent_config.path_manager.workspace_dir)
        )
        assert not hasattr(real_agent_config, "_request_workspace_root")
        assert real_agent_config.bash_tool_enabled is True

    @pytest.mark.asyncio
    async def test_enterprise_requires_authenticated_user(self, real_agent_config):
        from datus.api.models.cli_models import StreamChatInput

        manager = ChatTaskManager(enterprise_enabled=True)
        request = StreamChatInput(message="hi", session_id="enterprise-workspace-required")

        with pytest.raises(ValueError, match="AUTH_REQUIRED"):
            await manager.start_chat(real_agent_config, request)
