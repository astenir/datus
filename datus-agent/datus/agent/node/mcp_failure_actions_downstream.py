"""Build downstream action-history events for non-fatal MCP connection failures."""

from __future__ import annotations

import uuid
from typing import Any

from datus.schemas.action_history import ActionHistory, ActionRole, ActionStatus


def record_mcp_connection_failure(node: Any, server_name: str, error: str) -> None:
    failure = (server_name, error)
    failures = getattr(node, "_mcp_connection_failures", None)
    if failures is None:
        failures = []
        node._mcp_connection_failures = failures
    if failure not in failures:
        failures.append(failure)


def drain_mcp_connection_failure_actions(node: Any, manager: Any) -> list[ActionHistory]:
    failures = getattr(node, "_mcp_connection_failures", [])
    node._mcp_connection_failures = []
    actions: list[ActionHistory] = []
    for server_name, error in failures:
        action = ActionHistory(
            action_id=str(uuid.uuid4()),
            role=ActionRole.TOOL,
            action_type=f"mcp.{server_name}.connect",
            input={"server_name": server_name},
            output={
                "error": error,
                "summary": f"MCP Server '{server_name}' connection failed; the Agent continued without it.",
            },
            status=ActionStatus.FAILED,
        )
        manager.add_action(action)
        actions.append(action)
    return actions
