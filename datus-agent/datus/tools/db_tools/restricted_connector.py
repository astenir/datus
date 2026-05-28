# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Datasource-level database/schema/table allowlist wrapper for SQL connectors."""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
from typing import Any, Iterable, List, Optional, Sequence

from datus_db_core import BaseSqlConnector, ExecuteSQLResult, connector_registry

from datus.utils.constants import DBType
from datus.utils.sql_utils import extract_table_names

_SYSTEM_SCHEMAS = {"information_schema", "pg_catalog"}


@dataclass(frozen=True)
class _TablePattern:
    raw: str
    catalog: str = ""
    database: str = ""
    schema: str = ""
    table: str = ""

    def matches(self, coordinate: "_TableCoordinate") -> bool:
        return all(
            _pattern_matches(getattr(self, field), getattr(coordinate, field))
            for field in ("catalog", "database", "schema", "table")
        )


@dataclass(frozen=True)
class _TableCoordinate:
    catalog: str = ""
    database: str = ""
    schema: str = ""
    table: str = ""


def _clean_identifier(value: Optional[str]) -> str:
    if value is None:
        return ""
    return str(value).strip().strip("`\"'[]").lower()


def _pattern_matches(pattern: str, value: str) -> bool:
    if not pattern or pattern in {"*", "%"}:
        return True
    if not value:
        return True
    return fnmatchcase(value, pattern.replace("%", "*"))


