"""Build downstream action-history events for non-fatal MCP connection failures."""

from __future__ import annotations

import uuid
from typing import Any

from datus.models.mcp_utils import safe_mcp_connection_error
from datus.schemas.action_history import ActionHistory, ActionRole, ActionStatus

MCP_CONNECTION_ACTION_PREFIX = "mcp."
MCP_CONNECTION_ACTION_SUFFIX = ".connect"


def request_mcp_display_names(node: Any) -> dict[str, str]:
    """Resolve request-scoped personal MCP aliases to user-facing display names.

    ``project_personal_mcp_for_chat`` stores ``{alias: display_name}`` on the
    request clone as ``agent_config._request_mcp_display_names``. Unknown or
    non-personal servers fall back to their raw alias/name.
    """
    agent_config = getattr(node, "agent_config", None)
    if agent_config is None:
        return {}
    raw = getattr(agent_config, "_request_mcp_display_names", None)
    return {str(key): str(value) for key, value in dict(raw or {}).items()}


def is_mcp_connection_tool_name(tool_name: Any) -> bool:
    return (
        isinstance(tool_name, str)
        and tool_name.startswith(MCP_CONNECTION_ACTION_PREFIX)
        and tool_name.endswith(MCP_CONNECTION_ACTION_SUFFIX)
        and len(tool_name) > len(MCP_CONNECTION_ACTION_PREFIX) + len(MCP_CONNECTION_ACTION_SUFFIX)
    )


def is_mcp_connection_failure_action(action: Any) -> bool:
    return (
        getattr(action, "role", None) == ActionRole.TOOL
        and getattr(action, "status", None) == ActionStatus.FAILED
        and is_mcp_connection_tool_name(getattr(action, "action_type", None))
    )


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
    display_names = request_mcp_display_names(node)
    actions: list[ActionHistory] = []
    for server_name, error in failures:
        display_name = display_names.get(server_name) or server_name
        tool_name = f"{MCP_CONNECTION_ACTION_PREFIX}{server_name}{MCP_CONNECTION_ACTION_SUFFIX}"
        call_tool_id = str(uuid.uuid4())
        input_data = {"function_name": tool_name, "arguments": {}, "server_name": server_name}
        safe_error = safe_mcp_connection_error(error)
        start_action = ActionHistory(
            action_id=call_tool_id,
            role=ActionRole.TOOL,
            action_type=tool_name,
            input=input_data,
            output=None,
            status=ActionStatus.PROCESSING,
        )
        result_action = ActionHistory(
            action_id=f"complete_{call_tool_id}",
            role=ActionRole.TOOL,
            action_type=tool_name,
            input=input_data,
            output={
                "error": safe_error,
                "summary": f"MCP Server '{display_name}' connection failed; the Agent continued without it.",
            },
            status=ActionStatus.FAILED,
            start_time=start_action.start_time,
        )
        manager.add_action(start_action)
        manager.add_action(result_action)
        actions.extend((start_action, result_action))
    return actions
