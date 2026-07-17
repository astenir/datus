from types import SimpleNamespace

import pytest

from datus.agent.tool_policy import (
    apply_agent_runtime_policy,
    include_bound_mcp_servers,
    normalize_runtime_policy,
    normalize_tool_policy,
    permission_mode_exceeds,
)
from datus.tools.permission.permission_config import PermissionConfig, PermissionLevel
from datus.tools.registry.tool_registry import ToolRegistry


def _node(*, tool_policy, runtime_policy):
    tools = [
        SimpleNamespace(name="read_file"),
        SimpleNamespace(name="write_file"),
        SimpleNamespace(name="execute_command"),
        SimpleNamespace(name="task"),
    ]
    registry = ToolRegistry()
    registry.register_tools("filesystem_tools", ["read_file", "write_file"])
    registry.register_tools("bash_tools", ["execute_command"])
    registry.register_tools("sub_agent_tools", ["task"])
    return SimpleNamespace(
        node_config={"tool_policy": tool_policy, "runtime_policy": runtime_policy},
        tools=tools,
        tool_registry=registry,
        permission_manager=SimpleNamespace(global_config=PermissionConfig()),
        sub_agent_task_tool=SimpleNamespace(_allowed_subagents=None),
        mcp_servers={"filesystem": object(), "remote": object()},
    )


def test_allowlist_prunes_visible_tools_and_adds_call_time_denies():
    node = _node(
        tool_policy={
            "mode": "allowlist",
            "allowed": ["filesystem_tools.read_file"],
            "denied": ["filesystem_tools.write_file", "bash_tools.*"],
        },
        runtime_policy={"max_permission_mode": "normal", "allow_subagent_delegation": False},
    )

    apply_agent_runtime_policy(node)

    assert [tool.name for tool in node.tools] == ["read_file"]
    denied = {
        (rule.tool, rule.pattern)
        for rule in node.permission_manager.global_config.rules
        if rule.permission == PermissionLevel.DENY
    }
    assert denied == {
        ("filesystem_tools", "write_file"),
        ("bash_tools", "execute_command"),
        ("sub_agent_tools", "task"),
    }
    assert node.sub_agent_task_tool._allowed_subagents == []
    assert node.mcp_servers == {}


def test_runtime_policy_can_limit_delegation_to_explicit_agents():
    node = _node(
        tool_policy={"mode": "inherit"},
        runtime_policy={
            "max_permission_mode": "auto",
            "allow_subagent_delegation": True,
            "allowed_subagents": ["safe_sql"],
        },
    )

    apply_agent_runtime_policy(node)

    assert {tool.name for tool in node.tools} == {"read_file", "write_file", "execute_command", "task"}
    assert node.sub_agent_task_tool._allowed_subagents == ["safe_sql"]


def test_bound_mcp_servers_are_added_to_allowlist_and_denies_still_win():
    policy = include_bound_mcp_servers(
        {"mode": "allowlist", "allowed": ["db_tools.*"], "denied": ["mcp.blocked.*"]},
        ["remote", "blocked"],
    )

    assert policy["allowed"] == ["db_tools.*", "mcp.blocked.*", "mcp.remote.*"]

    node = _node(tool_policy=policy, runtime_policy={})
    apply_agent_runtime_policy(node)

    assert set(node.mcp_servers) == {"remote"}


def test_policy_normalization_and_permission_ceiling_fail_closed():
    assert normalize_tool_policy(None) == {"mode": "inherit", "allowed": [], "denied": []}
    assert normalize_runtime_policy(None)["max_permission_mode"] == "normal"
    assert permission_mode_exceeds("dangerous", "normal") is True
    assert permission_mode_exceeds("normal", "auto") is False
    with pytest.raises(ValueError):
        normalize_tool_policy({"mode": "unknown"})
    with pytest.raises(ValueError):
        normalize_runtime_policy({"max_permission_mode": "root"})
