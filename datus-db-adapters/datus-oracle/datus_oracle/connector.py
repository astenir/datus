# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

from typing import Any, Dict, List, Optional, Set, Union, override

from sqlalchemy import text

from datus_db_core import TABLE_TYPE, DatusDbException, ErrorCode, MigrationTargetMixin, get_logger
from datus_sqlalchemy import SQLAlchemyConnector

from .config import OracleConfig
from .handlers import build_oracle_uri

logger = get_logger(__name__)


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

    def _format_data_type(self, row: Dict[str, Any]) -> str:
        data_type = row["DATA_TYPE"]
        precision = row.get("DATA_PRECISION")
        scale = row.get("DATA_SCALE")
        if data_type == "NUMBER" and precision is not None:
            return f"NUMBER({precision},{scale or 0})"
        return data_type

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
        owner = (schema_name or self.schema_name).upper().replace("'", "''")
        safe_table = table_name.upper().replace("'", "''")
        sql = f"""
            SELECT
                c.COLUMN_ID,
                c.COLUMN_NAME,
                c.DATA_TYPE,
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
                  AND cons.TABLE_NAME = '{safe_table}'
            ) pk
              ON pk.OWNER = c.OWNER
             AND pk.TABLE_NAME = c.TABLE_NAME
             AND pk.COLUMN_NAME = c.COLUMN_NAME
            LEFT JOIN ALL_COL_COMMENTS cc
              ON cc.OWNER = c.OWNER
             AND cc.TABLE_NAME = c.TABLE_NAME
             AND cc.COLUMN_NAME = c.COLUMN_NAME
            WHERE c.OWNER = '{owner}'
              AND c.TABLE_NAME = '{safe_table}'
            ORDER BY c.COLUMN_ID
        """
        query_result = self._execute_pandas(sql)
        result = []
        for i, row in enumerate(
            self._frame_rows(
                query_result,
                "COLUMN_ID",
                "COLUMN_NAME",
                "DATA_TYPE",
                "DATA_PRECISION",
                "DATA_SCALE",
                "NULLABLE",
                "DATA_DEFAULT",
                "IS_PK",
                "COMMENTS",
            )
        ):
            result.append(
                {
                    "cid": i,
                    "name": row["COLUMN_NAME"],
                    "type": self._format_data_type(row),
                    "nullable": row["NULLABLE"] == "Y",
                    "default_value": row["DATA_DEFAULT"],
                    "pk": bool(row["IS_PK"]),
                    "comment": row["COMMENTS"] or None,
                }
            )
        return result

    def _get_ddl(self, schema_name: str, table_name: str, object_type: str = "TABLE") -> str:
        owner = schema_name.upper().replace("'", "''")
        object_name = table_name.upper().replace("'", "''")
        sql = f"""
            SELECT DBMS_METADATA.GET_DDL('{object_type}', '{object_name}', '{owner}') AS DDL
            FROM DUAL
        """
        result = self._execute_pandas(sql)
        rows = self._frame_rows(result, "DDL")
        if rows and rows[0]["DDL"]:
            return str(rows[0]["DDL"])
        return f"-- DDL not available for {self.full_name(schema_name=schema_name, table_name=table_name)}"

    def _get_objects_with_ddl(
        self,
        table_type: TABLE_TYPE = "table",
        tables: Optional[List[str]] = None,
        catalog_name: str = "",
        database_name: str = "",
        schema_name: str = "",
    ) -> List[Dict[str, str]]:
        object_type_map = {"table": "TABLE", "view": "VIEW", "mv": "MATERIALIZED_VIEW"}
        result = []
        filter_tables = self._reset_filter_tables(tables, catalog_name, database_name, schema_name)
        for meta in self._get_metadata(table_type, catalog_name, database_name, schema_name):
            full_name = self.full_name(schema_name=meta["schema_name"], table_name=meta["table_name"])
            if filter_tables and full_name not in filter_tables:
                continue
            try:
                meta["definition"] = self._get_ddl(meta["schema_name"], meta["table_name"], object_type_map[table_type])
            except Exception as e:
                logger.warning(f"Could not get DDL for {full_name}: {e}")
                meta["definition"] = f"-- DDL not available for {meta['table_name']}"
            result.append(meta)
        return result

    @override
    def get_tables_with_ddl(
        self,
        catalog_name: str = "",
        database_name: str = "",
        schema_name: str = "",
        tables: Optional[List[str]] = None,
    ) -> List[Dict[str, str]]:
        return self._get_objects_with_ddl("table", tables, catalog_name, database_name, schema_name)

    @override
    def get_views_with_ddl(
        self, catalog_name: str = "", database_name: str = "", schema_name: str = ""
    ) -> List[Dict[str, str]]:
        return self._get_objects_with_ddl("view", None, catalog_name, database_name, schema_name)

    @override
    def do_switch_context(self, conn, catalog_name: str = "", database_name: str = "", schema_name: str = ""):
        if schema_name:
            conn.execute(text(f"ALTER SESSION SET CURRENT_SCHEMA = {self.quote_identifier(schema_name.upper())}"))
            conn.commit()

    def get_sample_rows(
        self,
        tables: Optional[List[str]] = None,
        top_n: int = 5,
        catalog_name: str = "",
        database_name: str = "",
        schema_name: str = "",
        table_type: TABLE_TYPE = "table",
    ) -> List[Dict[str, str]]:
        schema_name = schema_name or self.schema_name
        result = []
        target_tables = tables or self.get_tables(schema_name=schema_name)
        for table in target_tables:
            full_name = self.full_name(schema_name=schema_name, table_name=table)
            df = self._execute_pandas(f"SELECT * FROM {full_name} FETCH FIRST {top_n} ROWS ONLY")
            if hasattr(df, "empty") and df.empty:
                continue
            result.append(
                {
                    "identifier": self.identifier(schema_name=schema_name, table_name=table),
                    "catalog_name": "",
                    "database_name": self.database_name,
                    "schema_name": schema_name,
                    "table_name": table,
                    "sample_rows": df.to_csv(index=False) if hasattr(df, "to_csv") else str(df),
                }
            )
        return result

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
