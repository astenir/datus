"""PostgreSQL-backed chat session body store.

This store persists the body/state that ``AdvancedSQLiteSession`` keeps in
local SQLite files: agent messages, message structure, turn usage, running
turn usage, and system-prompt snapshots. It does not replace
``SessionOwnerStore``; owner metadata remains the authorization/index surface.

Schema bootstrap is intentionally limited to additive
``CREATE TABLE IF NOT EXISTS`` / ``CREATE INDEX IF NOT EXISTS`` statements.
Production migrations are a separate operations concern.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

from agents.items import TResponseInputItem

from datus.utils.exceptions import DatusException, ErrorCode
from datus.utils.message_utils import extract_user_input
from datus.utils.time_utils import to_utc_iso
from datus_enterprise.postgres_stores import (
    _close_pool_best_effort,
    _is_transient_pg_connection_error,
    _query_summary,
)

logger = logging.getLogger(__name__)


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
        self._schema_ready = False
        self._schema_lock = asyncio.Lock()

    def open_session(self, *, project_id: str, scope: str | None, session_id: str) -> "PgSessionBodySession":
        return PgSessionBodySession(
            store=self,
            project_id=_normalize_project_id(project_id),
            scope=_normalize_scope(scope),
            session_id=session_id,
        )

    async def close(self) -> None:
        pool = self._pool
        if pool is None:
            return
        pool_loop = self._pool_loop
        self._pool = None
        self._pool_loop = None
        self._schema_ready = False
        await _close_pool_best_effort(pool, graceful=pool_loop is asyncio.get_running_loop())

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
        async with self._schema_lock:
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
        if self._pool is not None and self._pool_loop is not current_loop:
            await self._reset_pool_after_connection_error(
                RuntimeError("asyncpg pool is bound to a different event loop"),
                operation="event_loop_changed",
                graceful=False,
            )
        if self._pool is None:
            asyncpg = importlib.import_module("asyncpg")
            self._pool = await asyncpg.create_pool(
                dsn=self._dsn,
                min_size=self._min_size,
                max_size=self._max_size,
                command_timeout=self._command_timeout,
            )
            self._pool_loop = current_loop
        return self._pool

    async def _reset_pool_after_connection_error(
        self, exc: BaseException, *, operation: str, graceful: bool = True
    ) -> None:
        pool = self._pool
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
            await _close_pool_best_effort(pool, graceful=graceful)

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


class PgSessionBodySession:
    """AdvancedSQLiteSession-compatible PG session handle."""

    def __init__(self, *, store: PgSessionBodyStore, project_id: str, scope: str, session_id: str) -> None:
        self._store = store
        self._project_id = project_id
        self._scope = scope
        self.session_id = session_id
        self._current_branch_id = "main"
        self._logger = logging.getLogger(__name__)

    async def add_items(self, items: list[TResponseInputItem]) -> None:
        if not items:
            return
        await self._store._ensure_schema()
        pool = await self._store._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                await _ensure_body(conn, self._project_id, self._scope, self.session_id)
                message_ids: list[int] = []
                for item in items:
                    message_id = await conn.fetchval(
                        """
                        INSERT INTO enterprise_session_messages (project_id, scope, session_id, message_data)
                        VALUES ($1,$2,$3,$4)
                        RETURNING id
                        """,
                        self._project_id,
                        self._scope,
                        self.session_id,
                        json.dumps(item, ensure_ascii=False),
                    )
                    message_ids.append(int(message_id))
                seq_start = await conn.fetchval(
                    """
                    SELECT COALESCE(MAX(sequence_number), 0)
                    FROM enterprise_session_message_structure
                    WHERE project_id=$1 AND scope=$2 AND session_id=$3
                    """,
                    self._project_id,
                    self._scope,
                    self.session_id,
                )
                turn_row = await conn.fetchrow(
                    """
                    SELECT
                      COALESCE(MAX(user_turn_number), 0) AS user_turn_number,
                      COALESCE(MAX(branch_turn_number), 0) AS branch_turn_number
                    FROM enterprise_session_message_structure
                    WHERE project_id=$1 AND scope=$2 AND session_id=$3 AND branch_id=$4
                    """,
                    self._project_id,
                    self._scope,
                    self.session_id,
                    self._current_branch_id,
                )
                current_turn = int(turn_row["user_turn_number"] or 0) if turn_row else 0
                current_branch_turn = int(turn_row["branch_turn_number"] or 0) if turn_row else 0
                structure_rows = []
                user_message_count = 0
                for index, (item, message_id) in enumerate(zip(items, message_ids)):
                    if _is_user_message(item):
                        user_message_count += 1
                    item_turn = current_turn + user_message_count
                    branch_turn = current_branch_turn + user_message_count
                    structure_rows.append(
                        (
                            self._project_id,
                            self._scope,
                            self.session_id,
                            message_id,
                            self._current_branch_id,
                            _classify_message_type(item),
                            int(seq_start or 0) + index + 1,
                            item_turn,
                            branch_turn,
                            _extract_tool_name(item),
                        )
                    )
                await conn.executemany(
                    """
                    INSERT INTO enterprise_session_message_structure
                    (project_id, scope, session_id, message_id, branch_id, message_type, sequence_number,
                     user_turn_number, branch_turn_number, tool_name)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                    """,
                    structure_rows,
                )
                await conn.execute(
                    """
                    UPDATE enterprise_session_bodies
                    SET updated_at=now()
                    WHERE project_id=$1 AND scope=$2 AND session_id=$3
                    """,
                    self._project_id,
                    self._scope,
                    self.session_id,
                )

    async def get_items(self, limit: int | None = None, branch_id: str | None = None) -> list[TResponseInputItem]:
        branch = branch_id or self._current_branch_id
        if limit is None:
            rows = await self._store._fetch(
                """
                SELECT m.message_data
                FROM enterprise_session_messages m
                JOIN enterprise_session_message_structure s
                  ON m.id = s.message_id
                 AND m.project_id = s.project_id
                 AND m.scope = s.scope
                 AND m.session_id = s.session_id
                WHERE m.project_id=$1 AND m.scope=$2 AND m.session_id=$3 AND s.branch_id=$4
                ORDER BY s.sequence_number ASC
                """,
                self._project_id,
                self._scope,
                self.session_id,
                branch,
            )
        else:
            rows = await self._store._fetch(
                """
                SELECT m.message_data
                FROM enterprise_session_messages m
                JOIN enterprise_session_message_structure s
                  ON m.id = s.message_id
                 AND m.project_id = s.project_id
                 AND m.scope = s.scope
                 AND m.session_id = s.session_id
                WHERE m.project_id=$1 AND m.scope=$2 AND m.session_id=$3 AND s.branch_id=$4
                ORDER BY s.sequence_number DESC
                LIMIT $5
                """,
                self._project_id,
                self._scope,
                self.session_id,
                branch,
                int(limit),
            )
            rows = list(reversed(rows))
        items: list[TResponseInputItem] = []
        for row in rows:
            parsed = _loads(row["message_data"])
            if isinstance(parsed, dict):
                items.append(parsed)
        return items

    async def pop_item(self) -> TResponseInputItem | None:
        await self._store._ensure_schema()
        pool = await self._store._get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    SELECT id, message_data
                    FROM enterprise_session_messages
                    WHERE project_id=$1 AND scope=$2 AND session_id=$3
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    self._project_id,
                    self._scope,
                    self.session_id,
                )
                if row is None:
                    return None
                await conn.execute(
                    """
                    DELETE FROM enterprise_session_message_structure
                    WHERE project_id=$1 AND scope=$2 AND session_id=$3 AND message_id=$4
                    """,
                    self._project_id,
                    self._scope,
                    self.session_id,
                    row["id"],
                )
                await conn.execute(
                    "DELETE FROM enterprise_session_messages WHERE id=$1",
                    row["id"],
                )
        parsed = _loads(row["message_data"])
        return parsed if isinstance(parsed, dict) else None

    async def clear_session(self) -> None:
        await self._store.delete_session(project_id=self._project_id, scope=self._scope, session_id=self.session_id)

    async def store_run_usage(self, result: Any) -> None:
        try:
            usage = result.context_wrapper.usage
        except Exception:
            usage = None
        if usage is None:
            return
        current_turn = await self._current_turn_number()
        await self._store._execute(
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
              output_tokens_details=excluded.output_tokens_details,
              created_at=now()
            """,
            self._project_id,
            self._scope,
            self.session_id,
            self._current_branch_id,
            int(current_turn or 0),
            int(getattr(usage, "requests", 0) or 0),
            int(getattr(usage, "input_tokens", 0) or 0),
            int(getattr(usage, "output_tokens", 0) or 0),
            int(getattr(usage, "total_tokens", 0) or 0),
            _details_json(getattr(usage, "input_tokens_details", None)),
            _details_json(getattr(usage, "output_tokens_details", None)),
        )

    async def get_turn_usage(
        self, user_turn_number: int | None = None, branch_id: str | None = None
    ) -> list[dict[str, Any]] | dict[str, Any]:
        branch = branch_id or self._current_branch_id
        if user_turn_number is not None:
            row = await self._store._fetchrow(
                """
                SELECT requests, input_tokens, output_tokens, total_tokens,
                       input_tokens_details, output_tokens_details
                FROM enterprise_session_turn_usage
                WHERE project_id=$1 AND scope=$2 AND session_id=$3 AND branch_id=$4 AND user_turn_number=$5
                """,
                self._project_id,
                self._scope,
                self.session_id,
                branch,
                int(user_turn_number),
            )
            return _usage_record(row, include_turn=False) if row else {}
        rows = await self._store._fetch(
            """
            SELECT user_turn_number, requests, input_tokens, output_tokens, total_tokens,
                   input_tokens_details, output_tokens_details
            FROM enterprise_session_turn_usage
            WHERE project_id=$1 AND scope=$2 AND session_id=$3 AND branch_id=$4
            ORDER BY user_turn_number ASC
            """,
            self._project_id,
            self._scope,
            self.session_id,
            branch,
        )
        return [_usage_record(row, include_turn=True) for row in rows]

    async def get_session_usage(self, branch_id: str | None = None) -> dict[str, int] | None:
        branch_filter = branch_id
        if branch_filter:
            row = await self._store._fetchrow(
                """
                SELECT SUM(requests) AS requests, SUM(input_tokens) AS input_tokens,
                       SUM(output_tokens) AS output_tokens, SUM(total_tokens) AS total_tokens,
                       COUNT(*) AS total_turns
                FROM enterprise_session_turn_usage
                WHERE project_id=$1 AND scope=$2 AND session_id=$3 AND branch_id=$4
                """,
                self._project_id,
                self._scope,
                self.session_id,
                branch_filter,
            )
        else:
            row = await self._store._fetchrow(
                """
                SELECT SUM(requests) AS requests, SUM(input_tokens) AS input_tokens,
                       SUM(output_tokens) AS output_tokens, SUM(total_tokens) AS total_tokens,
                       COUNT(*) AS total_turns
                FROM enterprise_session_turn_usage
                WHERE project_id=$1 AND scope=$2 AND session_id=$3
                """,
                self._project_id,
                self._scope,
                self.session_id,
            )
        if row is None or row["requests"] is None:
            return None
        return {
            "requests": int(row["requests"] or 0),
            "input_tokens": int(row["input_tokens"] or 0),
            "output_tokens": int(row["output_tokens"] or 0),
            "total_tokens": int(row["total_tokens"] or 0),
            "total_turns": int(row["total_turns"] or 0),
        }

    async def _current_turn_number(self) -> int:
        row = await self._store._fetchrow(
            """
            SELECT COALESCE(MAX(user_turn_number), 0) AS turn
            FROM enterprise_session_message_structure
            WHERE project_id=$1 AND scope=$2 AND session_id=$3 AND branch_id=$4
            """,
            self._project_id,
            self._scope,
            self.session_id,
            self._current_branch_id,
        )
        return int(row["turn"] or 0) if row else 0


