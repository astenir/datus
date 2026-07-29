from types import SimpleNamespace

import pytest

from datus.agent.tool_policy import (
    apply_agent_runtime_policy,
    include_bound_mcp_servers,
    normalize_runtime_policy,
    normalize_tool_policy,
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
        agent_config=SimpleNamespace(_request_required_subagent_ids=set()),
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
        runtime_policy={"allow_subagent_delegation": False},
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
            "allow_subagent_delegation": True,
            "allowed_subagents": ["safe_sql"],
        },
    )

    apply_agent_runtime_policy(node)

    assert {tool.name for tool in node.tools} == {"read_file", "write_file", "execute_command", "task"}
    assert node.sub_agent_task_tool._allowed_subagents == ["safe_sql"]


def test_request_required_subagent_is_added_to_explicit_runtime_allowlist():
    node = _node(
        tool_policy={"mode": "inherit"},
        runtime_policy={
            "allow_subagent_delegation": True,
            "allowed_subagents": ["safe_sql"],
        },
    )
    node.agent_config._request_required_subagent_ids = {"explore"}

    apply_agent_runtime_policy(node)

    assert {tool.name for tool in node.tools} == {"read_file", "write_file", "execute_command", "task"}
    assert node.sub_agent_task_tool._allowed_subagents == ["safe_sql", "explore"]


def test_request_required_subagent_enables_only_task_when_general_delegation_is_disabled():
    node = _node(
        tool_policy={"mode": "allowlist", "allowed": ["filesystem_tools.read_file"]},
        runtime_policy={"allow_subagent_delegation": False},
    )
    node.agent_config._request_required_subagent_ids = {"explore"}

    apply_agent_runtime_policy(node)

    assert [tool.name for tool in node.tools] == ["read_file", "task"]
    assert node.sub_agent_task_tool._allowed_subagents == ["explore"]


def test_explicit_task_deny_still_blocks_request_required_subagent():
    node = _node(
        tool_policy={"mode": "inherit", "denied": ["sub_agent_tools.task"]},
        runtime_policy={"allow_subagent_delegation": False},
    )
    node.agent_config._request_required_subagent_ids = {"explore"}

    apply_agent_runtime_policy(node)

    assert "task" not in {tool.name for tool in node.tools}


def test_allowlist_keeps_task_when_runtime_delegation_is_enabled():
    node = _node(
        tool_policy={"mode": "allowlist", "allowed": ["filesystem_tools.read_file"]},
        runtime_policy={"allow_subagent_delegation": True},
    )

    apply_agent_runtime_policy(node)

    assert [tool.name for tool in node.tools] == ["read_file", "task"]


def test_explicit_task_deny_wins_over_runtime_delegation():
    node = _node(
        tool_policy={
            "mode": "allowlist",
            "allowed": ["filesystem_tools.read_file"],
            "denied": ["sub_agent_tools.task"],
        },
        runtime_policy={"allow_subagent_delegation": True},
    )

    apply_agent_runtime_policy(node)

    assert [tool.name for tool in node.tools] == ["read_file"]


def test_disabled_runtime_delegation_wins_over_task_allow_rule():
    node = _node(
        tool_policy={
            "mode": "allowlist",
            "allowed": ["filesystem_tools.read_file", "sub_agent_tools.*"],
        },
        runtime_policy={"allow_subagent_delegation": False},
    )

    apply_agent_runtime_policy(node)

    assert [tool.name for tool in node.tools] == ["read_file"]


def test_allowlist_keeps_registered_interaction_tools_by_default_wildcard():
    node = _node(
        tool_policy={"mode": "allowlist", "allowed": ["tools.*"], "denied": []},
        runtime_policy={"allow_subagent_delegation": False},
    )
    interaction_names = ["ask_user", "confirm_plan", "todo_list", "todo_read", "todo_write", "todo_update"]
    node.tools.extend(SimpleNamespace(name=name) for name in interaction_names)
    node.tool_registry.register_tools("tools", interaction_names)

    apply_agent_runtime_policy(node)

    assert [tool.name for tool in node.tools] == interaction_names


def test_interaction_wildcard_still_honors_exact_deny():
    node = _node(
        tool_policy={"mode": "allowlist", "allowed": ["tools.*"], "denied": ["tools.ask_user"]},
        runtime_policy={"allow_subagent_delegation": False},
    )
    node.tools.extend([SimpleNamespace(name="ask_user"), SimpleNamespace(name="todo_list")])
    node.tool_registry.register_tools("tools", ["ask_user", "todo_list"])

    apply_agent_runtime_policy(node)

    assert [tool.name for tool in node.tools] == ["todo_list"]


def test_bound_mcp_servers_are_added_to_allowlist_and_denies_still_win():
    policy = include_bound_mcp_servers(
        {"mode": "allowlist", "allowed": ["db_tools.*"], "denied": ["mcp.blocked.*"]},
        ["remote", "blocked"],
    )

    assert policy["allowed"] == ["db_tools.*", "mcp.blocked.*", "mcp.remote.*"]

    node = _node(tool_policy=policy, runtime_policy={})
    apply_agent_runtime_policy(node)

    assert set(node.mcp_servers) == {"remote"}


def test_policy_normalization_ignores_legacy_permission_ceiling():
    assert normalize_tool_policy(None) == {"mode": "inherit", "allowed": [], "denied": []}
    assert normalize_runtime_policy(None) == {
        "allow_subagent_delegation": False,
        "allowed_subagents": [],
    }
    assert normalize_runtime_policy(
        {
            "max_permission_mode": "dangerous",
            "allow_subagent_delegation": True,
            "allowed_subagents": ["safe_sql"],
        }
    ) == {
        "allow_subagent_delegation": True,
        "allowed_subagents": ["safe_sql"],
    }
    with pytest.raises(ValueError):
        normalize_tool_policy({"mode": "unknown"})
