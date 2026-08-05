"""Async session-store adapters used by downstream Agent execution."""

from __future__ import annotations

import inspect
from typing import Any

from datus.utils.loggings import get_logger

logger = get_logger(__name__)


async def get_session_system_prompt(
    node: Any,
    prompt_version: str | None = None,
    template_context: dict[str, Any] | None = None,
) -> str:
    """Load or persist a prompt snapshot without crossing event loops."""

    session_id = getattr(node, "session_id", "") or ""
    meta = node._system_prompt_snapshot_meta(prompt_version)
    session_manager = None
    if session_id:
        try:
            session_manager = node.session_manager
        except Exception as exc:  # session manager wiring is optional in some unit paths
            logger.debug("System-prompt snapshot disabled (no session manager): %s", exc)

    if session_manager is not None:
        load_snapshot = getattr(session_manager, "load_system_prompt_snapshot_async", None)
        snapshot = (
            await load_snapshot(session_id)
            if inspect.iscoroutinefunction(load_snapshot)
            else session_manager.load_system_prompt_snapshot(session_id)
        )
        if node._system_prompt_snapshot_matches(snapshot, meta):
            node._ensure_lazy_tools_mounted()
            return snapshot["prompt"]

    prompt, snapshot_meta = node._build_system_prompt_snapshot(meta, prompt_version, template_context)

    if session_manager is not None:
        save_snapshot = getattr(session_manager, "save_system_prompt_snapshot_async", None)
        if inspect.iscoroutinefunction(save_snapshot):
            await save_snapshot(session_id, prompt, snapshot_meta)
        else:
            session_manager.save_system_prompt_snapshot(session_id, prompt, snapshot_meta)
    return prompt


async def delete_system_prompt_snapshot(session_manager: Any, session_id: str) -> None:
    delete_snapshot = getattr(session_manager, "delete_system_prompt_snapshot_async", None)
    if inspect.iscoroutinefunction(delete_snapshot):
        await delete_snapshot(session_id)
    else:
        session_manager.delete_system_prompt_snapshot(session_id)


async def persist_running_turn_usage(
    session_manager: Any,
    *,
    session_id: str,
    user_turn_number: int,
    cumulative: dict[str, Any],
    context_length: int,
) -> None:
    """Persist running usage through the async adapter when available."""

    persist_async = getattr(session_manager, "upsert_running_turn_usage_async", None)
    if inspect.iscoroutinefunction(persist_async):
        await persist_async(
            session_id=session_id,
            user_turn_number=user_turn_number,
            cumulative=cumulative,
            context_length=context_length,
        )
    else:
        session_manager.upsert_running_turn_usage(
            session_id=session_id,
            user_turn_number=user_turn_number,
            cumulative=cumulative,
            context_length=context_length,
        )


async def clear_running_turn_usage(session_manager: Any, session_id: str) -> None:
    clear_running_usage = getattr(session_manager, "clear_running_turn_usage_async", None)
    if inspect.iscoroutinefunction(clear_running_usage):
        await clear_running_usage(session_id)
    elif hasattr(session_manager, "clear_running_turn_usage"):
        session_manager.clear_running_turn_usage(session_id)