async def _ensure_body(conn: Any, project_id: str, scope: str, session_id: str) -> None:
    await conn.execute(
        """
        INSERT INTO enterprise_session_bodies (project_id, scope, session_id, created_at, updated_at)
        VALUES ($1, $2, $3, now(), now())
        ON CONFLICT(project_id, scope, session_id) DO UPDATE SET updated_at=now()
        """,
        project_id,
        scope,
        session_id,
    )


def _normalize_project_id(project_id: str | None) -> str:
    value = str(project_id or "").strip()
    return value or "default"


def _normalize_scope(scope: str | None) -> str:
    return str(scope or "")


def _loads(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds") + "Z"
    return to_utc_iso(value)


def _is_user_message(item: Any) -> bool:
    return isinstance(item, dict) and item.get("role") == "user"


def _classify_message_type(item: Any) -> str:
    if isinstance(item, dict):
        if item.get("role") == "user":
            return "user"
        if item.get("role") == "assistant":
            return "assistant"
        if item.get("type"):
            return str(item.get("type"))
    return "other"


def _extract_tool_name(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None
    item_type = item.get("type")
    if item_type in {"mcp_call", "mcp_approval_request"} and "server_label" in item:
        server_label = item.get("server_label")
        tool_name = item.get("name")
        if tool_name and server_label:
            return f"{server_label}.{tool_name}"
        if server_label:
            return str(server_label)
        if tool_name:
            return str(tool_name)
    if item_type in {"computer_call", "file_search_call", "web_search_call", "code_interpreter_call"}:
        return str(item_type)
    if "name" in item:
        name = item.get("name")
        return str(name) if name is not None else None
    return None


def _details_json(value: Any) -> str | None:
    if not value:
        return None
    try:
        if isinstance(value, dict):
            return json.dumps(value)
        return json.dumps(value.__dict__)
    except (TypeError, ValueError):
        return None


def _usage_record(row: Any, *, include_turn: bool) -> dict[str, Any]:
    if row is None:
        return {}
    record = {
        "requests": int(row["requests"] or 0),
        "input_tokens": int(row["input_tokens"] or 0),
        "output_tokens": int(row["output_tokens"] or 0),
        "total_tokens": int(row["total_tokens"] or 0),
        "input_tokens_details": _loads(row["input_tokens_details"]) if row["input_tokens_details"] else None,
        "output_tokens_details": _loads(row["output_tokens_details"]) if row["output_tokens_details"] else None,
    }
    if include_turn:
        record = {"user_turn_number": int(row["user_turn_number"] or 0), **record}
    return record


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS enterprise_session_bodies (
  project_id TEXT NOT NULL,
  scope TEXT NOT NULL DEFAULT '',
  session_id TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (project_id, scope, session_id)
);

CREATE TABLE IF NOT EXISTS enterprise_session_messages (
  id BIGSERIAL PRIMARY KEY,
  project_id TEXT NOT NULL,
  scope TEXT NOT NULL DEFAULT '',
  session_id TEXT NOT NULL,
  message_data TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS enterprise_session_message_structure (
  id BIGSERIAL PRIMARY KEY,
  project_id TEXT NOT NULL,
  scope TEXT NOT NULL DEFAULT '',
  session_id TEXT NOT NULL,
  message_id BIGINT NOT NULL,
  branch_id TEXT NOT NULL DEFAULT 'main',
  message_type TEXT NOT NULL,
  sequence_number INTEGER NOT NULL,
  user_turn_number INTEGER,
  branch_turn_number INTEGER,
  tool_name TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS enterprise_session_turn_usage (
  id BIGSERIAL PRIMARY KEY,
  project_id TEXT NOT NULL,
  scope TEXT NOT NULL DEFAULT '',
  session_id TEXT NOT NULL,
  branch_id TEXT NOT NULL DEFAULT 'main',
  user_turn_number INTEGER NOT NULL,
  requests INTEGER NOT NULL DEFAULT 0,
  input_tokens INTEGER NOT NULL DEFAULT 0,
  output_tokens INTEGER NOT NULL DEFAULT 0,
  total_tokens INTEGER NOT NULL DEFAULT 0,
  input_tokens_details TEXT,
  output_tokens_details TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(project_id, scope, session_id, branch_id, user_turn_number)
);

CREATE TABLE IF NOT EXISTS enterprise_session_running_usage (
  project_id TEXT NOT NULL,
  scope TEXT NOT NULL DEFAULT '',
  session_id TEXT NOT NULL,
  user_turn_number INTEGER,
  cumulative_json TEXT,
  context_length INTEGER,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (project_id, scope, session_id)
);

CREATE TABLE IF NOT EXISTS enterprise_session_system_prompts (
  project_id TEXT NOT NULL,
  scope TEXT NOT NULL DEFAULT '',
  session_id TEXT NOT NULL,
  snapshot_json TEXT NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (project_id, scope, session_id)
);

CREATE INDEX IF NOT EXISTS idx_enterprise_session_bodies_updated
  ON enterprise_session_bodies (project_id, scope, updated_at);
CREATE INDEX IF NOT EXISTS idx_enterprise_session_messages_session
  ON enterprise_session_messages (project_id, scope, session_id, id);
CREATE INDEX IF NOT EXISTS idx_enterprise_session_structure_seq
  ON enterprise_session_message_structure (project_id, scope, session_id, branch_id, sequence_number);
CREATE INDEX IF NOT EXISTS idx_enterprise_session_usage_turn
  ON enterprise_session_turn_usage (project_id, scope, session_id, branch_id, user_turn_number);
"""
