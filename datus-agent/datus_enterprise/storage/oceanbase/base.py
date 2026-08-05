"""Shared connection and query lifecycle for OceanBase enterprise stores."""

from __future__ import annotations

import asyncio
import threading
from typing import Any

from datus_enterprise.storage.oceanbase.common import (
    OceanBaseMySQLConfig,
    OceanBaseMySQLPool,
    OceanBaseSchemaMixin,
)
from datus_enterprise.storage.oceanbase.schema import _SCHEMA_SQL


class _ObStoreBase(OceanBaseSchemaMixin):
    """Blocking PyMySQL store base exposed through async protocol methods."""

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
