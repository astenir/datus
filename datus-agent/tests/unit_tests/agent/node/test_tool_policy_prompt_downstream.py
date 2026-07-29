"""Downstream regressions for Tool Policy and prompt-surface consistency."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from datus.agent.node_capabilities import get_agent_node_capability
from datus.agent.tool_policy import apply_agent_runtime_policy
from datus.configuration.node_type import NodeType


def test_prompt_capability_flags_do_not_read_instantiated_tool_objects():
    """Prompt flags must describe final ``self.tools``, not cached wrappers."""

    node_dir = Path(__file__).parents[4] / "datus" / "agent" / "node"
    forbidden_fragments = (
        '"has_ask_user_tool": self.ask_user_tool is not None',
        '"has_ask_user_tool": bool(self.ask_user_tool)',
        'context["has_ask_user_tool"] = self.ask_user_tool is not None',
        '"has_task_tool": bool(self.sub_agent_task_tool)',
        '"has_db_tools": bool(self.db_func_tool)',
        '"has_filesystem_tools": bool(self.filesystem_func_tool)',
        '"has_bi_tools": self.bi_func_tool is not None',
        '"has_skill_tools": bool(self.skill_func_tool_instance)',
    )

    offenders = []
    for source_path in node_dir.glob("*.py"):
        source = source_path.read_text(encoding="utf-8")
        for fragment in forbidden_fragments:
            if fragment in source:
                offenders.append(f"{source_path.name}: {fragment}")

    assert offenders == []


def _capture_prompt_context(node) -> dict:
    with patch("datus.prompts.prompt_manager.get_prompt_manager") as get_prompt_manager:
        prompt_manager = MagicMock()
        prompt_manager.render_template.return_value = "rendered prompt"
        get_prompt_manager.return_value = prompt_manager
        node._get_system_prompt()
    return prompt_manager.render_template.call_args.kwargs


def _apply_interaction_only_policy(node) -> None:
    node.node_config["tool_policy"] = {
        "mode": "allowlist",
        "allowed": ["tools.*"],
        "denied": [],
    }
    node.node_config["runtime_policy"] = {
        "allow_subagent_delegation": False,
        "allowed_subagents": [],
    }
    apply_agent_runtime_policy(node)


def test_gen_sql_prompt_flags_follow_policy_filtered_tools(real_agent_config, mock_llm_create):
    from datus.agent.node.gen_sql_agentic_node import GenSQLAgenticNode

    node = GenSQLAgenticNode(
        node_id="gen_sql_policy_prompt",
        description="Tool Policy prompt regression",
        node_type=NodeType.TYPE_GEN_SQL,
        agent_config=real_agent_config,
        node_name="gen_sql",
    )
    _apply_interaction_only_policy(node)

    context = _capture_prompt_context(node)

    assert context["has_db_tools"] is False
    assert context["has_filesystem_tools"] is False
    assert context["has_context_search_tools"] is False
    assert context["has_platform_doc_tools"] is False
    assert context["has_task_tool"] is False
    assert context["has_ask_user_tool"] is True


def test_gen_report_prompt_flags_follow_policy_filtered_tools(real_agent_config, mock_llm_create):
    from datus.agent.node.gen_report_agentic_node import GenReportAgenticNode

    node = GenReportAgenticNode(
        node_id="gen_report_policy_prompt",
        description="Tool Policy prompt regression",
        node_type=NodeType.TYPE_GEN_REPORT,
        agent_config=real_agent_config,
        node_name="gen_report",
    )
    _apply_interaction_only_policy(node)

    context = _capture_prompt_context(node)

    assert context["has_semantic_tools"] is False
    assert context["has_db_tools"] is False
    assert context["has_task_tool"] is False
    assert context["has_ask_user_tool"] is True


@pytest.mark.parametrize(
    ("node_type", "node_class", "module_name", "class_name"),
    [
        (
            NodeType.TYPE_GEN_VISUAL_REPORT,
            "gen_visual_report",
            "datus.agent.node.gen_visual_report_agentic_node",
            "GenVisualReportAgenticNode",
        ),
        (
            NodeType.TYPE_GEN_VISUAL_DASHBOARD,
            "gen_visual_dashboard",
            "datus.agent.node.gen_visual_dashboard_agentic_node",
            "GenVisualDashboardAgenticNode",
        ),
    ],
)
def test_visual_prompt_flags_follow_policy_filtered_tools(
    real_agent_config,
    mock_llm_create,
    node_type,
    node_class,
    module_name,
    class_name,
):
    module = __import__(module_name, fromlist=[class_name])
    node_cls = getattr(module, class_name)
    node = node_cls(
        node_id=f"{node_class}_policy_prompt",
        description="Tool Policy prompt regression",
        node_type=node_type,
        agent_config=real_agent_config,
        node_name=node_class,
    )
    _apply_interaction_only_policy(node)

    context = _capture_prompt_context(node)

    assert context["has_semantic_tools"] is False
    assert context["has_db_tools"] is False
    assert context["has_context_search_tools"] is False
    assert context["has_task_tool"] is False
    assert context["has_ask_user_tool"] is True


@pytest.mark.parametrize(
    ("node_type", "node_class", "module_name", "class_name", "input_module", "input_class", "required_tools"),
    [
        (
            NodeType.TYPE_GEN_VISUAL_REPORT,
            "gen_visual_report",
            "datus.agent.node.gen_visual_report_agentic_node",
            "GenVisualReportAgenticNode",
            "datus.schemas.gen_visual_report_models",
            "GenVisualReportNodeInput",
            {"write_file", "start_new_report", "save_query", "validate_render"},
        ),
        (
            NodeType.TYPE_GEN_VISUAL_DASHBOARD,
            "gen_visual_dashboard",
            "datus.agent.node.gen_visual_dashboard_agentic_node",
            "GenVisualDashboardAgenticNode",
            "datus.schemas.gen_visual_dashboard_models",
            "GenVisualDashboardNodeInput",
            {"write_file", "start_new_dashboard", "save_query_template", "validate_render"},
        ),
    ],
)
def test_visual_default_allowlist_keeps_required_authoring_tools(
    real_agent_config,
    mock_llm_create,
    node_type,
    node_class,
    module_name,
    class_name,
    input_module,
    input_class,
    required_tools,
):
    module = __import__(module_name, fromlist=[class_name])
    node_cls = getattr(module, class_name)
    input_model_module = __import__(input_module, fromlist=[input_class])
    input_model = getattr(input_model_module, input_class)
    node = node_cls(
        node_id=f"{node_class}_default_policy",
        description="Default Tool Policy regression",
        node_type=node_type,
        agent_config=real_agent_config,
        node_name=node_class,
    )
    node.input = input_model(user_message="Create an artifact")
    node._prepare_artifacts(node.input)
    capability = get_agent_node_capability(node_class)
    assert capability is not None
    node.node_config["tool_policy"] = {
        "mode": "allowlist",
        "allowed": list(capability.default_tools),
        "denied": [],
    }
    node.node_config["runtime_policy"] = {
        "allow_subagent_delegation": False,
        "allowed_subagents": [],
    }

    apply_agent_runtime_policy(node)

    assert required_tools.issubset({tool.name for tool in node.tools})
