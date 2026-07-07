"""Downstream token usage hook coverage kept out of the upstream test file."""

from unittest.mock import AsyncMock

import pytest

from datus.agent.node.token_usage_hook import TokenUsageHook
from tests.unit_tests.agent.node.test_token_usage_hook import _fake_node


@pytest.mark.asyncio
async def test_emit_manual_prefers_async_running_usage_persistence():
    node, manager, bus, sm, notify = _fake_node([])
    sm.upsert_running_turn_usage_async = AsyncMock()
    hook = TokenUsageHook(node)

    await hook.emit_manual({"input_tokens": 3, "output_tokens": 4, "total_tokens": 7})

    sm.upsert_running_turn_usage_async.assert_awaited_once()
    sm.upsert_running_turn_usage.assert_not_called()
    assert len(manager.added) == 1
    assert len(bus.published) == 1
    notify.assert_called_once()
