"""Runtime enforcement for enterprise Agent tool and permission policies."""

from __future__ import annotations

from fnmatch import fnmatchcase
from typing import Any

from datus.tools.permission.permission_config import PermissionLevel, PermissionRule

TOOL_POLICY_MODES = {"inherit", "allowlist"}
PERMISSION_MODE_ORDER = {"normal": 0, "auto": 1, "dangerous": 2}


def normalize_tool_policy(value: Any) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    mode = str(raw.get("mode") or "inherit").strip().lower()
    if mode not in TOOL_POLICY_MODES:
        raise ValueError(f"Agent tool policy mode must be one of: {', '.join(sorted(TOOL_POLICY_MODES))}.")
    return {
        "mode": mode,
        "allowed": _normalized_patterns(raw.get("allowed")),
        "denied": _normalized_patterns(raw.get("denied")),
    }


def normalize_runtime_policy(value: Any) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    max_permission_mode = str(raw.get("max_permission_mode") or "normal").strip().lower()
    if max_permission_mode not in PERMISSION_MODE_ORDER:
        raise ValueError(
            "Agent max_permission_mode must be one of: "
            f"{', '.join(PERMISSION_MODE_ORDER)}."
        )
    allowed_subagents = raw.get("allowed_subagents")
    return {
        "max_permission_mode": max_permission_mode,
        "allow_subagent_delegation": bool(raw.get("allow_subagent_delegation", False)),
        "allowed_subagents": _normalized_patterns(allowed_subagents) if allowed_subagents is not None else [],
    }


def permission_mode_exceeds(requested: str | None, maximum: str) -> bool:
    if not requested:
        return False
    return PERMISSION_MODE_ORDER.get(requested, len(PERMISSION_MODE_ORDER)) > PERMISSION_MODE_ORDER[maximum]


def apply_agent_runtime_policy(node: Any) -> None:
    """Prune a node's LLM tool surface and add call-time DENY rules.

    The visible-tool filter is a usability boundary.  The appended permission
    rules are the security boundary for direct/proxied calls that do not rely on
    the LLM-facing list.
    """

    node_config = getattr(node, "node_config", None)
    if not isinstance(node_config, dict) or (
        "tool_policy" not in node_config and "runtime_policy" not in node_config
    ):
        return
    raw_tool_policy = node_config.get("tool_policy") if isinstance(node_config, dict) else None
    raw_runtime_policy = node_config.get("runtime_policy") if isinstance(node_config, dict) else None
    tool_policy = normalize_tool_policy(raw_tool_policy)
    runtime_policy = normalize_runtime_policy(raw_runtime_policy)

    populate_registry = getattr(node, "_populate_tool_registry", None)
    if callable(populate_registry):
        populate_registry()
    registry = getattr(node, "tool_registry", None)

    denied_tools: list[tuple[str, str]] = []
    visible_tools = []
    for tool in list(getattr(node, "tools", None) or []):
        tool_name = str(getattr(tool, "name", ""))
        category = str(registry.get(tool_name, "tools")) if registry is not None else "tools"
        qualified_name = f"{category}.{tool_name}"
        is_denied = _matches_any(qualified_name, tool_policy["denied"])
        if tool_name == "task" and not runtime_policy["allow_subagent_delegation"]:
            is_denied = True
        if tool_policy["mode"] == "allowlist" and not _matches_any(qualified_name, tool_policy["allowed"]):
            is_denied = True
        if is_denied:
            denied_tools.append((category, tool_name))
            continue
        visible_tools.append(tool)
    node.tools = visible_tools

    if not runtime_policy["allow_subagent_delegation"]:
        subagent_tool = getattr(node, "sub_agent_task_tool", None)
        if subagent_tool is not None:
            subagent_tool._allowed_subagents = []
    elif runtime_policy["allowed_subagents"]:
        subagent_tool = getattr(node, "sub_agent_task_tool", None)
        if subagent_tool is not None:
            subagent_tool._allowed_subagents = list(runtime_policy["allowed_subagents"])

    permission_manager = getattr(node, "permission_manager", None)
    global_config = getattr(permission_manager, "global_config", None)
    if global_config is not None:
        existing = {
            (str(rule.tool), str(rule.pattern), str(rule.permission))
            for rule in global_config.rules
        }
        for category, tool_name in denied_tools:
            key = (category, tool_name, PermissionLevel.DENY.value)
            if key in existing:
                continue
            global_config.rules.append(
                PermissionRule(tool=category, pattern=tool_name, permission=PermissionLevel.DENY)
            )
            existing.add(key)

    mcp_servers = getattr(node, "mcp_servers", None)
    if isinstance(mcp_servers, dict):
        if tool_policy["mode"] == "allowlist":
            node.mcp_servers = {
                name: server
                for name, server in mcp_servers.items()
                if _matches_any(f"mcp.{name}.*", tool_policy["allowed"])
                and not _matches_any(f"mcp.{name}.*", tool_policy["denied"])
            }
        else:
            node.mcp_servers = {
                name: server
                for name, server in mcp_servers.items()
                if not _matches_any(f"mcp.{name}.*", tool_policy["denied"])
            }


def _normalized_patterns(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values = value.split(",")
    elif isinstance(value, (list, tuple, set)):
        values = value
    else:
        raise ValueError("Agent policy patterns must be a string list.")
    return sorted({str(item).strip() for item in values if str(item).strip()})


def _matches_any(value: str, patterns: list[str]) -> bool:
    return any(fnmatchcase(value, pattern) for pattern in patterns)
