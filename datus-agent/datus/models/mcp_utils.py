# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import asyncio
import re
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any, Callable, Dict, Optional

from datus.utils.loggings import get_logger

logger = get_logger(__name__)


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

        yield connected_servers

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
