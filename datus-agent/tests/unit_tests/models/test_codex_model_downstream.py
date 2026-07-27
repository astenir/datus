"""Downstream Codex interrupt-persistence coverage."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from datus.cli.execution_state import ExecutionInterrupted
from datus.configuration.agent_config import ModelConfig
from datus.models.codex_model import CodexModel


@pytest.fixture
def model_config():
    return ModelConfig(
        type="codex",
        api_key="",
        model="gpt-5.3-codex",
        base_url="https://chatgpt.com/backend-api/codex",
        auth_type="oauth",
    )


@pytest.mark.asyncio
@patch("datus.models.codex_model.OAuthManager")
@patch("datus.models.codex_model.multiple_mcp_servers")
@patch("datus.models.codex_model.Runner")
@patch("datus.models.codex_model.Agent")
async def test_interrupt_after_completed_task_waits_for_turn_persistence(
    mock_agent_cls,
    mock_runner,
    mock_mcp,
    mock_oauth_cls,
    model_config,
):
    class SessionStub:
        def __init__(self):
            self.items = []

        async def get_items(self):
            return list(self.items)

    class InterruptControllerStub:
        is_interrupted = False

    interrupt_controller = InterruptControllerStub()
    session = SessionStub()

    tool_call_event = MagicMock()
    tool_call_event.type = "run_item_stream_event"
    tool_call_event.item.type = "tool_call_item"
    tool_call_event.item.raw_item = {
        "name": "task",
        "call_id": "task-call",
        "arguments": '{"type":"explore"}',
    }
    tool_output_event = MagicMock()
    tool_output_event.type = "run_item_stream_event"
    tool_output_event.item.type = "tool_call_output_item"
    tool_output_event.item.output = "delegated result"
    tool_output_event.item.raw_item = {"call_id": "task-call"}
    trailing_event = MagicMock()
    trailing_event.type = "raw_response_event"
    trailing_event.data.type = "response.created"

    class ResultStub:
        def __init__(self):
            self.is_complete = False
            self.final_output = ""
            self.cancel_modes = []

        def cancel(self, mode="immediate"):
            self.cancel_modes.append(mode)

        async def stream_events(self):
            yield tool_call_event
            yield tool_output_event
            interrupt_controller.is_interrupted = True
            yield trailing_event
            if self.cancel_modes == ["after_turn"]:
                session.items.append({"type": "function_call_output", "call_id": "task-call"})
            self.is_complete = True

    mock_oauth = MagicMock()
    mock_oauth.get_access_token.return_value = "tok"
    mock_oauth_cls.return_value = mock_oauth
    model = CodexModel(model_config=model_config)
    model._async_client = MagicMock()
    result = ResultStub()

    with patch("agents.models.openai_responses.OpenAIResponsesModel"):
        mock_mcp.return_value.__aenter__ = AsyncMock(return_value={})
        mock_mcp.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_runner.run_streamed.return_value = result

        with pytest.raises(ExecutionInterrupted):
            async for _ in model.generate_with_tools_stream(
                prompt="test",
                session=session,
                interrupt_controller=interrupt_controller,
            ):
                pass

    assert result.cancel_modes == ["after_turn"]
    assert session.items == [{"type": "function_call_output", "call_id": "task-call"}]
