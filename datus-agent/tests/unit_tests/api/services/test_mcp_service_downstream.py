"""Downstream MCP service coverage kept out of the upstream test file."""

from datus.api.models.downstream import UpdateServerInput
from datus.api.models.mcp_models import AddServerInput
from datus_enterprise.services.mcp_service import EnterpriseMCPService


def test_update_server_replaces_existing_config(real_agent_config):
    svc = EnterpriseMCPService(agent_config=real_agent_config)
    svc.add_server(AddServerInput(name="to_update", type="stdio", command="echo"))

    result = svc.update_server("to_update", UpdateServerInput(type="stdio", command="node", cwd="/workspace"))

    assert result.success is True
    assert result.data["server"]["command"] == "node"
    assert result.data["server"]["cwd"] == "/workspace"
    svc.remove_server("to_update")


def test_update_nonexistent_server(real_agent_config):
    svc = EnterpriseMCPService(agent_config=real_agent_config)

    result = svc.update_server("ghost_server", UpdateServerInput(type="stdio", command="echo"))

    assert result.success is False
