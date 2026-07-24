# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Shared interruption handling for Agents SDK streaming model adapters."""

from typing import Any

from datus.utils.loggings import get_logger

logger = get_logger(__name__)


async def handle_stream_interrupt(
    *,
    interrupt_controller: Any,
    result: Any,
    session: Any,
    completed_task_call_ids: set[str],
    graceful_interrupt_requested: bool,
) -> bool:
    """Let an uncommitted completed ``task`` result reach the session before stopping."""
    if not interrupt_controller or not interrupt_controller.is_interrupted:
        return graceful_interrupt_requested
    if graceful_interrupt_requested:
        return True

    task_outputs_persisted = False
    if session is not None and completed_task_call_ids:
        try:
            persisted_items = await session.get_items()
            persisted_call_ids = {
                item.get("call_id")
                for item in persisted_items
                if isinstance(item, dict) and item.get("type") == "function_call_output"
            }
            task_outputs_persisted = completed_task_call_ids.issubset(persisted_call_ids)
        except Exception:
            logger.debug("Failed to inspect session before interrupt", exc_info=True)

    if completed_task_call_ids and not task_outputs_persisted and session is not None:
        cancel = getattr(result, "cancel", None)
        if callable(cancel):
            cancel(mode="after_turn")
            return True

    from datus.cli.execution_state import ExecutionInterrupted

    raise ExecutionInterrupted("Interrupted by user")
