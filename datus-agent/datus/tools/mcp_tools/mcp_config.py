# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""
MCP Config - Pydantic models for MCP server config management.

This module provides data models for MCP server configs with validation
and serialization capabilities.
"""

import os
import re
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator


class MCPServerType(str, Enum):
    """Enumeration of MCP server communication types."""

    STDIO = "stdio"  # Standard input/output communication
    SSE = "sse"  # Server-sent events communication
    HTTP = "http"  # HTTP communication protocol


class MCPAuthMode(str, Enum):
    """Authentication strategy for remote MCP servers."""

    NONE = "none"
    STATIC_BEARER = "static_bearer"
    REQUEST_BEARER = "request_bearer"


class MCPAuthConfig(BaseModel):
    """Persisted remote MCP authentication configuration.

    ``token`` is intentionally excluded from ordinary ``model_dump`` calls so
    API responses and debug serialization cannot expose it accidentally. The
    MCP config writer persists it explicitly for backwards-compatible manual
    credentials.
    """

    mode: MCPAuthMode = Field(default=MCPAuthMode.NONE, description="Remote MCP authentication mode")
    token: Optional[str] = Field(default=None, exclude=True, repr=False, description="Static bearer token")

    @model_validator(mode="after")
    def validate_credentials(self) -> "MCPAuthConfig":
        token = normalize_bearer_token(self.token)
        if self.mode == MCPAuthMode.STATIC_BEARER and not token:
            raise ValueError("static_bearer authentication requires a token")
        if self.mode != MCPAuthMode.STATIC_BEARER and token:
            raise ValueError(f"{self.mode.value} authentication must not include a token")
        self.token = token
        return self

    @property
    def credential_configured(self) -> bool:
        """Whether the selected strategy has a usable credential source."""

        return self.mode == MCPAuthMode.REQUEST_BEARER or bool(self.token)


def normalize_bearer_token(value: Optional[str]) -> Optional[str]:
    """Normalize a pasted bearer credential without logging or serializing it."""

    token = (value or "").strip()
    if not token:
        return None
    if "\r" in token or "\n" in token:
        raise ValueError("Bearer token must not contain line breaks")
    scheme, separator, credential = token.partition(" ")
    if separator and scheme.lower() == "bearer":
        token = credential.strip()
    if not token:
        raise ValueError("Bearer token is empty")
    return token


def _pop_header(headers: Dict[str, str], name: str) -> Optional[str]:
    """Remove and return one HTTP header using case-insensitive matching."""

    target = name.casefold()
    for key in list(headers):
        if key.casefold() == target:
            return headers.pop(key)
    return None


class ToolFilterConfig(BaseModel):
    """Configuration for tool filtering on MCP servers."""

    allowed_tool_names: Optional[List[str]] = Field(
        None, description="List of allowed tool names (whitelist). If specified, only these tools are allowed."
    )
    blocked_tool_names: Optional[List[str]] = Field(
        None, description="List of blocked tool names (blacklist). These tools are excluded."
    )
    enabled: bool = Field(default=True, description="Whether tool filtering is enabled")

    def is_tool_allowed(self, tool_name: str) -> bool:
        """
        Check if a tool is allowed based on filter configuration.

        Args:
            tool_name: Name of the tool to check

        Returns:
            True if tool is allowed, False otherwise
        """
        if not self.enabled:
            return True

        # First apply allowlist (if configured)
        if self.allowed_tool_names is not None:
            if tool_name not in self.allowed_tool_names:
                return False

        # Then apply blocklist to remaining tools
        if self.blocked_tool_names is not None:
            if tool_name in self.blocked_tool_names:
                return False

        return True


# Type alias for any MCP server config subclass
AnyMCPServerConfig = Union["STDIOServerConfig", "SSEServerConfig", "HTTPServerConfig"]


def expand_env_vars(value: str) -> str:
    """
    Expand env variables in a string.

    Supports format: ${VAR} and ${VAR:-default}

    Args:
        value: String that may contain env variables

    Returns:
        String with env variables expanded
    """

    def replace_var(match):
        var_expr = match.group(1)
        if ":-" in var_expr:
            var_name, default_value = var_expr.split(":-", 1)
            return os.getenv(var_name, default_value)
        else:
            return os.getenv(var_expr, match.group(0))  # Return original if not found

    # Pattern to match ${VAR} or ${VAR:-default}
    pattern = r"\$\{([^}]+)\}"
    return re.sub(pattern, replace_var, value)


def expand_config_env_vars(config_dict: dict) -> dict:
    """
    Expand environment variables in config dictionary recursively.

    Args:
        config_dict: Dictionary that may contain env variables in string values

    Returns:
        Dictionary with env variables expanded
    """
    expanded = {}
    for key, value in config_dict.items():
        if isinstance(value, str):
            expanded[key] = expand_env_vars(value)
        elif isinstance(value, dict):
            # Recursively expand env variables in nested dicts (like headers)
            expanded_dict = {}
            for k, v in value.items():
                if isinstance(v, str):
                    expanded_dict[k] = expand_env_vars(v)
                else:
                    expanded_dict[k] = v
            expanded[key] = expanded_dict
        elif isinstance(value, list):
            # Handle list values (like args)
            expanded_list = []
            for item in value:
                if isinstance(item, str):
                    expanded_list.append(expand_env_vars(item))
                else:
                    expanded_list.append(item)
            expanded[key] = expanded_list
        else:
            expanded[key] = value
    return expanded


class MCPServerConfig(BaseModel):
    """Base config for an MCP server instance."""

    name: str = Field(..., description="Server name/identifier")
    type: MCPServerType = Field(..., description="Server communication type")
    tool_filter: Optional[ToolFilterConfig] = Field(None, description="Tool filtering configuration")

    class Config:
        use_enum_values = True

    @field_validator("type", mode="before")
    @classmethod
    def validate_type(cls, v):
        """Convert string to MCPServerType enum."""
        if isinstance(v, str):
            try:
                return MCPServerType(v)
            except ValueError:
                raise ValueError(f"Invalid server type: {v}")
        return v

    @classmethod
    def from_config_format(cls, name: str, config: Dict[str, Any]) -> "AnyMCPServerConfig":
        """
        Create appropriate MCPServerConfig subclass from config format.

        Args:
            name: Server name
            config: Config in standard format

        Returns:
            MCPServerConfig instance (appropriate subclass)
        """
        server_type = config.get("type", "stdio")

        # Handle env variables expansion
        expanded_config = {}
        for key, value in config.items():
            if isinstance(value, str):
                expanded_config[key] = expand_env_vars(value)
            elif isinstance(value, dict):
                # Recursively expand env variables in nested dicts
                expanded_dict = {}
                for k, v in value.items():
                    if isinstance(v, str):
                        expanded_dict[k] = expand_env_vars(v)
                    else:
                        expanded_dict[k] = v
                expanded_config[key] = expanded_dict
            else:
                expanded_config[key] = value

        # Parse tool filter configuration if present
        tool_filter = None
        if "tool_filter" in expanded_config:
            filter_config = expanded_config["tool_filter"]
            if isinstance(filter_config, dict):
                tool_filter = ToolFilterConfig(**filter_config)
            elif isinstance(filter_config, ToolFilterConfig):
                tool_filter = filter_config

        headers = dict(expanded_config.get("headers") or {})
        auth_config = expanded_config.get("auth")
        auth = MCPAuthConfig(**auth_config) if isinstance(auth_config, dict) else auth_config
        legacy_authorization = _pop_header(headers, "Authorization")
        if auth is None and legacy_authorization:
            auth = MCPAuthConfig(mode=MCPAuthMode.STATIC_BEARER, token=legacy_authorization)
        elif auth is not None and legacy_authorization:
            raise ValueError("Authorization must be configured through auth when auth mode is present")

        # Create appropriate subclass based on server type
        if server_type == MCPServerType.STDIO:
            return STDIOServerConfig(
                name=name,
                command=expanded_config.get("command"),
                args=expanded_config.get("args"),
                env=expanded_config.get("env"),
                cwd=expanded_config.get("cwd"),
                tool_filter=tool_filter,
            )
        elif server_type == MCPServerType.SSE:
            return SSEServerConfig(
                name=name,
                url=expanded_config.get("url"),
                headers=headers or None,
                auth=auth,
                timeout=expanded_config.get("timeout"),
                tool_filter=tool_filter,
            )
        elif server_type == MCPServerType.HTTP:
            return HTTPServerConfig(
                name=name,
                url=expanded_config.get("url"),
                headers=headers or None,
                auth=auth,
                timeout=expanded_config.get("timeout"),
                tool_filter=tool_filter,
            )
        else:
            raise ValueError(f"Unknown server type: {server_type}")


class STDIOServerConfig(MCPServerConfig):
    """Config for STDIO MCP servers."""

    type: MCPServerType = Field(default=MCPServerType.STDIO, description="Server communication type")
    command: str = Field(..., description="Command to execute")
    args: Optional[List[str]] = Field(None, description="Command arguments")
    env: Optional[Dict[str, str]] = Field(None, description="Env variables")
    cwd: Optional[str] = Field(None, description="Working directory")

    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information for STDIO server."""
        return {
            "type": "stdio",
            "command": self.command,
            "args": self.args or [],
            "env": self.env or {},
            "cwd": self.cwd,
        }


