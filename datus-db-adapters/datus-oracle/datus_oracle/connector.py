# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

from typing import Any, Dict, List, Set, Union, override

from datus_db_core import TABLE_TYPE, DatusDbException, ErrorCode, MigrationTargetMixin
from datus_sqlalchemy import SQLAlchemyConnector

from .config import OracleConfig
from .handlers import build_oracle_uri


class OracleConnector(SQLAlchemyConnector, MigrationTargetMixin):
    """Oracle database connector."""

    def __init__(self, config: Union[OracleConfig, dict]):
        if isinstance(config, dict):
            config = OracleConfig(**config)
        elif not isinstance(config, OracleConfig):
            raise TypeError(f"config must be OracleConfig or dict, got {type(config)}")

        self.config = config
        self.host = config.host
        self.port = config.port
        self.username = config.username
        self.password = config.password
        database = config.database
        schema = config.schema_name or config.username.upper()

        super().__init__(
            build_oracle_uri(config),
            dialect="oracle",
            timeout_seconds=config.timeout_seconds,
        )
        self.config = config
        self._default_database = database
        self._default_schema = schema

    @override
    def _sys_databases(self) -> Set[str]:
        return set()

    @override
    def _sys_schemas(self) -> Set[str]:
        return {
            "SYS",
            "SYSTEM",
            "OUTLN",
            "DBSNMP",
            "APPQOSSYS",
            "AUDSYS",
            "CTXSYS",
            "GSMADMIN_INTERNAL",
            "MDSYS",
            "OJVMSYS",
            "ORDDATA",
            "ORDSYS",
            "XDB",
            "WMSYS",
        }

    @override
    def get_databases(self, catalog_name: str = "", include_sys: bool = False) -> List[str]:
        return [self.database_name] if self.database_name else []

    def _owner_filter(self, schema_name: str = "") -> str:
        owner = (schema_name or self.schema_name or self.username).upper().replace("'", "''")
        return f"OWNER = '{owner}'"

    def _frame_rows(self, query_result, *columns: str) -> List[Dict[str, Any]]:
        rows = []
        if hasattr(query_result, "empty"):
            if query_result.empty:
                return rows
            for _, row in query_result.iterrows():
                rows.append({column: row[column] for column in columns})
            return rows
        count = len(query_result[columns[0]]) if columns and columns[0] in query_result else 0
        for i in range(count):
            rows.append({column: query_result[column][i] for column in columns})
        return rows

    def _get_metadata(
        self,
        table_type: TABLE_TYPE = "table",
        catalog_name: str = "",
        database_name: str = "",
        schema_name: str = "",
    ) -> List[Dict[str, str]]:
        self.connect()
        object_sql = {
            "table": ("ALL_TABLES", "TABLE_NAME", "DROPPED = 'NO'"),
            "view": ("ALL_VIEWS", "VIEW_NAME", "1 = 1"),
            "mv": ("ALL_MVIEWS", "MVIEW_NAME", "1 = 1"),
        }
        if table_type not in object_sql:
            raise DatusDbException(ErrorCode.COMMON_FIELD_INVALID, f"Invalid table type '{table_type}'")

        table_name, name_column, extra_filter = object_sql[table_type]
        sql = f"""
            SELECT OWNER, {name_column}
            FROM {table_name}
            WHERE {self._owner_filter(schema_name)}
              AND {extra_filter}
            ORDER BY OWNER, {name_column}
        """
        query_result = self._execute_pandas(sql)
        result = []
        for row in self._frame_rows(query_result, "OWNER", name_column):
            owner = row["OWNER"]
            object_name = row[name_column]
            result.append(
                {
                    "identifier": self.identifier(schema_name=owner, table_name=object_name),
                    "catalog_name": "",
                    "database_name": database_name or self.database_name,
                    "schema_name": owner,
                    "table_name": object_name,
                    "table_type": table_type,
                }
            )
        return result

    @override
    def get_tables(self, catalog_name: str = "", database_name: str = "", schema_name: str = "") -> List[str]:
        return [meta["table_name"] for meta in self._get_metadata("table", catalog_name, database_name, schema_name)]

    @override
    def get_views(self, catalog_name: str = "", database_name: str = "", schema_name: str = "") -> List[str]:
        return [meta["table_name"] for meta in self._get_metadata("view", catalog_name, database_name, schema_name)]

    @override
    def get_materialized_views(
        self, catalog_name: str = "", database_name: str = "", schema_name: str = ""
    ) -> List[str]:
        return [meta["table_name"] for meta in self._get_metadata("mv", catalog_name, database_name, schema_name)]

    @override
    def get_schemas(self, catalog_name: str = "", database_name: str = "", include_sys: bool = False) -> List[str]:
        result = self._execute_pandas("SELECT USERNAME FROM ALL_USERS ORDER BY USERNAME")
        schemas = [row["USERNAME"] for row in self._frame_rows(result, "USERNAME")]
        if not include_sys:
            schemas = [schema for schema in schemas if schema not in self._sys_schemas()]
        return schemas

    @override
    def quote_identifier(self, name: str) -> str:
        escaped = name.replace('"', '""')
        return f'"{escaped}"'

    @override
    def identifier(
        self,
        catalog_name: str = "",
        database_name: str = "",
        schema_name: str = "",
        table_name: str = "",
    ) -> str:
        schema_name = schema_name or self.schema_name
        if schema_name:
            return f"{schema_name}.{table_name}"
        return table_name

    @override
    def full_name(
        self,
        catalog_name: str = "",
        database_name: str = "",
        schema_name: str = "",
        table_name: str = "",
    ) -> str:
        schema_name = schema_name or self.schema_name
        if schema_name:
            return f"{self.quote_identifier(schema_name)}.{self.quote_identifier(table_name)}"
        return self.quote_identifier(table_name)
