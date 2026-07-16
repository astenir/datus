"""Tests for datus.api.services.mcp_service — MCP tool management."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from datus.api.enterprise.defaults import InMemoryEnterpriseAgentStore
from datus.api.models.base_models import Result
from datus.api.models.mcp_models import AddServerInput, ToolFilterInput
from datus.api.services.mcp_service import MCPService


class TestMCPServiceInit:
    """Tests for MCPService initialization."""

    def test_init_with_real_config(self, real_agent_config):
        """MCPService initializes with real agent config."""
        svc = MCPService(agent_config=real_agent_config)
        assert isinstance(svc, MCPService)
        assert svc.manager.config_path == Path(real_agent_config.home) / "conf" / ".mcp.json"


class TestMCPServiceListServers:
    """Tests for list_servers."""

    def test_list_servers_returns_result(self, real_agent_config):
        """list_servers returns a Result object."""
        svc = MCPService(agent_config=real_agent_config)
        result = svc.list_servers()
        assert result.success is True

    def test_list_servers_with_type_filter(self, real_agent_config):
        """list_servers with type filter returns Result."""
        svc = MCPService(agent_config=real_agent_config)
        result = svc.list_servers(server_type="stdio")
        assert result.success is True

    def test_list_servers_returns_dict_data(self, real_agent_config):
        """list_servers data is a dict (possibly empty)."""
        svc = MCPService(agent_config=real_agent_config)
        result = svc.list_servers()
        assert isinstance(result.data, dict)


class TestMCPServiceAddRemoveServer:
    """Tests for add_server and remove_server."""

    def test_add_server_stdio(self, real_agent_config):
        """add_server creates a new stdio server config."""
        svc = MCPService(agent_config=real_agent_config)
        request = AddServerInput(
            name="test_server",
            type="stdio",
            command="echo",
            args=["hello"],
        )
        result = svc.add_server(request)
        assert result.success is True

    def test_remove_server(self, real_agent_config):
        """remove_server removes a server config."""
        svc = MCPService(agent_config=real_agent_config)
        svc.add_server(AddServerInput(name="to_remove", type="stdio", command="echo"))
        result = svc.remove_server("to_remove")
        assert result.success is True

    def test_remove_nonexistent_server(self, real_agent_config):
        """remove_server for nonexistent server returns error."""
        svc = MCPService(agent_config=real_agent_config)
        result = svc.remove_server("ghost_server")
        assert result.success is False


class TestMCPServiceToolFilter:
    """Tests for tool filter operations."""

    def test_get_tool_filter_nonexistent(self, real_agent_config):
        """get_tool_filter for nonexistent server returns error."""
        svc = MCPService(agent_config=real_agent_config)
        result = svc.get_tool_filter("nonexistent")
        assert result.success is False

    def test_remove_tool_filter_nonexistent(self, real_agent_config):
        """remove_tool_filter for nonexistent server returns error."""
        svc = MCPService(agent_config=real_agent_config)
        result = svc.remove_tool_filter("nonexistent")
        assert result.success is False

    def test_set_tool_filter_nonexistent(self, real_agent_config):
        """set_tool_filter for nonexistent server returns error."""
        svc = MCPService(agent_config=real_agent_config)
        result = svc.set_tool_filter("nonexistent", ToolFilterInput(allowed_tools=["tool1"]))
        assert result.success is False


@pytest.mark.asyncio
class TestMCPServiceAsync:
    """Tests for async MCP operations."""

    async def test_check_connectivity_nonexistent(self, real_agent_config):
        """check_connectivity for nonexistent server returns error."""
        svc = MCPService(agent_config=real_agent_config)
        result = await svc.check_connectivity("nonexistent_server")
        assert result.success is False

    async def test_list_tools_nonexistent(self, real_agent_config):
        """list_tools for nonexistent server returns error."""
        svc = MCPService(agent_config=real_agent_config)
        result = await svc.list_tools("nonexistent_server")
        assert result.success is False

    async def test_call_tool_nonexistent(self, real_agent_config):
        """call_tool for nonexistent server returns error."""
        from datus.api.models.mcp_models import CallToolInput

        svc = MCPService(agent_config=real_agent_config)
        result = await svc.call_tool("nonexistent", "some_tool", CallToolInput())
        assert result.success is False

    async def test_remove_server_blocks_enterprise_and_local_agent_references(self, real_agent_config):
        svc = MCPService(agent_config=real_agent_config)
        svc.add_server(AddServerInput(name="shared_mcp", type="stdio", command="echo"))
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

        result = await svc.remove_server_if_unreferenced("shared_mcp", agent_store)

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
        assert svc.manager.get_server_config("shared_mcp") is not None
        svc.remove_server("shared_mcp")

    async def test_remove_server_fails_closed_when_reference_check_fails(self, real_agent_config):
        svc = MCPService(agent_config=real_agent_config)
        svc.add_server(AddServerInput(name="guarded_mcp", type="stdio", command="echo"))
        agent_store = AsyncMock()
        agent_store.list_agents.side_effect = RuntimeError("store unavailable")

        result = await svc.remove_server_if_unreferenced("guarded_mcp", agent_store)

        assert result.success is False
        assert result.errorCode == "MCP_REFERENCE_CHECK_FAILED"
        assert svc.manager.get_server_config("guarded_mcp") is not None
        svc.remove_server("guarded_mcp")

    async def test_remove_server_succeeds_without_agent_references(self, real_agent_config):
        svc = MCPService(agent_config=real_agent_config)
        svc.add_server(AddServerInput(name="unused_mcp", type="stdio", command="echo"))

        result = await svc.remove_server_if_unreferenced("unused_mcp", InMemoryEnterpriseAgentStore())

        assert result.success is True
        assert svc.manager.get_server_config("unused_mcp") is None


class TestMCPServiceWithServer:
    """Tests for MCP operations with a real added server."""

    def test_full_server_lifecycle(self, real_agent_config):
        """Add server, list, get filter, remove filter, remove server."""
        svc = MCPService(agent_config=real_agent_config)

        # Add server
        add_result = svc.add_server(AddServerInput(name="lifecycle_srv", type="stdio", command="echo"))
        assert add_result.success is True

        # List servers should include it
        list_result = svc.list_servers()
        assert list_result.success is True
        assert "lifecycle_srv" in str(list_result.data)

        # Get tool filter (should work now that server exists)
        filter_result = svc.get_tool_filter("lifecycle_srv")
        assert isinstance(filter_result, Result)
        assert filter_result.success is True
        assert filter_result.data["filter"] is None

        # Set tool filter
        set_result = svc.set_tool_filter("lifecycle_srv", ToolFilterInput(allowed_tools=["tool_a"]))
        assert set_result.success is True
        assert set_result.data["filter"]["allowed_tool_names"] == ["tool_a"]

        # Remove tool filter
        rm_filter_result = svc.remove_tool_filter("lifecycle_srv")
        assert rm_filter_result.success is True
        assert rm_filter_result.data == {
            "server_name": "lifecycle_srv",
            "message": "Tool filter removed",
        }

        # Remove server
        rm_result = svc.remove_server("lifecycle_srv")
        assert rm_result.success is True

    def test_add_server_duplicate(self, real_agent_config):
        """add_server with duplicate name returns error."""
        svc = MCPService(agent_config=real_agent_config)
        svc.add_server(AddServerInput(name="dup_srv", type="stdio", command="echo"))
        result = svc.add_server(AddServerInput(name="dup_srv", type="stdio", command="echo"))
        assert result.success is False
        # Clean up
        svc.remove_server("dup_srv")
