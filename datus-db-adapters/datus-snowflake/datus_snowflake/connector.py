# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

from typing import Any, Dict, List, Literal, Optional, Sequence, Set, Union, override

import pyarrow as pa
import pyarrow.compute as pc
from datus.schemas.base import TABLE_TYPE
from datus.schemas.node_models import ExecuteSQLResult
from datus.tools.db_tools.base import BaseSqlConnector, _to_sql_literal, list_to_in_str
from datus.tools.db_tools.config import ConnectionConfig
from datus.tools.db_tools.mixins import MaterializedViewSupportMixin, SchemaNamespaceMixin
from datus.utils.constants import DBType
from datus.utils.exceptions import DatusException, ErrorCode
from datus.utils.loggings import get_logger
from datus.utils.sql_utils import parse_context_switch
from pandas import DataFrame
from snowflake.connector import Connect, SnowflakeConnection
from snowflake.connector.errors import (
    DatabaseError,
    DataError,
    ForbiddenError,
    IntegrityError,
    InterfaceError,
    InternalError,
    NotSupportedError,
    OperationalError,
    ProgrammingError,
    RequestTimeoutError,
    ServiceUnavailableError,
)

from .config import SnowflakeConfig

logger = get_logger(__name__)


def _handle_snowflake_exception(e: Exception, sql: str = "") -> DatusException:
    """Handle Snowflake exceptions and map to appropriate Datus ErrorCode."""

    if isinstance(e, ProgrammingError):
        return DatusException(
            ErrorCode.DB_EXECUTION_SYNTAX_ERROR, message_args={"sql": sql, "error_message": e.raw_msg}
        )

    elif isinstance(e, (OperationalError, DatabaseError)):
        return DatusException(ErrorCode.DB_EXECUTION_ERROR, message_args={"sql": sql, "error_message": e.raw_msg})

    elif isinstance(e, IntegrityError):
        return DatusException(ErrorCode.DB_CONSTRAINT_VIOLATION, message_args={"sql": sql, "error_message": e.raw_msg})

    elif isinstance(e, (RequestTimeoutError, ServiceUnavailableError)):
        return DatusException(ErrorCode.DB_EXECUTION_TIMEOUT, message_args={"sql": sql, "error_message": e.raw_msg})

    elif isinstance(e, (InterfaceError, InternalError)):
        return DatusException(ErrorCode.DB_CONNECTION_FAILED, message_args={"error_message": e.raw_msg})

    elif isinstance(e, ForbiddenError):
        return DatusException(
            ErrorCode.DB_PERMISSION_DENIED, message_args={"operation": "query execution", "error_message": e.raw_msg}
        )

    elif isinstance(e, (DataError, NotSupportedError)):
        return DatusException(ErrorCode.DB_EXECUTION_ERROR, message_args={"sql": sql, "error_message": e.raw_msg})

    else:
        return DatusException(ErrorCode.DB_FAILED, message_args={"error_message": str(e)})


