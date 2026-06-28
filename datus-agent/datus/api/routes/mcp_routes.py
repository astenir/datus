"""
API routes for MCP (Model Context Protocol) endpoints.
"""

from typing import Annotated, Any, Dict, Optional

from fastapi import APIRouter, Depends, Path, Query, Request

from datus.api import deps as api_deps
from datus.api.auth.context import AppContext
from datus.api.deps import ServiceDep
from datus.api.enterprise.deps import require_authorized_module, require_module, require_platform_active
from datus.api.enterprise.models import ResourceRef
from datus.api.models.base_models import Result
from datus.api.models.mcp_models import (
    AddServerInput,
    CallToolInput,
    ToolFilterInput,
)

router = APIRouter(prefix="/api/v1/mcp", tags=["mcp"])
_require_mcp_module = require_module("module.mcp")
McpModuleCtx = Annotated[AppContext, Depends(_require_mcp_module)]

# Pre-configured parameters to avoid definition-time evaluation in defaults
SERVER_TYPE_QUERY = Query(None, description="Filter by server type (stdio, sse, http)")
REMOVE_SERVER_NAME_PATH = Path(..., description="Name of the server to remove")
SERVER_NAME_CHECK_PATH = Path(..., description="Name of the server to check")
SERVER_NAME_PATH = Path(..., description="Name of the server")
TOOL_NAME_PATH = Path(..., description="Name of the tool to call")


async def _require_mcp_permission(
    ctx: AppContext,
    permission_key: str,
    *,
    resource_type: str,
    resource_id: str | None,
    attributes: dict[str, Any] | None = None,
) -> None:
    await require_authorized_module(
        ctx,
        permission_key,
        resource=ResourceRef(
            type=resource_type,
            id=resource_id,
            attributes=attributes or {},
        ),
    )


async def _require_mcp_server_add_permission(
    ctx: McpModuleCtx,
) -> None:
    await _require_mcp_permission(
        ctx,
        "mcp.server.add",
        resource_type="mcp_server",
        resource_id=None,
    )


async def _require_mcp_server_list_permission(
    ctx: McpModuleCtx,
) -> None:
    await _require_mcp_permission(
        ctx,
        "mcp.server.list",
        resource_type="mcp_server",
        resource_id=None,
    )


async def _require_mcp_server_remove_permission(
    server_name: str,
    ctx: McpModuleCtx,
) -> None:
    await _require_mcp_permission(
        ctx,
        "mcp.server.remove",
        resource_type="mcp_server",
        resource_id=server_name,
        attributes={"server_name": server_name},
    )


async def _require_mcp_server_connectivity_permission(
    server_name: str,
    ctx: McpModuleCtx,
) -> None:
    await _require_mcp_permission(
        ctx,
        "mcp.server.connectivity",
        resource_type="mcp_server",
        resource_id=server_name,
        attributes={"server_name": server_name},
    )


async def _require_mcp_server_tools_permission(
    server_name: str,
    ctx: McpModuleCtx,
) -> None:
    await _require_mcp_permission(
        ctx,
        "mcp.server.tools",
        resource_type="mcp_server",
        resource_id=server_name,
        attributes={"server_name": server_name},
    )


async def _require_mcp_tool_call_permission(
    server_name: str,
    tool_name: str,
    ctx: McpModuleCtx,
) -> None:
    permission_key = f"mcp.{server_name}.{tool_name}"
    await _require_mcp_permission(
        ctx,
        permission_key,
        resource_type="mcp_tool",
        resource_id=f"{server_name}/{tool_name}",
        attributes={"server_name": server_name, "tool_name": tool_name},
    )


async def _require_mcp_filter_view_permission(
    server_name: str,
    ctx: McpModuleCtx,
) -> None:
    await _require_mcp_permission(
        ctx,
        "mcp.filter.view",
        resource_type="mcp_filter",
        resource_id=server_name,
        attributes={"server_name": server_name},
    )


async def _require_mcp_filter_set_permission(
    server_name: str,
    ctx: McpModuleCtx,
) -> None:
    await _require_mcp_permission(
        ctx,
        "mcp.filter.set",
        resource_type="mcp_filter",
        resource_id=server_name,
        attributes={"server_name": server_name},
    )


async def _require_mcp_filter_remove_permission(
    server_name: str,
    ctx: McpModuleCtx,
) -> None:
    await _require_mcp_permission(
        ctx,
        "mcp.filter.remove",
        resource_type="mcp_filter",
        resource_id=server_name,
        attributes={"server_name": server_name},
    )


@router.get(
    "/servers",
    response_model=Result[Dict[str, Any]],
    summary="List MCP Servers",
    description="List all MCP servers with optional filtering by type",
    dependencies=[Depends(_require_mcp_module), Depends(_require_mcp_server_list_permission)],
)
async def list_servers(
    svc: ServiceDep,
    _ctx: McpModuleCtx,
    server_type: Optional[str] = SERVER_TYPE_QUERY,
) -> Result[Dict[str, Any]]:
    """List all MCP servers."""
    return svc.mcp.list_servers(server_type=server_type)


