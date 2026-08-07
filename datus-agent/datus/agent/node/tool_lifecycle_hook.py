# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Publish each tool completion as soon as its SDK hook fires."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from agents.lifecycle import AgentHooks

from datus.schemas.action_bus import action_bus_put_source
from datus.schemas.action_history import ActionHistory, ActionRole, ActionStatus
from datus.schemas.tool_summary import detect_tool_failure, summarize_tool_execution
from datus.utils.loggings import get_logger

logger = get_logger(__name__)


class ToolLifecycleHook(AgentHooks):
    """Bridge per-tool SDK completion hooks into the node's live ActionBus.

    The Agents SDK executes sibling tools concurrently but exposes their normal
    ``tool_call_output_item`` records only after the whole ``asyncio.gather``
    batch returns. ``on_tool_end`` fires for each tool independently, so this
    hook publishes the matching Datus completion action without waiting for the
    slowest sibling. The delayed SDK completion is suppressed by AgenticNode.
    """

    def __init__(self, node: Any) -> None:
        self._node = node
        self._started_at: dict[str, datetime] = {}
        self._published_completion_ids: set[str] = set()

    async def on_start(self, context: Any, agent: Any) -> None:  # noqa: ARG002
        self._started_at.clear()
        self._published_completion_ids.clear()

    async def on_tool_start(self, context: Any, agent: Any, tool: Any) -> None:  # noqa: ARG002
        call_id = self._call_id(context)
        if call_id:
            self._started_at[call_id] = datetime.now()

    async def on_tool_end(self, context: Any, agent: Any, tool: Any, result: Any) -> None:  # noqa: ARG002
        call_id = self._call_id(context)
        if not call_id:
            return

        completion_id = f"complete_{call_id}"
        manager = getattr(self._node, "_current_action_history", None)
        action_bus = getattr(self._node, "action_bus", None)
        put = getattr(action_bus, "put", None) if action_bus is not None else None
        if (
            manager is None
            or not getattr(self._node, "_tool_completion_bus_active", False)
            or not callable(put)
            or manager.find_action_by_id(completion_id) is not None
        ):
            self._started_at.pop(call_id, None)
            return

        tool_name = str(getattr(context, "tool_name", None) or getattr(tool, "name", None) or "tool")
        arguments = self._arguments(context)
        failed = detect_tool_failure(result)
        summary = summarize_tool_execution(result, tool_name, arguments)
        action = ActionHistory(
            action_id=completion_id,
            role=ActionRole.TOOL,
            messages=f"Tool call: {tool_name}",
            action_type=tool_name,
            input={"function_name": tool_name, "arguments": arguments},
            output={
                "success": not failed,
                "raw_output": result,
                "summary": summary,
                "status_message": summary,
            },
            status=ActionStatus.FAILED if failed else ActionStatus.SUCCESS,
            start_time=self._started_at.pop(call_id, datetime.now()),
            end_time=datetime.now(),
        )
        try:
            with action_bus_put_source("tool_lifecycle"):
                put(action)
        except Exception:  # noqa: BLE001 - observability must not fail the tool run
            logger.debug("ToolLifecycleHook: action_bus.put failed", exc_info=True)
            return
        manager.add_action(action)
        self._published_completion_ids.add(completion_id)

    def consume_published_completion(self, action_id: str) -> bool:
        """Return whether ``action_id`` was already published through ActionBus."""
        if action_id not in self._published_completion_ids:
            return False
        self._published_completion_ids.remove(action_id)
        return True

    @staticmethod
    def _call_id(context: Any) -> str:
        value = getattr(context, "tool_call_id", None)
        return value if isinstance(value, str) and value else ""

    @staticmethod
    def _arguments(context: Any) -> Any:
        raw = getattr(context, "tool_arguments", None)
        if not isinstance(raw, str):
            return raw if raw is not None else {}
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return raw
