"""OceanBase MySQL mode implementation of the Datus RDB storage backend."""

from __future__ import annotations

import dataclasses
import queue
import re
import threading
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional, Type

import pymysql
from pymysql.connections import Connection
from pymysql.cursors import DictCursor

from datus_storage_base.backend_config import LOGICAL_NAMESPACE_COLUMN, IsolationType
from datus_storage_base.rdb.base import (
    BaseRdbBackend,
    ColumnDef,
    IndexDef,
    IntegrityError,
    RdbDatabase,
    RdbTable,
    T,
    TableDefinition,
    UniqueViolationError,
    WhereClause,
    WhereOp,
    _normalize_where,
)

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_identifier(name: str) -> str:
    if not _IDENTIFIER_RE.fullmatch(name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    return name


def _quote_ident(name: str) -> str:
    return f"`{_validate_identifier(name)}`"


def _quote_qualified(database: str, table: str) -> str:
    return f"{_quote_ident(database)}.{_quote_ident(table)}"


def _literal(value: Any) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


_INDEXABLE_TEXT_TYPE = "VARCHAR(1024)"

_OB_TYPE_MAP: Dict[str, str] = {
    "INTEGER": "BIGINT",
    "TEXT": "LONGTEXT",
    "TIMESTAMP": "TIMESTAMP",
    "BOOLEAN": "TINYINT(1)",
    "REAL": "DOUBLE",
    "BLOB": "BLOB",
}


def _ob_map_type(col_type: str, *, indexed: bool = False) -> str:
    if col_type.upper() == "TEXT" and indexed:
        return _INDEXABLE_TEXT_TYPE
    return _OB_TYPE_MAP.get(col_type.upper(), col_type)


def _ob_col_ddl(col: ColumnDef, *, indexed: bool = False) -> str:
    col_name = _quote_ident(col.name)
    parts: List[str] = [col_name]
    if col.primary_key and col.autoincrement:
        parts.append("BIGINT PRIMARY KEY AUTO_INCREMENT")
    else:
        parts.append(_ob_map_type(col.col_type, indexed=indexed or col.unique or col.primary_key))
        if col.primary_key:
            parts.append("PRIMARY KEY")
        if col.unique:
            parts.append("UNIQUE")
        if not col.nullable:
            parts.append("NOT NULL")
        if col.default is not None:
            parts.append(f"DEFAULT {_literal(col.default)}")
    return " ".join(parts)


def _parse_unique_constraint_columns(constraint: str) -> Optional[List[str]]:
    match = re.fullmatch(r"\s*UNIQUE\s*\(([^)]+)\)\s*", constraint, flags=re.IGNORECASE)
    if not match:
        return None
    columns = [part.strip().strip("`") for part in match.group(1).split(",")]
    for column in columns:
        _validate_identifier(column)
    return columns


def _scope_unique_constraint(constraint: str) -> str:
    columns = _parse_unique_constraint_columns(constraint)
    if not columns or LOGICAL_NAMESPACE_COLUMN in columns:
        return constraint
    return f"UNIQUE({', '.join(_quote_ident(c) for c in columns + [LOGICAL_NAMESPACE_COLUMN])})"


def _scoped_unique_index_name(table_name: str, columns: List[str]) -> str:
    _validate_identifier(table_name)
    for column in columns:
        _validate_identifier(column)
    return f"idx_{table_name}_{'_'.join(columns)}_uq"


class _ConnectionPool:
    def __init__(self, config: Dict[str, Any]) -> None:
        self._config = config
        self._max_size = int(config.get("pool_max_size", 10))
        self._available: queue.LifoQueue[Connection] = queue.LifoQueue(maxsize=self._max_size)
        self._created = 0
        self._closed = False
        self._lock = threading.Lock()

    def _create_connection(self, database: Optional[str] = None) -> Connection:
        return pymysql.connect(
            host=self._config["host"],
            port=int(self._config["port"]),
            user=self._config["user"],
            password=self._config["password"],
            database=database,
            charset=self._config.get("charset", "utf8mb4"),
            connect_timeout=int(self._config.get("connect_timeout", 10)),
            read_timeout=int(self._config.get("read_timeout", 30)),
            write_timeout=int(self._config.get("write_timeout", 30)),
            autocommit=False,
            cursorclass=DictCursor,
        )

    @contextmanager
    def connection(self, database: Optional[str] = None) -> Iterator[Connection]:
        if self._closed:
            raise RuntimeError("OceanBase MySQL connection pool is closed")
        conn: Optional[Connection] = None
        use_shared = database is None
        if use_shared:
            try:
                conn = self._available.get_nowait()
            except queue.Empty:
                with self._lock:
                    if self._created < self._max_size:
                        conn = self._create_connection()
                        self._created += 1
                if conn is None:
                    conn = self._available.get()
        else:
            conn = self._create_connection(database=database)
        try:
            if not conn.open:
                conn = self._create_connection(database=database)
            yield conn
        finally:
            if use_shared and not self._closed and conn.open:
                self._available.put(conn)
            else:
                try:
                    conn.close()
                except Exception:
                    pass

    def close(self) -> None:
        self._closed = True
        while True:
            try:
                conn = self._available.get_nowait()
            except queue.Empty:
                break
            try:
                conn.close()
            except Exception:
                pass


class OceanBaseMySQLRdbTable(RdbTable):
    def __init__(
        self,
        pool: _ConnectionPool,
        database_name: str,
        table_name: str,
        local: threading.local,
        isolation: IsolationType = IsolationType.PHYSICAL,
        logical_namespace: Optional[str] = None,
    ) -> None:
        self._pool = pool
        self._database_name = database_name
        self._table_name = table_name
        self._qualified_name = _quote_qualified(database_name, table_name)
        self._local = local
        self._isolation = isolation
        self._logical_namespace = logical_namespace

    @property
    def table_name(self) -> str:
        return self._qualified_name

    @contextmanager
    def _auto_conn(self) -> Iterator[Connection]:
        txn_conn = getattr(self._local, "txn_conn", None)
        if txn_conn is not None:
            yield txn_conn
            return
        with self._pool.connection(database=self._database_name) as conn:
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def _inject_namespace_where(self, where: Optional[WhereClause]) -> Optional[WhereClause]:
        if self._isolation != IsolationType.LOGICAL or self._logical_namespace is None:
            return where
        return [(LOGICAL_NAMESPACE_COLUMN, WhereOp.EQ, self._logical_namespace)] + _normalize_where(where)

    def _inject_namespace_into_record(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if self._isolation != IsolationType.LOGICAL or self._logical_namespace is None:
            return data
        return {**data, LOGICAL_NAMESPACE_COLUMN: self._logical_namespace}

    @staticmethod
    def _build_where(where: Optional[WhereClause]) -> tuple[str, List[Any]]:
        conditions = _normalize_where(where)
        if not conditions:
            return "", []
        parts = []
        params = []
        for col, op, val in conditions:
            safe_col = _quote_ident(col)
            if op in (WhereOp.IS_NULL, WhereOp.IS_NOT_NULL):
                parts.append(f"{safe_col} {op.value}")
            else:
                parts.append(f"{safe_col} {op.value} %s")
                params.append(val)
        return " WHERE " + " AND ".join(parts), params

    @staticmethod
    def _build_order_by(order_by: Optional[List[str]]) -> str:
        if not order_by:
            return ""
        parts = []
        for item in order_by:
            if item.startswith("-"):
                parts.append(f"{_quote_ident(item[1:])} DESC")
            else:
                parts.append(f"{_quote_ident(item)} ASC")
        return " ORDER BY " + ", ".join(parts)

    def insert(self, record: Any) -> int:
        data = self._inject_namespace_into_record(
            {k: v for k, v in dataclasses.asdict(record).items() if v is not None}
        )
        if not data:
            sql = f"INSERT INTO {self._qualified_name} () VALUES ()"
            params: tuple[Any, ...] = ()
        else:
            columns = [_quote_ident(k) for k in data]
            sql = (
                f"INSERT INTO {self._qualified_name} ({', '.join(columns)}) VALUES ({', '.join(['%s'] * len(columns))})"
            )
            params = tuple(data.values())
        try:
            with self._auto_conn() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql, params)
                    return int(cursor.lastrowid or 0)
        except pymysql.err.IntegrityError as e:
            if e.args and e.args[0] in (1062, 1586):
                raise UniqueViolationError(str(e)) from e
            raise IntegrityError(str(e)) from e

    def query(
        self,
        model: Type[T],
        where: Optional[WhereClause] = None,
        columns: Optional[List[str]] = None,
        order_by: Optional[List[str]] = None,
    ) -> List[T]:
        where = self._inject_namespace_where(where)
        col_str = ", ".join(_quote_ident(c) for c in columns) if columns else "*"
        where_sql, params = self._build_where(where)
        order_sql = self._build_order_by(order_by)
        sql = f"SELECT {col_str} FROM {self._qualified_name}{where_sql}{order_sql}"
        with self._auto_conn() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
        results = []
        for row in rows:
            row.pop(LOGICAL_NAMESPACE_COLUMN, None)
            results.append(model(**row))
        return results

    def update(self, data: Dict[str, Any], where: Optional[WhereClause] = None) -> int:
        if self._isolation == IsolationType.LOGICAL and LOGICAL_NAMESPACE_COLUMN in data:
            raise ValueError(f"{LOGICAL_NAMESPACE_COLUMN} is managed internally and cannot be updated")
        where = self._inject_namespace_where(where)
        if not data:
            return 0
        set_sql = ", ".join(f"{_quote_ident(col)} = %s" for col in data)
        where_sql, where_params = self._build_where(where)
        sql = f"UPDATE {self._qualified_name} SET {set_sql}{where_sql}"
        try:
            with self._auto_conn() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql, list(data.values()) + where_params)
                    return int(cursor.rowcount)
        except pymysql.err.IntegrityError as e:
            if e.args and e.args[0] in (1062, 1586):
                raise UniqueViolationError(str(e)) from e
            raise IntegrityError(str(e)) from e

    def delete(self, where: Optional[WhereClause] = None) -> int:
        where = self._inject_namespace_where(where)
        where_sql, params = self._build_where(where)
        sql = f"DELETE FROM {self._qualified_name}{where_sql}"
        with self._auto_conn() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                return int(cursor.rowcount)

    def upsert(self, record: Any, conflict_columns: List[str]) -> None:
        data = self._inject_namespace_into_record(
            {k: v for k, v in dataclasses.asdict(record).items() if v is not None}
        )
        if not data:
            raise ValueError("Cannot upsert a record with no non-None fields")
        columns = [_quote_ident(k) for k in data]
        update_cols = [col for col in data if col not in conflict_columns]
        if self._isolation == IsolationType.LOGICAL:
            update_cols = [col for col in update_cols if col != LOGICAL_NAMESPACE_COLUMN]
        update_sql = ", ".join(f"{_quote_ident(col)} = VALUES({_quote_ident(col)})" for col in update_cols)
        if update_sql:
            sql = (
                f"INSERT INTO {self._qualified_name} ({', '.join(columns)}) "
                f"VALUES ({', '.join(['%s'] * len(columns))}) ON DUPLICATE KEY UPDATE {update_sql}"
            )
        else:
            sql = (
                f"INSERT IGNORE INTO {self._qualified_name} ({', '.join(columns)}) "
                f"VALUES ({', '.join(['%s'] * len(columns))})"
            )
        try:
            with self._auto_conn() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql, tuple(data.values()))
        except pymysql.err.IntegrityError as e:
            if e.args and e.args[0] in (1062, 1586):
                raise UniqueViolationError(str(e)) from e
            raise IntegrityError(str(e)) from e


