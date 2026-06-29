# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""
Async channel for proxy tool results.

Allows proxy tools to await results that are published from stdin dispatch.
Wait and publish are order-independent: either side can arrive first.
"""

import asyncio
from typing import Any, Dict

from datus.utils.loggings import get_logger

logger = get_logger(__name__)


class ToolResultChannel:
    """Async pub/sub channel for proxy tool call results.

    Both ``wait_for`` and ``publish`` lazily create a Future on first access,
    so the result is never lost regardless of which side arrives first.
    """

    def __init__(self):
        self._futures: Dict[str, asyncio.Future[Any]] = {}
        self._lock = asyncio.Lock()

    def _get_or_create_future(self, call_id: str) -> asyncio.Future[Any]:
        fut = self._futures.get(call_id)
        if fut is None:
            fut = asyncio.get_running_loop().create_future()
            self._futures[call_id] = fut
        return fut

    async def wait_for(self, call_id: str, timeout: float | None = None) -> Any:
        """Wait for a result to be published for the given call_id.

        When ``timeout`` is provided, the pending future is removed on timeout so
        a missing external callback does not leave stale state behind.
        """
        async with self._lock:
            future = self._get_or_create_future(call_id)
        if timeout is None:
            return await future
        try:
            return await asyncio.wait_for(asyncio.shield(future), timeout=timeout)
        except asyncio.TimeoutError:
            async with self._lock:
                if self._futures.get(call_id) is future and not future.done():
                    self._futures.pop(call_id, None)
            raise

    async def publish(self, call_id: str, result: Any) -> None:
        """Publish a result for the given call_id."""
        async with self._lock:
            future = self._get_or_create_future(call_id)
            if not future.done():
                future.set_result(result)

    def cancel_all(self, reason: str = "Channel closed"):
        """Cancel all pending futures.

        Note: This is a synchronous method and must be called from the
        same event-loop thread that owns the futures.
        """
        for future in self._futures.values():
            if not future.done():
                future.set_exception(RuntimeError(reason))
        self._futures.clear()
