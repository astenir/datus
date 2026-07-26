"""Enterprise extensions for the upstream MCP service."""

from typing import Any, Dict

from datus.api.enterprise.protocols import EnterpriseAgentStore
from datus.api.models.base_models import Result
from datus.api.models.downstream import UpdateServerInput
from datus.api.services.mcp_service import MCPService
from datus.tools.mcp_tools.mcp_config import MCPServerConfig
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


class EnterpriseMCPService(MCPService):
    """Add downstream mutation and Agent-reference safeguards."""

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
