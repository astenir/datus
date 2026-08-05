"""AdvancedSQLiteSession-compatible PostgreSQL session handle."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from agents.items import TResponseInputItem

from datus_enterprise.storage.postgres.session_records import (
    _classify_message_type,
    _details_json,
    _ensure_body,
    _extract_tool_name,
    _is_user_message,
    _loads,
    _usage_record,
)

if TYPE_CHECKING:
    from datus_enterprise.storage.postgres.session_store import PgSessionBodyStore


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
