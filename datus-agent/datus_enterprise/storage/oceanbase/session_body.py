"""AdvancedSQLiteSession-compatible OceanBase session handle."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any

from agents.items import TResponseInputItem

from datus_enterprise.storage.oceanbase.session_records import (
    _classify_message_type,
    _details_json,
    _ensure_body_sync,
    _extract_tool_name,
    _is_user_message,
    _loads,
    _usage_record,
)
from datus_enterprise.storage.oceanbase.session_schema import _SCHEMA_SQL

if TYPE_CHECKING:
    from datus_enterprise.storage.oceanbase.session_store import ObSessionBodyStore


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
