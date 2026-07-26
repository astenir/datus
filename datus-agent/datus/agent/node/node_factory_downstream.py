"""Downstream interactive-node factory adapters."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from datus.agent.node_capabilities import get_agent_node_capability

if TYPE_CHECKING:
    from datus.agent.node.agentic_node import AgenticNode
    from datus.configuration.agent_config import AgentConfig


def create_interactive_node(
    subagent_name: str,
    node_class_type: str | None,
    agent_config: "AgentConfig",
    node_id_suffix: str,
    scope: str | None,
    execution_mode: Literal["interactive", "workflow"],
    node_id: str | None,
    session_id: str | None,
) -> "AgenticNode | None":
    if node_class_type and subagent_name != node_class_type:
        capability = get_agent_node_capability(node_class_type)
        if capability is None or not capability.customizable:
            raise ValueError(f"Unsupported custom Agent node_class '{node_class_type}'.")

    if subagent_name != "chat" and node_class_type != "chat":
        return None

    from datus.agent.node.chat_agentic_node import ChatAgenticNode

    return ChatAgenticNode(
        node_id=node_id if node_id is not None else f"{subagent_name}{node_id_suffix}",
        description=f"Chat node for {subagent_name}",
        node_type="chat",
        input_data=None,
        agent_config=agent_config,
        tools=None,
        scope=scope,
        execution_mode=execution_mode,
        node_name=subagent_name,
        session_id=session_id,
    )
