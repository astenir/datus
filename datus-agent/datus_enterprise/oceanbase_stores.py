"""OceanBase MySQL-backed enterprise metadata stores."""

from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timezone
from typing import Any

from datus.utils.time_utils import to_utc_iso
from datus_enterprise.oceanbase_common import (
    OceanBaseMySQLConfig,
    OceanBaseMySQLPool,
    OceanBaseSchemaMixin,
)


class ObSessionOwnerStore(OceanBaseSchemaMixin):
    """OceanBase MySQL-backed session owner metadata store."""

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

    async def close(self) -> None:
        await asyncio.to_thread(self._pool.close)

    async def set_owner(self, project_id: str, session_id: str, user_id: str) -> None:
        await asyncio.to_thread(self._set_owner_sync, project_id, session_id, user_id)

    async def get_owner(self, project_id: str, session_id: str) -> str | None:
        row = await asyncio.to_thread(
            self._fetchone_sync,
            """
            SELECT user_id
            FROM session_owners
            WHERE project_id = %s AND session_id = %s
            """,
            (project_id, session_id),
        )
        return str(row["user_id"]) if row else None

    async def delete_owner(self, project_id: str, session_id: str) -> None:
        await asyncio.to_thread(
            self._execute_sync,
            "DELETE FROM session_owners WHERE project_id = %s AND session_id = %s",
            (project_id, session_id),
        )

    async def list_session_ids(self, project_id: str, user_id: str) -> list[str]:
        rows = await asyncio.to_thread(
            self._fetchall_sync,
            """
            SELECT session_id
            FROM session_owners
            WHERE project_id = %s AND user_id = %s
            ORDER BY updated_at DESC, session_id ASC
            """,
            (project_id, user_id),
        )
        return [str(row["session_id"]) for row in rows]

    async def list_sessions(self, project_id: str, user_id: str | None = None) -> list[dict[str, Any]]:
        if user_id is None:
            rows = await asyncio.to_thread(
                self._fetchall_sync,
                """
                SELECT project_id, session_id, user_id, created_at, updated_at
                FROM session_owners
                WHERE project_id = %s
                ORDER BY updated_at DESC, session_id ASC
                """,
                (project_id,),
            )
        else:
            rows = await asyncio.to_thread(
                self._fetchall_sync,
                """
                SELECT project_id, session_id, user_id, created_at, updated_at
                FROM session_owners
                WHERE project_id = %s AND user_id = %s
                ORDER BY updated_at DESC, session_id ASC
                """,
                (project_id, user_id),
            )
        return [_session_owner_record(row) for row in rows]

    def _set_owner_sync(self, project_id: str, session_id: str, user_id: str) -> None:
        self._execute_sync(
            """
            INSERT INTO session_owners (project_id, session_id, user_id, created_at, updated_at)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON DUPLICATE KEY UPDATE
              user_id = VALUES(user_id),
              updated_at = CURRENT_TIMESTAMP
            """,
            (project_id, session_id, user_id),
        )

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


def _session_owner_record(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "project_id": str(row["project_id"]),
        "session_id": str(row["session_id"]),
        "user_id": str(row["user_id"]),
        "created_at": _iso(row.get("created_at")),
        "updated_at": _iso(row.get("updated_at")),
    }


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()
    return to_utc_iso(value)


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS session_owners (
  project_id VARCHAR(255) NOT NULL,
  session_id VARCHAR(255) NOT NULL,
  user_id VARCHAR(255) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (project_id, session_id),
  INDEX idx_session_owners_user (project_id, user_id, updated_at)
);
"""
