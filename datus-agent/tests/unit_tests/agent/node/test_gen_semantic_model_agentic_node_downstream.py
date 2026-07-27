"""Downstream workspace-boundary coverage for semantic authoring."""

from pathlib import Path

from datus.agent.node.gen_semantic_model_agentic_node import GenSemanticModelAgenticNode


def test_project_authoring_root_ignores_request_workspace(real_agent_config, mock_llm_create, tmp_path):
    real_agent_config._request_workspace_root = str(tmp_path / "private" / "alice")
    try:
        node = GenSemanticModelAgenticNode(
            agent_config=real_agent_config,
            execution_mode="workflow",
        )

        assert node.filesystem_func_tool.root_path == str(Path(real_agent_config.project_root).expanduser())
    finally:
        del real_agent_config._request_workspace_root
