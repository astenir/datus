"""Downstream read-only coverage for the unified gen-job node."""


def test_enterprise_read_only_hides_transfer_query_result(real_agent_config, mock_llm_create):
    from datus.agent.node.gen_job_agentic_node import GenJobAgenticNode

    real_agent_config._enterprise_enabled = True
    node = GenJobAgenticNode(agent_config=real_agent_config, execution_mode="workflow")
    tool_names = {tool.name for tool in node.tools}

    assert node.db_func_tool.read_only is True
    assert "execute_sql" in tool_names
    assert "transfer_query_result" not in tool_names
