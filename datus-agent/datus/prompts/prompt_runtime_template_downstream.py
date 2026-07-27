"""Downstream request-scoped prompt template resolution."""

from __future__ import annotations

from typing import Any


def find_runtime_template_content(
    agent_config: Any,
    template_name: str,
    version: str | None,
) -> str | None:
    agentic_nodes = getattr(agent_config, "agentic_nodes", None)
    if not isinstance(agentic_nodes, dict):
        return None

    for node_name, node_config in agentic_nodes.items():
        if not isinstance(node_config, dict):
            continue
        system_prompt_name = node_config.get("system_prompt") or node_name
        if f"{system_prompt_name}_system" != template_name:
            continue
        content = node_config.get("prompt_template")
        if not isinstance(content, str) or not content.strip():
            continue
        configured_version = node_config.get("prompt_version")
        if version and configured_version and str(version) != str(configured_version):
            continue
        return content
    return None
