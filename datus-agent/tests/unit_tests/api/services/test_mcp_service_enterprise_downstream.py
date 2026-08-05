"""Downstream enterprise reference protection for MCP server removal."""

from unittest.mock import AsyncMock

import pytest

from datus.api.enterprise.defaults import InMemoryEnterpriseAgentStore
from datus.api.models.downstream import UpdateServerInput
from datus.api.models.mcp_models import AddServerInput, MCPAuthInput
from datus_enterprise.services.mcp_service import EnterpriseMCPService


class TestMCPServerAuthUpdate:
    def test_blank_static_token_preserves_existing_credential(self, real_agent_config):
        service = EnterpriseMCPService(agent_config=real_agent_config)
        service.add_server(
            AddServerInput(
                name="secured",
                type="http",
                url="http://example.com/mcp",
                auth=MCPAuthInput(mode="static_bearer", token="original-value"),
            )
        )

        result = service.update_server(
            "secured",
            UpdateServerInput(
                type="http",
                url="http://example.com/v2/mcp",
                auth=MCPAuthInput(mode="static_bearer", token=""),
            ),
        )

        assert result.success is True
        updated = service.manager.get_server_config("secured")
        assert updated.auth.token == "original-value"
        assert "original-value" not in str(result.model_dump())

    def test_switch_to_request_bearer_removes_static_credential(self, real_agent_config):
        service = EnterpriseMCPService(agent_config=real_agent_config)
        service.add_server(
            AddServerInput(
                name="secured",
                type="http",
                url="http://example.com/mcp",
                auth=MCPAuthInput(mode="static_bearer", token="old-value"),
            )
        )

        result = service.update_server(
            "secured",
            UpdateServerInput(
                type="http",
                url="http://example.com/mcp",
                auth=MCPAuthInput(mode="request_bearer"),
            ),
        )

        assert result.success is True
        updated = service.manager.get_server_config("secured")
        assert updated.auth.mode == "request_bearer"
        assert updated.auth.token is None
        assert "old-value" not in service.manager.config_path.read_text()


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