class SSEServerConfig(MCPServerConfig):
    """Config for SSE (Server-Sent Events) MCP servers."""

    type: MCPServerType = Field(default=MCPServerType.SSE, description="Server communication type")
    url: str = Field(..., description="Server URL")
    headers: Optional[Dict[str, str]] = Field(None, description="HTTP headers")
    auth: Optional[MCPAuthConfig] = Field(None, description="Remote authentication strategy")
    timeout: Optional[float] = Field(None, description="Connection timeout")

    @field_validator("timeout")
    @classmethod
    def validate_timeout(cls, v):
        """Validate timeout value."""
        if v is not None and v <= 0:
            raise ValueError("Timeout must be positive")
        return v

    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information for SSE server."""
        return {
            "type": "sse",
            "url": self.url,
            "headers": self.headers or {},
            "timeout": self.timeout,
        }


class HTTPServerConfig(MCPServerConfig):
    """Config for HTTP MCP servers."""

    type: MCPServerType = Field(default=MCPServerType.HTTP, description="Server communication type")
    url: str = Field(..., description="Server URL")
    headers: Optional[Dict[str, str]] = Field(None, description="HTTP headers")
    auth: Optional[MCPAuthConfig] = Field(None, description="Remote authentication strategy")
    timeout: Optional[float] = Field(None, description="Connection timeout")

    @field_validator("timeout")
    @classmethod
    def validate_timeout(cls, v):
        """Validate timeout value."""
        if v is not None and v <= 0:
            raise ValueError("Timeout must be positive")
        return v

    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information for HTTP server."""
        return {
            "type": "http",
            "url": self.url,
            "headers": self.headers or {},
            "timeout": self.timeout,
        }


