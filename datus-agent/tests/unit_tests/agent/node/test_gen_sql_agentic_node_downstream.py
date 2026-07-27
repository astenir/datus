"""Downstream degraded-capability coverage for GenSQL MCP setup."""

from unittest.mock import MagicMock, patch

from datus.agent.node.gen_sql_agentic_node import GenSQLAgenticNode
from datus.configuration.node_type import NodeType


def _make_node(real_agent_config):
    return GenSQLAgenticNode(
        node_id="gen_sql_downstream",
        description="Downstream gen_sql test",
        node_type=NodeType.TYPE_GEN_SQL,
        agent_config=real_agent_config,
        node_name="gen_sql",
    )


def test_mcp_instance_creation_failure_records_degraded_capability(real_agent_config, mock_llm_create):
    node = _make_node(real_agent_config)
    manager = MagicMock()
    manager.get_server_config.return_value = MagicMock()
    manager._create_server_instance.return_value = (None, {"error": "invalid transport config"})

    with patch("datus.tools.mcp_tools.mcp_manager.MCPManager", return_value=manager):
        result = node._setup_mcp_server_from_config("broken_server")

    assert result is None
    assert node.degraded_capabilities["mcp.broken_server"] == (
        "MCP Server 'broken_server' could not be initialized: invalid transport config"
    )
