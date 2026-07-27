"""Downstream tests for Claude model extensions."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from datus.schemas.action_history import ActionHistoryManager
from tests.unit_tests.models.test_claude_model import (
    _FakeAsyncStreamManager,
    _FakeStreamEvent,
    _make_claude_model,
    _make_model_config,
    _make_response,
    _make_text_block,
)


class TestGenerateWithMcpStreamTextDeltas:
    @pytest.mark.asyncio
    async def test_streams_native_thinking_separately_from_normal_text(self):
        """Claude thinking blocks use thinking actions while text stays markdown."""
        cfg = _make_model_config(use_native_api=True)
        model = _make_claude_model(cfg)

        thinking_block_start = MagicMock()
        thinking_block_start.type = "thinking"
        thinking_delta = MagicMock()
        thinking_delta.type = "thinking_delta"
        thinking_delta.thinking = "Inspecting the request."
        text_block_start = MagicMock()
        text_block_start.type = "text"
        text_delta = MagicMock()
        text_delta.type = "text_delta"
        text_delta.text = "Here is the answer."
        events = [
            _FakeStreamEvent("content_block_start", content_block=thinking_block_start),
            _FakeStreamEvent("content_block_delta", delta=thinking_delta),
            _FakeStreamEvent("content_block_stop"),
            _FakeStreamEvent("content_block_start", content_block=text_block_start),
            _FakeStreamEvent("content_block_delta", delta=text_delta),
            _FakeStreamEvent("content_block_stop"),
        ]
        final_msg = _make_response([_make_text_block("Here is the answer.")])
        stream_manager = _FakeAsyncStreamManager(events, final_msg)

        async_client = MagicMock()
        async_client.messages.stream = MagicMock(return_value=stream_manager)
        model.async_anthropic_client = async_client

        actions = []
        with patch("datus.models.claude_model.multiple_mcp_servers") as mock_mcp:
            mock_mcp.return_value.__aenter__ = AsyncMock(return_value={})
            mock_mcp.return_value.__aexit__ = AsyncMock(return_value=False)
            async for action in model._generate_with_mcp_stream(
                prompt="test",
                mcp_servers={},
                instruction="sys",
                output_type={},
                action_history_manager=ActionHistoryManager(),
            ):
                actions.append(action)

        reasoning_deltas = [a for a in actions if a.action_type == "thinking_delta"]
        reasoning_actions = [a for a in actions if a.action_type == "thinking"]
        response_deltas = [a for a in actions if a.action_type == "response_delta"]
        responses = [a for a in actions if a.action_type == "response"]

        assert len(reasoning_deltas) == 1
        assert reasoning_deltas[0].output["delta"] == "Inspecting the request."
        assert len(reasoning_actions) == 1
        assert reasoning_actions[0].action_id == reasoning_deltas[0].action_id
        assert reasoning_actions[0].output == {
            "thinking": "Inspecting the request.",
            "content_type": "thinking",
        }
        assert len(response_deltas) == 1
        assert response_deltas[0].output["delta"] == "Here is the answer."
        assert len(responses) == 1
        assert responses[0].action_id == response_deltas[0].action_id
        assert responses[0].output["content_type"] == "markdown"
        assert reasoning_actions[0].action_id != responses[0].action_id