class MCPConfig(BaseModel):
    """Root config containing all MCP servers."""

    version: str = Field(default="1.0", description="Config version")
    servers: Dict[str, AnyMCPServerConfig] = Field(default_factory=dict, description="MCP servers")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    class Config:
        use_enum_values = True

    def add_server(self, config: AnyMCPServerConfig) -> None:
        """Add a server config."""
        self.servers[config.name] = config

    def remove_server(self, name: str) -> bool:
        """Remove a server config."""
        if name in self.servers:
            del self.servers[name]
            return True
        return False

    def get_server(self, name: str) -> Optional[AnyMCPServerConfig]:
        """Get server config by name."""
        return self.servers.get(name)

    def list_servers(self, server_type: Optional[MCPServerType] = None) -> List[AnyMCPServerConfig]:
        """List server configs with optional filtering."""
        servers = list(self.servers.values())

        if server_type:
            servers = [s for s in servers if s.type == server_type]

        return servers

    @classmethod
    def from_config_format(cls, config: Dict[str, Any]) -> "MCPConfig":
        """
        Create MCPConfig from config format.

        Args:
            config: Config with "mcpServers" key

        Returns:
            MCPConfig instance
        """
        mcp_config = cls()

        if "mcpServers" in config:
            for name, server_config in config["mcpServers"].items():
                server = MCPServerConfig.from_config_format(name, server_config)
                mcp_config.add_server(server)

        return mcp_config

    def to_config_format(self) -> Dict[str, Any]:
        """
        Convert to config format.

        Returns:
            Dictionary in standard config format
        """
        config = {"mcpServers": {}}

        for name, server in self.servers.items():
            server_config = {"type": server.type}

            # Add tool filter configuration if present
            if server.tool_filter:
                filter_dict = server.tool_filter.model_dump(exclude_none=True)
                if filter_dict:  # Only add if not empty
                    server_config["tool_filter"] = filter_dict

            if server.type == MCPServerType.STDIO:
                if server.command:
                    server_config["command"] = server.command
                if server.args:
                    server_config["args"] = server.args
                if server.env:
                    server_config["env"] = server.env
                if server.cwd:
                    server_config["cwd"] = server.cwd

            elif server.type == MCPServerType.SSE:
                if server.url:
                    server_config["url"] = server.url
                if server.headers:
                    server_config["headers"] = server.headers
                if server.timeout:
                    server_config["timeout"] = server.timeout
                self._add_auth_config(server_config, server.auth)

            elif server.type == MCPServerType.HTTP:
                if server.url:
                    server_config["url"] = server.url
                if server.headers:
                    server_config["headers"] = server.headers
                if server.timeout:
                    server_config["timeout"] = server.timeout
                self._add_auth_config(server_config, server.auth)

            config["mcpServers"][name] = server_config

        return config

    @staticmethod
    def _add_auth_config(server_config: Dict[str, Any], auth: Optional[MCPAuthConfig]) -> None:
        """Persist auth explicitly because raw tokens are excluded from model dumps."""

        if auth is None or auth.mode == MCPAuthMode.NONE:
            return
        auth_config: Dict[str, Any] = {"mode": auth.mode.value}
        if auth.mode == MCPAuthMode.STATIC_BEARER:
            auth_config["token"] = auth.token
        server_config["auth"] = auth_config
