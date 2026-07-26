# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

from typing import Any, Sequence

import pyarrow as pa

from datus.storage.datasource_scope import DATASOURCE_ID_COLUMN, STORAGE_KEY_COLUMN, build_storage_key
from datus.utils.exceptions import DatusException, ErrorCode


def apply_storage_key(row: dict[str, Any], schema_names: set[str], source_column: str) -> None:
    """Populate a datasource-scoped physical key from the configured business-key column."""
    if STORAGE_KEY_COLUMN in schema_names and row.get(source_column) not in (None, ""):
        row.setdefault(
            STORAGE_KEY_COLUMN,
            build_storage_key(row.get(DATASOURCE_ID_COLUMN, ""), row[source_column]),
        )


def storage_key_migration_expr(schema_names: set[str], source_column: str) -> str | None:
    """Build the legacy-row SQL expression for a configured storage-key source column."""
    if STORAGE_KEY_COLUMN not in schema_names or source_column not in schema_names:
        return None
    if not source_column.isidentifier():
        raise ValueError(f"Invalid storage key source column: {source_column!r}")
    if DATASOURCE_ID_COLUMN in schema_names:
        return f"coalesce(nullif({DATASOURCE_ID_COLUMN}, ''), 'legacy') || ':' || {source_column}"
    return f"'legacy:' || {source_column}"


def read_select_fields(
    schema: pa.Schema | None,
    vector_column_name: str,
    select_fields: list[str] | None,
) -> list[str] | None:
    """Exclude stored vectors from backend read-only selections."""
    if not vector_column_name or schema is None:
        return select_fields
    if select_fields is None:
        return [field.name for field in schema if field.name != vector_column_name]
    return [field for field in select_fields if field != vector_column_name]


def set_backend_table_schema(db: Any, table_name: str, schema: pa.Schema | None) -> None:
    """Provide schema metadata to backends that need it before opening a table."""
    if schema is None:
        return
    set_table_schema = getattr(db, "set_table_schema", None)
    if callable(set_table_schema):
        set_table_schema(table_name, schema)


def ensure_persisted_unique_columns(
    table: Any | None,
    unique_columns: Sequence[str] | None,
    *,
    table_name: str,
) -> None:
    """Repair physical unique keys when the active backend exposes that capability."""
    if table is None or not unique_columns:
        return
    ensure_unique_columns = getattr(table, "ensure_unique_columns", None)
    if ensure_unique_columns is None:
        return
    try:
        ensure_unique_columns(unique_columns)
    except Exception as exc:
        raise DatusException(
            ErrorCode.STORAGE_TABLE_OPERATION_FAILED,
            message_args={
                "operation": "ensure_unique_columns",
                "table_name": table_name,
                "error_message": str(exc),
            },
        ) from exc
