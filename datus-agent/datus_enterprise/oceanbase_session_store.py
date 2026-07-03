"""OceanBase MySQL-backed chat session body store.

This store persists the body/state that ``AdvancedSQLiteSession`` keeps in
local SQLite files: agent messages, message structure, turn usage, running
turn usage, and system-prompt snapshots. It does not replace
``SessionOwnerStore``; owner metadata remains the authorization/index surface.

Schema bootstrap is intentionally limited to additive
``CREATE TABLE IF NOT EXISTS`` statements. Production migrations are a
separate operations concern.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, TypeVar

from agents.items import TResponseInputItem

from datus.utils.message_utils import extract_user_input
from datus.utils.time_utils import to_utc_iso
from datus_enterprise.oceanbase_common import (
    OceanBaseMySQLConfig,
    OceanBaseMySQLPool,
    OceanBaseSchemaMixin,
)

logger = logging.getLogger(__name__)
_T = TypeVar("_T")


class ObSessionBodyStore(OceanBaseSchemaMixin):
    """OceanBase MySQL-backed AdvancedSQLiteSession-compatible body store."""

    def __init__(
        self,
        *,
        host: str,
        port: int | str = 2881,
        user: str,
        password: str,
        database: str,
        charset: str = "utf8mb4",
        connect_timeout: int | str = 10,
        read_timeout: int | str = 30,
        write_timeout: int | str = 30,
        pool_max_size: int | str | None = None,
        max_size: int | str | None = None,
    ) -> None:
        self._config = OceanBaseMySQLConfig.from_kwargs(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            charset=charset,
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
            write_timeout=write_timeout,
            pool_max_size=pool_max_size,
            max_size=max_size,
        )
        self._pool = OceanBaseMySQLPool(self._config)
        self._schema_ready = False
        self._schema_lock = threading.Lock()

    def open_session(self, *, project_id: str, scope: str | None, session_id: str) -> "ObSessionBodySession":
        return ObSessionBodySession(
            store=self,
            project_id=_normalize_project_id(project_id),
            scope=_normalize_scope(scope),
            session_id=session_id,
        )

    async def close(self) -> None:
        await asyncio.to_thread(self._pool.close)

    def run_sync(self, operation: Callable[[], Awaitable[_T]]) -> _T:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(operation())

        result: dict[str, _T] = {}
        error: dict[str, BaseException] = {}

        def _runner() -> None:
            try:
                result["value"] = asyncio.run(operation())
            except BaseException as exc:
                error["value"] = exc

        thread = threading.Thread(target=_runner, name="ob-session-body-store-sync-call", daemon=True)
        thread.start()
        thread.join()
        if error:
            raise error["value"]
        return result["value"]

    async def session_exists(self, *, project_id: str, scope: str | None, session_id: str) -> bool:
        row = await self._fetchone(
            """
            SELECT 1
            FROM enterprise_session_bodies
            WHERE project_id = %s AND scope = %s AND session_id = %s
            """,
            (_normalize_project_id(project_id), _normalize_scope(scope), session_id),
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
        rows = await self._fetchall(
            f"""
            SELECT session_id
            FROM enterprise_session_bodies
            WHERE project_id = %s AND scope = %s
            ORDER BY {order_by}
            """,
            (_normalize_project_id(project_id), _normalize_scope(scope)),
        )
        session_ids = [str(row["session_id"]) for row in rows]
        return session_ids[:limit] if limit is not None else session_ids

    async def get_session_info(self, *, project_id: str, scope: str | None, session_id: str) -> dict[str, Any]:
        project = _normalize_project_id(project_id)
        scoped = _normalize_scope(scope)
        row = await self._fetchone(
            """
            SELECT created_at, updated_at
            FROM enterprise_session_bodies
            WHERE project_id = %s AND scope = %s AND session_id = %s
            """,
            (project, scoped, session_id),
        )
        if row is None:
            return {"exists": False}

        stats = await self._fetchone(
            """
            SELECT COUNT(*) AS message_count, MAX(created_at) AS latest_message_at
            FROM enterprise_session_messages
            WHERE project_id = %s AND scope = %s AND session_id = %s
            """,
            (project, scoped, session_id),
        )
        token_row = await self._fetchone(
            """
            SELECT COALESCE(SUM(total_tokens), 0) AS total_tokens
            FROM enterprise_session_turn_usage
            WHERE project_id = %s AND scope = %s AND session_id = %s
            """,
            (project, scoped, session_id),
        )
        message_rows = await self._message_rows(project_id=project, scope=scoped, session_id=session_id, desc=True)
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

        message_count = int((stats or {}).get("message_count") or 0)
        return {
            "exists": True,
            "session_id": session_id,
            "created_at": _iso(row["created_at"]),
            "updated_at": _iso(row["updated_at"]),
            "file_modified_iso": _iso(row["updated_at"]),
            "total_tokens": int((token_row or {}).get("total_tokens") or 0),
            "message_count": message_count,
            "item_count": message_count,
            "latest_message_at": _iso((stats or {}).get("latest_message_at")),
            "latest_user_message": latest_user_message,
            "latest_user_message_at": _iso(latest_user_message_at),
            "first_user_message": first_user_message,
            "first_user_message_at": _iso(first_user_message_at),
        }

    async def delete_session(self, *, project_id: str, scope: str | None, session_id: str) -> None:
        await asyncio.to_thread(
            self._delete_session_sync,
            _normalize_project_id(project_id),
            _normalize_scope(scope),
            session_id,
        )

    async def copy_session(
        self,
        *,
        project_id: str,
        scope: str | None,
        source_session_id: str,
        target_session_id: str,
    ) -> None:
        await asyncio.to_thread(
            self._copy_session_sync,
            _normalize_project_id(project_id),
            _normalize_scope(scope),
            source_session_id,
            target_session_id,
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
            VALUES (%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP)
            ON DUPLICATE KEY UPDATE
              user_turn_number=VALUES(user_turn_number),
              cumulative_json=VALUES(cumulative_json),
              context_length=VALUES(context_length),
              updated_at=CURRENT_TIMESTAMP
            """,
            (
                _normalize_project_id(project_id),
                _normalize_scope(scope),
                session_id,
                int(user_turn_number or 0),
                json.dumps(cumulative or {}, ensure_ascii=False),
                int(context_length or 0),
            ),
        )

    async def get_running_turn_usage(
        self, *, project_id: str, scope: str | None, session_id: str
    ) -> dict[str, Any] | None:
        row = await self._fetchone(
            """
            SELECT user_turn_number, cumulative_json, context_length, updated_at
            FROM enterprise_session_running_usage
            WHERE project_id=%s AND scope=%s AND session_id=%s
            """,
            (_normalize_project_id(project_id), _normalize_scope(scope), session_id),
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
            "DELETE FROM enterprise_session_running_usage WHERE project_id=%s AND scope=%s AND session_id=%s",
            (_normalize_project_id(project_id), _normalize_scope(scope), session_id),
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
            VALUES (%s,%s,%s,%s,CURRENT_TIMESTAMP)
            ON DUPLICATE KEY UPDATE
              snapshot_json=VALUES(snapshot_json),
              updated_at=CURRENT_TIMESTAMP
            """,
            (
                _normalize_project_id(project_id),
                _normalize_scope(scope),
                session_id,
                json.dumps(payload, ensure_ascii=False),
            ),
        )

    async def load_system_prompt_snapshot(
        self, *, project_id: str, scope: str | None, session_id: str
    ) -> dict[str, Any] | None:
        row = await self._fetchone(
            """
            SELECT snapshot_json
            FROM enterprise_session_system_prompts
            WHERE project_id=%s AND scope=%s AND session_id=%s
            """,
            (_normalize_project_id(project_id), _normalize_scope(scope), session_id),
        )
        if row is None:
            return None
        payload = _loads(row["snapshot_json"])
        return payload if isinstance(payload, dict) else None

    async def delete_system_prompt_snapshot(self, *, project_id: str, scope: str | None, session_id: str) -> None:
        await self._execute(
            "DELETE FROM enterprise_session_system_prompts WHERE project_id=%s AND scope=%s AND session_id=%s",
            (_normalize_project_id(project_id), _normalize_scope(scope), session_id),
        )

    async def _message_rows(
        self, *, project_id: str, scope: str, session_id: str, desc: bool = False
    ) -> list[tuple[str, Any]]:
        order = "DESC" if desc else "ASC"
        rows = await self._fetchall(
            f"""
            SELECT message_data, created_at
            FROM enterprise_session_messages
            WHERE project_id=%s AND scope=%s AND session_id=%s
            ORDER BY created_at {order}, id {order}
            """,
            (project_id, scope, session_id),
        )
        return [(str(row["message_data"]), row["created_at"]) for row in rows]

    async def _execute(self, query: str, params: tuple[Any, ...] = ()) -> int:
        return await asyncio.to_thread(self._execute_sync, query, params)

    async def _fetchone(self, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._fetchone_sync, query, params)

    async def _fetchall(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._fetchall_sync, query, params)

    def _execute_sync(self, query: str, params: tuple[Any, ...] = ()) -> int:
        self._ensure_database_and_schema_sync(_SCHEMA_SQL)
        with self._pool.connection(database=self._config.database) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                return int(cursor.rowcount or 0)

    def _fetchone_sync(self, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        self._ensure_database_and_schema_sync(_SCHEMA_SQL)
        with self._pool.connection(database=self._config.database) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                row = cursor.fetchone()
                return dict(row) if row else None

    def _fetchall_sync(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        self._ensure_database_and_schema_sync(_SCHEMA_SQL)
        with self._pool.connection(database=self._config.database) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]

    def _delete_session_sync(self, project_id: str, scope: str, session_id: str) -> None:
        self._ensure_database_and_schema_sync(_SCHEMA_SQL)
        keys = (project_id, scope, session_id)
        with self._pool.connection(database=self._config.database) as conn:
            with conn.cursor() as cursor:
                for table in (
                    "enterprise_session_running_usage",
                    "enterprise_session_system_prompts",
                    "enterprise_session_turn_usage",
                    "enterprise_session_message_structure",
                    "enterprise_session_messages",
                    "enterprise_session_bodies",
                ):
                    cursor.execute(f"DELETE FROM {table} WHERE project_id=%s AND scope=%s AND session_id=%s", keys)

    def _copy_session_sync(
        self,
        project_id: str,
        scope: str,
        source_session_id: str,
        target_session_id: str,
    ) -> None:
        self._ensure_database_and_schema_sync(_SCHEMA_SQL)
        with self._pool.connection(database=self._config.database) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT created_at
                    FROM enterprise_session_bodies
                    WHERE project_id=%s AND scope=%s AND session_id=%s
                    """,
                    (project_id, scope, source_session_id),
                )
                if cursor.fetchone() is None:
                    return
                _ensure_body_sync(cursor, project_id, scope, target_session_id)
                cursor.execute(
                    """
                    SELECT id, message_data
                    FROM enterprise_session_messages
                    WHERE project_id=%s AND scope=%s AND session_id=%s
                    ORDER BY id ASC
                    """,
                    (project_id, scope, source_session_id),
                )
                id_map: dict[int, int] = {}
                for row in cursor.fetchall():
                    cursor.execute(
                        """
                        INSERT INTO enterprise_session_messages (project_id, scope, session_id, message_data)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (project_id, scope, target_session_id, str(row["message_data"])),
                    )
                    id_map[int(row["id"])] = int(cursor.lastrowid)
                cursor.execute(
                    """
                    SELECT message_id, branch_id, message_type, sequence_number, user_turn_number,
                           branch_turn_number, tool_name
                    FROM enterprise_session_message_structure
                    WHERE project_id=%s AND scope=%s AND session_id=%s
                    ORDER BY sequence_number ASC
                    """,
                    (project_id, scope, source_session_id),
                )
                structure_rows = [
                    (
                        project_id,
                        scope,
                        target_session_id,
                        id_map[int(row["message_id"])],
                        row["branch_id"],
                        row["message_type"],
                        row["sequence_number"],
                        row["user_turn_number"],
                        row["branch_turn_number"],
                        row["tool_name"],
                    )
                    for row in cursor.fetchall()
                    if int(row["message_id"]) in id_map
                ]
                if structure_rows:
                    cursor.executemany(
                        """
                        INSERT INTO enterprise_session_message_structure
                        (project_id, scope, session_id, message_id, branch_id, message_type, sequence_number,
                         user_turn_number, branch_turn_number, tool_name)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        """,
                        structure_rows,
                    )
                cursor.execute(
                    """
                    SELECT branch_id, user_turn_number, requests, input_tokens, output_tokens,
                           total_tokens, input_tokens_details, output_tokens_details
                    FROM enterprise_session_turn_usage
                    WHERE project_id=%s AND scope=%s AND session_id=%s
                    """,
                    (project_id, scope, source_session_id),
                )
                usage_rows = [
                    (
                        project_id,
                        scope,
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
                    for row in cursor.fetchall()
                ]
                if usage_rows:
                    cursor.executemany(
                        """
                        INSERT INTO enterprise_session_turn_usage
                        (project_id, scope, session_id, branch_id, user_turn_number, requests, input_tokens,
                         output_tokens, total_tokens, input_tokens_details, output_tokens_details)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON DUPLICATE KEY UPDATE
                          requests=VALUES(requests),
                          input_tokens=VALUES(input_tokens),
                          output_tokens=VALUES(output_tokens),
                          total_tokens=VALUES(total_tokens),
                          input_tokens_details=VALUES(input_tokens_details),
                          output_tokens_details=VALUES(output_tokens_details)
                        """,
                        usage_rows,
                    )
                cursor.execute(
                    """
                    SELECT snapshot_json
                    FROM enterprise_session_system_prompts
                    WHERE project_id=%s AND scope=%s AND session_id=%s
                    """,
                    (project_id, scope, source_session_id),
                )
                prompt_row = cursor.fetchone()
                if prompt_row is not None:
                    cursor.execute(
                        """
                        INSERT INTO enterprise_session_system_prompts
                        (project_id, scope, session_id, snapshot_json, updated_at)
                        VALUES (%s,%s,%s,%s,CURRENT_TIMESTAMP)
                        ON DUPLICATE KEY UPDATE
                          snapshot_json=VALUES(snapshot_json),
                          updated_at=CURRENT_TIMESTAMP
                        """,
                        (project_id, scope, target_session_id, str(prompt_row["snapshot_json"])),
                    )


class ObSessionBodySession:
    """AdvancedSQLiteSession-compatible OceanBase session handle."""

    def __init__(self, *, store: ObSessionBodyStore, project_id: str, scope: str, session_id: str) -> None:
        self._store = store
        self._project_id = project_id
        self._scope = scope
        self.session_id = session_id
        self._current_branch_id = "main"
        self._logger = logging.getLogger(__name__)

    async def add_items(self, items: list[TResponseInputItem]) -> None:
        if not items:
            return
        await asyncio.to_thread(self._add_items_sync, items)

    async def get_items(self, limit: int | None = None, branch_id: str | None = None) -> list[TResponseInputItem]:
        branch = branch_id or self._current_branch_id
        if limit is None:
            rows = await self._store._fetchall(
                """
                SELECT m.message_data
                FROM enterprise_session_messages m
                JOIN enterprise_session_message_structure s
                  ON m.id = s.message_id
                 AND m.project_id = s.project_id
                 AND m.scope = s.scope
                 AND m.session_id = s.session_id
                WHERE m.project_id=%s AND m.scope=%s AND m.session_id=%s AND s.branch_id=%s
                ORDER BY s.sequence_number ASC
                """,
                (self._project_id, self._scope, self.session_id, branch),
            )
        else:
            rows = await self._store._fetchall(
                """
                SELECT m.message_data
                FROM enterprise_session_messages m
                JOIN enterprise_session_message_structure s
                  ON m.id = s.message_id
                 AND m.project_id = s.project_id
                 AND m.scope = s.scope
                 AND m.session_id = s.session_id
                WHERE m.project_id=%s AND m.scope=%s AND m.session_id=%s AND s.branch_id=%s
                ORDER BY s.sequence_number DESC
                LIMIT %s
                """,
                (self._project_id, self._scope, self.session_id, branch, int(limit)),
            )
            rows = list(reversed(rows))
        items: list[TResponseInputItem] = []
        for row in rows:
            parsed = _loads(row["message_data"])
            if isinstance(parsed, dict):
                items.append(parsed)
        return items

    async def pop_item(self) -> TResponseInputItem | None:
        return await asyncio.to_thread(self._pop_item_sync)

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
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
              requests=VALUES(requests),
              input_tokens=VALUES(input_tokens),
              output_tokens=VALUES(output_tokens),
              total_tokens=VALUES(total_tokens),
              input_tokens_details=VALUES(input_tokens_details),
              output_tokens_details=VALUES(output_tokens_details),
              created_at=CURRENT_TIMESTAMP
            """,
            (
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
            ),
        )

    async def get_turn_usage(
        self, user_turn_number: int | None = None, branch_id: str | None = None
    ) -> list[dict[str, Any]] | dict[str, Any]:
        branch = branch_id or self._current_branch_id
        if user_turn_number is not None:
            row = await self._store._fetchone(
                """
                SELECT requests, input_tokens, output_tokens, total_tokens,
                       input_tokens_details, output_tokens_details
                FROM enterprise_session_turn_usage
                WHERE project_id=%s AND scope=%s AND session_id=%s AND branch_id=%s AND user_turn_number=%s
                """,
                (self._project_id, self._scope, self.session_id, branch, int(user_turn_number)),
            )
            return _usage_record(row, include_turn=False) if row else {}
        rows = await self._store._fetchall(
            """
            SELECT user_turn_number, requests, input_tokens, output_tokens, total_tokens,
                   input_tokens_details, output_tokens_details
            FROM enterprise_session_turn_usage
            WHERE project_id=%s AND scope=%s AND session_id=%s AND branch_id=%s
            ORDER BY user_turn_number ASC
            """,
            (self._project_id, self._scope, self.session_id, branch),
        )
        return [_usage_record(row, include_turn=True) for row in rows]

    async def get_session_usage(self, branch_id: str | None = None) -> dict[str, int] | None:
        if branch_id:
            row = await self._store._fetchone(
                """
                SELECT SUM(requests) AS requests, SUM(input_tokens) AS input_tokens,
                       SUM(output_tokens) AS output_tokens, SUM(total_tokens) AS total_tokens,
                       COUNT(*) AS total_turns
                FROM enterprise_session_turn_usage
                WHERE project_id=%s AND scope=%s AND session_id=%s AND branch_id=%s
                """,
                (self._project_id, self._scope, self.session_id, branch_id),
            )
        else:
            row = await self._store._fetchone(
                """
                SELECT SUM(requests) AS requests, SUM(input_tokens) AS input_tokens,
                       SUM(output_tokens) AS output_tokens, SUM(total_tokens) AS total_tokens,
                       COUNT(*) AS total_turns
                FROM enterprise_session_turn_usage
                WHERE project_id=%s AND scope=%s AND session_id=%s
                """,
                (self._project_id, self._scope, self.session_id),
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
        row = await self._store._fetchone(
            """
            SELECT COALESCE(MAX(user_turn_number), 0) AS turn
            FROM enterprise_session_message_structure
            WHERE project_id=%s AND scope=%s AND session_id=%s AND branch_id=%s
            """,
            (self._project_id, self._scope, self.session_id, self._current_branch_id),
        )
        return int(row["turn"] or 0) if row else 0

    def _add_items_sync(self, items: list[TResponseInputItem]) -> None:
        self._store._ensure_database_and_schema_sync(_SCHEMA_SQL)
        with self._store._pool.connection(database=self._store._config.database) as conn:
            with conn.cursor() as cursor:
                _ensure_body_sync(cursor, self._project_id, self._scope, self.session_id)
                message_ids: list[int] = []
                for item in items:
                    cursor.execute(
                        """
                        INSERT INTO enterprise_session_messages (project_id, scope, session_id, message_data)
                        VALUES (%s,%s,%s,%s)
                        """,
                        (self._project_id, self._scope, self.session_id, json.dumps(item, ensure_ascii=False)),
                    )
                    message_ids.append(int(cursor.lastrowid))
                cursor.execute(
                    """
                    SELECT COALESCE(MAX(sequence_number), 0) AS seq
                    FROM enterprise_session_message_structure
                    WHERE project_id=%s AND scope=%s AND session_id=%s
                    """,
                    (self._project_id, self._scope, self.session_id),
                )
                seq_start = int((cursor.fetchone() or {}).get("seq") or 0)
                cursor.execute(
                    """
                    SELECT
                      COALESCE(MAX(user_turn_number), 0) AS user_turn_number,
                      COALESCE(MAX(branch_turn_number), 0) AS branch_turn_number
                    FROM enterprise_session_message_structure
                    WHERE project_id=%s AND scope=%s AND session_id=%s AND branch_id=%s
                    """,
                    (self._project_id, self._scope, self.session_id, self._current_branch_id),
                )
                turn_row = cursor.fetchone() or {}
                current_turn = int(turn_row.get("user_turn_number") or 0)
                current_branch_turn = int(turn_row.get("branch_turn_number") or 0)
                structure_rows = []
                user_message_count = 0
                for index, (item, message_id) in enumerate(zip(items, message_ids)):
                    if _is_user_message(item):
                        user_message_count += 1
                    structure_rows.append(
                        (
                            self._project_id,
                            self._scope,
                            self.session_id,
                            message_id,
                            self._current_branch_id,
                            _classify_message_type(item),
                            seq_start + index + 1,
                            current_turn + user_message_count,
                            current_branch_turn + user_message_count,
                            _extract_tool_name(item),
                        )
                    )
                cursor.executemany(
                    """
                    INSERT INTO enterprise_session_message_structure
                    (project_id, scope, session_id, message_id, branch_id, message_type, sequence_number,
                     user_turn_number, branch_turn_number, tool_name)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    structure_rows,
                )
                cursor.execute(
                    """
                    UPDATE enterprise_session_bodies
                    SET updated_at=CURRENT_TIMESTAMP
                    WHERE project_id=%s AND scope=%s AND session_id=%s
                    """,
                    (self._project_id, self._scope, self.session_id),
                )

    def _pop_item_sync(self) -> TResponseInputItem | None:
        self._store._ensure_database_and_schema_sync(_SCHEMA_SQL)
        with self._store._pool.connection(database=self._store._config.database) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, message_data
                    FROM enterprise_session_messages
                    WHERE project_id=%s AND scope=%s AND session_id=%s
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (self._project_id, self._scope, self.session_id),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                cursor.execute(
                    """
                    DELETE FROM enterprise_session_message_structure
                    WHERE project_id=%s AND scope=%s AND session_id=%s AND message_id=%s
                    """,
                    (self._project_id, self._scope, self.session_id, row["id"]),
                )
                cursor.execute("DELETE FROM enterprise_session_messages WHERE id=%s", (row["id"],))
        parsed = _loads(row["message_data"])
        return parsed if isinstance(parsed, dict) else None


def _ensure_body_sync(cursor: Any, project_id: str, scope: str, session_id: str) -> None:
    cursor.execute(
        """
        INSERT INTO enterprise_session_bodies (project_id, scope, session_id, created_at, updated_at)
        VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON DUPLICATE KEY UPDATE updated_at=CURRENT_TIMESTAMP
        """,
        (project_id, scope, session_id),
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


def _usage_record(row: dict[str, Any] | None, *, include_turn: bool) -> dict[str, Any]:
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
  project_id VARCHAR(255) NOT NULL,
  scope VARCHAR(255) NOT NULL DEFAULT '',
  session_id VARCHAR(255) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (project_id, scope, session_id),
  INDEX idx_enterprise_session_bodies_updated (project_id, scope, updated_at)
);

CREATE TABLE IF NOT EXISTS enterprise_session_messages (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  project_id VARCHAR(255) NOT NULL,
  scope VARCHAR(255) NOT NULL DEFAULT '',
  session_id VARCHAR(255) NOT NULL,
  message_data LONGTEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_enterprise_session_messages_session (project_id, scope, session_id, id)
);

CREATE TABLE IF NOT EXISTS enterprise_session_message_structure (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  project_id VARCHAR(255) NOT NULL,
  scope VARCHAR(255) NOT NULL DEFAULT '',
  session_id VARCHAR(255) NOT NULL,
  message_id BIGINT NOT NULL,
  branch_id VARCHAR(255) NOT NULL DEFAULT 'main',
  message_type VARCHAR(64) NOT NULL,
  sequence_number INTEGER NOT NULL,
  user_turn_number INTEGER,
  branch_turn_number INTEGER,
  tool_name VARCHAR(255),
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_enterprise_session_structure_seq (project_id, scope, session_id, branch_id, sequence_number)
);

CREATE TABLE IF NOT EXISTS enterprise_session_turn_usage (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  project_id VARCHAR(255) NOT NULL,
  scope VARCHAR(255) NOT NULL DEFAULT '',
  session_id VARCHAR(255) NOT NULL,
  branch_id VARCHAR(255) NOT NULL DEFAULT 'main',
  user_turn_number INTEGER NOT NULL,
  requests INTEGER NOT NULL DEFAULT 0,
  input_tokens INTEGER NOT NULL DEFAULT 0,
  output_tokens INTEGER NOT NULL DEFAULT 0,
  total_tokens INTEGER NOT NULL DEFAULT 0,
  input_tokens_details LONGTEXT,
  output_tokens_details LONGTEXT,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_enterprise_session_turn_usage (project_id, scope, session_id, branch_id, user_turn_number),
  INDEX idx_enterprise_session_usage_turn (project_id, scope, session_id, branch_id, user_turn_number)
);

CREATE TABLE IF NOT EXISTS enterprise_session_running_usage (
  project_id VARCHAR(255) NOT NULL,
  scope VARCHAR(255) NOT NULL DEFAULT '',
  session_id VARCHAR(255) NOT NULL,
  user_turn_number INTEGER,
  cumulative_json LONGTEXT,
  context_length INTEGER,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (project_id, scope, session_id)
);

CREATE TABLE IF NOT EXISTS enterprise_session_system_prompts (
  project_id VARCHAR(255) NOT NULL,
  scope VARCHAR(255) NOT NULL DEFAULT '',
  session_id VARCHAR(255) NOT NULL,
  snapshot_json LONGTEXT NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (project_id, scope, session_id)
);
"""
