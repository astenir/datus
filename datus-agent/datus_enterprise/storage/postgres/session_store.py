"""PostgreSQL storage and query operations for chat session bodies."""

from __future__ import annotations

import asyncio
import importlib
import json
import logging
import threading
from typing import Any, Awaitable, Callable, TypeVar

from datus.utils.exceptions import DatusException, ErrorCode
from datus.utils.message_utils import extract_user_input
from datus_enterprise.storage.postgres.base import (
    _close_pool_best_effort,
    _is_transient_pg_connection_error,
    _query_summary,
)
from datus_enterprise.storage.postgres.session_body import PgSessionBodySession
from datus_enterprise.storage.postgres.session_records import (
    _ensure_body,
    _iso,
    _loads,
    _normalize_project_id,
    _normalize_scope,
)
from datus_enterprise.storage.postgres.session_schema import _SCHEMA_SQL

logger = logging.getLogger(__name__)
_T = TypeVar("_T")


class PgSessionBodyStore:
    """PostgreSQL-backed AdvancedSQLiteSession-compatible body store."""

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
        self._sync_loop: asyncio.AbstractEventLoop | None = None
        self._sync_thread: threading.Thread | None = None
        self._sync_loop_lock = threading.Lock()

    def open_session(self, *, project_id: str, scope: str | None, session_id: str) -> "PgSessionBodySession":
        return PgSessionBodySession(
            store=self,
            project_id=_normalize_project_id(project_id),
            scope=_normalize_scope(scope),
            session_id=session_id,
        )

    async def close(self) -> None:
        pools = list(self._pools_by_loop.values())
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
        self._stop_sync_loop()

    def run_sync(self, operation: Callable[[], Awaitable[_T]]) -> _T:
        """Run a body-store coroutine on one persistent loop for sync callers.

        ``SessionManager`` still exposes synchronous methods for CLI and legacy
        call sites. Creating a fresh event loop for every call causes asyncpg to
        create a fresh pool per loop. Keeping one bridge loop per store bounds
        sync-path PostgreSQL usage to one pool instead of one pool per call.
        """
        loop = self._ensure_sync_loop()
        future = asyncio.run_coroutine_threadsafe(operation(), loop)
        return future.result()

    def _ensure_sync_loop(self) -> asyncio.AbstractEventLoop:
        with self._sync_loop_lock:
            if self._sync_loop is not None and self._sync_loop.is_running():
                return self._sync_loop

            ready = threading.Event()
            loop_holder: dict[str, asyncio.AbstractEventLoop] = {}

            def _run_loop() -> None:
                loop = asyncio.new_event_loop()
                loop_holder["loop"] = loop
                self._sync_loop = loop
                asyncio.set_event_loop(loop)
                ready.set()
                try:
                    loop.run_forever()
                finally:
                    pending = asyncio.all_tasks(loop)
                    for task in pending:
                        task.cancel()
                    if pending:
                        try:
                            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                        except Exception as exc:
                            logger.debug("Failed to drain PgSessionBodyStore sync loop tasks: %s", exc)
                    loop.close()

            thread = threading.Thread(
                target=_run_loop,
                name="pg-session-body-store-sync-loop",
                daemon=True,
            )
            self._sync_thread = thread
            thread.start()
            ready.wait(timeout=2.0)
            loop = loop_holder.get("loop")
            if loop is None:
                raise RuntimeError("Failed to start PgSessionBodyStore sync loop")
            return loop

    def _stop_sync_loop(self) -> None:
        with self._sync_loop_lock:
            loop = self._sync_loop
            thread = self._sync_thread
            self._sync_loop = None
            self._sync_thread = None
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(loop.stop)
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
            if thread.is_alive():
                logger.warning("PgSessionBodyStore sync loop thread did not stop within timeout")

    async def session_exists(self, *, project_id: str, scope: str | None, session_id: str) -> bool:
        row = await self._fetchrow(
            """
            SELECT 1
            FROM enterprise_session_bodies b
            WHERE b.project_id = $1
              AND b.scope = $2
              AND b.session_id = $3
              AND (
                  EXISTS (
                    SELECT 1 FROM enterprise_session_messages m
                    WHERE m.project_id = b.project_id
                      AND m.scope = b.scope
                      AND m.session_id = b.session_id
                    LIMIT 1
                  )
                  OR b.session_id IS NOT NULL
              )
            """,
            _normalize_project_id(project_id),
            _normalize_scope(scope),
            session_id,
        )
        return row is not None

    async def list_session_ids(
        self,
        *,
        project_id: str,
        scope: str | None,
        limit: int | None = None,
        sort_by_modified: bool = False,
    ) -> list[str]:
        order_by = "updated_at DESC, session_id ASC" if sort_by_modified else "session_id ASC"
        query = f"""
            SELECT session_id
            FROM enterprise_session_bodies
            WHERE project_id = $1 AND scope = $2
            ORDER BY {order_by}
            """
        rows = await self._fetch(query, _normalize_project_id(project_id), _normalize_scope(scope))
        session_ids = [str(row["session_id"]) for row in rows]
        return session_ids[:limit] if limit is not None else session_ids

    async def get_session_info(self, *, project_id: str, scope: str | None, session_id: str) -> dict[str, Any]:
        row = await self._fetchrow(
            """
            SELECT created_at, updated_at
            FROM enterprise_session_bodies
            WHERE project_id = $1 AND scope = $2 AND session_id = $3
            """,
            _normalize_project_id(project_id),
            _normalize_scope(scope),
            session_id,
        )
        if row is None:
            return {"exists": False}

        stats = await self._fetchrow(
            """
            SELECT COUNT(*) AS message_count, MAX(created_at) AS latest_message_at
            FROM enterprise_session_messages
            WHERE project_id = $1 AND scope = $2 AND session_id = $3
            """,
            _normalize_project_id(project_id),
            _normalize_scope(scope),
            session_id,
        )
        token_row = await self._fetchrow(
            """
            SELECT COALESCE(SUM(total_tokens), 0) AS total_tokens
            FROM enterprise_session_turn_usage
            WHERE project_id = $1 AND scope = $2 AND session_id = $3
            """,
            _normalize_project_id(project_id),
            _normalize_scope(scope),
            session_id,
        )
        message_rows = await self._message_rows(
            project_id=_normalize_project_id(project_id),
            scope=_normalize_scope(scope),
            session_id=session_id,
            desc=True,
        )
        latest_user_message = None
        latest_user_message_at = None
        first_user_message = None
        first_user_message_at = None
        for message_data, created_at in message_rows:
            parsed = _loads(message_data)
            if isinstance(parsed, dict) and parsed.get("role") == "user":
                latest_user_message = extract_user_input(parsed.get("content", ""))
                latest_user_message_at = created_at
                break
        for message_data, created_at in reversed(message_rows):
            parsed = _loads(message_data)
            if isinstance(parsed, dict) and parsed.get("role") == "user":
                first_user_message = extract_user_input(parsed.get("content", ""))
                first_user_message_at = created_at
                break

        message_count = int(stats["message_count"] or 0) if stats else 0
        return {
            "exists": True,
            "session_id": session_id,
            "created_at": _iso(row["created_at"]),
            "updated_at": _iso(row["updated_at"]),
            "file_modified_iso": _iso(row["updated_at"]),
            "total_tokens": int(token_row["total_tokens"] or 0) if token_row else 0,
            "message_count": message_count,
            "item_count": message_count,
            "latest_message_at": _iso(stats["latest_message_at"]) if stats else None,
            "latest_user_message": latest_user_message,
            "latest_user_message_at": _iso(latest_user_message_at),
            "first_user_message": first_user_message,
            "first_user_message_at": _iso(first_user_message_at),
        }

    async def delete_session(self, *, project_id: str, scope: str | None, session_id: str) -> None:
        await self._ensure_schema()
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                keys = (_normalize_project_id(project_id), _normalize_scope(scope), session_id)
                await conn.execute(
                    "DELETE FROM enterprise_session_running_usage WHERE project_id=$1 AND scope=$2 AND session_id=$3",
                    *keys,
                )
                await conn.execute(
                    "DELETE FROM enterprise_session_system_prompts WHERE project_id=$1 AND scope=$2 AND session_id=$3",
                    *keys,
                )
                await conn.execute(
                    "DELETE FROM enterprise_session_terminal_events WHERE project_id=$1 AND scope=$2 AND session_id=$3",
                    *keys,
                )
                await conn.execute(
                    "DELETE FROM enterprise_session_turn_usage WHERE project_id=$1 AND scope=$2 AND session_id=$3",
                    *keys,
                )
                await conn.execute(
                    "DELETE FROM enterprise_session_message_structure WHERE project_id=$1 AND scope=$2 AND session_id=$3",
                    *keys,
                )
                await conn.execute(
                    "DELETE FROM enterprise_session_messages WHERE project_id=$1 AND scope=$2 AND session_id=$3",
                    *keys,
                )
                await conn.execute(
                    "DELETE FROM enterprise_session_bodies WHERE project_id=$1 AND scope=$2 AND session_id=$3",
                    *keys,
                )

    async def copy_session(
        self,
        *,
        project_id: str,
        scope: str | None,
        source_session_id: str,
        target_session_id: str,
    ) -> None:
        project = _normalize_project_id(project_id)
        scoped = _normalize_scope(scope)
        await self._ensure_schema()
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                source = await conn.fetchrow(
                    """
                    SELECT created_at
                    FROM enterprise_session_bodies
                    WHERE project_id=$1 AND scope=$2 AND session_id=$3
                    """,
                    project,
                    scoped,
                    source_session_id,
                )
                if source is None:
                    return
                await _ensure_body(conn, project, scoped, target_session_id)
                rows = await conn.fetch(
                    """
                    SELECT id, message_data
                    FROM enterprise_session_messages
                    WHERE project_id=$1 AND scope=$2 AND session_id=$3
                    ORDER BY id ASC
                    """,
                    project,
                    scoped,
                    source_session_id,
                )
                id_map: dict[int, int] = {}
                for row in rows:
                    new_id = await conn.fetchval(
                        """
                        INSERT INTO enterprise_session_messages (project_id, scope, session_id, message_data)
                        VALUES ($1, $2, $3, $4)
                        RETURNING id
                        """,
                        project,
                        scoped,
                        target_session_id,
                        str(row["message_data"]),
                    )
                    id_map[int(row["id"])] = int(new_id)
                structure_rows = await conn.fetch(
                    """
                    SELECT message_id, branch_id, message_type, sequence_number, user_turn_number,
                           branch_turn_number, tool_name
                    FROM enterprise_session_message_structure
                    WHERE project_id=$1 AND scope=$2 AND session_id=$3
                    ORDER BY sequence_number ASC
                    """,
                    project,
                    scoped,
                    source_session_id,
                )
                await conn.executemany(
                    """
                    INSERT INTO enterprise_session_message_structure
                    (project_id, scope, session_id, message_id, branch_id, message_type, sequence_number,
                     user_turn_number, branch_turn_number, tool_name)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                    """,
                    [
                        (
                            project,
                            scoped,
                            target_session_id,
                            id_map[int(row["message_id"])],
                            row["branch_id"],
                            row["message_type"],
                            row["sequence_number"],
                            row["user_turn_number"],
                            row["branch_turn_number"],
                            row["tool_name"],
                        )
                        for row in structure_rows
                        if int(row["message_id"]) in id_map
                    ],
                )
                usage_rows = await conn.fetch(
                    """
                    SELECT branch_id, user_turn_number, requests, input_tokens, output_tokens,
                           total_tokens, input_tokens_details, output_tokens_details
                    FROM enterprise_session_turn_usage
                    WHERE project_id=$1 AND scope=$2 AND session_id=$3
                    """,
                    project,
                    scoped,
                    source_session_id,
                )
                await conn.executemany(
                    """
                    INSERT INTO enterprise_session_turn_usage
                    (project_id, scope, session_id, branch_id, user_turn_number, requests, input_tokens,
                     output_tokens, total_tokens, input_tokens_details, output_tokens_details)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                    ON CONFLICT(project_id, scope, session_id, branch_id, user_turn_number) DO UPDATE SET
                      requests=excluded.requests,
                      input_tokens=excluded.input_tokens,
                      output_tokens=excluded.output_tokens,
                      total_tokens=excluded.total_tokens,
                      input_tokens_details=excluded.input_tokens_details,
                      output_tokens_details=excluded.output_tokens_details
                    """,
                    [
                        (
                            project,
                            scoped,
                            target_session_id,
                            row["branch_id"],
                            row["user_turn_number"],
                            row["requests"],
                            row["input_tokens"],
                            row["output_tokens"],
                            row["total_tokens"],
                            row["input_tokens_details"],
                            row["output_tokens_details"],
                        )
                        for row in usage_rows
                    ],
                )
                prompt_row = await conn.fetchrow(
                    """
                    SELECT snapshot_json
                    FROM enterprise_session_system_prompts
                    WHERE project_id=$1 AND scope=$2 AND session_id=$3
                    """,
                    project,
                    scoped,
                    source_session_id,
                )
                if prompt_row is not None:
                    await conn.execute(
                        """
                        INSERT INTO enterprise_session_system_prompts
                        (project_id, scope, session_id, snapshot_json, updated_at)
                        VALUES ($1,$2,$3,$4,now())
                        ON CONFLICT(project_id, scope, session_id) DO UPDATE SET
                          snapshot_json=excluded.snapshot_json,
                          updated_at=now()
                        """,
                        project,
                        scoped,
                        target_session_id,
                        str(prompt_row["snapshot_json"]),
                    )

    async def get_session_messages(
        self, *, project_id: str, scope: str | None, session_id: str
    ) -> list[dict[str, Any]]:
        return [
            {"message_data": message_data, "created_at": created_at}
            for message_data, created_at in await self._message_rows(
                project_id=_normalize_project_id(project_id),
                scope=_normalize_scope(scope),
                session_id=session_id,
            )
        ]

    async def append_session_terminal_event(
        self,
        *,
        project_id: str,
        scope: str | None,
        session_id: str,
        event: dict[str, Any],
    ) -> None:
        await self._ensure_schema()
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO enterprise_session_terminal_events
                  (project_id, scope, session_id, event_id, event_type, payload_json)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (project_id, scope, session_id, event_id) DO NOTHING
                """,
                _normalize_project_id(project_id),
                _normalize_scope(scope),
                session_id,
                str(event["event_id"]),
                str(event["event_type"]),
                json.dumps(event, ensure_ascii=False),
            )

    async def get_session_terminal_events(
        self, *, project_id: str, scope: str | None, session_id: str
    ) -> list[dict[str, Any]]:
        await self._ensure_schema()
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT payload_json
                FROM enterprise_session_terminal_events
                WHERE project_id=$1 AND scope=$2 AND session_id=$3
                ORDER BY created_at, id
                """,
                _normalize_project_id(project_id),
                _normalize_scope(scope),
                session_id,
            )
        events: list[dict[str, Any]] = []
        for row in rows:
            payload = _loads(row["payload_json"])
            if isinstance(payload, dict):
                events.append(payload)
        return events

    async def get_detailed_usage(self, *, project_id: str, scope: str | None, session_id: str) -> dict[str, Any]:
        session = self.open_session(project_id=project_id, scope=scope, session_id=session_id)
        turns = await session.get_turn_usage()
        total = {"requests": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cached_tokens": 0}
        for turn in turns if isinstance(turns, list) else []:
            total["requests"] += int(turn.get("requests", 0) or 0)
            total["input_tokens"] += int(turn.get("input_tokens", 0) or 0)
            total["output_tokens"] += int(turn.get("output_tokens", 0) or 0)
            total["total_tokens"] += int(turn.get("total_tokens", 0) or 0)
            details = turn.get("input_tokens_details") or {}
            if isinstance(details, dict):
                total["cached_tokens"] += int(details.get("cached_tokens", 0) or 0)
        running = await self.get_running_turn_usage(project_id=project_id, scope=scope, session_id=session_id)
        if running is not None:
            cumulative = running.get("cumulative") or {}
            for key in ("requests", "input_tokens", "output_tokens", "total_tokens", "cached_tokens"):
                total[key] += int(cumulative.get(key, 0) or 0)
        return {
            "total": total,
            "turns": turns,
            "turn_count": len(turns) if isinstance(turns, list) else 0,
            "running": running,
        }

    async def upsert_running_turn_usage(
        self,
        *,
        project_id: str,
        scope: str | None,
        session_id: str,
        user_turn_number: int,
        cumulative: dict[str, Any],
        context_length: int,
    ) -> None:
        exists = await self.session_exists(project_id=project_id, scope=scope, session_id=session_id)
        if not exists:
            return
        await self._execute(
            """
            INSERT INTO enterprise_session_running_usage
            (project_id, scope, session_id, user_turn_number, cumulative_json, context_length, updated_at)
            VALUES ($1,$2,$3,$4,$5,$6,now())
            ON CONFLICT(project_id, scope, session_id) DO UPDATE SET
              user_turn_number=excluded.user_turn_number,
              cumulative_json=excluded.cumulative_json,
              context_length=excluded.context_length,
              updated_at=now()
            """,
            _normalize_project_id(project_id),
            _normalize_scope(scope),
            session_id,
            int(user_turn_number or 0),
            json.dumps(cumulative or {}, ensure_ascii=False),
            int(context_length or 0),
        )

    async def get_running_turn_usage(
        self, *, project_id: str, scope: str | None, session_id: str
    ) -> dict[str, Any] | None:
        row = await self._fetchrow(
            """
            SELECT user_turn_number, cumulative_json, context_length, updated_at
            FROM enterprise_session_running_usage
            WHERE project_id=$1 AND scope=$2 AND session_id=$3
            """,
            _normalize_project_id(project_id),
            _normalize_scope(scope),
            session_id,
        )
        if row is None:
            return None
        return {
            "user_turn_number": int(row["user_turn_number"] or 0),
            "cumulative": _loads(row["cumulative_json"]) or {},
            "context_length": int(row["context_length"] or 0),
            "updated_at": _iso(row["updated_at"]),
        }

    async def clear_running_turn_usage(self, *, project_id: str, scope: str | None, session_id: str) -> None:
        await self._execute(
            "DELETE FROM enterprise_session_running_usage WHERE project_id=$1 AND scope=$2 AND session_id=$3",
            _normalize_project_id(project_id),
            _normalize_scope(scope),
            session_id,
        )

    async def save_system_prompt_snapshot(
        self,
        *,
        project_id: str,
        scope: str | None,
        session_id: str,
        payload: dict[str, Any],
    ) -> None:
        await self._execute(
            """
            INSERT INTO enterprise_session_system_prompts
            (project_id, scope, session_id, snapshot_json, updated_at)
            VALUES ($1,$2,$3,$4,now())
            ON CONFLICT(project_id, scope, session_id) DO UPDATE SET
              snapshot_json=excluded.snapshot_json,
              updated_at=now()
            """,
            _normalize_project_id(project_id),
            _normalize_scope(scope),
            session_id,
            json.dumps(payload, ensure_ascii=False),
        )

    async def load_system_prompt_snapshot(
        self, *, project_id: str, scope: str | None, session_id: str
    ) -> dict[str, Any] | None:
        row = await self._fetchrow(
            """
            SELECT snapshot_json
            FROM enterprise_session_system_prompts
            WHERE project_id=$1 AND scope=$2 AND session_id=$3
            """,
            _normalize_project_id(project_id),
            _normalize_scope(scope),
            session_id,
        )
        if row is None:
            return None
        payload = _loads(row["snapshot_json"])
        return payload if isinstance(payload, dict) else None

    async def delete_system_prompt_snapshot(self, *, project_id: str, scope: str | None, session_id: str) -> None:
        await self._execute(
            "DELETE FROM enterprise_session_system_prompts WHERE project_id=$1 AND scope=$2 AND session_id=$3",
            _normalize_project_id(project_id),
            _normalize_scope(scope),
            session_id,
        )

    async def _message_rows(
        self, *, project_id: str, scope: str, session_id: str, desc: bool = False
    ) -> list[tuple[str, Any]]:
        order = "DESC" if desc else "ASC"
        rows = await self._fetch(
            f"""
            SELECT message_data, created_at
            FROM enterprise_session_messages
            WHERE project_id=$1 AND scope=$2 AND session_id=$3
            ORDER BY created_at {order}, id {order}
            """,
            project_id,
            scope,
            session_id,
        )
        return [(str(row["message_data"]), row["created_at"]) for row in rows]

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