@router.post(
    "/servers",
    response_model=Result[Dict[str, Any]],
    summary="Add MCP Server",
    description="Add a new MCP server configuration",
    dependencies=[
        Depends(_require_mcp_module),
        Depends(_require_mcp_server_add_permission),
        Depends(require_platform_active(operation="mcp.server.add", resource_type="mcp_server")),
    ],
)
async def add_server(
    server_config: AddServerInput,
    _ctx: McpModuleCtx,
    http_request: Request,
) -> Result[Dict[str, Any]]:
    """Add a new MCP server."""
    svc = await api_deps.resolve_datus_service_for_request(http_request)
    return svc.mcp.add_server(server_config)


@router.delete(
    "/servers/{server_name}",
    response_model=Result[Dict[str, Any]],
    summary="Remove MCP Server",
    description="Remove an MCP server configuration",
    dependencies=[
        Depends(_require_mcp_module),
        Depends(_require_mcp_server_remove_permission),
        Depends(require_platform_active(operation="mcp.server.remove", resource_type="mcp_server")),
    ],
)
async def remove_server(
    svc: ServiceDep,
    _ctx: McpModuleCtx,
    server_name: str = REMOVE_SERVER_NAME_PATH,
) -> Result[Dict[str, Any]]:
    """Remove an MCP server."""
    return svc.mcp.remove_server(server_name)


@router.get(
    "/servers/{server_name}/connectivity",
    response_model=Result[Dict[str, Any]],
    summary="Check Server Connectivity",
    description="Check connectivity status of an MCP server",
    dependencies=[
        Depends(_require_mcp_module),
        Depends(_require_mcp_server_connectivity_permission),
        Depends(require_platform_active(operation="mcp.server.connectivity", resource_type="mcp_server")),
    ],
)
async def check_connectivity(
    svc: ServiceDep,
    _ctx: McpModuleCtx,
    server_name: str = SERVER_NAME_CHECK_PATH,
) -> Result[Dict[str, Any]]:
    """Check server connectivity status."""
    return await svc.mcp.check_connectivity(server_name)


@router.get(
    "/servers/{server_name}/tools",
    response_model=Result[Dict[str, Any]],
    summary="List Server Tools",
    description="List tools available on an MCP server",
    dependencies=[Depends(_require_mcp_module), Depends(_require_mcp_server_tools_permission)],
)
async def list_tools(
    svc: ServiceDep,
    _ctx: McpModuleCtx,
    server_name: str = SERVER_NAME_PATH,
) -> Result[Dict[str, Any]]:
    """List tools available on an MCP server."""
    return await svc.mcp.list_tools(server_name, True)


@router.post(
    "/servers/{server_name}/tools/{tool_name}/call",
    response_model=Result[Dict[str, Any]],
    summary="Call Tool",
    description="Call a tool on an MCP server",
    dependencies=[
        Depends(_require_mcp_module),
        Depends(_require_mcp_tool_call_permission),
        Depends(require_platform_active(operation="mcp.tool.call", resource_type="mcp_tool")),
    ],
)
async def call_tool(
    request: CallToolInput,
    _ctx: McpModuleCtx,
    http_request: Request,
    server_name: str = SERVER_NAME_PATH,
    tool_name: str = TOOL_NAME_PATH,
) -> Result[Dict[str, Any]]:
    """Call a tool on an MCP server."""
    svc = await api_deps.resolve_datus_service_for_request(http_request)
    return await svc.mcp.call_tool(server_name, tool_name, request)


@router.get(
    "/servers/{server_name}/filters",
    response_model=Result[Dict[str, Any]],
    summary="Get Tool Filter",
    description="Get tool filter configuration for an MCP server",
    dependencies=[Depends(_require_mcp_module), Depends(_require_mcp_filter_view_permission)],
)
async def get_tool_filter(
    svc: ServiceDep,
    _ctx: McpModuleCtx,
    server_name: str = SERVER_NAME_PATH,
) -> Result[Dict[str, Any]]:
    """Get tool filter configuration."""
    return svc.mcp.get_tool_filter(server_name)


@router.put(
    "/servers/{server_name}/filters",
    response_model=Result[Dict[str, Any]],
    summary="Set Tool Filter",
    description="Set tool filter configuration for an MCP server",
    dependencies=[
        Depends(_require_mcp_module),
        Depends(_require_mcp_filter_set_permission),
        Depends(require_platform_active(operation="mcp.filter.set", resource_type="mcp_filter")),
    ],
)
async def set_tool_filter(
    filter_config: ToolFilterInput,
    _ctx: McpModuleCtx,
    http_request: Request,
    server_name: str = SERVER_NAME_PATH,
) -> Result[Dict[str, Any]]:
    """Set tool filter configuration."""
    svc = await api_deps.resolve_datus_service_for_request(http_request)
    return svc.mcp.set_tool_filter(server_name, filter_config)


@router.delete(
    "/servers/{server_name}/filters",
    response_model=Result[Dict[str, Any]],
    summary="Remove Tool Filter",
    description="Remove tool filter configuration from an MCP server",
    dependencies=[
        Depends(_require_mcp_module),
        Depends(_require_mcp_filter_remove_permission),
        Depends(require_platform_active(operation="mcp.filter.remove", resource_type="mcp_filter")),
    ],
)
async def remove_tool_filter(
    svc: ServiceDep,
    _ctx: McpModuleCtx,
    server_name: str = SERVER_NAME_PATH,
) -> Result[Dict[str, Any]]:
    """Remove tool filter configuration."""
    return svc.mcp.remove_tool_filter(server_name)
