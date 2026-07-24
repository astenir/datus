"""Downstream chat task policy coverage kept out of the upstream test file."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from datus.api.models.cli_models import StreamChatInput
from datus.api.services.chat_task_manager import ChatTask, ChatTaskManager


@pytest.mark.asyncio
async def test_server_web_executor_keeps_normal_profile_tools_on_backend(real_agent_config):
    class FakeNode:
        session_id = "s-web-server"
        permission_manager = SimpleNamespace(active_profile="normal")

        def __init__(self):
            self.proxied_tool_names = {"write_file"}

        def get_node_name(self):
            return "chat"

        async def execute_stream_with_interactions(self, action_history_manager):
            return
            yield  # pragma: no cover - makes this an async generator

        async def get_last_turn_usage(self):
            return None

    node = FakeNode()
    shared_proxied_names = node.proxied_tool_names
    manager = ChatTaskManager(web_filesystem_executor="server")
    manager._create_node = lambda *args, **kwargs: node  # type: ignore[method-assign]
    task = ChatTask(session_id=node.session_id, asyncio_task=MagicMock())

    with patch("datus.api.services.chat_task_manager.apply_proxy_tools") as apply_proxy_tools:
        await manager._run_loop(
            task,
            real_agent_config,
            StreamChatInput(message="hi", source="web", session_id=node.session_id),
        )

    apply_proxy_tools.assert_not_called()
    assert task.node.proxied_tool_names is shared_proxied_names
    assert shared_proxied_names == set()
    assert task.status == "completed"


def test_rejects_unknown_web_filesystem_executor():
    with pytest.raises(ValueError, match="web_filesystem_executor"):
        ChatTaskManager(web_filesystem_executor="browser")  # type: ignore[arg-type]
