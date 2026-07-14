# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import re
from typing import Any, Dict, List, Literal, Optional, Sequence, Set, Union, override
from urllib.parse import urlencode

import jaydebeapi
import pandas as pd
from dbutils.pooled_db import PooledDB

from datus_db_core import BaseSqlConnector, ConnectionConfig, MigrationTargetMixin, get_logger
from datus_db_core.models import ExecuteSQLResult
from datus_db_core.sql_utils import strip_sql_comments

from .config import OceanBaseOracleConfig

logger = get_logger(__name__)

_TENANT_RE = re.compile(r"@([^#]+)")


class _PingableJayDeBeApiConnection:
    """JayDeBeApi connection proxy with the health check DBUtils expects."""

    Error = jaydebeapi.Error
    DatabaseError = jaydebeapi.DatabaseError
    OperationalError = jaydebeapi.OperationalError
    InterfaceError = jaydebeapi.InterfaceError
    InternalError = jaydebeapi.InternalError

    def __init__(self, connection: Any, ping_timeout_seconds: int):
        self._connection = connection
        self._ping_timeout_seconds = ping_timeout_seconds

    def ping(self, _reconnect: bool = False) -> bool:
        try:
            if self._connection._closed:
                return False
            jdbc_connection = self._connection.jconn
            if jdbc_connection.isClosed():
                return False
            return bool(jdbc_connection.isValid(self._ping_timeout_seconds))
        except Exception:
            return False

    def __getattr__(self, name: str):
        return getattr(self._connection, name)


class _JayDeBeApiCreator:
    """DB-API shaped creator that adapts DBUtils kwargs to JayDeBeApi."""

    threadsafety = jaydebeapi.threadsafety
    apilevel = jaydebeapi.apilevel
    paramstyle = jaydebeapi.paramstyle
    Error = jaydebeapi.Error
    DatabaseError = jaydebeapi.DatabaseError
    OperationalError = jaydebeapi.OperationalError
    InterfaceError = jaydebeapi.InterfaceError
    InternalError = jaydebeapi.InternalError

    @staticmethod
    def connect(
        *,
        driver_class: str,
        jdbc_url: str,
        username: str,
        password: str,
        jar_path: str,
        ping_timeout_seconds: int,
    ):
        connection = jaydebeapi.connect(driver_class, jdbc_url, [username, password], jar_path, None)
        return _PingableJayDeBeApiConnection(connection, ping_timeout_seconds)


def _parse_base_username(username: str) -> str:
    return re.split(r"[@#]", username, maxsplit=1)[0]


def _parse_tenant(username: str) -> str:
    match = _TENANT_RE.search(username)
    return match.group(1) if match else ""


def _quote_identifier(name: str) -> str:
    escaped = name.replace('"', '""')
    return f'"{escaped}"'


def _sql_string(value: str) -> str:
    return value.replace("'", "''")


