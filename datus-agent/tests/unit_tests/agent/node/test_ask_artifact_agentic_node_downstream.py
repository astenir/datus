"""Downstream interaction-tool coverage for ask-artifact nodes."""

from tests.unit_tests.agent.node.test_ask_artifact_agentic_node import (
    _make_ask_report_with_tools,
    _tool_names,
)


def test_interaction_wildcard_exposes_registered_controls(real_agent_config):
    """``tools.*`` keeps the node's session-local interaction surface."""
    node = _make_ask_report_with_tools(real_agent_config, "tools.*", name="ask_controls", slug="controls")

    assert {
        "ask_user",
        "confirm_plan",
        "todo_list",
        "todo_read",
        "todo_write",
        "todo_update",
    }.issubset(_tool_names(node))
