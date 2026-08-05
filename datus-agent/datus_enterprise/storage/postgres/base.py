"""Shared asyncpg pool and query lifecycle for PostgreSQL enterprise stores."""

from __future__ import annotations

import asyncio
import importlib
import inspect
from typing import Any

from datus.utils.exceptions import DatusException, ErrorCode
from datus.utils.loggings import get_logger
from datus_enterprise.storage.postgres.schema import _SCHEMA_SQL

logger = get_logger(__name__)

_TRANSIENT_CONNECTION_ERROR_NAMES = {
    "ConnectionDoesNotExistError",
    "ConnectionResetError",
    "ConnectionFailureError",
    "ConnectionError",
    "InterfaceError",
}


class _PgStoreBase:
    """Lazy asyncpg pool owner with idempotent schema initialization."""

    def __init__(
        self,
        dsn: str,
        *,
        min_size: int = 1,
        max_size: int = 2,
        command_timeout: float | None = 30.0,
    ) -> None:
        if not str(dsn or "").strip():
            raise DatusException(ErrorCode.COMMON_CONFIG_ERROR, message="PostgreSQL DSN is required.")
        self._dsn = dsn
        self._min_size = int(min_size)
        self._max_size = int(max_size)
        self._command_timeout = command_timeout
        self._pool: Any | None = None
        self._pool_loop: asyncio.AbstractEventLoop | None = None
        self._pools_by_loop: dict[int, tuple[asyncio.AbstractEventLoop, Any]] = {}
        self._schema_ready = False
        self._schema_locks_by_loop: dict[int, tuple[asyncio.AbstractEventLoop, asyncio.Lock]] = {}

    async def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        schema_lock = self._schema_lock_for_current_loop()
        async with schema_lock:
            if self._schema_ready:
                return
            for attempt in range(2):
                try:
                    pool = await self._get_pool()
                    async with pool.acquire() as conn:
                        await conn.execute(_SCHEMA_SQL)
                    self._schema_ready = True
                    return
                except Exception as exc:
                    if attempt == 0 and _is_transient_pg_connection_error(exc):
                        await self._reset_pool_after_connection_error(exc, operation="ensure_schema")
                        continue
                    raise

    async def _get_pool(self) -> Any:
        current_loop = asyncio.get_running_loop()
        loop_key = id(current_loop)
        entry = self._pools_by_loop.get(loop_key)
        if entry is not None and entry[0] is current_loop:
            self._pool_loop, self._pool = entry
            return self._pool
        if entry is not None:
            stale_loop, stale_pool = entry
            del self._pools_by_loop[loop_key]
            await _close_pool_best_effort(stale_pool, graceful=stale_loop is current_loop)

        asyncpg = importlib.import_module("asyncpg")
        pool = await asyncpg.create_pool(
            dsn=self._dsn,
            min_size=self._min_size,
            max_size=self._max_size,
            command_timeout=self._command_timeout,
        )
        self._pools_by_loop[loop_key] = (current_loop, pool)
        self._pool = pool
        self._pool_loop = current_loop
        return pool

    async def close(self) -> None:
        """Close the owned asyncpg pool."""
        pools = list(self._pools_by_loop.values())
        if not pools:
            return
        current_loop = asyncio.get_running_loop()
        self._pools_by_loop.clear()
        self._schema_locks_by_loop.clear()
        self._pool = None
        self._pool_loop = None
        self._schema_ready = False
        seen: set[int] = set()
        for pool_loop, pool in pools:
            pool_id = id(pool)
            if pool_id in seen:
                continue
            seen.add(pool_id)
            await _close_pool_best_effort(pool, graceful=pool_loop is current_loop)

    async def _reset_pool_after_connection_error(
        self, exc: BaseException, *, operation: str, graceful: bool = True
    ) -> None:
        current_loop = asyncio.get_running_loop()
        entry = self._pools_by_loop.pop(id(current_loop), None)
        pool_loop, pool = entry if entry is not None else (self._pool_loop, self._pool)
        if self._pool is pool:
            self._pool = None
            self._pool_loop = None
        self._schema_ready = False
        log = logger.debug if operation == "event_loop_changed" else logger.warning
        log(
            "%s %s resetting asyncpg pool: %s",
            self.__class__.__name__,
            operation,
            exc,
        )
        if pool is not None:
            await _close_pool_best_effort(pool, graceful=graceful and pool_loop is current_loop)

    def _schema_lock_for_current_loop(self) -> asyncio.Lock:
        current_loop = asyncio.get_running_loop()
        loop_key = id(current_loop)
        entry = self._schema_locks_by_loop.get(loop_key)
        if entry is not None and entry[0] is current_loop:
            return entry[1]
        lock = asyncio.Lock()
        self._schema_locks_by_loop[loop_key] = (current_loop, lock)
        return lock

    async def _fetch(self, query: str, *args: Any) -> list[Any]:
        for attempt in range(2):
            await self._ensure_schema()
            pool = await self._get_pool()
            try:
                async with pool.acquire() as conn:
                    return list(await conn.fetch(query, *args))
            except Exception as exc:
                if attempt == 0 and _is_transient_pg_connection_error(exc):
                    await self._reset_pool_after_connection_error(exc, operation=f"fetch {_query_summary(query)}")
                    continue
                logger.exception("%s fetch failed for query: %s", self.__class__.__name__, _query_summary(query))
                raise
        raise RuntimeError("unreachable PostgreSQL fetch retry state")

    async def _fetchrow(self, query: str, *args: Any) -> Any | None:
        for attempt in range(2):
            await self._ensure_schema()
            pool = await self._get_pool()
            try:
                async with pool.acquire() as conn:
                    return await conn.fetchrow(query, *args)
            except Exception as exc:
                if attempt == 0 and _is_transient_pg_connection_error(exc):
                    await self._reset_pool_after_connection_error(exc, operation=f"fetchrow {_query_summary(query)}")
                    continue
                logger.exception("%s fetchrow failed for query: %s", self.__class__.__name__, _query_summary(query))
                raise
        raise RuntimeError("unreachable PostgreSQL fetchrow retry state")

    async def _execute(self, query: str, *args: Any) -> str:
        for attempt in range(2):
            await self._ensure_schema()
            pool = await self._get_pool()
            try:
                async with pool.acquire() as conn:
                    return str(await conn.execute(query, *args))
            except Exception as exc:
                if attempt == 0 and _is_transient_pg_connection_error(exc):
                    await self._reset_pool_after_connection_error(exc, operation=f"execute {_query_summary(query)}")
                    continue
                logger.exception("%s execute failed for query: %s", self.__class__.__name__, _query_summary(query))
                raise
        raise RuntimeError("unreachable PostgreSQL execute retry state")


