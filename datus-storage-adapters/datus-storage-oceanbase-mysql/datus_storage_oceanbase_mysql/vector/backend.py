"""OceanBase MySQL mode vector backend for Datus storage."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

import pandas as pd
import pyarrow as pa

from datus_storage_base.backend_config import LOGICAL_NAMESPACE_COLUMN, IsolationType
from datus_storage_base.conditions import WhereExpr, build_where
from datus_storage_base.vector.base import BaseVectorBackend, EmbeddingFunction, VectorDatabase, VectorTable
from datus_storage_oceanbase_mysql.rdb.backend import (
    _ConnectionPool,
    _quote_ident,
    _quote_qualified,
    _validate_identifier,
)
from datus_storage_oceanbase_mysql.vector.schema_converter import schema_to_create_table_sql


def _vector_literal(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return "[" + ",".join(str(float(v)) for v in list(value)) + "]"


def _parse_vector(value: Any, dim: int) -> List[float]:
    if value is None:
        return [0.0] * dim
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("[") and text.endswith("]"):
            text = text[1:-1]
        if not text:
            return []
        return [float(part) for part in text.split(",")]
    return [float(v) for v in list(value)]


class OceanBaseMySQLVectorTable(VectorTable):
    def __init__(
        self,
        pool: _ConnectionPool,
        database_name: str,
        table_name: str,
        embedding_fn: Optional[EmbeddingFunction] = None,
        vector_column: str = "vector",
        source_column: str = "description",
        vector_dim: int = 384,
        column_names: Optional[List[str]] = None,
        isolation: IsolationType = IsolationType.PHYSICAL,
        logical_namespace: Optional[str] = None,
    ) -> None:
        self._pool = pool
        self._database_name = database_name
        self._table_name = table_name
        self._qualified_name = _quote_qualified(database_name, table_name)
        self._embedding_fn = embedding_fn
        self._vector_column = vector_column
        self._source_column = source_column
        self._vector_dim = vector_dim
        self._column_names = column_names or []
        self._isolation = isolation
        self._logical_namespace = logical_namespace
        self._ensured_conflict_indexes: set[tuple[str, ...]] = set()

    @property
    def table_name(self) -> str:
        return self._qualified_name

    @property
    def embedding_fn(self) -> Optional[EmbeddingFunction]:
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

    def add(self, data: pd.DataFrame) -> None:
        df = self._inject_namespace_df(data)
        df = self._compute_embeddings_for_insert(df)
        self._insert_dataframe(df)

    def merge_insert(self, data: pd.DataFrame, on_column: str) -> None:
        df = self._inject_namespace_df(data)
        df = self._compute_embeddings_for_insert(df)
        self._upsert_dataframe(df, on_column)

    def delete(self, where: WhereExpr) -> None:
        compiled = where if isinstance(where, str) else build_where(where)
        combined = self._namespace_where_fragment(compiled)
        if not combined:
            return
        with self._pool.connection(database=self._database_name) as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"DELETE FROM {self._qualified_name} WHERE {combined}")
            conn.commit()

    def update(self, where: WhereExpr, values: Dict[str, Any]) -> None:
        if self._isolation == IsolationType.LOGICAL and LOGICAL_NAMESPACE_COLUMN in values:
            raise ValueError(f"{LOGICAL_NAMESPACE_COLUMN} is managed internally and cannot be updated")
        compiled = where if isinstance(where, str) else build_where(where)
        combined = self._namespace_where_fragment(compiled)
        set_parts = []
        params = []
        for col, val in values.items():
            _validate_identifier(col)
            set_parts.append(f"{_quote_ident(col)} = %s")
            params.append(_vector_literal(val) if col == self._vector_column else val)
        where_clause = f" WHERE {combined}" if combined else ""
        with self._pool.connection(database=self._database_name) as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"UPDATE {self._qualified_name} SET {', '.join(set_parts)}{where_clause}", params)
            conn.commit()

    def ensure_columns(self, expressions: Dict[str, str]) -> None:
        if not expressions:
            return
        existing = set(self._fetch_column_names())
        missing = {name: expr for name, expr in expressions.items() if name not in existing}
        if not missing:
            return
        with self._pool.connection(database=self._database_name) as conn:
            with conn.cursor() as cursor:
                for name, expr in missing.items():
                    _validate_identifier(name)
                    cursor.execute(f"ALTER TABLE {self._qualified_name} ADD COLUMN {_quote_ident(name)} LONGTEXT")
                    cursor.execute(
                        f"UPDATE {self._qualified_name} SET {_quote_ident(name)} = {expr} WHERE {_quote_ident(name)} IS NULL"
                    )
            conn.commit()
        for name in missing:
            if name not in self._column_names:
                self._column_names.append(name)

    def search_vector(
        self,
        query_text: str,
        vector_column: str,
        top_n: int,
        where: WhereExpr = None,
        select_fields: Optional[List[str]] = None,
    ) -> pa.Table:
        compiled = where if isinstance(where, str) else build_where(where)
        combined = self._namespace_where_fragment(compiled)
        query_embedding = self._compute_query_embedding(query_text)
        columns = self._validate_select_fields(select_fields) if select_fields else self._select_columns()
        _validate_identifier(vector_column)
        where_clause = f"WHERE {combined}" if combined else ""
        distance_fn = "cosine_distance"
        sql = (
            f"SELECT {columns} FROM {self._qualified_name} {where_clause} "
            f"ORDER BY {distance_fn}({_quote_ident(vector_column)}, %s) LIMIT %s"
        )
        with self._pool.connection(database=self._database_name) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, (_vector_literal(query_embedding), int(top_n)))
                rows = cursor.fetchall()
        return self._rows_to_arrow(rows, select_fields)

    def search_hybrid(
        self,
        query_text: str,
        vector_source_column: str,
        top_n: int,
        where: WhereExpr = None,
        select_fields: Optional[List[str]] = None,
    ) -> pa.Table:
        return self.search_vector(query_text, self._vector_column, top_n, where=where, select_fields=select_fields)

    def search_all(
        self,
        where: WhereExpr = None,
        select_fields: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> pa.Table:
        compiled = where if isinstance(where, str) else build_where(where)
        combined = self._namespace_where_fragment(compiled)
        columns = self._validate_select_fields(select_fields) if select_fields else self._select_columns()
        where_clause = f"WHERE {combined}" if combined else ""
        limit_clause = f"LIMIT {int(limit)}" if limit is not None else ""
        with self._pool.connection(database=self._database_name) as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"SELECT {columns} FROM {self._qualified_name} {where_clause} {limit_clause}")
                rows = cursor.fetchall()
        return self._rows_to_arrow(rows, select_fields)

    def count_rows(self, where: WhereExpr = None) -> int:
        compiled = where if isinstance(where, str) else build_where(where)
        combined = self._namespace_where_fragment(compiled)
        where_clause = f"WHERE {combined}" if combined else ""
        with self._pool.connection(database=self._database_name) as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) AS cnt FROM {self._qualified_name} {where_clause}")
                row = cursor.fetchone()
        return int(row["cnt"] if row else 0)

    def create_vector_index(self, column: str, metric: str = "cosine", **kwargs) -> None:
        _validate_identifier(column)
        table_token = self._table_name
        index_name = kwargs.get("name") or f"idx_{table_token}_{column}_hnsw"
        distance = {"cosine": "cosine", "l2": "l2", "ip": "inner_product"}.get(metric, "cosine")
        with self._pool.connection(database=self._database_name) as conn:
            with conn.cursor() as cursor:
                try:
                    cursor.execute(
                        f"CREATE VECTOR INDEX {_quote_ident(index_name)} ON {self._qualified_name}({_quote_ident(column)}) "
                        f"WITH (distance={distance}, type=hnsw, lib=vsag)"
                    )
                except Exception as e:
                    if getattr(e, "args", None) and e.args[0] == 1061:
                        pass
                    else:
                        raise
            conn.commit()

    def create_fts_index(self, field_names: Union[str, List[str]]) -> None:
        if isinstance(field_names, str):
            field_names = [field_names]
        for field_name in field_names:
            self.create_scalar_index(field_name)

    def create_scalar_index(self, column: str) -> None:
        _validate_identifier(column)
        index_name = f"idx_{self._table_name}_{column}_btree"
        with self._pool.connection(database=self._database_name) as conn:
            with conn.cursor() as cursor:
                try:
                    cursor.execute(
                        f"CREATE INDEX {_quote_ident(index_name)} ON {self._qualified_name} ({_quote_ident(column)})"
                    )
                except Exception as e:
                    if getattr(e, "args", None) and e.args[0] == 1061:
                        pass
                    elif getattr(e, "args", None) and e.args[0] == 1167:
                        cursor.execute(
                            f"CREATE INDEX {_quote_ident(index_name)} ON {self._qualified_name} ({_quote_ident(column)}(255))"
                        )
                    else:
                        raise
            conn.commit()

    @staticmethod
    def _validate_select_fields(fields: List[str]) -> str:
        return ", ".join(_quote_ident(field) for field in fields)

    def _namespace_where_fragment(self, existing_compiled: Optional[str] = None) -> str:
        if self._isolation != IsolationType.LOGICAL or self._logical_namespace is None:
            return existing_compiled or ""
        namespace = self._logical_namespace.replace("'", "''")
        namespace_cond = f"{_quote_ident(LOGICAL_NAMESPACE_COLUMN)} = '{namespace}'"
        if existing_compiled:
            return f"{namespace_cond} AND ({existing_compiled})"
        return namespace_cond

    def _inject_namespace_df(self, df: pd.DataFrame) -> pd.DataFrame:
        if self._isolation != IsolationType.LOGICAL or self._logical_namespace is None:
            return df
        df = df.copy()
        df[LOGICAL_NAMESPACE_COLUMN] = self._logical_namespace
        return df

    def _compute_embeddings_for_insert(self, df: pd.DataFrame) -> pd.DataFrame:
        if self._embedding_fn is None:
            return df
        if self._vector_column not in df.columns:
            df = df.copy()
            df[self._vector_column] = self._embedding_fn.generate_embeddings(df[self._source_column].tolist())
            return df
        missing = df[self._vector_column].isna()
        if missing.any():
            df = df.copy()
            df.loc[missing, self._vector_column] = self._embedding_fn.generate_embeddings(
                df.loc[missing, self._source_column].tolist()
            )
        return df

    def _compute_query_embedding(self, query_text: str) -> List[float]:
        if self._embedding_fn is None:
            raise RuntimeError(f"No embedding function available for table '{self._table_name}'.")
        return self._embedding_fn.generate_embeddings([query_text])[0]

    def _insert_dataframe(self, df: pd.DataFrame) -> None:
        if df.empty:
            return
        columns = list(df.columns)
        for column in columns:
            _validate_identifier(column)
        col_names = ", ".join(_quote_ident(column) for column in columns)
        placeholders = ", ".join(["%s"] * len(columns))
        rows = [self._row_values(row, columns) for _, row in df.iterrows()]
        with self._pool.connection(database=self._database_name) as conn:
            with conn.cursor() as cursor:
                cursor.executemany(f"INSERT INTO {self._qualified_name} ({col_names}) VALUES ({placeholders})", rows)
            conn.commit()

    def _upsert_dataframe(self, df: pd.DataFrame, on_column: str) -> None:
        if df.empty:
            return
        _validate_identifier(on_column)
        columns = list(df.columns)
        for column in columns:
            _validate_identifier(column)
        conflict_cols = [on_column]
        if self._isolation == IsolationType.LOGICAL:
            conflict_cols.append(LOGICAL_NAMESPACE_COLUMN)
        self._ensure_conflict_index(conflict_cols)
        col_names = ", ".join(_quote_ident(column) for column in columns)
        placeholders = ", ".join(["%s"] * len(columns))
        skip_cols = set(conflict_cols)
        update_cols = [column for column in columns if column not in skip_cols]
        update_set = ", ".join(f"{_quote_ident(column)} = VALUES({_quote_ident(column)})" for column in update_cols)
        if update_set:
            sql = f"INSERT INTO {self._qualified_name} ({col_names}) VALUES ({placeholders}) ON DUPLICATE KEY UPDATE {update_set}"
        else:
            sql = f"INSERT IGNORE INTO {self._qualified_name} ({col_names}) VALUES ({placeholders})"
        rows = [self._row_values(row, columns) for _, row in df.iterrows()]
        with self._pool.connection(database=self._database_name) as conn:
            with conn.cursor() as cursor:
                cursor.executemany(sql, rows)
            conn.commit()

    def _row_values(self, row: pd.Series, columns: List[str]) -> tuple[Any, ...]:
        values = []
        for column in columns:
            value = row[column]
            if column == self._vector_column:
                values.append(_vector_literal(value))
            elif pd.isna(value):
                values.append(None)
            else:
                values.append(value)
        return tuple(values)

    def _ensure_conflict_index(self, conflict_cols: List[str]) -> None:
        key = tuple(conflict_cols)
        if key in self._ensured_conflict_indexes:
            return
        for column in conflict_cols:
            _validate_identifier(column)
        index_name = f"idx_{self._table_name}_{'_'.join(conflict_cols)}_uq"
        cols_sql = ", ".join(_quote_ident(column) for column in conflict_cols)
        with self._pool.connection(database=self._database_name) as conn:
            with conn.cursor() as cursor:
                try:
                    cursor.execute(
                        f"CREATE UNIQUE INDEX {_quote_ident(index_name)} ON {self._qualified_name} ({cols_sql})"
                    )
                except Exception as e:
                    if getattr(e, "args", None) == (1061, "Duplicate key name") or (
                        getattr(e, "args", None) and e.args[0] == 1061
                    ):
                        pass
                    else:
                        raise
            conn.commit()
        self._ensured_conflict_indexes.add(key)

    def _fetch_column_names(self) -> List[str]:
        with self._pool.connection(database=self._database_name) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s ORDER BY ORDINAL_POSITION",
                    (self._database_name, self._table_name),
                )
                rows = cursor.fetchall()
        return [row["COLUMN_NAME"] for row in rows]

    @property
    def _default_columns(self) -> List[str]:
        if self._isolation == IsolationType.LOGICAL:
            return [column for column in self._column_names if column != LOGICAL_NAMESPACE_COLUMN]
        return self._column_names

    def _select_columns(self) -> str:
        columns = self._default_columns
        return ", ".join(_quote_ident(column) for column in columns) if columns else "*"

    def _rows_to_arrow(self, rows: List[Dict[str, Any]], select_fields: Optional[List[str]] = None) -> pa.Table:
        columns = select_fields or self._default_columns
        if not rows:
            arrays = {
                column: pa.array(
                    [],
                    type=pa.list_(pa.float32(), list_size=self._vector_dim)
                    if column == self._vector_column
                    else pa.string(),
                )
                for column in columns
            }
            return pa.table(arrays)
        arrays = {}
        for column in columns:
            values = [row[column] for row in rows]
            if column == self._vector_column:
                arrays[column] = pa.array(
                    [_parse_vector(value, self._vector_dim) for value in values],
                    type=pa.list_(pa.float32(), list_size=self._vector_dim),
                )
            else:
                arrays[column] = pa.array(values)
        return pa.table(arrays)


class OceanBaseMySQLVectorDb(VectorDatabase):
    def __init__(
        self,
        pool: _ConnectionPool,
        configured_database: str,
        namespace: str,
        isolation: IsolationType,
    ) -> None:
        self._pool = pool
        self._configured_database = configured_database
        self._namespace = namespace
        self._isolation = isolation
        self._table_cache: Dict[tuple, OceanBaseMySQLVectorTable] = {}
        if isolation == IsolationType.LOGICAL:
            self._database_name = configured_database
            self._logical_namespace = namespace
        else:
            self._database_name = _validate_identifier(namespace) if namespace else configured_database
            self._logical_namespace = None
        self._ensure_database()

    @property
    def pool(self) -> _ConnectionPool:
        return self._pool

    @property
    def namespace(self) -> str:
        return self._namespace

    def _ensure_database(self) -> None:
        with self._pool.connection(database=None) as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS {_quote_ident(self._database_name)}")
            conn.commit()

    def table_exists(self, table_name: str) -> bool:
        _validate_identifier(table_name)
        with self._pool.connection(database=self._database_name) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*) AS cnt FROM information_schema.TABLES WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s",
                    (self._database_name, table_name),
                )
                row = cursor.fetchone()
        return bool(row and row["cnt"])

    def table_names(self, limit: int = 100) -> List[str]:
        with self._pool.connection(database=self._database_name) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA = %s ORDER BY TABLE_NAME LIMIT %s",
                    (self._database_name, int(limit)),
                )
                rows = cursor.fetchall()
        return [row["TABLE_NAME"] for row in rows]

    def create_table(
        self,
        table_name: str,
        schema: Optional[pa.Schema] = None,
        embedding_function: Optional[EmbeddingFunction] = None,
        vector_column: str = "",
        source_column: str = "",
        exist_ok: bool = True,
        unique_columns: Optional[List[str]] = None,
    ) -> OceanBaseMySQLVectorTable:
        _validate_identifier(table_name)
        vector_column = vector_column or "vector"
        source_column = source_column or "description"
        vector_dim = embedding_function.ndims() if embedding_function else 384
        unique_columns = unique_columns or []
        column_names: List[str] = []
        if schema is not None:
            if not isinstance(schema, pa.Schema):
                raise TypeError(f"Unsupported schema type: {type(schema)}")
            if self._isolation == IsolationType.LOGICAL and LOGICAL_NAMESPACE_COLUMN not in schema.names:
                schema = schema.append(pa.field(LOGICAL_NAMESPACE_COLUMN, pa.string()))
            indexed_columns = set(unique_columns)
            if self._isolation == IsolationType.LOGICAL:
                indexed_columns.add(LOGICAL_NAMESPACE_COLUMN)
            ddl = schema_to_create_table_sql(self._database_name, table_name, schema, indexed_columns=indexed_columns)
            column_names = list(schema.names)
            with self._pool.connection(database=self._database_name) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(ddl)
                    if self._isolation == IsolationType.LOGICAL:
                        try:
                            cursor.execute(
                                f"CREATE INDEX {_quote_ident(f'idx_{table_name}_{LOGICAL_NAMESPACE_COLUMN}')} "
                                f"ON {_quote_qualified(self._database_name, table_name)} ({_quote_ident(LOGICAL_NAMESPACE_COLUMN)})"
                            )
                        except Exception as e:
                            if not (getattr(e, "args", None) and e.args[0] == 1061):
                                raise
                    for column in unique_columns:
                        conflict_cols = [column]
                        if self._isolation == IsolationType.LOGICAL:
                            conflict_cols.append(LOGICAL_NAMESPACE_COLUMN)
                        cols_sql = ", ".join(_quote_ident(col) for col in conflict_cols)
                        index_name = f"idx_{table_name}_{'_'.join(conflict_cols)}_uq"
                        try:
                            cursor.execute(
                                f"CREATE UNIQUE INDEX {_quote_ident(index_name)} "
                                f"ON {_quote_qualified(self._database_name, table_name)} ({cols_sql})"
                            )
                        except Exception as e:
                            if not (getattr(e, "args", None) and e.args[0] == 1061):
                                raise
                conn.commit()
        elif not exist_ok:
            raise ValueError(f"Schema is required to create table '{table_name}'")
        elif not self.table_exists(table_name):
            raise ValueError(f"Table '{table_name}' does not exist and no schema was provided to create it.")
        table = self._make_table(table_name, embedding_function, vector_column, source_column, vector_dim, column_names)
        self._table_cache[(table_name, id(embedding_function), vector_dim, vector_column, source_column)] = table
        return table

    def open_table(
        self,
        table_name: str,
        embedding_function: Optional[EmbeddingFunction] = None,
        vector_column: str = "",
        source_column: str = "",
    ) -> OceanBaseMySQLVectorTable:
        vector_column = vector_column or "vector"
        source_column = source_column or "description"
        vector_dim = embedding_function.ndims() if embedding_function else 384
        cache_key = (table_name, id(embedding_function), vector_dim, vector_column, source_column)
        if cache_key in self._table_cache:
            return self._table_cache[cache_key]
        column_names = self._fetch_column_names(table_name)
        if not column_names:
            raise ValueError(
                f"Table '{table_name}' not found in database '{self._database_name}'. Use create_table() first."
            )
        table = self._make_table(table_name, embedding_function, vector_column, source_column, vector_dim, column_names)
        self._table_cache[cache_key] = table
        return table

    def drop_table(self, table_name: str, ignore_missing: bool = False) -> None:
        if self._isolation == IsolationType.LOGICAL:
            raise RuntimeError("drop_table() is not allowed in logical isolation mode because tables are shared.")
        _validate_identifier(table_name)
        clause = "IF EXISTS " if ignore_missing else ""
        with self._pool.connection(database=self._database_name) as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"DROP TABLE {clause}{_quote_qualified(self._database_name, table_name)}")
            conn.commit()
        self._invalidate_cache(table_name)

    def refresh_table(
        self,
        table_name: str,
        embedding_function: Optional[EmbeddingFunction] = None,
        vector_column: str = "",
        source_column: str = "",
    ) -> OceanBaseMySQLVectorTable:
        self._invalidate_cache(table_name)
        return self.open_table(table_name, embedding_function, vector_column, source_column)

    def _make_table(
        self,
        table_name: str,
        embedding_function: Optional[EmbeddingFunction],
        vector_column: str,
        source_column: str,
        vector_dim: int,
        column_names: List[str],
    ) -> OceanBaseMySQLVectorTable:
        return OceanBaseMySQLVectorTable(
            pool=self._pool,
            database_name=self._database_name,
            table_name=table_name,
            embedding_fn=embedding_function,
            vector_column=vector_column,
            source_column=source_column,
            vector_dim=vector_dim,
            column_names=column_names,
            isolation=self._isolation,
            logical_namespace=self._logical_namespace,
        )

    def _fetch_column_names(self, table_name: str) -> List[str]:
        _validate_identifier(table_name)
        with self._pool.connection(database=self._database_name) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s ORDER BY ORDINAL_POSITION",
                    (self._database_name, table_name),
                )
                rows = cursor.fetchall()
        return [row["COLUMN_NAME"] for row in rows]

    def _invalidate_cache(self, table_name: str) -> None:
        for key in [key for key in self._table_cache if key[0] == table_name]:
            del self._table_cache[key]


class OceanBaseMySQLVectorBackend(BaseVectorBackend):
    def __init__(self) -> None:
        self._config: Dict[str, Any] = {}
        self._pool: Optional[_ConnectionPool] = None
        self._isolation: IsolationType = IsolationType.PHYSICAL

    def initialize(self, config: Dict[str, Any]) -> None:
        required = ("host", "port", "user", "password", "database")
        missing = [key for key in required if key not in config]
        if missing:
            raise ValueError(f"Missing required OceanBase MySQL config keys: {', '.join(missing)}")
        self._config = config
        self._isolation = IsolationType(config.get("isolation", IsolationType.PHYSICAL.value))

    def _get_or_create_pool(self) -> _ConnectionPool:
        if self._pool is None:
            self._pool = _ConnectionPool(self._config)
        return self._pool

    def connect(self, namespace: str) -> OceanBaseMySQLVectorDb:
        return OceanBaseMySQLVectorDb(
            pool=self._get_or_create_pool(),
            configured_database=self._config["database"],
            namespace=namespace,
            isolation=self._isolation,
        )

    def close(self) -> None:
        if self._pool is not None:
            self._pool.close()
            self._pool = None
