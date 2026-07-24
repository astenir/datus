# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Downstream regression tests for proxy tool timeouts."""

from types import SimpleNamespace

import pytest
from agents import FunctionTool

from datus.tools.proxy.proxy_tool import create_proxy_tool
from datus.tools.proxy.tool_result_channel import ToolResultChannel


@pytest.mark.asyncio
async def test_proxy_tool_supports_explicit_timeout() -> None:
    channel = ToolResultChannel()
    original = FunctionTool(
        name="edit_file",
        description="Edit a file",
        params_json_schema={"type": "object", "properties": {}},
        on_invoke_tool=lambda ctx, args: {"success": 1},
    )
    proxy = create_proxy_tool(original, channel, timeout_seconds=0.01)

    ctx = SimpleNamespace(tool_call_id="call_timeout")
    result = await proxy.on_invoke_tool(ctx, "{}")

    assert result["success"] == 0
    assert "Timed out waiting for external tool result for 'edit_file'" in result["error"]
    assert result["result"] is None
    assert channel._futures["call_timeout"].done()
