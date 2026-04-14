"""PostgreSQL implementation of BaseRdbBackend using psycopg v3.

Three-layer architecture:
  PostgresRdbBackend(BaseRdbBackend)  - lifecycle: initialize, connect, close
      |
      +-- connect(ns, db) -> PgRdbDatabase(RdbDatabase)  - DDL + transaction
                                  |
                                  +-- ensure_table(def) -> PgRdbTable(RdbTable)  - table-level CRUD
"""

import dataclasses
import logging
import re
import threading
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional, Type

from psycopg import sql as psql
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from datus_storage_base.backend_config import DATASOURCE_ID_COLUMN, IsolationType
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

logger = logging.getLogger(__name__)

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_identifier(name: str) -> str:
    """Validate that a name is a safe SQL identifier."""
    if not _SAFE_IDENTIFIER.match(name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    return name


_PG_TYPE_MAP: Dict[str, str] = {
    "INTEGER": "INTEGER",
    "TEXT": "TEXT",
    "TIMESTAMP": "TIMESTAMP",
    "BOOLEAN": "BOOLEAN",
    "REAL": "REAL",
    "BLOB": "BYTEA",
}


def _pg_map_type(col_type: str) -> str:
    """Map a generic column type to a PostgreSQL-specific type."""
    return _PG_TYPE_MAP.get(col_type.upper(), col_type)


def _pg_col_ddl(col: ColumnDef) -> str:
    """Generate DDL fragment for a single column (PostgreSQL dialect)."""
    col_name = _validate_identifier(col.name)
    parts: List[str] = [col_name]

    if col.primary_key and col.autoincrement:
        parts.append("SERIAL PRIMARY KEY")
    else:
        parts.append(_pg_map_type(col.col_type))
        if col.primary_key:
            parts.append("PRIMARY KEY")
        if col.unique:
            parts.append("UNIQUE")
        if not col.nullable:
            parts.append("NOT NULL")
        if col.default is not None:
            if isinstance(col.default, str):
                escaped = col.default.replace("'", "''")
                parts.append(f"DEFAULT '{escaped}'")
            else:
                parts.append(f"DEFAULT {col.default}")

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Table-level implementation
# ---------------------------------------------------------------------------


class PgRdbTable(RdbTable):
    """PostgreSQL implementation of RdbTable (table-level CRUD)."""

    def __init__(
        self,
        pool: ConnectionPool,
        qualified_name: str,
        local: threading.local,
        pk_column: str = "id",
        isolation: IsolationType = IsolationType.PHYSICAL,
        datasource_id: Optional[str] = None,
    ):
        self._pool = pool
        self._qualified_name = qualified_name
        self._local = local
        self._pk_column = pk_column
        self._isolation = isolation
        self._datasource_id = datasource_id

    def _inject_datasource_where(self, where: Optional[WhereClause]) -> Optional[WhereClause]:
        """Prepend datasource_id condition for logical isolation."""
        if self._isolation != IsolationType.LOGICAL or self._datasource_id is None:
            return where
        ds_condition = (DATASOURCE_ID_COLUMN, WhereOp.EQ, self._datasource_id)
        conditions = _normalize_where(where)
        return [ds_condition] + conditions

    def _inject_datasource_into_record(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Add datasource_id to a record dict for logical isolation."""
        if self._isolation != IsolationType.LOGICAL or self._datasource_id is None:
            return data
        return {**data, DATASOURCE_ID_COLUMN: self._datasource_id}

    @property
    def table_name(self) -> str:
        return self._qualified_name

    # -- internal helpers --

    @contextmanager
    def _auto_conn(self) -> Iterator[Any]:
        """Yield a connection: reuse transaction conn or open a fresh auto-commit one."""
        txn_conn = getattr(self._local, "txn_conn", None)
        if txn_conn is not None:
            yield txn_conn
        else:
            with self._pool.connection() as conn:
                try:
                    yield conn
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise

    @staticmethod
    def _build_where(where: Optional[WhereClause]) -> tuple:
        conditions = _normalize_where(where)
        if not conditions:
            return "", []
        parts = []
        params = []
        for col, op, val in conditions:
            _validate_identifier(col)
            if op in (WhereOp.IS_NULL, WhereOp.IS_NOT_NULL):
                parts.append(f"{col} {op.value}")
            else:
                parts.append(f"{col} {op.value} %s")
                params.append(val)
        return " WHERE " + " AND ".join(parts), params

    @staticmethod
    def _build_order_by(order_by: Optional[List[str]]) -> str:
        if not order_by:
            return ""
        parts = []
        for item in order_by:
            if item.startswith("-"):
                col = _validate_identifier(item[1:])
                parts.append(f"{col} DESC")
            else:
                col = _validate_identifier(item)
                parts.append(f"{col} ASC")
        return " ORDER BY " + ", ".join(parts)

    # -- CRUD --

    def insert(self, record: Any) -> int:
        data = {k: v for k, v in dataclasses.asdict(record).items() if v is not None}
        data = self._inject_datasource_into_record(data)
        if not data:
            sql = f"INSERT INTO {self._qualified_name} DEFAULT VALUES RETURNING {self._pk_column}"
        else:
            columns = [_validate_identifier(k) for k in data.keys()]
            placeholders = ", ".join(["%s"] * len(columns))
            col_names = ", ".join(columns)
            sql = (
                f"INSERT INTO {self._qualified_name} ({col_names}) VALUES ({placeholders}) RETURNING {self._pk_column}"
            )
        try:
            with self._auto_conn() as conn:
                cursor = conn.execute(sql, tuple(data.values()))
                row = cursor.fetchone()
                if row:
                    if isinstance(row, dict):
                        return next(iter(row.values()))
                    return row[0]
                return 0
        except Exception as e:
            exc_type_name = type(e).__name__
            if "UniqueViolation" in exc_type_name:
                raise UniqueViolationError(str(e)) from e
            if "IntegrityError" in exc_type_name:
                raise IntegrityError(str(e)) from e
            raise

    def query(
        self,
        model: Type[T],
        where: Optional[WhereClause] = None,
        columns: Optional[List[str]] = None,
        order_by: Optional[List[str]] = None,
    ) -> List[T]:
        where = self._inject_datasource_where(where)
        if columns:
            for c in columns:
                _validate_identifier(c)
        col_str = ", ".join(columns) if columns else "*"
        where_sql, params = self._build_where(where)
        order_sql = self._build_order_by(order_by)
        sql = f"SELECT {col_str} FROM {self._qualified_name}{where_sql}{order_sql}"
        with self._auto_conn() as conn:
            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()
            results = []
            for row in rows:
                row_dict = dict(row)
                row_dict.pop(DATASOURCE_ID_COLUMN, None)
                results.append(model(**row_dict))
            return results

    def update(self, data: Dict[str, Any], where: Optional[WhereClause] = None) -> int:
        if self._isolation == IsolationType.LOGICAL and DATASOURCE_ID_COLUMN in data:
            raise ValueError(f"{DATASOURCE_ID_COLUMN} is managed internally and cannot be updated")
        where = self._inject_datasource_where(where)
        if not data:
            return 0
        for col in data.keys():
            _validate_identifier(col)
        set_parts = [f"{col} = %s" for col in data.keys()]
        set_sql = ", ".join(set_parts)
        where_sql, where_params = self._build_where(where)
        sql = f"UPDATE {self._qualified_name} SET {set_sql}{where_sql}"
        params = list(data.values()) + where_params
        try:
            with self._auto_conn() as conn:
                cursor = conn.execute(sql, params)
                return cursor.rowcount
        except Exception as e:
            exc_type_name = type(e).__name__
            if "UniqueViolation" in exc_type_name:
                raise UniqueViolationError(str(e)) from e
            if "IntegrityError" in exc_type_name:
                raise IntegrityError(str(e)) from e
            raise

    def delete(self, where: Optional[WhereClause] = None) -> int:
        where = self._inject_datasource_where(where)
        where_sql, params = self._build_where(where)
        sql = f"DELETE FROM {self._qualified_name}{where_sql}"
        with self._auto_conn() as conn:
            cursor = conn.execute(sql, params)
            return cursor.rowcount

    def upsert(self, record: Any, conflict_columns: List[str]) -> None:
        data = {k: v for k, v in dataclasses.asdict(record).items() if v is not None}
        data = self._inject_datasource_into_record(data)
        if not data:
            raise ValueError("Cannot upsert a record with no non-None fields")
        # In logical mode, scope conflict target to tenant
        if self._isolation == IsolationType.LOGICAL and DATASOURCE_ID_COLUMN not in conflict_columns:
            conflict_columns = list(conflict_columns) + [DATASOURCE_ID_COLUMN]
        columns = [_validate_identifier(k) for k in data.keys()]
        placeholders = ", ".join(["%s"] * len(columns))
        col_names = ", ".join(columns)
        conflict_cols = ", ".join(_validate_identifier(c) for c in conflict_columns)
        update_cols = [c for c in columns if c not in conflict_columns]
        update_set = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)

        if update_set:
            sql = (
                f"INSERT INTO {self._qualified_name} ({col_names}) VALUES ({placeholders}) "
                f"ON CONFLICT ({conflict_cols}) DO UPDATE SET {update_set}"
            )
        else:
            sql = (
                f"INSERT INTO {self._qualified_name} ({col_names}) VALUES ({placeholders}) "
                f"ON CONFLICT ({conflict_cols}) DO NOTHING"
            )
        try:
            with self._auto_conn() as conn:
                conn.execute(sql, tuple(data.values()))
        except Exception as e:
            exc_type_name = type(e).__name__
            if "UniqueViolation" in exc_type_name:
                raise UniqueViolationError(str(e)) from e
            if "IntegrityError" in exc_type_name:
                raise IntegrityError(str(e)) from e
            raise


# ---------------------------------------------------------------------------
# Database-level implementation
# ---------------------------------------------------------------------------


class PgRdbDatabase(RdbDatabase):
    """PostgreSQL implementation of RdbDatabase (DDL + transaction)."""

    def __init__(
        self,
        pool: ConnectionPool,
        namespace: str = "",
        store_db_name: str = "",
        isolation: IsolationType = IsolationType.PHYSICAL,
    ):
        self._pool = pool
        self._namespace = namespace
        self._store_db_name = store_db_name
        self._isolation = isolation
        self._local = threading.local()

        if isolation == IsolationType.LOGICAL:
            self._schema = "public"
            self._datasource_id = namespace
        else:
            self._schema = _validate_identifier(namespace) if namespace else "public"
            self._datasource_id = None

        # Ensure schema exists for non-public namespaces
        if self._schema != "public":
            with self._pool.connection() as conn:
                conn.execute(psql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(psql.Identifier(self._schema)))
                conn.commit()

    @property
    def pool(self) -> ConnectionPool:
        return self._pool

    @property
    def namespace(self) -> str:
        return self._namespace

    def _qualified(self, table_name: str) -> str:
        """Return schema-qualified table name."""
        _validate_identifier(table_name)
        if self._schema == "public":
            return table_name
        return f"{self._schema}.{table_name}"

    @staticmethod
    def _generate_ddl(qualified_name: str, table_def: TableDefinition) -> List[str]:
        """Generate CREATE TABLE and CREATE INDEX DDL statements for PostgreSQL."""
        statements: List[str] = []

        col_parts = [_pg_col_ddl(col) for col in table_def.columns]
        col_parts.extend(table_def.constraints)

        create_table = (
            f"CREATE TABLE IF NOT EXISTS {qualified_name} (\n" + ",\n".join(f"    {p}" for p in col_parts) + "\n)"
        )
        statements.append(create_table)

        for idx in table_def.indices:
            unique = "UNIQUE " if idx.unique else ""
            idx_name = _validate_identifier(idx.name)
            cols = ", ".join(_validate_identifier(c) for c in idx.columns)
            statements.append(f"CREATE {unique}INDEX IF NOT EXISTS {idx_name} ON {qualified_name}({cols})")

        return statements

    def ensure_table(self, table_def: TableDefinition) -> PgRdbTable:
        # For logical isolation, inject datasource_id column if not present
        if self._isolation == IsolationType.LOGICAL:
            has_datasource_col = any(c.name == DATASOURCE_ID_COLUMN for c in table_def.columns)
            if not has_datasource_col:
                extra_col = ColumnDef(
                    name=DATASOURCE_ID_COLUMN,
                    col_type="TEXT",
                    nullable=False,
                )
                # Add datasource_id to unique indices so tenants don't conflict
                patched_indices = []
                for idx in table_def.indices:
                    if idx.unique and DATASOURCE_ID_COLUMN not in idx.columns:
                        patched_indices.append(
                            IndexDef(
                                name=idx.name,
                                columns=list(idx.columns) + [DATASOURCE_ID_COLUMN],
                                unique=True,
                            )
                        )
                    else:
                        patched_indices.append(idx)
                # Add composite unique index for PK + datasource_id (needed for upsert ON CONFLICT)
                pk_cols = [c.name for c in table_def.columns if c.primary_key]
                if pk_cols:
                    patched_indices.append(
                        IndexDef(
                            name=f"idx_{table_def.table_name}_pk_{DATASOURCE_ID_COLUMN}",
                            columns=pk_cols + [DATASOURCE_ID_COLUMN],
                            unique=True,
                        )
                    )
                # Add standalone datasource_id index for filtering
                patched_indices.append(
                    IndexDef(
                        name=f"idx_{table_def.table_name}_{DATASOURCE_ID_COLUMN}",
                        columns=[DATASOURCE_ID_COLUMN],
                    )
                )
                table_def = TableDefinition(
                    table_name=table_def.table_name,
                    columns=list(table_def.columns) + [extra_col],
                    indices=patched_indices,
                    constraints=list(table_def.constraints),
                )

        qualified = self._qualified(table_def.table_name)
        ddl_statements = self._generate_ddl(qualified, table_def)

        # For logical isolation, ensure datasource_id exists on pre-existing tables.
        # CREATE TABLE IF NOT EXISTS is a no-op when the table already exists, so the
        # column would be missing and subsequent CREATE INDEX statements would fail.
        if self._isolation == IsolationType.LOGICAL:
            ddl_statements.insert(
                1,
                f"ALTER TABLE {qualified} "
                f"ADD COLUMN IF NOT EXISTS {DATASOURCE_ID_COLUMN} TEXT NOT NULL DEFAULT ''",
            )

        try:
            with self._pool.connection() as conn:
                for stmt in ddl_statements:
                    conn.execute(stmt)
                conn.commit()
        except Exception as e:
            ddl_text = "\n".join(ddl_statements)
            logger.exception("Auto-create table '%s' failed", table_def.table_name)
            raise RuntimeError(
                f"Failed to create table '{table_def.table_name}'. Please create it manually:\n\n{ddl_text}"
            ) from e

        pk_column = "id"
        for col in table_def.columns:
            if col.primary_key:
                pk_column = col.name
                break

        return PgRdbTable(
            self._pool,
            qualified,
            self._local,
            pk_column=pk_column,
            isolation=self._isolation,
            datasource_id=self._datasource_id,
        )

    @contextmanager
    def transaction(self) -> Iterator[None]:
        with self._pool.connection() as conn:
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
        # Pool is managed by the backend; database-level close is a no-op.
        logger.info("PostgreSQL RDB database handle closed")

    # ========== Convenience methods ==========

    @contextmanager
    def get_connection(self) -> Iterator[Any]:
        with self._pool.connection() as conn:
            yield conn

    def execute(self, conn: Any, sql: str, params: Any = None) -> Any:
        cursor = conn.cursor()
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        return cursor

    def execute_query(self, conn: Any, sql: str, params: Any = None) -> List[Dict[str, Any]]:
        cursor = conn.cursor(row_factory=dict_row)
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        return [dict(row) for row in cursor.fetchall()]

    def execute_insert(self, conn: Any, sql: str, params: Any = None) -> int:
        cursor = conn.cursor()
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        try:
            row = cursor.fetchone()
            if row:
                if isinstance(row, dict):
                    return next(iter(row.values()))
                return row[0]
        except Exception as e:
            logger.warning("execute_insert fetchone failed: %s", e)
        return 0

    def param_placeholder(self) -> str:
        return "%s"

    @property
    def dialect(self) -> str:
        return "postgresql"


# ---------------------------------------------------------------------------
# Backend-level implementation (lifecycle only)
# ---------------------------------------------------------------------------


class PostgresRdbBackend(BaseRdbBackend):
    """PostgreSQL implementation of the RDB backend (lifecycle only)."""

    def __init__(self):
        self._config: Dict[str, Any] = {}
        self._databases: List[PgRdbDatabase] = []
        self._pool: Optional[ConnectionPool] = None
        self._pool_lock = threading.Lock()
        self._isolation: IsolationType = IsolationType.PHYSICAL

    def initialize(self, config: Dict[str, Any]) -> None:
        _REQUIRED_KEYS = ("host", "port", "user", "password", "dbname")
        missing = [k for k in _REQUIRED_KEYS if k not in config]
        if missing:
            raise ValueError(f"Missing required PostgreSQL config keys: {', '.join(missing)}")
        self._config = config
        self._isolation = IsolationType(config.get("isolation", IsolationType.PHYSICAL.value))

    def _get_or_create_pool(self) -> ConnectionPool:
        """Return the shared connection pool, creating it on first use."""
        if self._pool is not None:
            return self._pool
        with self._pool_lock:
            if self._pool is not None:
                return self._pool
            config = self._config
            host = config["host"]
            port = config["port"]
            user = config["user"]
            password = config["password"]
            dbname = config["dbname"]
            min_size = config.get("pool_min_size", 1)
            max_size = config.get("pool_max_size", 10)

            conninfo = f"host={host} port={port} user={user} password={password} dbname={dbname}"
            self._pool = ConnectionPool(
                conninfo=conninfo,
                min_size=min_size,
                max_size=max_size,
                kwargs={"row_factory": dict_row},
            )
            logger.info("PostgreSQL connection pool created for %s:%s/%s", host, port, dbname)
        return self._pool

    def connect(self, namespace: str, store_db_name: str) -> PgRdbDatabase:
        """Create a database-level handle for the given namespace/store.

        Args:
            namespace: Logical namespace mapped to a PostgreSQL schema.
            store_db_name: Logical store identifier.
        """
        pool = self._get_or_create_pool()
        db = PgRdbDatabase(
            pool=pool,
            namespace=namespace,
            store_db_name=store_db_name,
            isolation=self._isolation,
        )
        self._databases.append(db)
        return db

    def close(self) -> None:
        self._databases.clear()
        if self._pool is not None:
            try:
                self._pool.close()
            except Exception as e:
                logger.warning("Error closing connection pool: %s", e)
            self._pool = None
