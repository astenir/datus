"""Downstream enterprise visual-report authoring coverage."""

from pathlib import Path

from datus.prompts.prompt_manager import get_prompt_manager
from datus.schemas.gen_visual_report_models import GenVisualReportNodeInput
from tests.unit_tests.agent.node.test_gen_visual_report_agentic_node import _make_node


def _render_prompt(real_agent_config, *, access_mode: str, version: str | None = None) -> str:
    return get_prompt_manager(agent_config=real_agent_config).render_template(
        template_name="gen_visual_report_system",
        version=version,
        artifact_access_mode=access_mode,
        has_semantic_tools=False,
        has_db_tools=False,
        has_context_search_tools=False,
        has_ask_user_tool=False,
        has_task_tool=False,
        agent_config=real_agent_config,
        report_slug=None,
        rules=[],
        agent_description="",
    )


def test_input_backed_init_includes_artifact_tools(real_agent_config, mock_llm_create):
    node = _make_node(
        real_agent_config,
        input_data=GenVisualReportNodeInput(user_message="编辑 existing_demo"),
    )
    tool_names = {tool.name for tool in node.tools}

    assert {"start_new_report", "bind_existing_report", "save_query", "validate_render"} <= tool_names


def test_enterprise_create_node_is_create_only_until_acl_binding(real_agent_config, mock_llm_create):
    real_agent_config._enterprise_enabled = True
    node = _make_node(
        real_agent_config,
        input_data=GenVisualReportNodeInput(user_message="创建报告"),
    )
    tool_names = {tool.name for tool in node.tools}

    assert "start_new_report" in tool_names
    assert "bind_existing_report" not in tool_names
    result = node.filesystem_func_tool.write_file(
        "reports/not_authorized/render/app.jsx",
        "export default function App() {}\n",
    )
    assert result.success == 0
    assert "ACL-authorized binding" in (result.error or "")


def test_enterprise_create_prompt_does_not_require_slug_discovery(real_agent_config):
    prompt = _render_prompt(real_agent_config, access_mode="create")

    assert "Enterprise create-only report session" in prompt
    assert "always** run `glob('reports/*')`" not in prompt
    assert "Use `glob('reports/*')` to discover existing slugs" not in prompt


def test_local_prompt_keeps_slug_discovery(real_agent_config):
    prompt = _render_prompt(real_agent_config, access_mode="legacy", version="1.0")

    assert "always** run `glob('reports/*')`" in prompt


def test_locked_edit_session_auto_binds_and_bootstraps(real_agent_config, mock_llm_create):
    node_name = "report_edit__unit"
    slug = "existing_demo"
    artifact_dir = Path(real_agent_config.project_root) / "reports" / slug
    artifact_dir.mkdir(parents=True)
    real_agent_config.agentic_nodes[node_name] = {
        "node_class": "gen_visual_report",
        "artifact_slug": slug,
        "edit_locked": True,
    }
    node = _make_node(real_agent_config, node_name=node_name)
    user_input = GenVisualReportNodeInput(user_message="看看这个报表")
    node.input = user_input

    node._prepare_artifacts(user_input)

    assert node.report_artifact_tools.report_slug == slug
    assert node.report_artifact_tools.mode == "edit"
    assert (artifact_dir / "manifest.json").is_file()
    assert (artifact_dir / "render").is_dir()
    assert (artifact_dir / "queries").is_dir()
    assert (artifact_dir / "analysis").is_dir()
