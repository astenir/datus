"""Downstream MCP connection option adapters shared by model runtimes."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def connection_failure_options(kwargs: Mapping[str, Any]) -> dict[str, Any]:
    """Keep chat-visible MCP failures to one connection attempt.

    Runtimes that do not opt into the downstream callback retain the generic
    MCP helper's retry behavior.  A chat run with the callback can surface a
    useful failure card and continue without repeatedly blocking the turn on
    an already-unavailable remote endpoint.
    """
    callback = kwargs.get("mcp_connection_failure_callback")
    return {"on_connection_failure": callback, "max_retries": 1} if callback else {}
