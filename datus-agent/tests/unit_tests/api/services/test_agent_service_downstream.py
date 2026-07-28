"""Downstream tool-profile coverage for ``AgentService``."""

import pytest

from datus.agent.node_capabilities import get_agent_node_capability
from datus.api.services.agent_service import AgentService, _validate_tools, _validate_tools_for_agent_type


@pytest.mark.parametrize("agent_type", ["gen_visual_report", "gen_visual_dashboard"])
def test_visual_artifact_types_use_registered_tool_profile(agent_type):
    result = AgentService.get_use_tools(agent_type)

    assert result.success is True
    capability = get_agent_node_capability(agent_type)
    assert capability is not None
    assert result.data["default_tools"] == list(capability.default_tools)
    assert set(result.data["tool_types"]) == {
        "db_tools",
        "semantic_tools",
        "context_search_tools",
        "filesystem_tools",
        "artifact_tools",
        "tools",
    }
    assert "tools.*" in result.data["default_tools"]
    assert any(tool.startswith("filesystem_tools.") for tool in result.data["default_tools"])
    assert any(tool.startswith("artifact_tools.") for tool in result.data["default_tools"])


@pytest.mark.parametrize(
    "agent_type",
    ["chat", "gen_sql", "gen_report", "gen_visual_report", "gen_visual_dashboard", "ask_report", "ask_dashboard"],
)
def test_interactive_agent_profiles_enable_interaction_tools_by_default(agent_type):
    result = AgentService.get_use_tools(agent_type)

    assert result.success is True
    assert "tools.*" in result.data["default_tools"]
    assert result.data["tool_types"]["tools"]["tools"] == [
        "ask_user",
        "confirm_plan",
        "todo_list",
        "todo_read",
        "todo_update",
        "todo_write",
    ]


def test_chat_tool_catalog_expands_every_default_category():
    result = AgentService.get_use_tools("chat")

    assert result.success is True
    assert "platform_doc_tools" in result.data["tool_types"]
    assert result.data["tool_types"]["platform_doc_tools"]["tools"]
    assert all(pattern.split(".", 1)[0] in result.data["tool_types"] for pattern in result.data["default_tools"])


@pytest.mark.parametrize(
    "agent_type",
    [
        "chat",
        "gen_sql",
        "gen_report",
        "gen_visual_report",
        "gen_visual_dashboard",
        "ask_metrics",
        "ask_report",
        "ask_dashboard",
    ],
)
def test_every_editor_default_resolves_and_passes_node_gate(agent_type):
    capability = get_agent_node_capability(agent_type)
    assert capability is not None
    defaults = list(capability.default_tools)

    assert _validate_tools(defaults) == []
    assert _validate_tools_for_agent_type(defaults, agent_type) == []
