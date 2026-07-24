"""Downstream enterprise visual-dashboard authoring coverage."""

from pathlib import Path

import pytest

from datus.prompts.prompt_manager import get_prompt_manager
from datus.schemas.action_history import ActionHistoryManager, ActionStatus
from datus.schemas.gen_visual_dashboard_models import GenVisualDashboardNodeInput
from tests.unit_tests.agent.node.test_gen_visual_dashboard_agentic_node import (
    _make_node,
    _seed_dashboard_on_disk,
)
from tests.unit_tests.mock_llm_model import build_simple_response


def _render_prompt(real_agent_config, *, access_mode: str) -> str:
    return get_prompt_manager(agent_config=real_agent_config).render_template(
        template_name="gen_visual_dashboard_system",
        version=None,
        artifact_access_mode=access_mode,
        has_semantic_tools=False,
        has_db_tools=False,
        has_context_search_tools=False,
        has_ask_user_tool=False,
        has_task_tool=False,
        agent_config=real_agent_config,
        dashboard_slug=None,
        rules=[],
        agent_description="",
    )


def test_input_backed_init_includes_artifact_tools(real_agent_config, mock_llm_create):
    node = _make_node(
        real_agent_config,
        input_data=GenVisualDashboardNodeInput(user_message="编辑 existing_demo"),
    )
    tool_names = {tool.name for tool in node.tools}

    assert {"start_new_dashboard", "bind_existing_dashboard", "save_query_template", "validate_render"} <= tool_names


def test_enterprise_create_node_is_create_only_until_acl_binding(real_agent_config, mock_llm_create):
    real_agent_config._enterprise_enabled = True
    node = _make_node(
        real_agent_config,
        input_data=GenVisualDashboardNodeInput(user_message="创建仪表盘"),
    )
    tool_names = {tool.name for tool in node.tools}

    assert "start_new_dashboard" in tool_names
    assert "bind_existing_dashboard" not in tool_names
    result = node.filesystem_func_tool.write_file(
        "dashboards/not_authorized/render/app.jsx",
        "export default function App() {}\n",
    )
    assert result.success == 0
    assert "ACL-authorized binding" in (result.error or "")


def test_enterprise_create_prompt_does_not_require_slug_discovery(real_agent_config):
    prompt = _render_prompt(real_agent_config, access_mode="create")

    assert "Enterprise create-only dashboard session" in prompt
    assert "always** run `glob('dashboards/*')`" not in prompt
    assert "Use `glob('dashboards/*')` to discover existing slugs" not in prompt


def test_locked_edit_session_auto_binds_and_bootstraps(real_agent_config, mock_llm_create):
    node_name = "dashboard_edit__unit"
    slug = "existing_demo"
    artifact_dir = Path(real_agent_config.project_root) / "dashboards" / slug
    artifact_dir.mkdir(parents=True)
    real_agent_config.agentic_nodes[node_name] = {
        "node_class": "gen_visual_dashboard",
        "artifact_slug": slug,
        "edit_locked": True,
    }
    node = _make_node(real_agent_config, node_name=node_name)
    user_input = GenVisualDashboardNodeInput(user_message="看看这个仪表盘")
    node.input = user_input

    node._prepare_artifacts(user_input)

    assert node.dashboard_artifact_tools.dashboard_slug == slug
    assert node.dashboard_artifact_tools.mode == "edit"
    assert (artifact_dir / "manifest.json").is_file()
    assert (artifact_dir / "render").is_dir()
    assert (artifact_dir / "queries").is_dir()
    assert (artifact_dir / "analysis").is_dir()


@pytest.mark.asyncio
async def test_locked_edit_session_auto_validates_when_model_only_answers(real_agent_config, mock_llm_create):
    node_name = "dashboard_edit__unit"
    existing_slug = "existing_demo"
    _seed_dashboard_on_disk(Path(real_agent_config.project_root), existing_slug)
    real_agent_config.agentic_nodes[node_name] = {
        "node_class": "gen_visual_dashboard",
        "artifact_slug": existing_slug,
        "edit_locked": True,
    }
    mock_llm_create.reset(responses=[build_simple_response("这是一个已有仪表盘。")])

    node = _make_node(real_agent_config, node_name=node_name)
    node.input = GenVisualDashboardNodeInput(user_message="什么仪表盘？")

    actions = []
    async for action in node.execute_stream(ActionHistoryManager()):
        actions.append(action)

    final = actions[-1]
    assert final.status == ActionStatus.SUCCESS
    assert final.output["success"] is True
    assert final.output["dashboard_slug"] == existing_slug
    assert final.output["app_jsx_path"] == f"dashboards/{existing_slug}/render/app.jsx"
