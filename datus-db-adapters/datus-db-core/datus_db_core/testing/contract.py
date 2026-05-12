# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Shared DB adapter contract assertions.

These helpers keep integration tests focused on adapter-specific SQL while
enforcing the same observable Datus-facing behavior across engines.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable, Iterable, Mapping, Sequence

RowAssert = Callable[[Mapping[str, Any]], None]


@dataclass(frozen=True)
class TableContractCase:
    """Contract case for adapters that can create a temporary table."""

    adapter_name: str
    table_name: str
    drop_sql: str
    create_sql: str
    insert_sqls: Sequence[str]
    qualified_select_sql: str
    limit_sql: str
    schema_kwargs: Mapping[str, Any]
    expected_columns: Sequence[str]
    limit_count: int = 1
    row_assert: RowAssert | None = None
    cleanup_sqls: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True)
class SelectContractCase:
    """Contract case for read-only adapters or read-only catalogs."""

    adapter_name: str
    select_sql: str
    limit_sql: str
    qualified_sql: str
    limit_count: int = 1
    row_assert: RowAssert | None = None


def assert_success(result: Any, operation: str) -> None:
    """Assert an ExecuteSQLResult-like object succeeded."""

    assert result.success, f"{operation} failed: {getattr(result, 'error', None)}"


def assert_error_result(result: Any, operation: str) -> None:
    """Assert an ExecuteSQLResult-like object failed with a useful error."""

    assert not result.success, f"{operation} unexpectedly succeeded: {getattr(result, 'sql_return', None)}"
    assert result.error, f"{operation} failed without an error message"


def assert_default_contract_row(row: Mapping[str, Any]) -> None:
    """Validate stable aliases returned by contract SELECT queries."""

    assert row["id_value"] == 1
    assert row["mixed_value"] == "Alpha"
    assert row["nullable_value"] is None
    assert str(row["event_date_value"]).startswith("2024-02-03")
    assert Decimal(str(row["amount_value"])) == Decimal("123.45")


def assert_schema_columns(schema: Iterable[Mapping[str, Any]], expected_columns: Sequence[str]) -> None:
    """Assert schema metadata includes expected columns case-insensitively."""

    actual = {str(column.get("name", "")).lower() for column in schema}
    missing = [column for column in expected_columns if column.lower() not in actual]
    assert not missing, f"Missing schema columns {missing}; actual columns: {sorted(actual)}"


def assert_table_contract(connector: Any, case: TableContractCase) -> None:
    """Run the shared table contract against a live adapter connector."""

    connector.execute_ddl(case.drop_sql)
    try:
        assert_success(
            connector.execute_ddl(case.create_sql),
            f"{case.adapter_name} create contract table",
        )
        for index, insert_sql in enumerate(case.insert_sqls, start=1):
            assert_success(
                connector.execute_insert(insert_sql),
                f"{case.adapter_name} insert contract row {index}",
            )

        schema = connector.get_schema(**dict(case.schema_kwargs, table_name=case.table_name))
        assert_schema_columns(schema, case.expected_columns)

        result = connector.execute({"sql_query": case.qualified_select_sql}, result_format="list")
        assert_success(result, f"{case.adapter_name} qualified contract SELECT")
        assert result.sql_return, f"{case.adapter_name} qualified contract SELECT returned no rows"
        (case.row_assert or assert_default_contract_row)(result.sql_return[0])

        limited = connector.execute({"sql_query": case.limit_sql}, result_format="list")
        assert_success(limited, f"{case.adapter_name} LIMIT contract SELECT")
        assert len(limited.sql_return) == case.limit_count
    finally:
        for cleanup_sql in case.cleanup_sqls:
            connector.execute_ddl(cleanup_sql)
        connector.execute_ddl(case.drop_sql)


def assert_select_contract(connector: Any, case: SelectContractCase) -> None:
    """Run the shared read-only contract against a live adapter connector."""

    result = connector.execute({"sql_query": case.select_sql}, result_format="list")
    assert_success(result, f"{case.adapter_name} typed SELECT contract")
    assert result.sql_return, f"{case.adapter_name} typed SELECT contract returned no rows"
    (case.row_assert or assert_default_contract_row)(result.sql_return[0])

    limited = connector.execute({"sql_query": case.limit_sql}, result_format="list")
    assert_success(limited, f"{case.adapter_name} LIMIT contract SELECT")
    assert len(limited.sql_return) == case.limit_count

    qualified = connector.execute({"sql_query": case.qualified_sql}, result_format="list")
    assert_success(qualified, f"{case.adapter_name} qualified identifier SELECT")
    assert qualified.sql_return, f"{case.adapter_name} qualified identifier SELECT returned no rows"