class SnowflakeConnector(BaseSqlConnector, SchemaNamespaceMixin, MaterializedViewSupportMixin):
    """
    Connector for Snowflake databases using native Snowflake SDK.

    This connector provides full support for Snowflake features including:
    - Multi-database and schema support
    - Tables, views, and materialized views
    - Efficient metadata retrieval using SHOW commands
    - Arrow-based query execution for performance

    Implements SchemaNamespaceMixin and MaterializedViewSupportMixin.
    """

    def __init__(self, config: Union[SnowflakeConfig, dict]):
        """
        Initialize Snowflake connector.

        Args:
            config: SnowflakeConfig object or dict with configuration
        """
        # Handle config object or dict
        if isinstance(config, dict):
            config = SnowflakeConfig(**config)
        elif not isinstance(config, SnowflakeConfig):
            raise TypeError(f"config must be SnowflakeConfig or dict, got {type(config)}")

        self.snowflake_config = config

        conn_config = ConnectionConfig(timeout_seconds=config.timeout_seconds)
        super().__init__(config=conn_config, dialect=DBType.SNOWFLAKE)
        self.connection: SnowflakeConnection = Connect(
            account=config.account,
            user=config.username,
            password=config.password,
            warehouse=config.warehouse,
            database=config.database if config.database else None,
            schema=config.schema_name if config.schema_name else None,
            login_timeout=config.timeout_seconds,
            network_timeout=config.timeout_seconds,
            socket_timeout=config.timeout_seconds,
        )
        self.database_name = config.database or ""
        self.schema_name = config.schema_name or ""

    def test_connection(self) -> Dict[str, Any]:
        """Test the database connection."""
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchall()
            return {
                "success": True,
                "message": "Connection successful",
                "databases": "",
            }

    def close(self):
        """Close the database connection."""
        self.connection.close()

    def get_type(self) -> str:
        """Return the database type."""
        return DBType.SNOWFLAKE

    def _sys_databases(self) -> Set[str]:
        """Return set of system databases to filter out."""
        return {"SNOWFLAKE", "SNOWFLAKE_SAMPLE_DATA"}

    def _sys_schemas(self) -> Set[str]:
        """Return set of system schemas to filter out."""
        return {"INFORMATION_SCHEMA"}

    def do_switch_context(self, catalog_name: str = "", database_name: str = "", schema_name: str = ""):
        """Switch database or schema context."""
        try:
            with self.connection.cursor() as cursor:
                if not schema_name:
                    if not database_name:
                        return
                    sql = f'USE DATABASE "{database_name}"'
                else:
                    sql = (
                        f'USE SCHEMA "{schema_name}"' if not database_name else f'USE "{database_name}"."{schema_name}"'
                    )
                cursor.execute(sql)
        except Exception as e:
            raise _handle_snowflake_exception(e, sql) from e

    def validate_input(self, input_params: Dict[str, Any]):
        """Validate input parameters."""
        super().validate_input(input_params)
        if "params" in input_params:
            if not isinstance(input_params["params"], Sequence) and not isinstance(input_params["params"], dict):
                raise ValueError("params must be dict or Sequence")

    def _do_execute_arrow(
        self, sql_query: str, params: Optional[Sequence[Any] | dict[Any, Any]] = None
    ) -> tuple[pa.Table, int]:
        """Execute SQL query and return results in Apache Arrow format."""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("ALTER SESSION SET PYTHON_CONNECTOR_QUERY_RESULT_FORMAT='ARROW'")
                cursor.execute(sql_query, params)
                return cursor.fetch_arrow_all(force_return_table=True), cursor.rowcount
        except Exception as e:
            raise _handle_snowflake_exception(e, sql_query)

    def execute_query_to_df(
        self,
        sql: str,
        params: Sequence[Any] | dict[Any, Any] | None = None,
    ) -> DataFrame:
        """Execute query and return pandas DataFrame."""
        with self.connection.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetch_pandas_all()

    def execute_query_to_dict(self, sql: str) -> List[Dict[str, Any]]:
        """Execute query and return list of dictionaries."""
        with self.connection.cursor() as cursor:
            cursor.execute(sql)
            query_result = cursor.fetchall()
            if not query_result or isinstance(query_result[0], dict):
                return query_result
            result = []
            for item in query_result:
                item_dict = {}
                for i, col in enumerate(cursor.description):
                    item_dict[col.name] = item[i]
                result.append(item_dict)
        return result

    @override
    def execute_ddl(self, sql: str) -> ExecuteSQLResult:
        """Execute DDL statement."""
        return self._execute_update_or_delete(sql)

    @override
    def execute_insert(self, sql: str) -> ExecuteSQLResult:
        """Execute INSERT statement."""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(sql)
                rowcount = cursor.rowcount
                last_rowid = cursor.sfqid

                return ExecuteSQLResult(
                    sql_query=sql,
                    row_count=rowcount,
                    sql_return=str(last_rowid),
                    success=True,
                    error=None,
                )
        except Exception as e:
            ex = _handle_snowflake_exception(e, sql)
            return ExecuteSQLResult(
                success=False,
                sql_query=sql,
                error=str(ex),
            )

    @override
    def execute_update(self, sql: str) -> ExecuteSQLResult:
        """Execute UPDATE statement."""
        return self._execute_update_or_delete(sql)

    @override
    def execute_delete(self, sql: str) -> ExecuteSQLResult:
        """Execute DELETE statement."""
        return self._execute_update_or_delete(sql)

    def _execute_update_or_delete(self, sql: str) -> ExecuteSQLResult:
        """Execute UPDATE or DELETE statement."""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(sql)
                rowcount = cursor.rowcount

                return ExecuteSQLResult(
                    sql_query=sql,
                    row_count=rowcount,
                    sql_return=str(rowcount),
                    success=True,
                    error=None,
                )
        except Exception as e:
            ex = _handle_snowflake_exception(e, sql)
            return ExecuteSQLResult(
                success=False,
                sql_query=sql,
                error=str(ex),
            )

    @override
    def execute_content_set(self, sql_query: str) -> ExecuteSQLResult:
        """Execute context switch statement (USE DATABASE/SCHEMA)."""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(sql_query)
            switch_context = parse_context_switch(sql=sql_query, dialect=self.dialect)
            if switch_context:
                if catalog_name := switch_context.get("catalog_name"):
                    self.catalog_name = catalog_name
                if database_name := switch_context.get("database_name"):
                    self.database_name = database_name
                if schema_name := switch_context.get("schema_name"):
                    self.schema_name = schema_name
            return ExecuteSQLResult(
                success=True,
                sql_query=sql_query,
                sql_return="Successful",
                row_count=0,
            )
        except Exception as e:
            ex = _handle_snowflake_exception(e, sql_query)
            return ExecuteSQLResult(success=False, sql_query=sql_query, error=str(ex))

    @override
    def execute_query(
        self, sql: str, result_format: Literal["csv", "arrow", "pandas", "list"] = "csv"
    ) -> ExecuteSQLResult:
        """Execute query and return results in specified format."""
        if sql.lower().startswith("show"):
            return self._execute_show(sql, result_format)

        if result_format == "csv":
            return self.execute_csv(sql)
        elif result_format == "pandas":
            return self.execute_pandas(sql)
        else:
            result = self.execute_arrow(sql)
            if result_format == "arrow":
                return result
            if result and result.success:
                result.sql_return = result.sql_return.to_pylist()
                result.result_format = result_format
            return result

    def _execute_show(
        self, sql: str, result_format: Literal["csv", "arrow", "pandas", "list"] = "csv"
    ) -> ExecuteSQLResult:
        """Execute SHOW command with special handling."""
        sql = sql.strip()
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(sql)
                result = cursor.fetchall()
                col_names = [col[0] for col in cursor.description][:7]
                row_count = len(result)

                if result:
                    columns = list(zip(*[row[:7] for row in result]))
                    arrow_result = pa.Table.from_arrays([pa.array(col) for col in columns], names=col_names)
                else:
                    arrow_result = pa.Table.from_arrays([])

                if result_format == "arrow":
                    final_result = arrow_result
                elif result_format == "list":
                    final_result = arrow_result.to_pylist()
                else:
                    df = arrow_result.to_pandas()
                    final_result = df if result_format == "pandas" else df.to_csv(index=False)

                return ExecuteSQLResult(
                    success=True,
                    result_format=result_format,
                    sql_return=final_result,
                    row_count=row_count,
                )
        except Exception as e:
            ex = _handle_snowflake_exception(e, sql)
            return ExecuteSQLResult(success=False, sql_query=sql, result_format=result_format, error=str(ex))

    def execute_arrow(self, sql: str) -> ExecuteSQLResult:
        """Execute query and return Arrow table."""
        try:
            arrow_table, row_count = self._do_execute_arrow(sql)
            if arrow_table is None:
                logger.debug(f"Arrow table is None for query. Row count: {row_count}")
                row_count = 0
                arrow_table = None
            else:
                row_count = arrow_table.num_rows

            return ExecuteSQLResult(
                sql_query=sql,
                row_count=row_count,
                sql_return=arrow_table,
                success=True,
                error=None,
                result_format="arrow",
            )
        except DatusException as e:
            return ExecuteSQLResult(success=False, sql_query=sql, error=str(e))

    def execute_pandas(self, sql: str) -> ExecuteSQLResult:
        """Execute query and return pandas DataFrame."""
        try:
            df = self.execute_query_to_df(sql)
            return ExecuteSQLResult(
                sql_query=sql,
                row_count=len(df),
                sql_return=df,
                success=True,
                error=None,
                result_format="pandas",
            )
        except Exception as e:
            ex = _handle_snowflake_exception(e, sql)
            return ExecuteSQLResult(success=False, sql_query=sql, result_format="pandas", error=str(ex))

    def execute_csv(self, query: str) -> ExecuteSQLResult:
        """Execute query and return CSV string."""
        result = self.execute_pandas(query)
        result.result_format = "csv"
        if result.success and result.row_count > 0:
            result.sql_return = result.sql_return.to_csv(index=False)
        return result

    def execute_queries(self, queries: List[str]) -> List[ExecuteSQLResult]:
        """Execute multiple queries."""
        return [self.execute_query(sql) for sql in queries]

    def execute_queries_arrow(self, queries: List[str]) -> List[ExecuteSQLResult]:
        """Execute multiple queries and return Arrow results."""
        return [self.execute_arrow(sql) for sql in queries]

    @override
    def get_databases(self, catalog_name: str = "", include_sys: bool = False) -> List[str]:
        """Get list of databases."""
        res = self._execute_show(sql="SHOW DATABASES", result_format="arrow").sql_return
        databases = res["name"]

        if not include_sys:
            system_dbs = pa.array(self._sys_databases(), type=pa.string())
            databases = databases.filter(pc.invert(pc.is_in(databases, system_dbs)))
            databases = [db.as_py() for db in databases if db.as_py().upper() not in self._sys_databases()]
        else:
            databases = databases.to_pylist()

        return databases

    @override
    def get_schemas(self, catalog_name: str = "", database_name: str = "", include_sys: bool = False) -> List[str]:
        """Get list of schemas using SHOW SCHEMAS command."""
        database_name = database_name or self.database_name

        if database_name:
            sql = f'SHOW SCHEMAS IN DATABASE "{database_name}"'
        else:
            sql = "SHOW SCHEMAS"

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(sql)
                results = cursor.fetchall()

                schemas = []
                for row in results:
                    schema_name = row[1]
                    if include_sys or schema_name.upper() not in self._sys_schemas():
                        schemas.append(schema_name)

                return schemas
        except Exception as e:
            logger.warning(f"Failed to get schemas using SHOW SCHEMAS, falling back to INFORMATION_SCHEMA: {e}")

            # Fallback to INFORMATION_SCHEMA
            select_table_name = (
                "INFORMATION_SCHEMA.SCHEMATA" if not database_name else f'"{database_name}".INFORMATION_SCHEMA.SCHEMATA'
            )

            sql = f"SELECT SCHEMA_NAME FROM {select_table_name}"
            if not include_sys:
                sql += " WHERE SCHEMA_NAME NOT IN ('INFORMATION_SCHEMA')"

            if database_name:
                if not include_sys:
                    sql += f" AND CATALOG_NAME='{database_name}'"
                else:
                    sql += f" WHERE CATALOG_NAME='{database_name}'"

            try:
                df = self.execute_query_to_df(sql=sql)
                return [item for item in df["SCHEMA_NAME"]]
            except Exception as e:
                raise _handle_snowflake_exception(e, sql) from e

    @override
    def get_tables(self, catalog_name: str = "", database_name: str = "", schema_name: str = "") -> List[str]:
        """Get list of table names."""
        tables = self._get_tables_per_db(
            catalog_name=catalog_name, database_name=database_name, schema_name=schema_name, table_type="table"
        )
        return [item["table_name"] for item in tables]

    def get_views(self, catalog_name: str = "", database_name: str = "", schema_name: str = "") -> List[str]:
        """Get list of view names."""
        views = self._get_tables_per_db(
            catalog_name=catalog_name, database_name=database_name, schema_name=schema_name, table_type="view"
        )
        return [view["table_name"] for view in views]

    def get_materialized_views(
        self, catalog_name: str = "", database_name: str = "", schema_name: str = ""
    ) -> List[str]:
        """Get list of materialized view names."""
        mvs = self._get_tables_per_db(
            catalog_name=catalog_name, database_name=database_name, schema_name=schema_name, table_type="mv"
        )
        return [mv["table_name"] for mv in mvs]

    def _get_tables_per_db(
        self,
        catalog_name: str = "",
        database_name: str = "",
        schema_name: str = "",
        tables: Optional[List[str]] = None,
        table_type: TABLE_TYPE = "",
    ) -> List[Dict[str, str]]:
        """Get table metadata (excluding DDL)."""
        catalog_name = catalog_name or self.catalog_name
        database_name = database_name or self.database_name
        result = []

        if not database_name:
            dbs = self.get_databases(catalog_name=catalog_name)
            for db in dbs:
                self._get_tables_single_db(
                    result=result,
                    database_name=db,
                    catalog_name=catalog_name,
                    schema_name=schema_name,
                    tables=tables,
                    table_type=table_type,
                )
        else:
            self._get_tables_single_db(
                result=result,
                database_name=database_name,
                catalog_name=catalog_name,
                schema_name=schema_name,
                tables=tables,
                table_type=table_type,
            )
        return result

    def _get_tables_single_db(
        self,
        result: List[Dict[str, Any]],
        database_name: str,
        catalog_name: str = "",
        schema_name: str = "",
        tables: Optional[List[str]] = None,
        table_type: TABLE_TYPE = "",
    ):
        """Get tables from a single database."""
        if table_type in ("table", "full"):
            db_tables = self._do_get_metas(
                database_name=database_name, schema_name=schema_name, tables=tables, meta_name="TABLES"
            )
            result.extend(self._metadata_to_dict(db_tables, "table", catalog_name))

        if table_type in ("view", "full"):
            db_views = self._do_get_metas(
                database_name=database_name, schema_name=schema_name, tables=tables, meta_name="VIEWS"
            )
            result.extend(self._metadata_to_dict(db_views, "view", catalog_name))

        if table_type in ("mv", "full"):
            db_mvs = self._do_get_metas(
                database_name=database_name, schema_name=schema_name, tables=tables, meta_name="MATERIALIZED VIEWS"
            )
            result.extend(self._metadata_to_dict(db_mvs, "mv", catalog_name))

    def _do_get_metas(
        self,
        database_name: str,
        schema_name: str = "",
        tables: Optional[List[str]] = None,
        meta_name: str = "TABLES",
    ) -> pa.Table:
        """Get metadata using SHOW command."""
        meta_name = meta_name.upper()
        sql = f'SHOW TERSE {meta_name} IN DATABASE "{database_name}"'

        try:
            query_tables = self.execute_query_to_dict(sql)
            if not query_tables:
                return pa.table([])

            query_tables = pa.Table.from_pylist(query_tables)

            if schema_name:
                query_tables = query_tables.filter(pc.equal(query_tables["schema_name"], schema_name))
            else:
                query_tables = query_tables.filter(
                    pc.invert(pc.is_in(query_tables["schema_name"], pa.array(self._sys_schemas(), type=pa.string())))
                )

            if tables:
                query_tables = query_tables.filter(pc.is_in(query_tables["name"], pa.array(tables, type=pa.string())))

            return query_tables
        except Exception as e:
            logger.warning(f"Failed to get meta using {sql}, falling back to INFORMATION_SCHEMA: {e}")

            # Fallback to INFORMATION_SCHEMA
            select_table_name = f'"{database_name}".INFORMATION_SCHEMA.TABLES'

            if meta_name == "TABLES":
                table_type = "BASE TABLE"
            elif meta_name == "VIEWS":
                table_type = "VIEW"
            else:
                table_type = "MATERIALIZED VIEW"

            sql = f"""SELECT TABLE_CATALOG as "database_name", TABLE_SCHEMA as "schema_name", TABLE_NAME as "name"
            FROM {select_table_name} WHERE TABLE_TYPE = '{table_type}'"""

            if schema_name:
                sql += f" AND TABLE_SCHEMA = {_to_sql_literal(schema_name, True)}"
            if tables:
                sql += list_to_in_str(prefix=" AND TABLE_NAME IN ", values=tables)

            try:
                tables_result, _ = self._do_execute_arrow(sql)
                return tables_result
            except Exception as e:
                raise _handle_snowflake_exception(e, sql) from e

    def _metadata_to_dict(
        self, tables: pa.Table, table_type: TABLE_TYPE, catalog_name: str = ""
    ) -> List[Dict[str, str]]:
        """Convert Arrow table metadata to dictionary list."""
        result = []
        for i in range(len(tables)):
            current_schema = tables["schema_name"][i].as_py()
            current_table_name = tables["name"][i].as_py()
            db_name = tables["database_name"][i].as_py()
            result.append(
                {
                    "catalog_name": catalog_name,
                    "database_name": db_name,
                    "schema_name": current_schema,
                    "table_name": current_table_name,
                    "table_type": table_type,
                    "identifier": self.identifier(
                        catalog_name=catalog_name,
                        database_name=db_name,
                        schema_name=current_schema,
                        table_name=current_table_name,
                    ),
                }
            )
        return result

    def get_schema(
        self,
        catalog_name: str = "",
        database_name: str = "",
        schema_name: str = "",
        table_name: str = "",
        table_type: str = "table",
    ) -> List[Dict[str, Any]]:
        """Get schema information for a table/view/materialized view."""
        if not table_name:
            return []

        catalog_name = catalog_name or self.catalog_name
        database_name = database_name or self.database_name
        schema_name = schema_name or self.schema_name

        full_name = self.full_name(
            catalog_name=catalog_name, database_name=database_name, schema_name=schema_name, table_name=table_name
        )
        table_type = table_type.upper()

        describe_target = {
            "TABLE": "TABLE",
            "VIEW": "VIEW",
            "MATERIALIZED VIEW": "MATERIALIZED VIEW",
            "MATERIALIZED_VIEW": "MATERIALIZED VIEW",
            "MV": "MATERIALIZED VIEW",
        }.get(table_type, "TABLE")

        describe_sql = f"DESCRIBE {describe_target} {full_name}"

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(describe_sql)
                describe_results = cursor.fetchall()
                column_names = [col[0].lower() for col in cursor.description]
        except Exception as e:
            raise _handle_snowflake_exception(e, describe_sql) from e

        def _row_map(row: Sequence[Any]) -> Dict[str, Any]:
            return {column_names[idx]: row[idx] for idx in range(min(len(column_names), len(row)))}

        schemas: List[Dict[str, Any]] = []
        columns_list: List[Dict[str, Any]] = []
        column_index = 0

        for row in describe_results:
            row_info = _row_map(row)
            kind = (row_info.get("kind") or "COLUMN").upper()
            if "COLUMN" not in kind:
                continue

            column_name = row_info.get("name")
            if not column_name:
                continue

            data_type = row_info.get("type", "")
            nullable_flag = str(row_info.get("null?") or row_info.get("null? ") or "").upper()
            default_value = row_info.get("default")
            comment = row_info.get("comment")
            pk_flag = str(row_info.get("primary key") or "").upper()

            column_info = {
                "cid": column_index,
                "name": column_name,
                "type": data_type,
                "nullable": nullable_flag == "Y",
                "pk": pk_flag == "Y" and table_type == "TABLE",
                "default_value": default_value,
                "comment": comment,
            }

            schemas.append(column_info)
            columns_list.append({"name": column_name, "type": data_type})
            column_index += 1

        schemas.append(
            {
                "table": table_name,
                "columns": columns_list,
                "table_type": table_type.lower(),
            }
        )

        return schemas

    def _fetch_object_ddl(self, object_type: str, full_name: str) -> str:
        """Retrieve DDL for a database object."""
        with self.connection.cursor() as cursor:
            sql = f"SELECT GET_DDL('{object_type}', '{full_name}', true)"
            try:
                cursor.execute(sql)
                row = cursor.fetchone()
                ddl = row[0] if row else ""
            except Exception as e:
                logger.warning(f"Failed to get DDL with {sql}: {e}")
                ddl = f"-- DDL not available for {object_type.lower()} {full_name}: {e}"
        return ddl

    @override
    def get_tables_with_ddl(
        self,
        catalog_name: str = "",
        database_name: str = "",
        schema_name: str = "",
        tables: Optional[List[str]] = None,
    ) -> List[Dict[str, str]]:
        """Get table metadata with DDL definitions."""
        table_entries = self._get_tables_per_db(
            catalog_name=catalog_name,
            database_name=database_name,
            schema_name=schema_name,
            tables=tables,
            table_type="table",
        )

        if not table_entries:
            return []

        for entry in table_entries:
            full_name = (
                f'{_to_sql_literal(entry["database_name"])}.'
                f'{_to_sql_literal(entry["schema_name"])}.'
                f'{_to_sql_literal(entry["table_name"])}'
            ).strip()
            entry["definition"] = self._fetch_object_ddl("TABLE", full_name)

        return table_entries

    def get_views_with_ddl(
        self, catalog_name: str = "", database_name: str = "", schema_name: str = ""
    ) -> List[Dict[str, str]]:
        """Get view metadata with DDL definitions."""
        view_entries = self._get_tables_per_db(
            catalog_name=catalog_name,
            database_name=database_name,
            schema_name=schema_name,
            table_type="view",
        )

        if not view_entries:
            return []

        for entry in view_entries:
            full_name = (
                f'{_to_sql_literal(entry["database_name"])}.'
                f'{_to_sql_literal(entry["schema_name"])}.'
                f'{_to_sql_literal(entry["table_name"])}'
            ).strip()
            entry["definition"] = self._fetch_object_ddl("VIEW", full_name)

        return view_entries

    def get_materialized_views_with_ddl(
        self, catalog_name: str = "", database_name: str = "", schema_name: str = ""
    ) -> List[Dict[str, str]]:
        """Get materialized view metadata with DDL definitions."""
        mv_entries = self._get_tables_per_db(
            catalog_name=catalog_name,
            database_name=database_name,
            schema_name=schema_name,
            table_type="mv",
        )

        if not mv_entries:
            return []

        for entry in mv_entries:
            full_name = (
                f'{_to_sql_literal(entry["database_name"])}.'
                f'{_to_sql_literal(entry["schema_name"])}.'
                f'{_to_sql_literal(entry["table_name"])}'
            ).strip()
            entry["definition"] = self._fetch_object_ddl("MATERIALIZED VIEW", full_name)

        return mv_entries

    @override
    def get_sample_rows(
        self,
        tables: Optional[List[str]] = None,
        top_n: int = 5,
        catalog_name: str = "",
        database_name: str = "",
        schema_name: str = "",
        table_type: TABLE_TYPE = "table",
    ) -> List[Dict[str, Any]]:
        """Get sample rows from tables."""
        result = []
        catalog_name = catalog_name or self.catalog_name
        database_name = database_name or self.database_name
        schema_name = schema_name or self.schema_name

        with self.connection.cursor() as cursor:
            if tables:
                for table in tables:
                    full_name = self.full_name(
                        catalog_name=catalog_name,
                        database_name=database_name,
                        schema_name=schema_name,
                        table_name=table,
                    )
                    sql = f"SELECT * FROM {full_name} LIMIT {top_n}"
                    res = cursor.execute(sql).fetch_pandas_all()
                    if not res.empty:
                        result.append(
                            {
                                "identifier": self.identifier(
                                    catalog_name=catalog_name,
                                    database_name=database_name,
                                    schema_name=schema_name,
                                    table_name=table,
                                ),
                                "catalog_name": catalog_name,
                                "database_name": database_name,
                                "schema_name": schema_name,
                                "table_name": table,
                                "table_type": table_type,
                                "sample_rows": res.to_csv(index=False),
                            }
                        )
            else:
                for t in self._get_tables_per_db(
                    catalog_name=catalog_name,
                    database_name=database_name,
                    schema_name=schema_name,
                    table_type=table_type,
                ):
                    full_table_name = self.full_name(
                        t["catalog_name"], t["database_name"], t["schema_name"], t["table_name"]
                    )
                    sql = f"SELECT * FROM {full_table_name} LIMIT {top_n}"
                    res = cursor.execute(sql).fetch_pandas_all()
                    if not res.empty:
                        result.append(
                            {
                                "identifier": t["identifier"],
                                "catalog_name": t["catalog_name"],
                                "database_name": t["database_name"],
                                "schema_name": t["schema_name"],
                                "table_name": t["table_name"],
                                "table_type": t["table_type"],
                                "sample_rows": res.to_csv(index=False),
                            }
                        )
        return result

    @override
    def full_name(
        self, catalog_name: str = "", database_name: str = "", schema_name: str = "", table_name: str = ""
    ) -> str:
        """Build fully qualified table name."""
        if schema_name:
            full_name = f'"{schema_name}"."{table_name}"'
        else:
            full_name = f'"{table_name}"'
        return full_name if not database_name else f'"{database_name}".{full_name}'