class OceanBaseMySQLRdbDatabase(RdbDatabase):
    def __init__(
        self,
        pool: _ConnectionPool,
        configured_database: str,
        namespace: str,
        store_db_name: str,
        isolation: IsolationType,
    ) -> None:
        self._pool = pool
        self._configured_database = configured_database
        self._namespace = namespace
        self._store_db_name = store_db_name
        self._isolation = isolation
        self._local = threading.local()
        if isolation == IsolationType.LOGICAL:
            self._database_name = configured_database
            self._logical_namespace = namespace
        else:
            safe_namespace = _validate_identifier(namespace) if namespace else configured_database
            safe_store = _validate_identifier(store_db_name) if store_db_name else "datus"
            self._database_name = f"{safe_namespace}__{safe_store}"
            self._logical_namespace = None
        self._ensure_database()

    @property
    def database_name(self) -> str:
        return self._database_name

    def _ensure_database(self) -> None:
        with self._pool.connection(database=None) as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS {_quote_ident(self._database_name)}")
            conn.commit()

    def _generate_ddl(self, table_def: TableDefinition) -> List[str]:
        indexed_columns = self._indexed_columns(table_def)
        col_parts = [_ob_col_ddl(col, indexed=col.name in indexed_columns) for col in table_def.columns]
        col_parts.extend(table_def.constraints)
        qualified = _quote_qualified(self._database_name, table_def.table_name)
        statements = [
            f"CREATE TABLE IF NOT EXISTS {qualified} (\n" + ",\n".join(f"    {part}" for part in col_parts) + "\n)"
        ]
        for idx in table_def.indices:
            unique = "UNIQUE " if idx.unique else ""
            cols = ", ".join(_quote_ident(c) for c in idx.columns)
            statements.append(f"CREATE {unique}INDEX {_quote_ident(idx.name)} ON {qualified} ({cols})")
        return statements

    @staticmethod
    def _indexed_columns(table_def: TableDefinition) -> set[str]:
        indexed_columns = {col.name for col in table_def.columns if col.primary_key or col.unique}
        for idx in table_def.indices:
            indexed_columns.update(idx.columns)
        for constraint in table_def.constraints:
            columns = _parse_unique_constraint_columns(constraint)
            if columns:
                indexed_columns.update(columns)
        return indexed_columns

    def ensure_table(self, table_def: TableDefinition) -> OceanBaseMySQLRdbTable:
        patched_def = table_def
        if self._isolation == IsolationType.LOGICAL:
            patched_columns: List[ColumnDef] = []
            patched_indices: List[IndexDef] = []
            for col in table_def.columns:
                if col.unique:
                    scoped_cols = [col.name, LOGICAL_NAMESPACE_COLUMN]
                    patched_indices.append(
                        IndexDef(
                            name=_scoped_unique_index_name(table_def.table_name, scoped_cols),
                            columns=scoped_cols,
                            unique=True,
                        )
                    )
                    patched_columns.append(dataclasses.replace(col, unique=False))
                else:
                    patched_columns.append(col)
            if not any(col.name == LOGICAL_NAMESPACE_COLUMN for col in patched_columns):
                patched_columns.append(ColumnDef(name=LOGICAL_NAMESPACE_COLUMN, col_type="TEXT", nullable=False))
            for idx in table_def.indices:
                if idx.unique and LOGICAL_NAMESPACE_COLUMN not in idx.columns:
                    patched_indices.append(
                        IndexDef(name=idx.name, columns=list(idx.columns) + [LOGICAL_NAMESPACE_COLUMN], unique=True)
                    )
                else:
                    patched_indices.append(idx)
            pk_cols = [col.name for col in patched_columns if col.primary_key]
            if pk_cols:
                patched_indices.append(
                    IndexDef(
                        name=f"idx_{table_def.table_name}_pk_{LOGICAL_NAMESPACE_COLUMN}",
                        columns=pk_cols + [LOGICAL_NAMESPACE_COLUMN],
                        unique=True,
                    )
                )
            patched_indices.append(
                IndexDef(
                    name=f"idx_{table_def.table_name}_{LOGICAL_NAMESPACE_COLUMN}", columns=[LOGICAL_NAMESPACE_COLUMN]
                )
            )
            patched_def = TableDefinition(
                table_name=table_def.table_name,
                columns=patched_columns,
                indices=patched_indices,
                constraints=[_scope_unique_constraint(c) for c in table_def.constraints],
            )

        ddl_statements = self._generate_ddl(patched_def)
        try:
            with self._pool.connection(database=self._database_name) as conn:
                with conn.cursor() as cursor:
                    for stmt in ddl_statements:
                        try:
                            cursor.execute(stmt)
                        except pymysql.err.OperationalError as e:
                            if e.args and e.args[0] == 1061:
                                continue
                            raise
                conn.commit()
        except Exception as e:
            ddl_text = "\n".join(ddl_statements)
            raise RuntimeError(
                f"Failed to create table '{table_def.table_name}'. Please create it manually:\n\n{ddl_text}"
            ) from e

        return OceanBaseMySQLRdbTable(
            self._pool,
            self._database_name,
            patched_def.table_name,
            self._local,
            isolation=self._isolation,
            logical_namespace=self._logical_namespace,
        )

    @contextmanager
    def transaction(self) -> Iterator[None]:
        with self._pool.connection(database=self._database_name) as conn:
            self._local.txn_conn = conn
            try:
                yield
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                self._local.txn_conn = None

    def close(self) -> None:
        pass


