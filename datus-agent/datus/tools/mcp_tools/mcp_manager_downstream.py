"""Downstream MCP manager adapters kept outside the upstream-owned manager."""

from __future__ import annotations

from typing import Any

from agents.mcp.util import ToolFilterStatic

from datus.tools.mcp_tools.mcp_config import AnyMCPServerConfig, ToolFilterConfig
from datus.utils.loggings import get_logger

logger = get_logger(__name__)


def sdk_tool_filter(config: ToolFilterConfig | None) -> ToolFilterStatic | None:
    """Translate persisted MCP filters into the Agents SDK runtime shape."""

    if config is None or not config.enabled:
        return None

    tool_filter: ToolFilterStatic = {}
    if config.allowed_tool_names is not None:
        tool_filter["allowed_tool_names"] = list(config.allowed_tool_names)
    if config.blocked_tool_names is not None:
        tool_filter["blocked_tool_names"] = list(config.blocked_tool_names)
    return tool_filter or None


def update_server(manager: Any, name: str, config: AnyMCPServerConfig) -> tuple[bool, str]:
    """Replace one persisted server config while retaining its tool filter."""

    try:
        with manager._lock:
            existing = manager.config.get_server(name)
            if not existing:
                return False, f"Server '{name}' not found"
            if config.name != name:
                return False, "Server name cannot be changed"

            if config.tool_filter is None:
                config.tool_filter = existing.tool_filter
            manager.config.add_server(config)

            if manager.save_config():
                logger.info("Updated MCP server: %s (%s)", name, config.type)
                return True, f"Successfully updated server '{name}'"
            return False, "Failed to save config"

    except Exception as exc:
        logger.error("Error updating server %s: %s", name, exc)
        return False, f"Error updating server: {exc}"