async def _close_pool_best_effort(pool: Any, *, graceful: bool = True) -> None:
    if not graceful:
        terminate = getattr(pool, "terminate", None)
        if terminate is not None:
            try:
                result = terminate()
                if inspect.isawaitable(result):
                    await result
                return
            except Exception as exc:
                if _is_event_loop_closed_error(exc):
                    logger.debug("Discarded asyncpg pool after its event loop was already closed")
                    return
                logger.warning("Failed to terminate asyncpg pool: %s", exc)
                return

    close = getattr(pool, "close", None)
    if close is not None:
        try:
            result = close()
            if inspect.isawaitable(result):
                await asyncio.wait_for(result, timeout=2.0)
            return
        except Exception as exc:
            logger.warning("Failed to close asyncpg pool cleanly; terminating if supported: %s", exc)

    terminate = getattr(pool, "terminate", None)
    if terminate is None:
        return
    try:
        result = terminate()
        if inspect.isawaitable(result):
            await result
    except Exception as exc:
        if _is_event_loop_closed_error(exc):
            logger.debug("Discarded asyncpg pool after its event loop was already closed")
            return
        logger.warning("Failed to terminate asyncpg pool: %s", exc)


def _is_event_loop_closed_error(exc: BaseException) -> bool:
    return isinstance(exc, RuntimeError) and "event loop is closed" in str(exc).lower()


def _is_transient_pg_connection_error(exc: BaseException) -> bool:
    current: BaseException | None = exc
    while current is not None:
        exc_type = type(current)
        name = exc_type.__name__
        module = exc_type.__module__
        if name in _TRANSIENT_CONNECTION_ERROR_NAMES:
            return True
        if module.startswith("asyncpg.") and "connection" in str(current).lower() and "closed" in str(current).lower():
            return True
        if isinstance(current, (ConnectionError, OSError)):
            return True
        current = current.__cause__ or current.__context__
    message = str(exc).lower()
    return "connection was closed" in message or "connection is closed" in message or "pool is closed" in message


def _query_summary(query: str) -> str:
    return " ".join(str(query).split())[:160]
