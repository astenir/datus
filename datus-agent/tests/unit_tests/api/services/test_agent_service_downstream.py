"""Downstream tool-profile coverage for ``AgentService``."""

import pytest

from datus.api.services.agent_service import AgentService


@pytest.mark.parametrize("agent_type", ["gen_visual_report", "gen_visual_dashboard"])
def test_visual_artifact_types_use_registered_tool_profile(agent_type):
    result = AgentService.get_use_tools(agent_type)

    assert result.success is True
    assert result.data["default_tools"] == [
        "semantic_tools.*",
        "db_tools.*",
        "context_search_tools.*",
    ]
    assert set(result.data["tool_types"]) == {
        "db_tools",
        "semantic_tools",
        "context_search_tools",
    }
