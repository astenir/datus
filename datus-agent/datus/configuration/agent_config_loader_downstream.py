"""Downstream raw configuration adapters for the agent config loader."""

from __future__ import annotations

import os
from typing import Any

from datus.configuration.agent_config import _load_datasources_file


def merge_datasources_file(agent_raw: dict[str, Any]) -> None:
    """Merge ``services.datasources_file`` before project override validation."""
    services_raw = agent_raw.get("services") or {}
    if not isinstance(services_raw, dict):
        return

    datasources_file = services_raw.get("datasources_file") or os.getenv("DATUS_DATASOURCES_FILE", "")
    if not datasources_file:
        return

    inline_datasources = services_raw.get("datasources") or {}
    if not isinstance(inline_datasources, dict):
        return

    datasources = dict(inline_datasources)
    datasources.update(_load_datasources_file(datasources_file))
    services_raw["datasources"] = datasources
    # Avoid re-loading the same file later in AgentConfig, which would undo
    # default flags flipped by .datus/config.yml.
    services_raw["datasources_file"] = ""
