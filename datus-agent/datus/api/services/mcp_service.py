"""
Service for handling MCP (Model Context Protocol) operations.

Stateless per-request service that wraps MCPManager with a tenant-specific
config path derived from the agent_config.
"""

from pathlib import Path
from typing import Any, Dict, Optional

from datus.api.enterprise.protocols import EnterpriseAgentStore
from datus.api.models.base_models import Result
from datus.api.models.mcp_models import AddServerInput, CallToolInput, ToolFilterInput, UpdateServerInput
from datus.configuration.agent_config import AgentConfig
from datus.tools.mcp_tools.mcp_config import MCPServerConfig, MCPServerType, ToolFilterConfig
from datus.tools.mcp_tools.mcp_manager import MCPManager
from datus.utils.loggings import get_logger

logger = get_logger(__name__)


def _normalize_mcp_names(value: Any) -> set[str]:
    """Normalize persisted MCP bindings from CSV or list form."""
    if isinstance(value, str):
        items = value.split(",")
    elif isinstance(value, (list, tuple, set)):
        items = value
    else:
        return set()
    return {str(item).strip() for item in items if str(item).strip()}


class MCPService:
    """
    Stateless MCP service scoped to a single tenant/project.

    Each request creates a fresh instance with the correct config path
    derived from ``agent_config.home``.
    """

    def __init__(self, agent_config: AgentConfig):
        self.agent_config = agent_config
        self.manager = self._create_manager(agent_config)

    # ------------------------------------------------------------------
    # Factory helper
    # ------------------------------------------------------------------

    @staticmethod
    def _create_manager(agent_config: AgentConfig) -> MCPManager:
        """Create an MCPManager whose config_path points to the tenant's home."""
        config_path = Path(agent_config.home) / "conf" / ".mcp.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)

        manager = MCPManager.__new__(MCPManager)
        # Replicate the fields that __init__ normally sets, but with our
        # custom config_path instead of the global singleton path.
        import threading

        from datus.tools.mcp_tools.mcp_config import MCPConfig

        manager.config_path = config_path
        manager.config = MCPConfig()
        manager._lock = threading.Lock()
        manager.load_config()

        logger.info(f"Created MCPManager with config path: {config_path}")
        return manager

    # ------------------------------------------------------------------
    # Server CRUD
    # ------------------------------------------------------------------

    def list_servers(self, server_type: Optional[str] = None) -> Result[Dict[str, Any]]:
        """List all MCP servers with optional filtering by type."""
        try:
            mcp_server_type = MCPServerType(server_type) if server_type else None
            servers = self.manager.list_servers(server_type=mcp_server_type)
            servers_data = [s.model_dump() for s in servers]
            return Result(success=True, data={"servers": servers_data, "total": len(servers_data)})
        except ValueError:
            return Result(success=False, errorMessage=f"Invalid server type: {server_type}")
        except Exception as e:
            logger.error(f"Error listing servers: {e}")
            return Result(success=False, errorMessage=f"Error listing servers: {e}")

    def add_server(self, server_input: AddServerInput) -> Result[Dict[str, Any]]:
        """Add a new MCP server configuration."""
        try:
            config_data = server_input.model_dump(exclude_none=True)
            name = config_data.pop("name")
            server_config = MCPServerConfig.from_config_format(name, config_data)

            success, message = self.manager.add_server(server_config)
            if success:
                return Result(success=True, data={"server": server_config.model_dump(), "message": message})
            return Result(success=False, errorMessage=message)
        except Exception as e:
            logger.error(f"Error adding server: {e}")
            return Result(success=False, errorMessage=f"Error adding server: {e}")

    def update_server(self, server_name: str, server_input: UpdateServerInput) -> Result[Dict[str, Any]]:
        """Update an existing MCP server configuration."""
        try:
            config_data = server_input.model_dump(exclude_none=True)
            server_config = MCPServerConfig.from_config_format(server_name, config_data)

            success, message = self.manager.update_server(server_name, server_config)
            if success:
                return Result(success=True, data={"server": server_config.model_dump(), "message": message})
            return Result(success=False, errorMessage=message)
        except Exception as e:
            logger.error(f"Error updating server: {e}")
            return Result(success=False, errorMessage=f"Error updating server: {e}")

    def remove_server(self, server_name: str) -> Result[Dict[str, Any]]:
        """Remove an MCP server configuration."""
        try:
            success, message = self.manager.remove_server(server_name)
            if success:
                return Result(success=True, data={"message": message})
            return Result(success=False, errorMessage=message)
        except Exception as e:
            logger.error(f"Error removing server: {e}")
            return Result(success=False, errorMessage=f"Error removing server: {e}")

    async def remove_server_if_unreferenced(
        self,
        server_name: str,
        agent_store: EnterpriseAgentStore,
    ) -> Result[Dict[str, Any]]:
        """Remove a server only when no configured Agent still references it."""
        references = await self._list_agent_references(server_name, agent_store)
        if not references.success:
            return references

        agents = (references.data or {}).get("agents", [])
        if agents:
            agent_names = ", ".join(str(agent.get("name") or agent.get("agent_id")) for agent in agents)
            return Result(
                success=False,
                data={"server_name": server_name, "agents": agents},
                errorCode="MCP_SERVER_IN_USE",
                errorMessage=(
                    f"MCP Server '{server_name}' is still referenced by Agent(s): {agent_names}. "
                    "Remove the Agent bindings before deleting the Server."
                ),
            )

        return self.remove_server(server_name)

    async def _list_agent_references(
        self,
        server_name: str,
        agent_store: EnterpriseAgentStore,
    ) -> Result[Dict[str, Any]]:
        """Return enterprise and local Agent definitions that reference a server."""
        try:
            records = await agent_store.list_agents(status=None)
        except Exception as e:
            logger.error(f"Error checking Agent references for MCP server '{server_name}': {e}")
            return Result(
                success=False,
                errorCode="MCP_REFERENCE_CHECK_FAILED",
                errorMessage="Unable to verify whether the MCP Server is still referenced by an Agent.",
            )

        references: dict[str, dict[str, Any]] = {}
        for record in records:
            agent_id = str(record.get("agent_id") or "").strip()
            if not agent_id or server_name not in _normalize_mcp_names(record.get("mcp")):
                continue
            references[agent_id] = {
                "agent_id": agent_id,
                "name": str(record.get("name") or agent_id),
                "status": str(record.get("status") or ""),
                "source": "enterprise",
            }

        for agent_id, node in (self.agent_config.agentic_nodes or {}).items():
            if not isinstance(node, dict) or server_name not in _normalize_mcp_names(node.get("mcp")):
                continue
            normalized_id = str(agent_id)
            references.setdefault(
                normalized_id,
                {
                    "agent_id": normalized_id,
                    "name": normalized_id,
                    "status": "configured",
                    "source": "local",
                },
            )

        return Result(
            success=True,
            data={
                "server_name": server_name,
                "agents": sorted(references.values(), key=lambda agent: str(agent["agent_id"])),
            },
        )

    # ------------------------------------------------------------------
    # Connectivity & Tools
    # ------------------------------------------------------------------

    async def check_connectivity(self, server_name: str) -> Result[Dict[str, Any]]:
        """Check connectivity status of an MCP server."""
        try:
            success, message, details = await self.manager.check_connectivity(server_name)
            if success:
                return Result(
                    success=True,
                    data={"server_name": server_name, "status": "connected", "message": message, **details},
                )
            return Result(success=False, errorMessage=message)
        except Exception as e:
            logger.error(f"Error checking connectivity: {e}")
            return Result(success=False, errorMessage=f"Error checking connectivity: {e}")

    async def list_tools(self, server_name: str, apply_filter: bool = True) -> Result[Dict[str, Any]]:
        """List tools available on an MCP server."""
        try:
            success, message, tools = await self.manager.list_tools(server_name, apply_filter=apply_filter)
            if success:
                return Result(
                    success=True,
                    data={"server_name": server_name, "tools": tools, "total": len(tools), "message": message},
                )
            return Result(success=False, errorMessage=message)
        except Exception as e:
            logger.error(f"Error listing tools: {e}")
            return Result(success=False, errorMessage=f"Error listing tools: {e}")

    async def call_tool(self, server_name: str, tool_name: str, request: CallToolInput) -> Result[Dict[str, Any]]:
        """Call a tool on an MCP server."""
        try:
            success, message, result = await self.manager.call_tool(server_name, tool_name, request.parameters)
            if success:
                return Result(
                    success=True,
                    data={"server_name": server_name, "tool_name": tool_name, "result": result, "message": message},
                )
            return Result(success=False, errorMessage=message)
        except Exception as e:
            logger.error(f"Error calling tool: {e}")
            return Result(success=False, errorMessage=f"Error calling tool: {e}")

    # ------------------------------------------------------------------
    # Tool Filters
    # ------------------------------------------------------------------

    def get_tool_filter(self, server_name: str) -> Result[Dict[str, Any]]:
        """Get tool filter configuration for an MCP server."""
        try:
            success, message, tool_filter = self.manager.get_tool_filter(server_name)
            if success:
                filter_data = tool_filter.model_dump() if tool_filter else None
                return Result(
                    success=True, data={"server_name": server_name, "filter": filter_data, "message": message}
                )
            return Result(success=False, errorMessage=message)
        except Exception as e:
            logger.error(f"Error getting tool filter: {e}")
            return Result(success=False, errorMessage=f"Error getting tool filter: {e}")

    def set_tool_filter(self, server_name: str, filter_input: ToolFilterInput) -> Result[Dict[str, Any]]:
        """Set tool filter configuration for an MCP server."""
        try:
            tool_filter = ToolFilterConfig(
                enabled=filter_input.enabled,
                allowed_tool_names=filter_input.allowed_tools,
                blocked_tool_names=filter_input.blocked_tools,
            )
            success, message = self.manager.set_tool_filter(server_name, tool_filter)
            if success:
                return Result(
                    success=True,
                    data={"server_name": server_name, "filter": tool_filter.model_dump(), "message": message},
                )
            return Result(success=False, errorMessage=message)
        except Exception as e:
            logger.error(f"Error setting tool filter: {e}")
            return Result(success=False, errorMessage=f"Error setting tool filter: {e}")

    def remove_tool_filter(self, server_name: str) -> Result[Dict[str, Any]]:
        """Remove tool filter configuration from an MCP server."""
        try:
            tool_filter = ToolFilterConfig(enabled=False, allowed_tool_names=None, blocked_tool_names=None)
            success, message = self.manager.set_tool_filter(server_name, tool_filter)
            if success:
                return Result(success=True, data={"server_name": server_name, "message": "Tool filter removed"})
            return Result(success=False, errorMessage=message)
        except Exception as e:
            logger.error(f"Error removing tool filter: {e}")
            return Result(success=False, errorMessage=f"Error removing tool filter: {e}")
