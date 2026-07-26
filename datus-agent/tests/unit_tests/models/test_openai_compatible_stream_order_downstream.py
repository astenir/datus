"""Downstream stream-order tests for OpenAI-compatible models."""

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from datus.schemas.action_history import ActionHistoryManager
from tests.unit_tests.models.test_openai_compatible_stream_order import (
    FakeEvent,
    _collect_actions,
    _make_raw_content_part_done_event,
    _make_raw_other_event,
    _make_raw_text_delta_event,
    _make_tool_call_event,
    _make_tool_output_event,
)


@dataclass
class FakeReasoningDeltaData:
    type: str = "response.reasoning_summary_text.delta"
    delta: str = ""


@dataclass
class FakeReasoningDoneData:
    type: str = "response.reasoning_summary_text.done"
    text: str = ""


def _make_raw_reasoning_delta_event(delta="reasoning"):
    return FakeEvent(type="raw_response_event", data=FakeReasoningDeltaData(delta=delta))


def _make_raw_reasoning_done_event(text="reasoning"):
    return FakeEvent(type="raw_response_event", data=FakeReasoningDoneData(text=text))


@pytest.mark.ci
class TestStreamActionOrdering:
    @pytest.mark.asyncio
    async def test_interrupt_after_completed_task_waits_for_turn_persistence(self):
        """A completed delegated task must reach the session before interruption wins."""
        from datus.cli.execution_state import ExecutionInterrupted
        from datus.models.openai_compatible import OpenAICompatibleModel

        class SessionStub:
            def __init__(self):
                self.items: list[dict[str, str]] = []

            async def get_items(self):
                return list(self.items)

        class InterruptControllerStub:
            is_interrupted = False

        session = SessionStub()
        interrupt_controller = InterruptControllerStub()

        class ResultStub:
            def __init__(self):
                self.is_complete = False
                self.final_output = ""
                self.cancel_modes: list[str] = []

            def cancel(self, mode="immediate"):
                self.cancel_modes.append(mode)

            async def stream_events(self):
                yield _make_tool_call_event(call_id="task-call", tool_name="task")
                yield _make_tool_output_event(call_id="task-call", output="delegated result")
                interrupt_controller.is_interrupted = True
                yield _make_raw_other_event()
                if self.cancel_modes == ["after_turn"]:
                    session.items.append({"type": "function_call_output", "call_id": "task-call"})
                self.is_complete = True

        model = object.__new__(OpenAICompatibleModel)
        model.model_name = "test-model"
        model._format_tool_result = lambda content, tool_name="": f"result: {content[:20]}"
        model._format_tool_result_from_dict = lambda data, tool_name="": f"result: {str(data)[:20]}"
        model._setup_custom_json_encoder = lambda: None
        model._extract_and_distribute_token_usage = AsyncMock()
        model.model_config = MagicMock(max_retry=1, retry_interval=0)
        model.default_headers = None
        model.base_url = None
        model.litellm_adapter = MagicMock(
            provider="openai",
            is_thinking_model=False,
            reasoning_effort_level=None,
        )
        result = ResultStub()

        with (
            patch("datus.models.openai_compatible.Runner") as mock_runner,
            patch("datus.models.openai_compatible.Agent"),
            patch("datus.models.openai_compatible.multiple_mcp_servers") as mock_mcp,
        ):
            mock_runner.run_streamed.return_value = result
            mock_mcp.return_value.__aenter__ = AsyncMock(return_value={})
            mock_mcp.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(ExecutionInterrupted):
                async for _ in model._generate_with_tools_stream_internal(
                    prompt="test prompt",
                    mcp_servers=None,
                    tools=None,
                    instruction="test instruction",
                    output_type=str,
                    strict_json_schema=False,
                    max_turns=10,
                    session=session,
                    action_history_manager=ActionHistoryManager(),
                    interrupt_controller=interrupt_controller,
                ):
                    pass

        assert result.cancel_modes == ["after_turn"]
        assert session.items == [{"type": "function_call_output", "call_id": "task-call"}]


@pytest.mark.ci
class TestRawEventEarlyCapture:
    @pytest.mark.asyncio
    async def test_reasoning_and_answer_stream_as_distinct_action_types(self):
        events = [
            _make_raw_reasoning_delta_event("Check "),
            _make_raw_reasoning_delta_event("context"),
            _make_raw_reasoning_done_event("Check context"),
            _make_raw_text_delta_event("Final answer"),
            _make_raw_content_part_done_event(),
        ]

        actions = await _collect_actions(events)

        reasoning_deltas = [action for action in actions if action.action_type == "thinking_delta"]
        reasoning = [action for action in actions if action.action_type == "thinking"]
        response_deltas = [action for action in actions if action.action_type == "response_delta"]
        responses = [action for action in actions if action.action_type == "response"]
        assert [action.output["delta"] for action in reasoning_deltas] == ["Check ", "context"]
        assert reasoning[0].output == {"thinking": "Check context", "content_type": "thinking"}
        assert response_deltas[0].output["delta"] == "Final answer"
        assert responses[0].output["content_type"] == "markdown"
        assert reasoning[0].action_id != responses[0].action_id
