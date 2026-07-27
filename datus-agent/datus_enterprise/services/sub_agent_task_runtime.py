"""Downstream runtime helpers for delegated Agent execution."""

from __future__ import annotations

from typing import Any

from datus.api.models.downstream import ChatSessionSubagentEvent
from datus.utils.loggings import get_logger

logger = get_logger(__name__)


async def persist_subagent_delegation(
    *,
    parent_node: Any,
    parent_session_id: str,
    call_id: str,
    child_session_id: str,
    subagent_type: str,
    prompt: str,
    description: str,
    resumed_session_id: str | None,
) -> None:
    """Persist the display sidecar without making it an execution dependency."""
    event_arguments = {
        "type": subagent_type,
        "prompt": prompt,
        "description": description,
    }
    if resumed_session_id is not None:
        event_arguments["session_id"] = resumed_session_id
    delegation_event = ChatSessionSubagentEvent(
        event_id=f"subagent-{call_id}",
        parent_action_id=call_id,
        child_session_id=child_session_id,
        subagent_type=subagent_type,
        arguments=event_arguments,
    )
    try:
        await parent_node.session_manager.append_subagent_event_async(
            parent_session_id,
            delegation_event,
        )
    except Exception:
        logger.warning(
            "Failed to persist sub-agent delegation for parent %s task %s",
            parent_session_id,
            call_id,
            exc_info=True,
        )