class OceanBaseOracleConnector(BaseSqlConnector, MigrationTargetMixin):
    """OceanBase Oracle mode database connector via JDBC."""

    def __init__(self, config: Union[OceanBaseOracleConfig, dict]):
        if isinstance(config, dict):
            config = OceanBaseOracleConfig(**config)
        elif not isinstance(config, OceanBaseOracleConfig):
            raise TypeError(f"config must be OceanBaseOracleConfig or dict, got {type(config)}")

        self._host = config.host
        self._port = config.port
        self._username = config.username
        self._password = config.password
        self._jar_path = config.jar_path
        self._driver_class = config.driver_class
        self._connect_timeout_seconds = config.connect_timeout_seconds
        self._query_timeout_seconds = config.query_timeout_seconds

        tenant = config.database or _parse_tenant(config.username)
        schema = config.schema_name or _parse_base_username(config.username).upper()

        # Build JDBC URL with recommended parameters
        jdbc_params: Dict[str, str] = {
            "useSSL": str(config.use_ssl).lower(),
            "useUnicode": "true",
            "characterEncoding": "utf-8",
        }
        if config.connect_timeout_seconds:
            jdbc_params["connectTimeout"] = str(int(config.connect_timeout_seconds) * 1000)
        if config.extra_jdbc_params:
            jdbc_params.update(config.extra_jdbc_params)
        query_string = urlencode(jdbc_params)
        self._jdbc_url = f"jdbc:oceanbase://{config.host}:{config.port}/{schema}?{query_string}"

        super().__init__(ConnectionConfig(timeout_seconds=config.timeout_seconds), dialect="oceanbase-oracle")
        self.config = config
        self._default_database = tenant or ""
        self._default_schema = schema

        self._pool = PooledDB(
            creator=_JayDeBeApiCreator,
            maxconnections=config.pool_maxconnections,
            mincached=config.pool_mincached,
            maxcached=config.pool_maxcached,
            blocking=config.pool_blocking,
            ping=1,
            driver_class=self._driver_class,
            jdbc_url=self._jdbc_url,
            username=self._username,
            password=self._password,
            jar_path=self._jar_path,
            ping_timeout_seconds=config.pool_ping_timeout_seconds,
        )

    def connect(self):
        if not self._pool:
            raise RuntimeError("Connection pool is not initialized")

    def close(self):
        if self._pool:
            try:
                self._pool.close()
            except Exception as e:
                logger.warning(f"Error closing pool: {e}")
            finally:
                self._pool = None

    def _get_raw_connection(self):
        conn = self._pool.connection()
        try:
            self._apply_context(conn)
            return conn
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
            raise

    def _apply_context(self, conn):
        schema_name = self.schema_name
        cursor = conn.cursor()
        try:
            # ob_query_timeout is in microseconds
            if self._query_timeout_seconds:
                cursor.execute(f"ALTER SESSION SET ob_query_timeout = {int(self._query_timeout_seconds) * 1_000_000}")
            if schema_name:
                cursor.execute(f"ALTER SESSION SET CURRENT_SCHEMA = {_quote_identifier(schema_name)}")
        finally:
            cursor.close()

    @override
    def do_switch_context(self, conn, catalog_name: str = "", database_name: str = "", schema_name: str = ""):
        if schema_name:
            cursor = conn.cursor()
            try:
                cursor.execute(f"ALTER SESSION SET CURRENT_SCHEMA = {_quote_identifier(schema_name.upper())}")
            finally:
                cursor.close()

    def test_connection(self) -> bool:
        try:
            conn = self._get_raw_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM DUAL")
                cursor.fetchall()
                cursor.close()
                return True
            finally:
                conn.close()
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    @override
    def _sys_databases(self) -> Set[str]:
        return set()

    @override
    def _sys_schemas(self) -> Set[str]:
        return {
            "SYS",
            "SYSTEM",
            "OUTLN",
            "LBACSYS",
            "CTXSYS",
            "MDSYS",
            "ORDDATA",
            "DBSNMP",
            "APPQOSSYS",
            "ORAAUDITOR",
            "XDB",
            "WMSYS",
            "OLAPSYS",
            "OJVMSYS",
            "GSMADMIN_INTERNAL",
            "ORDSYS",
            "DVSYS",
            "AUDSYS",
            "DBFS_MOCA",
            "ORDS_PUBLIC_USER",
            "ORDS_METADATA",
            "APEX_PUBLIC_USER",
            "APEX_REST_PUBLIC_USER",
            "REMOTE_SCHEDULER_AGENT",
        }

    @override
    def quote_identifier(self, name: str) -> str:
        return _quote_identifier(name)

    @override
    def full_name(
        self,
        catalog_name: str = "",
        database_name: str = "",
        schema_name: str = "",
        table_name: str = "",
    ) -> str:
        schema = schema_name or self.schema_name
        if schema:
            return f"{self.quote_identifier(schema)}.{self.quote_identifier(table_name)}"
        return self.quote_identifier(table_name)

    @override
    def identifier(
        self,
        catalog_name: str = "",
        database_name: str = "",
        schema_name: str = "",
        table_name: str = "",
    ) -> str:
        database_name = database_name or self.database_name
        schema_name = schema_name or self.schema_name
        if database_name and schema_name:
            return f"{database_name}.{schema_name}.{table_name}"
        if schema_name:
            return f"{schema_name}.{table_name}"
        return table_name

    def _execute_sql(self, sql: str, parameters: Optional[Sequence[Any]] = None) -> pd.DataFrame:
        conn = self._get_raw_connection()
        try:
            return self._read_dataframe(conn, sql, parameters)
        finally:
            conn.close()

    @staticmethod
    def _read_dataframe(
        conn: Any,
        sql: str,
        parameters: Optional[Sequence[Any]] = None,
    ) -> pd.DataFrame:
        cursor = conn.cursor()
        try:
            if parameters is None:
                cursor.execute(sql)
            else:
                cursor.execute(sql, tuple(parameters))
            columns = [column[0] for column in (cursor.description or [])]
            return pd.DataFrame.from_records(cursor.fetchall(), columns=columns)
        finally:
            cursor.close()

    def query_dataframe(self, sql: str, parameters: Optional[Sequence[Any]] = None) -> pd.DataFrame:
        """Execute a parameterized read query for integrations that need a DataFrame."""
        return self._execute_sql(sql, parameters)

    def execute_statement(self, sql: str, parameters: Optional[Sequence[Any]] = None) -> None:
        """Execute and commit a parameterized non-query statement."""
        conn = self._get_raw_connection()
        try:
            cursor = conn.cursor()
            try:
                if parameters is None:
                    cursor.execute(sql)
                else:
                    cursor.execute(sql, tuple(parameters))
                conn.commit()
            finally:
                cursor.close()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            conn.close()

    def _execute_dml(self, sql: str) -> int:
        conn = self._get_raw_connection()
        try:
            cursor = conn.cursor()
            try:
                cursor.execute(sql)
                conn.commit()
                rowcount = cursor.rowcount
                return rowcount if rowcount is not None else -1
            finally:
                cursor.close()
        finally:
            conn.close()

    @override
    def execute_query(
        self,
        sql: str,
        result_format: Literal["csv", "arrow", "pandas", "list"] = "csv",
        catalog_name: str = "",
        database_name: str = "",
        schema_name: str = "",
    ) -> ExecuteSQLResult:
        try:
            df = self._execute_sql(sql)
            row_count = len(df)
            if result_format == "csv":
                result_data = df.to_csv(index=False)
            elif result_format == "arrow":
                import pyarrow as pa

                result_data = pa.Table.from_pandas(df)
            elif result_format == "pandas":
                result_data = df
            elif result_format == "list":
                result_data = df.to_dict(orient="records")
            else:
                result_data = df.to_csv(index=False)
            return ExecuteSQLResult(
                success=True,
                sql_query=sql,
                sql_return=result_data,
                row_count=row_count,
                result_format=result_format,
            )
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            return ExecuteSQLResult(success=False, sql_query=sql, error=str(e), row_count=0)

    @override
    def execute_insert(
        self, sql: str, catalog_name: str = "", database_name: str = "", schema_name: str = ""
    ) -> ExecuteSQLResult:
        return self._execute_rowcount_sql(sql, "Insert")

    @override
    def execute_update(
        self, sql: str, catalog_name: str = "", database_name: str = "", schema_name: str = ""
    ) -> ExecuteSQLResult:
        return self._execute_rowcount_sql(sql, "Update")

    @override
    def execute_delete(
        self, sql: str, catalog_name: str = "", database_name: str = "", schema_name: str = ""
    ) -> ExecuteSQLResult:
        return self._execute_rowcount_sql(sql, "Delete")

    def _execute_rowcount_sql(self, sql: str, action: str) -> ExecuteSQLResult:
        try:
            rowcount = self._execute_dml(sql)
            return ExecuteSQLResult(success=True, sql_query=sql, sql_return=str(rowcount), row_count=rowcount)
        except Exception as e:
            logger.error(f"{action} execution failed: {e}")
            return ExecuteSQLResult(success=False, sql_query=sql, error=str(e), row_count=0)

    @override
    def execute_ddl(
        self, sql: str, catalog_name: str = "", database_name: str = "", schema_name: str = ""
    ) -> ExecuteSQLResult:
        try:
            conn = self._get_raw_connection()
            try:
                cursor = conn.cursor()
                try:
                    cursor.execute(sql)
                    conn.commit()
                finally:
                    cursor.close()
            finally:
                conn.close()
            return ExecuteSQLResult(success=True, sql_query=sql, sql_return="Successful", row_count=0)
        except Exception as e:
            logger.error(f"DDL execution failed: {e}")
            return ExecuteSQLResult(success=False, sql_query=sql, error=str(e), row_count=0)

    @override
    def execute_pandas(self, sql: str) -> ExecuteSQLResult:
        return self.execute_query(sql, result_format="pandas")

    @override
    def execute_csv(self, sql: str) -> ExecuteSQLResult:
        return self.execute_query(sql, result_format="csv")

    @override
    def execute_content_set(self, sql_query: str) -> ExecuteSQLResult:
        try:
            conn = self._get_raw_connection()
            try:
                cursor = conn.cursor()
                try:
                    cursor.execute(sql_query)
                    conn.commit()
                finally:
                    cursor.close()
            finally:
                conn.close()
            self._parse_session_context(sql_query)
            return ExecuteSQLResult(success=True, sql_query=sql_query, sql_return="Successful", row_count=0)
        except Exception as e:
            logger.error(f"Content set execution failed: {e}")
            return ExecuteSQLResult(success=False, error=str(e), sql_query=sql_query, row_count=0)

    def _parse_session_context(self, sql: str):
        match = re.search(r'ALTER\s+SESSION\s+SET\s+CURRENT_SCHEMA\s*=\s*"?([\w$#]+)"?', sql, re.IGNORECASE)
        if match:
            self.schema_name = match.group(1).strip().upper()

    @override
    def execute_queries(
        self, queries: List[str], catalog_name: str = "", database_name: str = "", schema_name: str = ""
    ) -> List[Any]:
        results = []
        conn = self._get_raw_connection()
        try:
            for query in queries:
                query_stripped = query.strip()
                clean = strip_sql_comments(query_stripped).strip().upper()
                if clean.startswith(("SELECT", "WITH")):
                    df = self._read_dataframe(conn, query_stripped)
                    results.append(df.to_dict(orient="records"))
                else:
                    cursor = conn.cursor()
                    try:
                        cursor.execute(query_stripped)
                        results.append(cursor.rowcount if clean.startswith(("INSERT", "UPDATE", "DELETE")) else None)
                    finally:
                        cursor.close()
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            conn.close()
        return results

    @override
    def get_databases(self, catalog_name: str = "", include_sys: bool = False) -> List[str]:
        return [self.database_name] if self.database_name else []

    @override
    def get_schemas(self, catalog_name: str = "", database_name: str = "", include_sys: bool = False) -> List[str]:
        df = self._execute_sql("SELECT USERNAME FROM ALL_USERS ORDER BY USERNAME")
        schemas = df["USERNAME"].tolist() if "USERNAME" in df.columns else []
        if not include_sys:
            schemas = [schema for schema in schemas if schema.upper() not in self._sys_schemas()]
        return schemas

    @override
    def get_tables(self, catalog_name: str = "", database_name: str = "", schema_name: str = "") -> List[str]:
        schema = (schema_name or self.schema_name).upper()
        if not schema:
            return []
        sql = f"""
            SELECT TABLE_NAME
            FROM ALL_TABLES
            WHERE OWNER = '{_sql_string(schema)}'
              AND DROPPED = 'NO'
            ORDER BY TABLE_NAME
        """
        df = self._execute_sql(sql)
        return df["TABLE_NAME"].tolist() if "TABLE_NAME" in df.columns else []

    @override
    def get_views(self, catalog_name: str = "", database_name: str = "", schema_name: str = "") -> List[str]:
        schema = (schema_name or self.schema_name).upper()
        if not schema:
            return []
        sql = f"""
            SELECT VIEW_NAME
            FROM ALL_VIEWS
            WHERE OWNER = '{_sql_string(schema)}'
            ORDER BY VIEW_NAME
        """
        df = self._execute_sql(sql)
        return df["VIEW_NAME"].tolist() if "VIEW_NAME" in df.columns else []

    @override
    def get_materialized_views(
        self, catalog_name: str = "", database_name: str = "", schema_name: str = ""
    ) -> List[str]:
        schema = (schema_name or self.schema_name).upper()
        if not schema:
            return []
        sql = f"""
            SELECT MVIEW_NAME
            FROM ALL_MVIEWS
            WHERE OWNER = '{_sql_string(schema)}'
            ORDER BY MVIEW_NAME
        """
        df = self._execute_sql(sql)
        return df["MVIEW_NAME"].tolist() if "MVIEW_NAME" in df.columns else []

    @override
    def get_schema(
        self,
        catalog_name: str = "",
        database_name: str = "",
        schema_name: str = "",
        table_name: str = "",
    ) -> List[Dict[str, Any]]:
        if not table_name:
            return []
        owner_name = (schema_name or self.schema_name).upper()
        table_name = table_name.upper()
        owner = _sql_string(owner_name)
        table = _sql_string(table_name)
        sql = f"""
            SELECT
                c.COLUMN_ID,
                c.COLUMN_NAME,
                c.DATA_TYPE,
                c.DATA_LENGTH,
                c.DATA_PRECISION,
                c.DATA_SCALE,
                c.NULLABLE,
                c.DATA_DEFAULT,
                CASE WHEN pk.COLUMN_NAME IS NOT NULL THEN 1 ELSE 0 END AS IS_PK,
                cc.COMMENTS
            FROM ALL_TAB_COLUMNS c
            LEFT JOIN (
                SELECT cols.OWNER, cols.TABLE_NAME, cols.COLUMN_NAME
                FROM ALL_CONSTRAINTS cons
                JOIN ALL_CONS_COLUMNS cols
                  ON cons.OWNER = cols.OWNER
                 AND cons.CONSTRAINT_NAME = cols.CONSTRAINT_NAME
                 AND cons.TABLE_NAME = cols.TABLE_NAME
                WHERE cons.CONSTRAINT_TYPE = 'P'
                  AND cons.OWNER = '{owner}'
                  AND cons.TABLE_NAME = '{table}'
            ) pk
              ON pk.OWNER = c.OWNER
             AND pk.TABLE_NAME = c.TABLE_NAME
             AND pk.COLUMN_NAME = c.COLUMN_NAME
            LEFT JOIN ALL_COL_COMMENTS cc
              ON cc.OWNER = c.OWNER
             AND cc.TABLE_NAME = c.TABLE_NAME
             AND cc.COLUMN_NAME = c.COLUMN_NAME
            WHERE c.OWNER = '{owner}'
              AND c.TABLE_NAME = '{table}'
            ORDER BY c.COLUMN_ID
        """
        df = self._execute_sql(sql)
        if df.empty:
            return self._get_view_schema(owner_name, table_name)

        result = []
        for i in range(len(df)):
            row = df.iloc[i]
            comments = row.get("COMMENTS")
            result.append(
                {
                    "cid": int(row["COLUMN_ID"]) if row["COLUMN_ID"] else i,
                    "name": row["COLUMN_NAME"],
                    "type": self._format_column_type(row),
                    "nullable": row["NULLABLE"] == "Y",
                    "default_value": row.get("DATA_DEFAULT"),
                    "pk": bool(row.get("IS_PK")),
                    "comment": comments if comments and str(comments) != "nan" else None,
                }
            )
        return result

    def _get_view_schema(self, owner_name: str, view_name: str) -> List[Dict[str, Any]]:
        owner = _sql_string(owner_name)
        view = _sql_string(view_name)
        view_df = self._execute_sql(
            f"""
                SELECT VIEW_NAME
                FROM ALL_VIEWS
                WHERE OWNER = '{owner}'
                  AND VIEW_NAME = '{view}'
            """
        )
        if view_df.empty or "VIEW_NAME" not in view_df.columns:
            return []

        conn = self._get_raw_connection()
        try:
            cursor = conn.cursor()
            try:
                full_name = f"{_quote_identifier(owner_name)}.{_quote_identifier(view_name)}"
                cursor.execute(f"SELECT * FROM {full_name} WHERE 1 = 0")
                return [
                    self._column_from_description(description, index)
                    for index, description in enumerate(cursor.description or [], start=1)
                ]
            finally:
                cursor.close()
        finally:
            conn.close()

    @staticmethod
    def _column_from_description(description: Any, index: int) -> Dict[str, Any]:
        type_code = description[1] if len(description) > 1 else None
        internal_size = description[3] if len(description) > 3 else None
        precision = description[4] if len(description) > 4 else None
        scale = description[5] if len(description) > 5 else None
        null_ok = description[6] if len(description) > 6 else None
        return {
            "cid": index,
            "name": description[0],
            "type": OceanBaseOracleConnector._format_description_type(
                type_code,
                internal_size=internal_size,
                precision=precision,
                scale=scale,
            ),
            "nullable": null_ok != 0,
            "default_value": None,
            "pk": False,
            "comment": None,
        }

    @staticmethod
    def _format_description_type(
        type_code: Any,
        *,
        internal_size: Any = None,
        precision: Any = None,
        scale: Any = None,
    ) -> str:
        if type_code in (jaydebeapi.DECIMAL, jaydebeapi.NUMBER):
            if precision:
                return f"NUMBER({int(precision)},{int(scale or 0)})"
            return "NUMBER"
        if type_code is jaydebeapi.STRING:
            return f"VARCHAR2({int(internal_size)})" if internal_size else "VARCHAR2"
        if type_code is jaydebeapi.TEXT:
            return "CLOB"
        if type_code is jaydebeapi.BINARY:
            return f"RAW({int(internal_size)})" if internal_size else "RAW"
        if type_code is jaydebeapi.FLOAT:
            return "FLOAT"
        if type_code is jaydebeapi.DATE:
            return "DATE"
        if type_code is jaydebeapi.TIME:
            return "TIME"
        if type_code is jaydebeapi.DATETIME:
            return "TIMESTAMP"
        if type_code is jaydebeapi.ROWID:
            return "ROWID"
        if isinstance(type_code, str) and type_code:
            return type_code.upper()
        return "UNKNOWN"

    def _format_column_type(self, row: Any) -> str:
        data_type = str(row["DATA_TYPE"]).upper() if row.get("DATA_TYPE") else "UNKNOWN"
        precision = row.get("DATA_PRECISION")
        scale = row.get("DATA_SCALE")
        length = row.get("DATA_LENGTH")
        if data_type == "NUMBER" and precision is not None and str(precision) != "nan":
            return f"NUMBER({int(precision)},{int(scale or 0)})"
        if data_type in ("VARCHAR2", "CHAR", "NVARCHAR2", "NCHAR", "RAW") and length:
            return f"{data_type}({int(length)})"
        return data_type

    def _get_ddl(self, schema_name: str, table_name: str, object_type: str = "TABLE") -> str:
        safe_schema = _sql_string(schema_name.upper())
        safe_table = _sql_string(table_name.upper())
        full_name = self.full_name(schema_name=schema_name, table_name=table_name)
        try:
            sql = f"SELECT DBMS_METADATA.GET_DDL('{object_type}', '{safe_table}', '{safe_schema}') AS DDL FROM DUAL"
            df = self._execute_sql(sql)
            if not df.empty:
                ddl = str(df.iloc[0, 0])
                if ddl and ddl != "None":
                    return ddl
        except Exception as e:
            logger.debug(f"DBMS_METADATA.GET_DDL failed, reconstructing: {e}")
        columns = self.get_schema(schema_name=schema_name, table_name=table_name)
        if not columns:
            return f"-- DDL not available for {full_name}"
        if object_type == "VIEW":
            return f"CREATE VIEW {full_name} AS\n-- View definition not available"

        col_defs = []
        comment_stmts = []
        for col in columns:
            col_def = f"    {self.quote_identifier(col['name'])} {col['type']}"
            if not col.get("nullable", True):
                col_def += " NOT NULL"
            col_defs.append(col_def)
            if col.get("comment"):
                comment_stmts.append(
                    f"COMMENT ON COLUMN {full_name}.{self.quote_identifier(col['name'])} "
                    f"IS '{_sql_string(col['comment'])}'"
                )

        pk_cols = [col["name"] for col in columns if col.get("pk")]
        if pk_cols:
            pk_names = ", ".join(self.quote_identifier(c) for c in pk_cols)
            col_defs.append(f"    PRIMARY KEY ({pk_names})")

        ddl = f"CREATE TABLE {full_name} (\n" + ",\n".join(col_defs) + "\n);"
        if comment_stmts:
            ddl += "\n\n" + "\n".join(comment_stmts) + ";"
        return ddl

    @override
    def get_tables_with_ddl(
        self,
        catalog_name: str = "",
        database_name: str = "",
        schema_name: str = "",
        tables: Optional[List[str]] = None,
    ) -> List[Dict[str, str]]:
        schema = schema_name or self.schema_name
        result = []
        for table_name in tables or self.get_tables(schema_name=schema):
            result.append(
                {
                    "identifier": self.identifier(schema_name=schema, table_name=table_name),
                    "catalog_name": "",
                    "database_name": self.database_name,
                    "schema_name": schema,
                    "table_name": table_name,
                    "table_type": "table",
                    "definition": self._get_ddl(schema, table_name, "TABLE"),
                }
            )
        return result

    @override
    def get_views_with_ddl(
        self, catalog_name: str = "", database_name: str = "", schema_name: str = ""
    ) -> List[Dict[str, str]]:
        schema = schema_name or self.schema_name
        result = []
        for view_name in self.get_views(schema_name=schema):
            result.append(
                {
                    "identifier": self.identifier(schema_name=schema, table_name=view_name),
                    "catalog_name": "",
                    "database_name": self.database_name,
                    "schema_name": schema,
                    "table_name": view_name,
                    "table_type": "view",
                    "definition": self._get_ddl(schema, view_name, "VIEW"),
                }
            )
        return result

    @override
    def get_sample_rows(
        self,
        tables: Optional[List[str]] = None,
        top_n: int = 5,
        catalog_name: str = "",
        database_name: str = "",
        schema_name: str = "",
        table_type: str = "table",
    ) -> List[Dict[str, Any]]:
        schema = schema_name or self.schema_name
        result = []
        for table_name in tables or self.get_tables(schema_name=schema):
            full_name = self.full_name(schema_name=schema, table_name=table_name)
            try:
                df = self._execute_sql(f"SELECT * FROM {full_name} WHERE ROWNUM <= {int(top_n)}")
                if not df.empty:
                    result.append(
                        {
                            "identifier": self.identifier(schema_name=schema, table_name=table_name),
                            "catalog_name": "",
                            "database_name": self.database_name,
                            "schema_name": schema,
                            "table_name": table_name,
                            "sample_rows": df.to_csv(index=False),
                        }
                    )
            except Exception as e:
                logger.warning(f"Could not sample {full_name}: {e}")
        return result

    def describe_migration_capabilities(self) -> Dict[str, Any]:
        return {
            "supported": True,
            "dialect_family": "oracle-like",
            "requires": [],
            "forbids": [
                "DUPLICATE KEY (StarRocks-only)",
                "DISTRIBUTED BY HASH ... BUCKETS (StarRocks-only)",
                "ENGINE = (MySQL/ClickHouse syntax)",
            ],
            "type_hints": {
                "HUGEINT": "NUMBER(38,0)",
                "LARGEINT": "NUMBER(38,0)",
                "BOOLEAN": "NUMBER(1)",
                "unbounded VARCHAR": "VARCHAR2(4000) or CLOB for larger text",
                "DATETIME": "TIMESTAMP",
                "TEXT": "CLOB",
                "SERIAL": "NUMBER GENERATED BY DEFAULT AS IDENTITY",
                "AUTO_INCREMENT": "NUMBER GENERATED BY DEFAULT AS IDENTITY",
            },
            "example_ddl": (
                'CREATE TABLE "SCHEMA"."T" (\n'
                '  "ID" NUMBER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,\n'
                '  "NAME" VARCHAR2(255),\n'
                '  "CREATED_AT" TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n'
                ")"
            ),
        }

    def suggest_table_layout(self, columns: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {}

    def validate_ddl(self, ddl: str) -> List[str]:
        errors: List[str] = []
        upper = ddl.upper()
        if "DUPLICATE KEY" in upper:
            errors.append("DUPLICATE KEY is StarRocks-only syntax; Oracle does not support it")
        if "BUCKETS" in upper and "DISTRIBUTED BY" in upper:
            errors.append("DISTRIBUTED BY ... BUCKETS is StarRocks syntax; Oracle does not support it")
        if "ENGINE =" in upper or "ENGINE=" in upper:
            errors.append("ENGINE clause is MySQL/ClickHouse syntax; not supported in Oracle")
        if "AUTO_INCREMENT" in upper:
            errors.append("AUTO_INCREMENT is MySQL syntax; use NUMBER GENERATED BY DEFAULT AS IDENTITY in Oracle")
        return errors

    def map_source_type(self, source_dialect: str, source_type: str) -> Optional[str]:
        base = re.sub(r"\(.*\)", "", source_type.strip().upper()).strip()
        overrides = {
            "HUGEINT": "NUMBER(38,0)",
            "LARGEINT": "NUMBER(38,0)",
            "BIGINT": "NUMBER(19)",
            "INT": "NUMBER(10)",
            "SMALLINT": "NUMBER(5)",
            "TINYINT": "NUMBER(3)",
            "BOOLEAN": "NUMBER(1)",
            "DATETIME": "TIMESTAMP",
            "TEXT": "CLOB",
            "LONGTEXT": "CLOB",
            "MEDIUMTEXT": "CLOB",
            "LONGBLOB": "BLOB",
            "FLOAT": "BINARY_FLOAT",
            "DOUBLE": "BINARY_DOUBLE",
            "SERIAL": "NUMBER GENERATED BY DEFAULT AS IDENTITY",
            "BIGSERIAL": "NUMBER GENERATED BY DEFAULT AS IDENTITY",
            "AUTO_INCREMENT": "NUMBER GENERATED BY DEFAULT AS IDENTITY",
            "JSON": "CLOB",
            "JSONB": "CLOB",
            "ENUM": "VARCHAR2(255)",
        }
        return overrides.get(base)