def _normalize_allowed_tables(value: Any) -> List[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        chunks = value.replace("\n", ",").split(",")
    elif isinstance(value, Iterable):
        chunks = list(value)
    else:
        chunks = [value]
    seen = set()
    tables: List[str] = []
    for chunk in chunks:
        token = str(chunk).strip()
        if token and token not in seen:
            tables.append(token)
            seen.add(token)
    return tables


class RestrictedSqlConnector:
    """Wrap a connector and enforce datasource-level allowlists.

    This wrapper is intentionally conservative for direct SQL execution: any
    query that references data outside the configured allowlists is rejected,
    and direct queries against common metadata schemas are blocked. Connector
    metadata methods still work, but their results are filtered.
    """

    def __init__(
        self,
        connector: BaseSqlConnector,
        allowed_tables: Sequence[str] = (),
        allowed_databases: Sequence[str] = (),
        allowed_schemas: Sequence[str] = (),
    ):
        self._connector = connector
        self._allowed_table_tokens = _normalize_allowed_tables(allowed_tables)
        self._allowed_database_tokens = [
            _clean_identifier(token) for token in _normalize_allowed_tables(allowed_databases)
        ]
        self._allowed_schema_tokens = [_clean_identifier(token) for token in _normalize_allowed_tables(allowed_schemas)]
        self._field_order = self._determine_field_order()
        self._table_patterns = [p for token in self._allowed_table_tokens if (p := self._parse_pattern(token))]

    def __getattr__(self, name: str) -> Any:
        return getattr(self._connector, name)

    @property
    def raw_connector(self) -> BaseSqlConnector:
        return self._connector

    @property
    def allowed_tables(self) -> List[str]:
        return list(self._allowed_table_tokens)

    @property
    def allowed_databases(self) -> List[str]:
        return list(self._allowed_database_tokens)

    @property
    def allowed_schemas(self) -> List[str]:
        return list(self._allowed_schema_tokens)

    def _determine_field_order(self) -> Sequence[str]:
        dialect = getattr(self._connector, "dialect", "") or ""
        fields: List[str] = []
        if connector_registry.support_catalog(dialect):
            fields.append("catalog")
        if connector_registry.support_database(dialect) or dialect == DBType.SQLITE:
            fields.append("database")
        if connector_registry.support_schema(dialect):
            fields.append("schema")
        fields.append("table")
        return fields

    def _default_field_value(self, field: str, explicit: Optional[str] = "") -> str:
        explicit_value = _clean_identifier(explicit)
        if explicit_value:
            return explicit_value
        attr_map = {
            "catalog": "catalog_name",
            "database": "database_name",
            "schema": "schema_name",
        }
        attr = attr_map.get(field)
        if attr and hasattr(self._connector, attr):
            return _clean_identifier(getattr(self._connector, attr))
        return ""

    def _parse_pattern(self, token: str) -> Optional[_TablePattern]:
        parts = [_clean_identifier(part) for part in str(token).split(".") if str(part).strip()]
        if not parts:
            return None
        values = {field: "" for field in self._field_order}
        trimmed = parts[-len(self._field_order) :]
        start = max(0, len(self._field_order) - len(trimmed))
        for idx, part in enumerate(trimmed):
            values[self._field_order[start + idx]] = part
        return _TablePattern(raw=token, **values)

    def _coordinate(
        self,
        raw_name: str,
        catalog_name: Optional[str] = "",
        database_name: Optional[str] = "",
        schema_name: Optional[str] = "",
    ) -> _TableCoordinate:
        coordinate = _TableCoordinate(
            catalog=self._default_field_value("catalog", catalog_name),
            database=self._default_field_value("database", database_name),
            schema=self._default_field_value("schema", schema_name),
            table=_clean_identifier(raw_name),
        )
        values = coordinate.__dict__.copy()
        parts = [_clean_identifier(part) for part in str(raw_name).split(".") if str(part).strip()]
        if parts:
            values["table"] = parts[-1]
            part_idx = len(parts) - 2
            for field in reversed(self._field_order[:-1]):
                if part_idx < 0:
                    break
                values[field] = parts[part_idx]
                part_idx -= 1
        return _TableCoordinate(**values)

    def _matches_allowed_database(self, database: str) -> bool:
        if not self._allowed_database_tokens:
            return True
        value = database or self._default_field_value("database")
        return any(_pattern_matches(pattern, value) for pattern in self._allowed_database_tokens)

    def _matches_allowed_schema(self, schema: str) -> bool:
        if not self._allowed_schema_tokens:
            return True
        value = schema or self._default_field_value("schema")
        return any(_pattern_matches(pattern, value) for pattern in self._allowed_schema_tokens)

    def _matches_allowed_table(self, coordinate: _TableCoordinate) -> bool:
        if not self._table_patterns:
            return True
        return any(pattern.matches(coordinate) for pattern in self._table_patterns)

    def _is_allowed(self, coordinate: _TableCoordinate) -> bool:
        return (
            self._matches_allowed_database(coordinate.database)
            and self._matches_allowed_schema(coordinate.schema)
            and self._matches_allowed_table(coordinate)
        )

    def _is_context_allowed(
        self,
        database_name: Optional[str] = "",
        schema_name: Optional[str] = "",
    ) -> bool:
        return self._matches_allowed_database(_clean_identifier(database_name)) and self._matches_allowed_schema(
            _clean_identifier(schema_name)
        )

    def _filter_names(
        self,
        names: Sequence[str],
        catalog_name: Optional[str] = "",
        database_name: Optional[str] = "",
        schema_name: Optional[str] = "",
    ) -> List[str]:
        return [
            name for name in names if self._is_allowed(self._coordinate(name, catalog_name, database_name, schema_name))
        ]

    def _reject_result(self, sql: Optional[str], message: str, result_format: str = "") -> ExecuteSQLResult:
        return ExecuteSQLResult(success=False, error=message, sql_query=sql or "", result_format=result_format)

    def _scope_error_for_sql(self, sql: str) -> Optional[str]:
        lowered = (sql or "").lower()
        if any(schema in lowered for schema in _SYSTEM_SCHEMAS):
            return (
                "Querying metadata schemas is not allowed for this datasource. "
                f"Allowed context: {self._allowed_context_message()}"
            )
        table_names = extract_table_names(sql, dialect=getattr(self._connector, "dialect", "") or "", ignore_empty=True)
        out_of_scope = [name for name in table_names if not self._is_allowed(self._coordinate(name))]
        if out_of_scope:
            return (
                "Query references objects outside datasource allowlist: "
                f"{', '.join(out_of_scope)}. Allowed context: {self._allowed_context_message()}"
            )
        return None

    def _allowed_context_message(self) -> str:
        parts = []
        if self._allowed_database_tokens:
            parts.append(f"databases={', '.join(self._allowed_database_tokens)}")
        if self._allowed_schema_tokens:
            parts.append(f"schemas={', '.join(self._allowed_schema_tokens)}")
        if self._allowed_table_tokens:
            parts.append(f"tables={', '.join(self._allowed_table_tokens)}")
        return "; ".join(parts) or "unrestricted"

    def _assert_table_allowed(
        self,
        table_name: str,
        catalog_name: Optional[str] = "",
        database_name: Optional[str] = "",
        schema_name: Optional[str] = "",
    ) -> None:
        if not self._is_allowed(self._coordinate(table_name, catalog_name, database_name, schema_name)):
            raise PermissionError(
                f"Table '{table_name}' is outside datasource allowlist: {self._allowed_context_message()}"
            )

    def execute(self, input_params: dict, result_format: str = "arrow") -> ExecuteSQLResult:
        sql = (input_params or {}).get("sql_query", "")
        if error := self._scope_error_for_sql(sql):
            return self._reject_result(sql, error, result_format=result_format)
        return self._connector.execute(input_params, result_format=result_format)

    def execute_query(self, sql: str, result_format: str = "arrow") -> ExecuteSQLResult:
        if error := self._scope_error_for_sql(sql):
            return self._reject_result(sql, error, result_format=result_format)
        return self._connector.execute_query(sql, result_format=result_format)

    def execute_pandas(self, sql: str) -> ExecuteSQLResult:
        if error := self._scope_error_for_sql(sql):
            return self._reject_result(sql, error, result_format="pandas")
        return self._connector.execute_pandas(sql)

    def execute_csv(self, sql: str) -> ExecuteSQLResult:
        if error := self._scope_error_for_sql(sql):
            return self._reject_result(sql, error, result_format="csv")
        return self._connector.execute_csv(sql)

    def execute_arrow(self, sql: str) -> ExecuteSQLResult:
        if error := self._scope_error_for_sql(sql):
            return self._reject_result(sql, error, result_format="arrow")
        return self._connector.execute_arrow(sql)

    def execute_ddl(self, sql: str) -> ExecuteSQLResult:
        if error := self._scope_error_for_sql(sql):
            return self._reject_result(sql, error)
        return self._connector.execute_ddl(sql)

    def get_databases(self, catalog_name: str = "", include_sys: bool = False) -> List[str]:
        databases = self._connector.get_databases(catalog_name, include_sys=include_sys)
        return [db for db in databases if self._matches_allowed_database(_clean_identifier(db))]

    def get_schemas(self, catalog_name: str = "", database_name: str = "", include_sys: bool = False) -> List[str]:
        if not self._matches_allowed_database(_clean_identifier(database_name)):
            return []
        if not hasattr(self._connector, "get_schemas"):
            return []
        schemas = self._connector.get_schemas(catalog_name, database_name, include_sys=include_sys)
        return [schema for schema in schemas if self._matches_allowed_schema(_clean_identifier(schema))]

    def get_tables(self, catalog_name: str = "", database_name: str = "", schema_name: str = "") -> List[str]:
        if not self._is_context_allowed(database_name, schema_name):
            return []
        return self._filter_names(
            self._connector.get_tables(catalog_name, database_name, schema_name),
            catalog_name,
            database_name,
            schema_name,
        )

    def get_views(self, catalog_name: str = "", database_name: str = "", schema_name: str = "") -> List[str]:
        if not self._is_context_allowed(database_name, schema_name):
            return []
        return self._filter_names(
            self._connector.get_views(catalog_name, database_name, schema_name),
            catalog_name,
            database_name,
            schema_name,
        )

    def get_materialized_views(
        self, catalog_name: str = "", database_name: str = "", schema_name: str = ""
    ) -> List[str]:
        if not self._is_context_allowed(database_name, schema_name):
            return []
        if not hasattr(self._connector, "get_materialized_views"):
            return []
        return self._filter_names(
            self._connector.get_materialized_views(catalog_name, database_name, schema_name),
            catalog_name,
            database_name,
            schema_name,
        )

    def get_schema(
        self,
        catalog_name: str = "",
        database_name: str = "",
        schema_name: str = "",
        table_name: str = "",
    ) -> Any:
        if not self._is_context_allowed(database_name, schema_name):
            raise PermissionError(f"Schema is outside datasource allowlist: {self._allowed_context_message()}")
        if table_name:
            self._assert_table_allowed(table_name, catalog_name, database_name, schema_name)
        return self._connector.get_schema(catalog_name, database_name, schema_name, table_name)

    def get_sample_rows(self, table_name: str, *args: Any, **kwargs: Any) -> Any:
        self._assert_table_allowed(
            table_name,
            kwargs.get("catalog_name", ""),
            kwargs.get("database_name", ""),
            kwargs.get("schema_name", ""),
        )
        return self._connector.get_sample_rows(table_name, *args, **kwargs)

    def get_tables_with_ddl(
        self,
        catalog_name: str = "",
        database_name: str = "",
        schema_name: str = "",
        tables: Optional[List[str]] = None,
    ) -> Any:
        if tables:
            for table in tables:
                self._assert_table_allowed(table, catalog_name, database_name, schema_name)
        allowed_tables = tables or self.get_tables(catalog_name, database_name, schema_name)
        return self._connector.get_tables_with_ddl(catalog_name, database_name, schema_name, allowed_tables)

    def get_views_with_ddl(
        self,
        catalog_name: str = "",
        database_name: str = "",
        schema_name: str = "",
        views: Optional[List[str]] = None,
    ) -> Any:
        if views:
            for view in views:
                self._assert_table_allowed(view, catalog_name, database_name, schema_name)
        allowed_views = views or self.get_views(catalog_name, database_name, schema_name)
        return self._connector.get_views_with_ddl(catalog_name, database_name, schema_name, allowed_views)
