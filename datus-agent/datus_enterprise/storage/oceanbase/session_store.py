"""OceanBase storage and query operations for chat session bodies."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Any, Awaitable, Callable, TypeVar

from datus.utils.message_utils import extract_user_input
from datus_enterprise.storage.oceanbase.common import (
    OceanBaseMySQLConfig,
    OceanBaseMySQLPool,
    OceanBaseSchemaMixin,
)
from datus_enterprise.storage.oceanbase.session_body import ObSessionBodySession
from datus_enterprise.storage.oceanbase.session_records import (
    _ensure_body_sync,
    _iso,
    _loads,
    _normalize_project_id,
    _normalize_scope,
)
from datus_enterprise.storage.oceanbase.session_schema import _SCHEMA_SQL

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

    async def append_session_terminal_event(
        self,
        *,
        project_id: str,
        scope: str | None,
        session_id: str,
        event: dict[str, Any],
    ) -> None:
        await self._execute(
            """
            INSERT INTO enterprise_session_terminal_events
              (project_id, scope, session_id, event_id, event_type, payload_json)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE event_id=VALUES(event_id)
            """,
            (
                _normalize_project_id(project_id),
                _normalize_scope(scope),
                session_id,
                str(event["event_id"]),
                str(event["event_type"]),
                json.dumps(event, ensure_ascii=False),
            ),
        )

    async def get_session_terminal_events(
        self, *, project_id: str, scope: str | None, session_id: str
    ) -> list[dict[str, Any]]:
        rows = await self._fetchall(
            """
            SELECT payload_json
            FROM enterprise_session_terminal_events
            WHERE project_id=%s AND scope=%s AND session_id=%s
            ORDER BY created_at, id
            """,
            (_normalize_project_id(project_id), _normalize_scope(scope), session_id),
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
                    "enterprise_session_terminal_events",
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
