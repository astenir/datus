"""Regression tests for the canonical Agent node capability registry."""

from types import SimpleNamespace

import pytest

from datus.agent.node.node_factory import create_interactive_node
from datus.agent.node_capabilities import (
    AGENT_NODE_CAPABILITIES,
    cli_agent_node_capabilities,
    enterprise_agent_node_capabilities,
    get_agent_node_capability,
    tool_editor_node_capabilities,
)
from datus.utils.constants import SYS_SUB_AGENTS


def test_registry_has_unique_classes_and_covers_system_subagents():
    registered = [capability.node_class for capability in AGENT_NODE_CAPABILITIES]

    assert len(registered) == len(set(registered))
    assert SYS_SUB_AGENTS <= set(registered)


def test_enterprise_surface_contains_only_customizable_editor_types():
    enterprise = enterprise_agent_node_capabilities()
    tool_editor_classes = {capability.node_class for capability in tool_editor_node_capabilities()}

    assert [capability.node_class for capability in enterprise] == [
        "chat",
        "gen_sql",
        "gen_report",
        "gen_visual_report",
        "gen_visual_dashboard",
        "ask_metrics",
        "ask_report",
        "ask_dashboard",
    ]
    assert all(capability.customizable and capability.enterprise_visible for capability in enterprise)
    assert {capability.node_class for capability in enterprise} <= tool_editor_classes


def test_cli_surface_is_derived_from_the_same_registry():
    assert [capability.node_class for capability in cli_agent_node_capabilities()] == [
        "gen_sql",
        "gen_report",
        "gen_visual_report",
        "gen_visual_dashboard",
    ]


def test_registry_owns_permissions_and_prompt_templates():
    assert get_agent_node_capability("gen_visual_report").module_permission == "module.report.query"
    assert get_agent_node_capability("gen_visual_dashboard").module_permission == "module.dashboard.query"
    assert get_agent_node_capability("gen_skill").prompt_template == "skill_creator_system"
    assert get_agent_node_capability("gen_semantic_model").customizable is False


def test_runtime_rejects_internal_node_class_for_custom_alias():
    agent_config = SimpleNamespace(
        agentic_nodes={"custom_semantic": {"node_class": "gen_semantic_model"}},
    )

    with pytest.raises(ValueError, match="Unsupported custom Agent node_class 'gen_semantic_model'"):
        create_interactive_node("custom_semantic", agent_config)
