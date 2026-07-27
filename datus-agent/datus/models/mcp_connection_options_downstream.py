"""Downstream MCP connection option adapters shared by model runtimes."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def connection_failure_options(kwargs: Mapping[str, Any]) -> dict[str, Any]:
    callback = kwargs.get("mcp_connection_failure_callback")
    return {"on_connection_failure": callback} if callback else {}
