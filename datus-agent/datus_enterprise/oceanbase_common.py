"""Shared helpers for OceanBase MySQL enterprise stores."""

from __future__ import annotations

import queue
import re
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

from datus.utils.exceptions import DatusException, ErrorCode

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def quote_identifier(name: str) -> str:
    value = str(name or "").strip()
    if not _IDENTIFIER_RE.fullmatch(value):
        raise DatusException(ErrorCode.COMMON_CONFIG_ERROR, message=f"Invalid OceanBase identifier: {name!r}")
    return f"`{value}`"


@dataclass(frozen=True)
class OceanBaseMySQLConfig:
    host: str
    port: int
    user: str
    password: str
    database: str
    charset: str = "utf8mb4"
    connect_timeout: int = 10
    read_timeout: int = 30
    write_timeout: int = 30
    pool_max_size: int = 5

    @classmethod
    def from_kwargs(
        cls,
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
    ) -> "OceanBaseMySQLConfig":
        if not str(host or "").strip():
            raise DatusException(ErrorCode.COMMON_CONFIG_ERROR, message="OceanBase host is required.")
        if not str(user or "").strip():
            raise DatusException(ErrorCode.COMMON_CONFIG_ERROR, message="OceanBase user is required.")
        if password is None:
            raise DatusException(ErrorCode.COMMON_CONFIG_ERROR, message="OceanBase password is required.")
        quote_identifier(database)
        size = pool_max_size if pool_max_size is not None else max_size
        return cls(
            host=str(host),
            port=int(port),
            user=str(user),
            password=str(password),
            database=str(database),
            charset=str(charset or "utf8mb4"),
            connect_timeout=int(connect_timeout),
            read_timeout=int(read_timeout),
            write_timeout=int(write_timeout),
            pool_max_size=int(size or 5),
        )


class OceanBaseMySQLPool:
    """Small PyMySQL connection pool for blocking OceanBase calls."""

    def __init__(self, config: OceanBaseMySQLConfig) -> None:
        self._config = config
        self._available: queue.LifoQueue[Any] = queue.LifoQueue(maxsize=config.pool_max_size)
        self._connections: set[Any] = set()
        self._created = 0
        self._closed = False
        self._lock = threading.Lock()

    @contextmanager
    def connection(self, *, database: str | None = None) -> Iterator[Any]:
        if self._closed:
            raise RuntimeError("OceanBase MySQL connection pool is closed")
        conn = self._acquire(database=database)
        use_shared = database == self._config.database
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._release(conn, use_shared=use_shared)

    def close(self) -> None:
        with self._lock:
            self._closed = True
            connections = list(self._connections)
        while True:
            try:
                self._available.get_nowait()
            except queue.Empty:
                break
        for conn in connections:
            try:
                conn.close()
            except Exception:
                pass

    def _acquire(self, *, database: str | None = None) -> Any:
        use_shared = database == self._config.database
        if not use_shared:
            return self._create_connection(database=database)
        try:
            conn = self._available.get_nowait()
        except queue.Empty:
            with self._lock:
                if self._created < self._config.pool_max_size:
                    conn = self._create_connection(database=self._config.database)
                    self._created += 1
                else:
                    conn = self._available.get()
        if not getattr(conn, "open", True):
            conn = self._create_connection(database=self._config.database)
        return conn

    def _release(self, conn: Any, *, use_shared: bool) -> None:
        if use_shared and not self._closed and getattr(conn, "open", True):
            self._available.put(conn)
            return
        try:
            conn.close()
        except Exception:
            pass

    def _create_connection(self, *, database: str | None = None) -> Any:
        import pymysql
        from pymysql.cursors import DictCursor

        conn = pymysql.connect(
            host=self._config.host,
            port=self._config.port,
            user=self._config.user,
            password=self._config.password,
            database=database,
            charset=self._config.charset,
            connect_timeout=self._config.connect_timeout,
            read_timeout=self._config.read_timeout,
            write_timeout=self._config.write_timeout,
            autocommit=False,
            cursorclass=DictCursor,
        )
        with self._lock:
            self._connections.add(conn)
        return conn


class OceanBaseSchemaMixin:
    _config: OceanBaseMySQLConfig
    _pool: OceanBaseMySQLPool
    _schema_ready: bool
    _schema_lock: threading.Lock

    def _ensure_database_and_schema_sync(self, schema_sql: str) -> None:
        if self._schema_ready:
            return
        with self._schema_lock:
            if self._schema_ready:
                return
            with self._pool.connection(database=None) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {quote_identifier(self._config.database)}")
            with self._pool.connection(database=self._config.database) as conn:
                with conn.cursor() as cursor:
                    for statement in _split_sql_statements(schema_sql):
                        cursor.execute(statement)
            self._schema_ready = True


def _split_sql_statements(sql: str) -> list[str]:
    return [part.strip() for part in sql.split(";") if part.strip()]
