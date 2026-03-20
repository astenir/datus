# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

from abc import ABC, abstractmethod
from typing import Any, Dict, Iterator, List, Literal, Optional, Set, Tuple

from datus_db_core.config import ConnectionConfig
from datus_db_core.constants import SQLType
from datus_db_core.logging import get_logger
from datus_db_core.models import TABLE_TYPE, ExecuteSQLInput, ExecuteSQLResult
from datus_db_core.sql_utils import metadata_identifier, parse_sql_type

logger = get_logger(__name__)


class BaseSqlConnector(ABC):
    def __init__(self, config: ConnectionConfig, dialect: str):
        self.config = config
        self.timeout_seconds = config.timeout_seconds
        self.connection: Any = None
        self.dialect = dialect
        self.catalog_name = ""
        self.database_name = ""
        self.schema_name = ""

    def close(self):
        if self.connection:
            self.connection.close()
            self.connection = None

    def connect(self):
        return

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            try:
                self._safe_rollback()
            except Exception as e:
                logger.warning(f"Failed to rollback during cleanup: {e}")
        try:
            self.close()
        except Exception as e:
            logger.warning(f"Failed to close connection during cleanup: {e}")
        return False

    def _safe_rollback(self):
        if hasattr(self, "connection") and self.connection:
            try:
                if hasattr(self.connection, "rollback"):
                    self.connection.rollback()
            except Exception:
                pass

    def execute(
        self,
        input_params: Any,
        result_format: Optional[Literal["csv", "arrow", "pandas", "list"]] = None,
    ) -> ExecuteSQLResult:
        self.validate_input(input_params)
        if isinstance(input_params, dict):
            input_params = ExecuteSQLInput(**input_params)
        sql_query = input_params.sql_query.strip()
        if result_format is None:
            result_format = getattr(input_params, "result_format", "csv") or "csv"
        try:
            sql_type = parse_sql_type(sql_query, self.dialect)
            if sql_type == SQLType.INSERT:
                result = self.execute_insert(sql_query)
            elif sql_type in (SQLType.UPDATE, SQLType.MERGE):
                result = self.execute_update(sql_query)
            elif sql_type == SQLType.DELETE:
                result = self.execute_delete(sql_query)
            elif sql_type == SQLType.CONTENT_SET:
                result = self.execute_content_set(sql_query)
            elif sql_type == SQLType.DDL:
                result = self.execute_ddl(sql_query)
            elif sql_type == SQLType.SELECT:
                result = self.execute_query(sql_query, result_format)
            elif sql_type == SQLType.METADATA_SHOW:
                result = self.execute_query(sql_query, result_format)
            elif sql_type == SQLType.EXPLAIN:
                result = self.execute_explain(sql_query, result_format)
            else:
                return ExecuteSQLResult(
                    success=False,
                    error="Unknown type of SQL",
                    sql_query=sql_query,
                    sql_return="",
                    row_count=0,
                    result_format=result_format,
                )

            return result
        except Exception as e:
            logger.error(f"Executing SQL query failed: {e}")
            return ExecuteSQLResult(
                success=False,
                error=str(e),
                sql_query=sql_query,
                sql_return="",
                row_count=0,
                result_format=result_format,
            )

    @abstractmethod
    def execute_insert(self, sql: str) -> ExecuteSQLResult:
        raise NotImplementedError()

    @abstractmethod
    def execute_update(self, sql: str) -> ExecuteSQLResult:
        raise NotImplementedError()

    @abstractmethod
    def execute_delete(self, sql: str) -> ExecuteSQLResult:
        raise NotImplementedError()

    def validate_input(self, input_params: Any):
        if isinstance(input_params, dict):
            if "sql_query" not in input_params:
                raise ValueError("'sql_query' parameter is required")
            if not isinstance(input_params["sql_query"], str):
                raise ValueError("'sql_query' must be a string")
        else:
            if not hasattr(input_params, "sql_query"):
                raise ValueError("'sql_query' parameter is required")
            if not isinstance(input_params.sql_query, str):
                raise ValueError("'sql_query' must be a string")

    def execute_arrow(self, sql: str) -> ExecuteSQLResult:
        raise NotImplementedError()

    @abstractmethod
    def execute_query(
        self, sql: str, result_format: Literal["csv", "arrow", "pandas", "list"] = "csv"
    ) -> ExecuteSQLResult:
        raise NotImplementedError()

    def execute_explain(
        self, sql: str, result_format: Literal["csv", "arrow", "pandas", "list"] = "csv"
    ) -> ExecuteSQLResult:
        return self.execute_query(sql, result_format)

    @abstractmethod
    def execute_pandas(self, sql: str) -> ExecuteSQLResult:
        raise NotImplementedError()

    @abstractmethod
    def execute_ddl(self, sql: str) -> ExecuteSQLResult:
        raise NotImplementedError()

    @abstractmethod
    def execute_csv(self, sql: str) -> ExecuteSQLResult:
        raise NotImplementedError()

    @abstractmethod
    def get_databases(self, catalog_name: str = "", include_sys: bool = False) -> List[str]:
        raise NotImplementedError()

    @abstractmethod
    def get_tables(self, catalog_name: str = "", database_name: str = "", schema_name: str = "") -> List[str]:
        raise NotImplementedError()

    def get_views(self, catalog_name: str = "", database_name: str = "", schema_name: str = "") -> List[str]:
        return []

    def _sys_databases(self) -> Set[str]:
        return set()

    def _sys_schemas(self) -> Set[str]:
        return set()

    def execute_csv_iterator(
        self, query: str, max_rows: int = 100, with_header: bool = True
    ) -> Iterator[Tuple[str, ...]]:
        raise NotImplementedError()

    @abstractmethod
    def test_connection(self):
        raise NotImplementedError()

    def get_type(self) -> str:
        return self.dialect

    @abstractmethod
    def execute_queries(self, queries: List[str]) -> List[Any]:
        raise NotImplementedError()

    def get_tables_with_ddl(
        self,
        catalog_name: str = "",
        database_name: str = "",
        schema_name: str = "",
        tables: Optional[List[str]] = None,
    ) -> List[Dict[str, str]]:
        raise NotImplementedError()

    def _reset_filter_tables(
        self,
        tables: Optional[List[str]] = None,
        catalog_name: str = "",
        database_name: str = "",
        schema_name: str = "",
    ) -> List[str]:
        filter_tables = []
        if tables:
            catalog_name = catalog_name or self.catalog_name
            database_name = database_name or self.database_name
            schema_name = schema_name or self.schema_name
            for table_name in tables:
                filter_tables.append(
                    self.full_name(
                        table_name=table_name,
                        catalog_name=catalog_name,
                        database_name=database_name,
                        schema_name=schema_name,
                    )
                )
        return filter_tables

    def get_views_with_ddl(
        self, catalog_name: str = "", database_name: str = "", schema_name: str = ""
    ) -> List[Dict[str, str]]:
        raise NotImplementedError()

    def switch_context(self, catalog_name: str = "", database_name: str = "", schema_name: str = ""):
        self.connect()
        self.do_switch_context(catalog_name=catalog_name, database_name=database_name, schema_name=schema_name)
        if catalog_name:
            self.catalog_name = catalog_name
        if database_name:
            self.database_name = database_name
        if schema_name:
            self.schema_name = schema_name

    def do_switch_context(self, catalog_name: str = "", database_name: str = "", schema_name: str = ""):
        return None

    def get_schema(
        self, catalog_name: str = "", database_name: str = "", schema_name: str = "", table_name: str = ""
    ) -> List[Dict[str, str]]:
        raise NotImplementedError()

    def get_sample_rows(
        self,
        tables: Optional[List[str]] = None,
        top_n: int = 5,
        catalog_name: str = "",
        database_name: str = "",
        schema_name: str = "",
        table_type: TABLE_TYPE = "table",
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError()

    def full_name(
        self, catalog_name: str = "", database_name: str = "", schema_name: str = "", table_name: str = ""
    ) -> str:
        raise NotImplementedError()

    def identifier(
        self, catalog_name: str = "", database_name: str = "", schema_name: str = "", table_name: str = ""
    ) -> str:
        return metadata_identifier(
            dialect=self.dialect,
            catalog_name=catalog_name,
            database_name=database_name,
            schema_name=schema_name,
            table_name=table_name,
        )

    @abstractmethod
    def execute_content_set(self, sql_query: str) -> ExecuteSQLResult:
        raise NotImplementedError()


def list_to_in_str(prefix: str, values: Optional[List[str]] = None) -> str:
    if not values:
        return ""
    value_str = ",".join(to_sql_literal(v, around_with_quotes=True) for v in values)
    return f"{prefix} ({value_str})"


def _escape_sql_string_standard(value: str) -> str:
    return value.replace("'", "''")


def to_sql_literal(value: Optional[str], around_with_quotes: bool = False) -> str:
    if value is None:
        return "NULL"
    if not value:
        return "" if not around_with_quotes else "''"
    replace_value = _escape_sql_string_standard(value)
    if not around_with_quotes:
        return replace_value
    else:
        return f"'{replace_value}'"
