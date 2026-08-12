# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import asyncio
import re
from contextlib import AsyncExitStack, asynccontextmanager
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

from datus.utils.loggings import get_logger

if TYPE_CHECKING:
    from mcp.types import Tool as MCPTool

logger = get_logger(__name__)


class PrefixedMCPServer:
    """Delegate that namespaces MCP tools under ``<server_name>_``.

    The Agents SDK requires tool names to be unique across all MCP servers
    bound to one agent (``MCPUtil.get_all_function_tools`` raises
    ``UserError`` on the first overlap). Two servers may point at the same
    endpoint -- e.g. an enterprise MCP and a user-owned personal MCP
    configured against the same service -- and therefore expose identical
    tool names. Wrapping every bound server in this delegate as soon as more
    than one server is configured gives each tool a server-qualified name;
    ``call_tool`` strips the prefix again so the underlying server still sees
    its original tool name.

    The delegate forwards attribute access so SDK lifecycle calls
    (``connect``/``cleanup``/``use_structured_content``) keep working on the
    wrapped instance.
    """

    def __init__(self, server: Any, prefix: str):
        self._delegate_server = server
        self._tool_prefix = prefix  # includes the trailing separator

    def __getattr__(self, item: str) -> Any:
        return getattr(self._delegate_server, item)

    @property
    def name(self) -> str:
        return self._delegate_server.name

    async def list_tools(self, run_context=None, agent=None):
        tools = await self._delegate_server.list_tools(run_context, agent)
        return [self._prefixed_tool(tool) for tool in tools]

    async def call_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None):
        original_name = self._original_tool_name(tool_name)
        return await self._delegate_server.call_tool(original_name, arguments)

    def _prefixed_tool(self, tool: "MCPTool") -> "MCPTool":
        return tool.model_copy(update={"name": f"{self._tool_prefix}{tool.name}"})

    def _original_tool_name(self, tool_name: str) -> str:
        if tool_name.startswith(self._tool_prefix):
            return tool_name[len(self._tool_prefix) :]
        return tool_name

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        exit_stack = getattr(self._delegate_server, "__aexit__", None)
        if callable(exit_stack):
            return await exit_stack(*args)
        return None


def _maybe_prefix_mcp_servers(connected_servers: Dict[str, Any], *, configured_count: int) -> Dict[str, Any]:
    """Wrap all connected servers with server-qualified tool names when more than one is configured.

    The condition mirrors the prompt-side naming in
    ``GenSQLAgenticNode._get_mcp_tool_names_for_prompt`` (based on the
    configured server set, not the connection outcome) so advertised tool
    names always match the SDK tool schema. A single server keeps its original
    tool names (zero behavior change for the common case); with two or more
    configured servers every tool becomes ``<server_name>_<tool_name>`` which
    is globally unique even when two servers expose the same endpoint and
    tool set.
    """

    if configured_count <= 1:
        return connected_servers
    return {
        server_name: PrefixedMCPServer(server, prefix=f"{server_name}_")
        for server_name, server in connected_servers.items()
    }


@asynccontextmanager
async def _safe_connect_server(server_name: str, server, max_retries: int = 3):
    """Context-managed safe MCP server connection"""
    provider = None
    max_retries = max(1, int(max_retries))

    for attempt in range(max_retries):
        try:
            logger.info(f"Attempting to connect to MCP server {server_name} (attempt {attempt + 1}/{max_retries})")
            logger.debug(f"MCP server {server_name} type: {type(server)}")

            provider = server  # assume already created via Provider.from_process(...)
            # async context here ensures lifecycle is tracked
            async with provider:
                logger.info(f"MCP server {server_name} connected successfully")
                try:
                    yield provider
                except GeneratorExit:
                    # Handle proper cleanup on generator exit
                    logger.debug(f"MCP server {server_name} generator being closed")
                    raise
                return  # only yield once; exit after use

        except asyncio.TimeoutError as e:
            safe_error = safe_mcp_connection_error(e)
            logger.warning(f"Failed to connect MCP server {server_name} (attempt {attempt + 1}): {safe_error}")
            if attempt == max_retries - 1:
                raise
        except asyncio.CancelledError:
            # Handle cancellation during connection attempts
            logger.debug(f"MCP server {server_name} connection cancelled")
            raise
        except GeneratorExit:
            # Re-raise GeneratorExit to ensure proper cleanup
            raise
        except Exception as e:
            safe_error = safe_mcp_connection_error(e)
            logger.warning(f"Failed to connect MCP server {server_name} (attempt {attempt + 1}): {safe_error}")
            if attempt == max_retries - 1:
                raise

            try:
                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                # Handle cancellation during retry sleep
                logger.debug(f"MCP server {server_name} retry cancelled")
                raise


@asynccontextmanager
async def multiple_mcp_servers(
    mcp_servers: Dict[str, Any],
    on_connection_failure: Optional[Callable[[str, str], None]] = None,
    max_retries: int = 3,
):
    """Context manager for managing multiple MCP servers.

    Args:
        mcp_servers: Dictionary of MCP servers to manage
        max_retries: Maximum connection attempts for each server. A failed
            server is isolated from the rest of the Agent run.

    Yields:
        Dictionary of connected MCP servers
    """
    connected_servers = {}
    stack = AsyncExitStack()
    max_retries = max(1, int(max_retries))

    try:
        logger.info(f"Attempting to connect {len(mcp_servers)} MCP servers: {list(mcp_servers.keys())}")

        for server_name, server in mcp_servers.items():
            try:
                logger.info(f"Connecting MCP server: {server_name}")
                cm = _safe_connect_server(server_name, server, max_retries=max_retries)
                connected_server = await stack.enter_async_context(cm)
                connected_servers[server_name] = connected_server
                logger.info(f"Successfully connected MCP server: {server_name}")
            except Exception as e:
                safe_error = safe_mcp_connection_error(e)
                logger.warning(f"Failed to start MCP server {server_name}: {safe_error}")
                if on_connection_failure is not None:
                    on_connection_failure(server_name, safe_error)

        if not connected_servers:
            logger.debug("Warning: No MCP servers were successfully connected")

        yield _maybe_prefix_mcp_servers(connected_servers, configured_count=len(mcp_servers))

    finally:
        logger.debug("Cleaning up all MCP servers via AsyncExitStack")
        try:
            await stack.aclose()
        except RuntimeError as e:
            if "Attempted to exit cancel scope in a different task than it was entered in" in str(e):
                # This is a known anyio issue that can be safely ignored during cleanup
                logger.debug("Suppressed cancel scope error during MCP server cleanup")
            else:
                raise


def safe_mcp_connection_error(error: Any) -> str:
    """Return a useful MCP connection error without exposing transport details."""
    raw_error = str(error)
    normalized = f"{type(error).__name__} {raw_error}".lower()

    if isinstance(error, asyncio.TimeoutError) or re.search(
        r"connecttimeout|readtimeout|timed?\s*out|timeout|aborterror",
        normalized,
    ):
        return "MCP server connection timed out."

    status_match = re.search(r"\b([45]\d{2})\b", raw_error)
    if status_match:
        return f"MCP server returned HTTP {status_match.group(1)}."

    if re.search(
        r"connecterror|connection\s+(?:refused|reset|closed|failed)|name or service not known|"
        r"getaddrinfo|temporary failure in name resolution|dns|network is unreachable",
        normalized,
    ):
        return "Failed to connect to MCP server. Please check the server address and network connectivity."

    return "MCP server connection failed."
