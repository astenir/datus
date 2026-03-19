"""pgvector implementation of BaseVectorBackend using psycopg v3.

Three-layer architecture:
  PgvectorBackend(BaseVectorBackend)  - lifecycle & embedding config
      |
      +-- connect(namespace) -> PgVectorDb(VectorDatabase)
                                    |
                                    +-- open_table(name) -> PgVectorTable(VectorTable)
"""

import logging
import re
import threading
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd
import pyarrow as pa
from psycopg import sql as psql
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from datus_storage_base.conditions import WhereExpr, build_where
from datus_storage_base.vector.base import BaseVectorBackend, EmbeddingFunction, VectorDatabase, VectorTable
from datus_storage_postgresql.vector.schema_converter import schema_to_create_table_sql

logger = logging.getLogger(__name__)

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_identifier(name: str) -> str:
    """Validate that a name is a safe SQL identifier."""
    if not _SAFE_IDENTIFIER.match(name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    return name


# ---------------------------------------------------------------------------
# Table-level implementation
# ---------------------------------------------------------------------------


class PgVectorTable(VectorTable):
    """pgvector implementation of VectorTable."""

    def __init__(
        self,
        table_name: str,
        pool: ConnectionPool,
        embedding_fn: Any = None,
        vector_column: str = "vector",
        source_column: str = "description",
        vector_dim: int = 384,
        column_names: Optional[List[str]] = None,
    ):
        self._table_name = table_name
        self._pool = pool
        self._embedding_fn = embedding_fn
        self._vector_column = vector_column
        self._source_column = source_column
        self._vector_dim = vector_dim
        self._column_names = column_names or []

    @property
    def table_name(self) -> str:
        return self._table_name

    @property
    def embedding_fn(self) -> Any:
        return self._embedding_fn

    @property
    def vector_column(self) -> str:
        return self._vector_column

    @property
    def source_column(self) -> str:
        return self._source_column

    @property
    def vector_dim(self) -> int:
        return self._vector_dim

    @property
    def column_names(self) -> List[str]:
        return self._column_names

    # -- Write operations --

    def add(self, data: pd.DataFrame) -> None:
        df = self._compute_embeddings_for_insert(data)
        self._insert_dataframe(df)

    def merge_insert(self, data: pd.DataFrame, on_column: str) -> None:
        df = self._compute_embeddings_for_insert(data)
        self._upsert_dataframe(df, on_column)

    def delete(self, where: WhereExpr) -> None:
        compiled = build_where(where)
        if compiled:
            sql = f"DELETE FROM {self._table_name} WHERE {compiled}"
            with self._pool.connection() as conn:
                conn.execute(sql)
                conn.commit()

    def update(self, where: WhereExpr, values: Dict[str, Any]) -> None:
        compiled = build_where(where)
        set_parts = []
        params = []
        for col, val in values.items():
            _validate_identifier(col)
            set_parts.append(f"{col} = %s")
            params.append(val)
        set_clause = ", ".join(set_parts)
        where_clause = f" WHERE {compiled}" if compiled else ""
        sql = f"UPDATE {self._table_name} SET {set_clause}{where_clause}"
        with self._pool.connection() as conn:
            conn.execute(sql, params)
            conn.commit()

    # -- Search operations --

    @staticmethod
    def _validate_select_fields(fields: List[str]) -> str:
        """Validate and join select field names."""
        for f in fields:
            _validate_identifier(f)
        return ", ".join(fields)

    def search_vector(
        self,
        query_text: str,
        vector_column: str,
        top_n: int,
        where: WhereExpr = None,
        select_fields: Optional[List[str]] = None,
    ) -> pa.Table:
        compiled = build_where(where)
        query_embedding = self._compute_query_embedding(query_text)

        columns = self._validate_select_fields(select_fields) if select_fields else self._select_columns()
        _validate_identifier(vector_column)
        where_clause = f"WHERE {compiled}" if compiled else ""
        sql = (
            f"SELECT {columns} FROM {self._table_name} "
            f"{where_clause} "
            f"ORDER BY {vector_column} <=> %s::vector "
            f"LIMIT %s"
        )
        with self._pool.connection() as conn:
            rows = conn.execute(sql, (str(query_embedding), top_n)).fetchall()

        return self._rows_to_arrow(rows, select_fields)

    def search_hybrid(
        self,
        query_text: str,
        vector_source_column: str,
        top_n: int,
        where: WhereExpr = None,
        select_fields: Optional[List[str]] = None,
    ) -> pa.Table:
        # Fallback to vector search since full hybrid requires tsvector setup
        return self.search_vector(
            query_text,
            self._vector_column,
            top_n,
            where=where,
            select_fields=select_fields,
        )

    def search_all(
        self,
        where: WhereExpr = None,
        select_fields: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> pa.Table:
        compiled = build_where(where)
        columns = self._validate_select_fields(select_fields) if select_fields else self._select_columns()
        where_clause = f"WHERE {compiled}" if compiled else ""

        limit_clause = f"LIMIT {int(limit)}" if limit is not None else ""
        sql = f"SELECT {columns} FROM {self._table_name} {where_clause} {limit_clause}"

        with self._pool.connection() as conn:
            rows = conn.execute(sql).fetchall()

        return self._rows_to_arrow(rows, select_fields)

    def count_rows(self, where: WhereExpr = None) -> int:
        compiled = build_where(where)
        where_clause = f"WHERE {compiled}" if compiled else ""
        sql = f"SELECT COUNT(*) AS cnt FROM {self._table_name} {where_clause}"
        with self._pool.connection() as conn:
            row = conn.execute(sql).fetchone()
            if isinstance(row, dict):
                return row["cnt"]
            return row[0] if row else 0

    # -- Index operations --

    def create_vector_index(self, column: str, metric: str = "cosine", **kwargs) -> None:
        _validate_identifier(column)
        table_token = self._table_name.rsplit(".", 1)[-1]
        index_name = f"idx_{table_token}_{column}_hnsw"
        ops_map = {
            "cosine": "vector_cosine_ops",
            "l2": "vector_l2_ops",
            "ip": "vector_ip_ops",
        }
        ops = ops_map.get(metric, "vector_cosine_ops")
        sql = (
            f"CREATE INDEX IF NOT EXISTS {index_name} "
            f"ON {self._table_name} USING hnsw ({column} {ops})"
        )
        with self._pool.connection() as conn:
            conn.execute(sql)
            conn.commit()

    def create_fts_index(self, field_names: Union[str, List[str]]) -> None:
        if isinstance(field_names, str):
            field_names = [field_names]
        for f in field_names:
            _validate_identifier(f)

        tsv_col = "tsv"
        coalesce_parts = " || ' ' || ".join(
            f"COALESCE({f}, '')" for f in field_names
        )
        table_token = self._table_name.rsplit(".", 1)[-1]
        index_name = f"idx_{table_token}_fts"

        with self._pool.connection() as conn:
            conn.execute(
                f"ALTER TABLE {self._table_name} "
                f"ADD COLUMN IF NOT EXISTS {tsv_col} tsvector "
                f"GENERATED ALWAYS AS (to_tsvector('english', {coalesce_parts})) STORED"
            )
            conn.execute(
                f"CREATE INDEX IF NOT EXISTS {index_name} "
                f"ON {self._table_name} USING gin ({tsv_col})"
            )
            conn.commit()

    def create_scalar_index(self, column: str) -> None:
        _validate_identifier(column)
        table_token = self._table_name.rsplit(".", 1)[-1]
        index_name = f"idx_{table_token}_{column}_btree"
        sql = (
            f"CREATE INDEX IF NOT EXISTS {index_name} "
            f"ON {self._table_name} ({column})"
        )
        with self._pool.connection() as conn:
            conn.execute(sql)
            conn.commit()

    # -- Private helpers --

    def _compute_embeddings_for_insert(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute source embeddings and fill the vector column in the DataFrame."""
        if self._embedding_fn is None:
            return df

        if self._vector_column not in df.columns:
            df = df.copy()
            df[self._vector_column] = self._embedding_fn.generate_embeddings(
                df[self._source_column].tolist()
            )
            return df

        missing = df[self._vector_column].isna()
        if missing.any():
            df = df.copy()
            df.loc[missing, self._vector_column] = self._embedding_fn.generate_embeddings(
                df.loc[missing, self._source_column].tolist()
            )

        return df

    def _compute_query_embedding(self, query_text: str) -> List[float]:
        """Compute embedding for a query text."""
        if self._embedding_fn is None:
            raise RuntimeError(
                f"No embedding function available for table '{self._table_name}'. "
                "Ensure the table was created with an embedding_function."
            )
        embeddings = self._embedding_fn.generate_embeddings([query_text])
        return embeddings[0]

    def _insert_dataframe(self, df: pd.DataFrame) -> None:
        """Insert all rows from a DataFrame into the table."""
        if df.empty:
            return

        columns = list(df.columns)
        for c in columns:
            _validate_identifier(c)
        col_names = ", ".join(columns)
        placeholders = ", ".join(["%s"] * len(columns))
        sql = f"INSERT INTO {self._table_name} ({col_names}) VALUES ({placeholders})"

        rows = []
        for _, row in df.iterrows():
            values = []
            for col in columns:
                val = row[col]
                if col == self._vector_column and val is not None:
                    val = str(list(val)) if not isinstance(val, str) else val
                values.append(val)
            rows.append(tuple(values))

        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(sql, rows)
            conn.commit()

    def _upsert_dataframe(self, df: pd.DataFrame, on_column: str) -> None:
        """Upsert all rows from a DataFrame into the table."""
        if df.empty:
            return

        columns = list(df.columns)
        for c in columns:
            _validate_identifier(c)
        _validate_identifier(on_column)
        col_names = ", ".join(columns)
        placeholders = ", ".join(["%s"] * len(columns))
        update_cols = [c for c in columns if c != on_column]
        update_set = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)

        if update_set:
            sql = (
                f"INSERT INTO {self._table_name} ({col_names}) VALUES ({placeholders}) "
                f"ON CONFLICT ({on_column}) DO UPDATE SET {update_set}"
            )
        else:
            sql = (
                f"INSERT INTO {self._table_name} ({col_names}) VALUES ({placeholders}) "
                f"ON CONFLICT ({on_column}) DO NOTHING"
            )

        rows = []
        for _, row in df.iterrows():
            values = []
            for col in columns:
                val = row[col]
                if col == self._vector_column and val is not None:
                    val = str(list(val)) if not isinstance(val, str) else val
                values.append(val)
            rows.append(tuple(values))

        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(sql, rows)
            conn.commit()

    def _select_columns(self) -> str:
        """Build the default SELECT column list."""
        if self._column_names:
            return ", ".join(self._column_names)
        return "*"

    def _rows_to_arrow(
        self,
        rows: List[Any],
        select_fields: Optional[List[str]] = None,
    ) -> pa.Table:
        """Convert fetched rows (list of dicts) to a PyArrow Table."""
        if not rows:
            if select_fields:
                arrays = {
                    f: pa.array([], type=pa.list_(pa.float32(), list_size=self._vector_dim) if f == self._vector_column else pa.string())
                    for f in select_fields
                }
            elif self._column_names:
                arrays = {
                    c: pa.array([], type=pa.list_(pa.float32(), list_size=self._vector_dim) if c == self._vector_column else pa.string())
                    for c in self._column_names
                }
            else:
                return pa.table({})
            return pa.table(arrays)

        if isinstance(rows[0], dict):
            col_names = select_fields or list(rows[0].keys())
        else:
            col_names = select_fields or self._column_names

        arrays = {}
        for idx, col in enumerate(col_names):
            values = [r[col] if isinstance(r, dict) else r[idx] for r in rows]
            if col == self._vector_column:
                parsed = []
                for v in values:
                    if isinstance(v, str):
                        parsed.append([float(x) for x in v.strip("[]").split(",")])
                    elif isinstance(v, list):
                        parsed.append(v)
                    else:
                        parsed.append(list(v) if v is not None else [0.0] * self._vector_dim)
                arrays[col] = pa.array(
                    parsed, type=pa.list_(pa.float32(), list_size=self._vector_dim)
                )
            else:
                arrays[col] = pa.array(values)

        return pa.table(arrays)


# ---------------------------------------------------------------------------
# Database-level implementation
# ---------------------------------------------------------------------------


class PgVectorDb(VectorDatabase):
    """pgvector implementation of VectorDatabase.

    Uses PostgreSQL schemas to implement namespace-based data isolation.
    """

    def __init__(self, pool: ConnectionPool, config: Dict[str, Any], namespace: str = ""):
        self._pool = pool
        self._config = config
        self._namespace = namespace
        self._schema = _validate_identifier(namespace) if namespace else "public"
        self._table_cache: Dict[tuple, PgVectorTable] = {}

        # Ensure schema exists for non-public namespaces
        if self._schema != "public":
            with self._pool.connection() as conn:
                conn.execute(
                    psql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(
                        psql.Identifier(self._schema)
                    )
                )
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

    def table_exists(self, table_name: str) -> bool:
        with self._pool.connection() as conn:
            rows = conn.execute(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = %s AND table_name = %s)",
                (self._schema, table_name),
            ).fetchone()
            if isinstance(rows, dict):
                return next(iter(rows.values()))
            return rows[0] if rows else False

    def table_names(self, limit: int = 100) -> List[str]:
        with self._pool.connection() as conn:
            rows = conn.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = %s "
                "ORDER BY table_name LIMIT %s",
                (self._schema, limit),
            ).fetchall()
            return [r["table_name"] if isinstance(r, dict) else r[0] for r in rows]

    def create_table(
        self,
        table_name: str,
        schema: Optional[pa.Schema] = None,
        embedding_function: Optional[EmbeddingFunction] = None,
        vector_column: str = "",
        source_column: str = "",
        exist_ok: bool = True,
        unique_columns: Optional[List[str]] = None,
    ) -> PgVectorTable:
        qualified = self._qualified(table_name)

        # Apply defaults when not specified
        vector_column = vector_column or "vector"
        source_column = source_column or "description"
        vector_dim = embedding_function.ndims() if embedding_function else 384

        # Build column list from schema
        column_names = []
        if schema is not None:
            if isinstance(schema, pa.Schema):
                ddl = schema_to_create_table_sql(qualified, schema, unique_columns=unique_columns)
                column_names = [f.name for f in schema]
            else:
                raise TypeError(f"Unsupported schema type: {type(schema)}")

            with self._pool.connection() as conn:
                conn.execute(ddl)
                conn.commit()
        elif not exist_ok:
            raise ValueError(f"Schema is required to create table '{table_name}'")
        else:
            if not self.table_exists(table_name):
                raise ValueError(
                    f"Table '{table_name}' does not exist and no schema was provided to create it."
                )

        table = PgVectorTable(
            table_name=qualified,
            pool=self._pool,
            embedding_fn=embedding_function,
            vector_column=vector_column,
            source_column=source_column,
            vector_dim=vector_dim,
            column_names=column_names,
        )
        cache_key = (table_name, id(embedding_function), vector_dim, vector_column, source_column)
        self._table_cache[cache_key] = table
        return table

    def open_table(
        self,
        table_name: str,
        embedding_function: Optional[EmbeddingFunction] = None,
        vector_column: str = "",
        source_column: str = "",
    ) -> PgVectorTable:
        vector_column = vector_column or "vector"
        source_column = source_column or "description"
        vector_dim = embedding_function.ndims() if embedding_function else 384

        # Build a cache key that includes runtime options so changed options
        # don't return a stale handle.
        cache_key = (table_name, id(embedding_function), vector_dim, vector_column, source_column)
        if cache_key in self._table_cache:
            return self._table_cache[cache_key]

        qualified = self._qualified(table_name)

        with self._pool.connection() as conn:
            rows = conn.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = %s AND table_name = %s "
                "ORDER BY ordinal_position",
                (self._schema, table_name),
            ).fetchall()
            column_names = [r["column_name"] if isinstance(r, dict) else r[0] for r in rows]

        if not column_names:
            raise ValueError(
                f"Table '{table_name}' not found in schema '{self._schema}'. "
                "Use create_table() first."
            )

        table = PgVectorTable(
            table_name=qualified,
            pool=self._pool,
            embedding_fn=embedding_function,
            vector_column=vector_column,
            source_column=source_column,
            vector_dim=vector_dim,
            column_names=column_names,
        )
        self._table_cache[cache_key] = table
        return table

    def _invalidate_cache(self, table_name: str) -> None:
        """Remove all cache entries for the given table name."""
        keys_to_remove = [k for k in self._table_cache if k[0] == table_name]
        for k in keys_to_remove:
            del self._table_cache[k]

    def refresh_table(
        self,
        table_name: str,
        embedding_function: Optional[EmbeddingFunction] = None,
        vector_column: str = "",
        source_column: str = "",
    ) -> PgVectorTable:
        """Invalidate cache and re-open the table."""
        self._invalidate_cache(table_name)
        return self.open_table(table_name, embedding_function, vector_column, source_column)

    def drop_table(self, table_name: str, ignore_missing: bool = False) -> None:
        qualified = self._qualified(table_name)
        if_exists = "IF EXISTS " if ignore_missing else ""
        sql = f"DROP TABLE {if_exists}{qualified}"
        with self._pool.connection() as conn:
            conn.execute(sql)
            conn.commit()
        self._invalidate_cache(table_name)


# ---------------------------------------------------------------------------
# Backend-level implementation (lifecycle only)
# ---------------------------------------------------------------------------


class PgvectorBackend(BaseVectorBackend):
    """pgvector implementation of the vector backend.

    Responsible only for lifecycle management and embedding configuration.
    """

    def __init__(self):
        self._config: Dict[str, Any] = {}
        self._connections: List[PgVectorDb] = []
        self._pool: Optional[ConnectionPool] = None
        self._pool_lock = threading.Lock()

    def initialize(self, config: Dict[str, Any]) -> None:
        self._config = config

    def _get_or_create_pool(self) -> ConnectionPool:
        """Return the shared connection pool, creating it on first use."""
        if self._pool is not None:
            return self._pool

        with self._pool_lock:
            if self._pool is not None:
                return self._pool

            config = self._config

            _REQUIRED_KEYS = ("host", "port", "user", "password", "dbname")
            missing = [k for k in _REQUIRED_KEYS if k not in config]
            if missing:
                raise ValueError(f"Missing required PostgreSQL config keys: {', '.join(missing)}")

            host = config["host"]
            port = config["port"]
            user = config["user"]
            password = config["password"]
            dbname = config["dbname"]
            min_size = config.get("pool_min_size", 1)
            max_size = config.get("pool_max_size", 10)

            conninfo = f"host={host} port={port} user={user} password={password} dbname={dbname}"
            pool = ConnectionPool(
                conninfo=conninfo,
                min_size=min_size,
                max_size=max_size,
                kwargs={"row_factory": dict_row},
            )

            # Ensure pgvector extension is available
            with pool.connection() as conn:
                row = conn.execute(
                    "SELECT 1 FROM pg_extension WHERE extname = 'vector'"
                ).fetchone()
                if not row:
                    try:
                        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
                        conn.commit()
                    except Exception as e:
                        pool.close()
                        raise RuntimeError(
                            "pgvector extension is not installed and current user "
                            "lacks permission to create it. Please ask a database "
                            "superuser to run: CREATE EXTENSION vector;"
                        ) from e

            self._pool = pool
        return self._pool

    def connect(self, namespace: str) -> PgVectorDb:
        """Connect to PostgreSQL and return a VectorDatabase handle.

        Args:
            namespace: Logical namespace for data isolation.
        """
        pool = self._get_or_create_pool()
        db = PgVectorDb(pool=pool, config=self._config, namespace=namespace)
        self._connections.append(db)
        return db

    def close(self) -> None:
        self._connections.clear()
        if self._pool is not None:
            try:
                self._pool.close()
            except Exception as e:
                logger.warning("Error closing vector database connection pool: %s", e)
            self._pool = None

