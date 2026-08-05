"""Policy and runtime helpers for user-owned MCP servers."""

from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
from fnmatch import fnmatchcase
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from datus.tools.mcp_tools.mcp_config import (
    HTTPServerConfig,
    MCPAuthConfig,
    MCPAuthMode,
    SSEServerConfig,
    ToolFilterConfig,
)
from datus.utils.exceptions import DatusException, ErrorCode

MCP_ID_RE = re.compile(r"^[A-Fa-f0-9]{32}$")
TOOL_NAME_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,160}$")
MAX_DISPLAY_NAME_LENGTH = 120
MAX_TOKEN_LENGTH = 4096
PERSONAL_MCP_ALIAS_PREFIX = "personal_"


def normalize_personal_mcp_id(value: str) -> str:
    mcp_id = value.strip().lower()
    if not MCP_ID_RE.fullmatch(mcp_id):
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="Invalid personal MCP id.")
    return mcp_id


def personal_mcp_alias(mcp_id: str) -> str:
    return f"{PERSONAL_MCP_ALIAS_PREFIX}{normalize_personal_mcp_id(mcp_id)}"


def normalize_display_name(value: str) -> str:
    name = value.strip()
    if not name:
        raise DatusException(ErrorCode.COMMON_FIELD_REQUIRED, message="Display name is required.")
    if len(name) > MAX_DISPLAY_NAME_LENGTH or any(ord(char) < 32 or ord(char) == 127 for char in name):
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="Invalid personal MCP display name.")
    return name


def normalize_transport(value: str) -> str:
    transport = value.strip().lower()
    if transport not in {"http", "sse"}:
        raise DatusException(
            ErrorCode.COMMON_FIELD_INVALID,
            message="Personal MCP transport must be http or sse; stdio is not allowed.",
        )
    return transport


def normalize_token(value: str | None) -> str | None:
    token = (value or "").strip()
    if not token:
        return None
    if len(token) > MAX_TOKEN_LENGTH or "\r" in token or "\n" in token:
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="Invalid personal MCP bearer token.")
    scheme, separator, credential = token.partition(" ")
    if separator and scheme.casefold() == "bearer":
        token = credential.strip()
    if not token:
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="Invalid personal MCP bearer token.")
    return token


def token_hint(token: str | None) -> str | None:
    if not token:
        return None
    return "***" if len(token) <= 4 else f"***{token[-4:]}"


def normalize_tool_names(values: list[str] | None) -> list[str]:
    names = sorted({str(value).strip() for value in values or [] if str(value).strip()})
    if any(not TOOL_NAME_RE.fullmatch(name) for name in names):
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="Invalid personal MCP tool filter.")
    return names


def personal_mcp_options(agent_config: Any) -> dict[str, Any]:
    enterprise = getattr(agent_config, "enterprise_config", {}) or {}
    raw = enterprise.get("user_mcp") or enterprise.get("personal_mcp") or {}
    if not isinstance(raw, dict):
        raw = {}
    allowed_hosts = _normalized_list(raw.get("allowed_hosts"))
    return {
        "enabled": bool(raw.get("enabled")) and bool(allowed_hosts),
        "allowed_hosts": allowed_hosts,
        "max_servers_per_user": _bounded_int(raw.get("max_servers_per_user"), default=10, minimum=1, maximum=100),
        "max_selected_per_session": _bounded_int(raw.get("max_selected_per_session"), default=3, minimum=1, maximum=10),
        "timeout_seconds": _bounded_float(raw.get("timeout_seconds"), default=30.0, minimum=1.0, maximum=60.0),
    }


def validate_personal_mcp_policy(agent_config: Any, *, url: str) -> str:
    options = personal_mcp_options(agent_config)
    if not options["enabled"]:
        raise DatusException(ErrorCode.COMMON_CONFIG_ERROR, message="Personal MCP is not enabled.")
    normalized, host = normalize_https_url(url)
    if not any(fnmatchcase(host, pattern) for pattern in options["allowed_hosts"]):
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="Personal MCP host is not allowed.")
    _reject_unsafe_ip_literal(host)
    return normalized


def normalize_https_url(value: str) -> tuple[str, str]:
    raw = value.strip()
    if len(raw) > 2048:
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="Personal MCP URL is too long.")
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError as exc:
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="Invalid personal MCP URL.") from exc
    host = (parsed.hostname or "").rstrip(".").lower()
    if parsed.scheme.casefold() != "https" or not host:
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="Personal MCP URL must use HTTPS.")
    if parsed.username is not None or parsed.password is not None:
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="Personal MCP URL must not contain userinfo.")
    if parsed.query or parsed.fragment:
        raise DatusException(
            ErrorCode.COMMON_FIELD_INVALID, message="Personal MCP URL must not contain query or fragment."
        )
    netloc = f"[{host}]" if ":" in host else host
    if port is not None:
        netloc = f"{netloc}:{port}"
    path = parsed.path or "/"
    return urlunsplit(("https", netloc, path, "", "")), host


async def validate_personal_mcp_destination(url: str) -> None:
    """Resolve the target immediately before connecting and reject unsafe IPs."""

    _, host = normalize_https_url(url)
    try:
        addresses = await asyncio.to_thread(socket.getaddrinfo, host, None, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="Personal MCP host cannot be resolved.") from exc
    resolved = {entry[4][0] for entry in addresses if entry[4]}
    if not resolved:
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="Personal MCP host cannot be resolved.")
    for value in resolved:
        _reject_unsafe_address(value)


def record_to_mcp_config(record: dict[str, Any], *, timeout_seconds: float):
    auth = (
        MCPAuthConfig(mode=MCPAuthMode.STATIC_BEARER, token=str(record["token"]))
        if record.get("token")
        else MCPAuthConfig(mode=MCPAuthMode.NONE)
    )
    tool_filter = ToolFilterConfig(
        enabled=True,
        allowed_tool_names=list(record.get("allowed_tools") or []) or None,
        blocked_tool_names=list(record.get("blocked_tools") or []) or None,
    )
    kwargs = {
        "name": personal_mcp_alias(str(record["id"])),
        "url": str(record["url"]),
        "auth": auth,
        "timeout": timeout_seconds,
        "tool_filter": tool_filter,
    }
    return SSEServerConfig(**kwargs) if record["transport"] == "sse" else HTTPServerConfig(**kwargs)


def _reject_unsafe_ip_literal(host: str) -> None:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return
    _reject_unsafe_address(host)


def _reject_unsafe_address(value: str) -> None:
    address = ipaddress.ip_address(value)
    if not address.is_global:
        raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="Personal MCP destination is not public.")


def _normalized_list(value: Any) -> list[str]:
    values = value.split(",") if isinstance(value, str) else value if isinstance(value, (list, tuple, set)) else []
    return sorted({str(item).strip().rstrip(".").lower() for item in values if str(item).strip()})


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        result = default
    return min(max(result, minimum), maximum)


def _bounded_float(value: Any, *, default: float, minimum: float, maximum: float) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        result = default
    return min(max(result, minimum), maximum)
