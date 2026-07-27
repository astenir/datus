"""Downstream enterprise reference protection for MCP server removal."""

from unittest.mock import AsyncMock

import pytest

from datus.api.enterprise.defaults import InMemoryEnterpriseAgentStore
from datus.api.models.mcp_models import AddServerInput
from datus_enterprise.services.mcp_service import EnterpriseMCPService


@pytest.mark.asyncio
class TestMCPServerReferenceProtection:
    async def test_remove_server_blocks_enterprise_and_local_agent_references(self, real_agent_config):
        service = EnterpriseMCPService(agent_config=real_agent_config)
        service.add_server(AddServerInput(name="shared_mcp", type="stdio", command="echo"))
        real_agent_config.agentic_nodes = {
            **(real_agent_config.agentic_nodes or {}),
            "local_agent": {"mcp": "shared_mcp, other_mcp"},
        }
        agent_store = InMemoryEnterpriseAgentStore()
        await agent_store.put_agent(
            agent_id="enterprise_agent",
            payload={
                "name": "Enterprise Agent",
                "node_class": "gen_sql",
                "status": "draft",
                "mcp": ["shared_mcp"],
            },
        )

        result = await service.remove_server_if_unreferenced("shared_mcp", agent_store)

        assert result.success is False
        assert result.errorCode == "MCP_SERVER_IN_USE"
        assert result.data == {
            "server_name": "shared_mcp",
            "agents": [
                {
                    "agent_id": "enterprise_agent",
                    "name": "Enterprise Agent",
                    "status": "draft",
                    "source": "enterprise",
                },
                {
                    "agent_id": "local_agent",
                    "name": "local_agent",
                    "status": "configured",
                    "source": "local",
                },
            ],
        }
        assert service.manager.get_server_config("shared_mcp") is not None
        service.remove_server("shared_mcp")

    async def test_remove_server_fails_closed_when_reference_check_fails(self, real_agent_config):
        service = EnterpriseMCPService(agent_config=real_agent_config)
        service.add_server(AddServerInput(name="guarded_mcp", type="stdio", command="echo"))
        agent_store = AsyncMock()
        agent_store.list_agents.side_effect = RuntimeError("store unavailable")

        result = await service.remove_server_if_unreferenced("guarded_mcp", agent_store)

        assert result.success is False
        assert result.errorCode == "MCP_REFERENCE_CHECK_FAILED"
        assert service.manager.get_server_config("guarded_mcp") is not None
        service.remove_server("guarded_mcp")

    async def test_remove_server_succeeds_without_agent_references(self, real_agent_config):
        service = EnterpriseMCPService(agent_config=real_agent_config)
        service.add_server(AddServerInput(name="unused_mcp", type="stdio", command="echo"))

        result = await service.remove_server_if_unreferenced("unused_mcp", InMemoryEnterpriseAgentStore())

        assert result.success is True
        assert service.manager.get_server_config("unused_mcp") is None
