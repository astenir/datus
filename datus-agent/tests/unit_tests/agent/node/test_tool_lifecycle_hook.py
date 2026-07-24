# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from datus.agent.node.agentic_node import AgenticNode
from datus.agent.node.tool_lifecycle_hook import ToolLifecycleHook
from datus.schemas.action_bus import ActionBus
from datus.schemas.action_history import ActionHistory, ActionHistoryManager, ActionRole, ActionStatus


def _context(call_id: str = "call-1") -> SimpleNamespace:
    return SimpleNamespace(
        tool_call_id=call_id,
        tool_name="search",
        tool_arguments='{"query":"revenue"}',
    )


@pytest.mark.asyncio
async def test_publishes_each_tool_completion_before_sdk_batch_finishes():
    manager = ActionHistoryManager()
    action_bus = SimpleNamespace(put=MagicMock())
    node = SimpleNamespace(
        _current_action_history=manager,
        action_bus=action_bus,
        _tool_completion_bus_active=True,
    )
    hook = ToolLifecycleHook(node)

    await hook.on_tool_start(_context(), None, SimpleNamespace(name="search"))
    await hook.on_tool_end(
        _context(),
        None,
        SimpleNamespace(name="search"),
        {"success": 1, "result": ["a", "b"]},
    )

    completion = manager.find_action_by_id("complete_call-1")
    assert completion is not None
    assert completion.status == ActionStatus.SUCCESS
    assert completion.input["arguments"] == {"query": "revenue"}
    action_bus.put.assert_called_once_with(completion)
    assert hook.consume_published_completion("complete_call-1") is True
    assert hook.consume_published_completion("complete_call-1") is False


@pytest.mark.asyncio
async def test_does_not_duplicate_completion_already_emitted_by_model_adapter():
    manager = ActionHistoryManager()
    existing = ActionHistory(
        action_id="complete_call-1",
        role=ActionRole.TOOL,
        action_type="search",
        input={},
        output={"success": True},
        status=ActionStatus.SUCCESS,
    )
    manager.add_action(existing)
    action_bus = SimpleNamespace(put=MagicMock())
    node = SimpleNamespace(
        _current_action_history=manager,
        action_bus=action_bus,
        _tool_completion_bus_active=True,
    )
    hook = ToolLifecycleHook(node)

    await hook.on_tool_end(_context(), None, SimpleNamespace(name="search"), {"success": 1})

    assert manager.get_actions() == [existing]
    action_bus.put.assert_not_called()
    assert hook.consume_published_completion("complete_call-1") is False


@pytest.mark.asyncio
async def test_marks_soft_failure_as_failed():
    manager = ActionHistoryManager()
    action_bus = SimpleNamespace(put=MagicMock())
    node = SimpleNamespace(
        _current_action_history=manager,
        action_bus=action_bus,
        _tool_completion_bus_active=True,
    )
    hook = ToolLifecycleHook(node)

    await hook.on_tool_end(
        _context(),
        None,
        SimpleNamespace(name="search"),
        {"success": 0, "error": "timeout"},
    )

    completion = manager.find_action_by_id("complete_call-1")
    assert completion is not None
    assert completion.status == ActionStatus.FAILED
    assert completion.output["summary"].startswith("Failed")


@pytest.mark.asyncio
async def test_does_not_publish_or_suppress_without_live_action_bus():
    manager = ActionHistoryManager()
    action_bus = SimpleNamespace(put=MagicMock())
    node = SimpleNamespace(
        _current_action_history=manager,
        action_bus=action_bus,
        _tool_completion_bus_active=False,
    )
    hook = ToolLifecycleHook(node)

    await hook.on_tool_end(_context(), None, SimpleNamespace(name="search"), {"success": 1})

    assert manager.find_action_by_id("complete_call-1") is None
    action_bus.put.assert_not_called()
    assert hook.consume_published_completion("complete_call-1") is False


@pytest.mark.asyncio
async def test_does_not_suppress_when_live_action_bus_rejects_publication():
    manager = ActionHistoryManager()
    action_bus = SimpleNamespace(put=MagicMock(side_effect=RuntimeError("closed")))
    node = SimpleNamespace(
        _current_action_history=manager,
        action_bus=action_bus,
        _tool_completion_bus_active=True,
    )
    hook = ToolLifecycleHook(node)

    await hook.on_tool_end(_context(), None, SimpleNamespace(name="search"), {"success": 1})

    assert manager.find_action_by_id("complete_call-1") is None
    assert hook.consume_published_completion("complete_call-1") is False


def test_node_only_composes_lifecycle_hook_for_a_live_action_bus():
    node = AgenticNode.__new__(AgenticNode)
    node._current_action_history = ActionHistoryManager()
    node._tool_completion_bus_active = False

    assert node._get_or_create_tool_lifecycle_hook() is None

    node._tool_completion_bus_active = True
    assert isinstance(node._get_or_create_tool_lifecycle_hook(), ToolLifecycleHook)


@pytest.mark.asyncio
async def test_action_bus_yields_fast_tool_completion_while_sibling_is_still_running():
    manager = ActionHistoryManager()
    action_bus = ActionBus()
    node = SimpleNamespace(
        _current_action_history=manager,
        action_bus=action_bus,
        _tool_completion_bus_active=True,
    )
    hook = ToolLifecycleHook(node)
    release_slow_tool = asyncio.Event()

    async def primary_stream():
        await hook.on_start(None, None)
        for call_id, tool_name in (("call-fast", "search"), ("call-slow", "query")):
            context = _context(call_id)
            context.tool_name = tool_name
            await hook.on_tool_start(context, None, SimpleNamespace(name=tool_name))
            start = ActionHistory(
                action_id=call_id,
                role=ActionRole.TOOL,
                action_type=tool_name,
                input={},
                output={},
                status=ActionStatus.PROCESSING,
            )
            manager.add_action(start)
            yield start

        await hook.on_tool_end(
            _context("call-fast"),
            None,
            SimpleNamespace(name="search"),
            {"success": 1, "result": ["done"]},
        )
        await release_slow_tool.wait()
        slow_context = _context("call-slow")
        slow_context.tool_name = "query"
        await hook.on_tool_end(
            slow_context,
            None,
            SimpleNamespace(name="query"),
            {"success": 1, "result": ["done"]},
        )

    merged = action_bus.merge(primary_stream())
    first = await anext(merged)
    second = await anext(merged)
    fast_completion = await anext(merged)

    assert [first.action_id, second.action_id] == ["call-fast", "call-slow"]
    assert fast_completion.action_id == "complete_call-fast"
    assert release_slow_tool.is_set() is False

    release_slow_tool.set()
    remaining = [action async for action in merged]
    assert [action.action_id for action in remaining] == ["complete_call-slow"]