class OceanBaseMySQLRdbBackend(BaseRdbBackend):
    def __init__(self) -> None:
        self._config: Dict[str, Any] = {}
        self._pool: Optional[_ConnectionPool] = None
        self._pool_lock = threading.Lock()
        self._isolation: IsolationType = IsolationType.PHYSICAL

    def initialize(self, config: Dict[str, Any]) -> None:
        required = ("host", "port", "user", "password", "database")
        missing = [key for key in required if key not in config]
        if missing:
            raise ValueError(f"Missing required OceanBase MySQL config keys: {', '.join(missing)}")
        self._config = config
        self._isolation = IsolationType(config.get("isolation", IsolationType.PHYSICAL.value))

    def _get_or_create_pool(self) -> _ConnectionPool:
        if self._pool is not None:
            return self._pool
        with self._pool_lock:
            if self._pool is None:
                self._pool = _ConnectionPool(self._config)
            return self._pool

    def connect(self, namespace: str, store_db_name: str) -> OceanBaseMySQLRdbDatabase:
        return OceanBaseMySQLRdbDatabase(
            pool=self._get_or_create_pool(),
            configured_database=self._config["database"],
            namespace=namespace,
            store_db_name=store_db_name,
            isolation=self._isolation,
        )

    def close(self) -> None:
        if self._pool is not None:
            self._pool.close()
            self._pool = None
