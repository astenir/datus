"""PyArrow schema to PostgreSQL DDL converter with pgvector support."""

import re
from typing import List, Optional, Tuple

import pyarrow as pa

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$")
_SIMPLE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_identifier(name: str) -> str:
    """Validate that a name is a safe SQL identifier (may be schema-qualified)."""
    if not _SAFE_IDENTIFIER.match(name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    return name


def _validate_column_name(name: str) -> str:
    """Validate that a name is a safe simple column name (no dots)."""
    if not _SIMPLE_IDENTIFIER.match(name):
        raise ValueError(f"Invalid column name: {name!r}")
    return name

# Mapping from PyArrow types to PostgreSQL types
_PA_TO_PG = {
    pa.string(): "TEXT",
    pa.large_string(): "TEXT",
    pa.utf8(): "TEXT",
    pa.bool_(): "BOOLEAN",
    pa.int8(): "SMALLINT",
    pa.int16(): "SMALLINT",
    pa.int32(): "INTEGER",
    pa.int64(): "BIGINT",
    pa.uint8(): "SMALLINT",
    pa.uint16(): "INTEGER",
    pa.uint32(): "BIGINT",
    pa.uint64(): "NUMERIC",
    pa.float16(): "REAL",
    pa.float32(): "REAL",
    pa.float64(): "DOUBLE PRECISION",
    pa.date32(): "DATE",
    pa.date64(): "DATE",
}


def _pa_type_to_pg(pa_type: pa.DataType) -> str:
    """Convert a PyArrow data type to a PostgreSQL column type string."""
    # Check for fixed-size list of floats -> vector(N)
    if isinstance(pa_type, pa.FixedSizeListType):
        if pa.types.is_floating(pa_type.value_type):
            return f"vector({pa_type.list_size})"

    # Check for variable-length list of floats -> vector (no fixed dim)
    if isinstance(pa_type, pa.ListType):
        if pa.types.is_floating(pa_type.value_type):
            return "vector"

    # Check for timestamp types
    if isinstance(pa_type, pa.TimestampType):
        return "TIMESTAMP"

    # Direct lookup
    if pa_type in _PA_TO_PG:
        return _PA_TO_PG[pa_type]

    # Fallback
    return "TEXT"


def schema_to_columns(schema: pa.Schema) -> List[Tuple[str, str]]:
    """Convert a PyArrow schema to a list of (column_name, pg_type) tuples.

    Args:
        schema: PyArrow schema to convert.

    Returns:
        List of (column_name, pg_type_string) tuples.
    """
    columns = []
    for field in schema:
        pg_type = _pa_type_to_pg(field.type)
        columns.append((field.name, pg_type))
    return columns


def schema_to_create_table_sql(
    table_name: str,
    schema: pa.Schema,
    unique_columns: Optional[List[str]] = None,
) -> str:
    """Generate a CREATE TABLE IF NOT EXISTS SQL statement from a PyArrow schema.

    Args:
        table_name: Name of the PostgreSQL table.
        schema: PyArrow schema describing the table columns.
        unique_columns: Optional list of column names that should have UNIQUE
            constraints.  Required for ``ON CONFLICT`` upsert operations.

    Returns:
        A CREATE TABLE SQL string.
    """
    _validate_identifier(table_name)
    unique_set = set(unique_columns) if unique_columns else set()
    if unique_set:
        unknown = unique_set.difference(schema.names)
        if unknown:
            raise ValueError(
                f"Unknown unique_columns for table '{table_name}': {sorted(unknown)}"
            )
    columns = schema_to_columns(schema)
    col_defs = []
    for name, pg_type in columns:
        _validate_column_name(name)
        suffix = " UNIQUE" if name in unique_set else ""
        col_defs.append(f"    {name} {pg_type}{suffix}")
    return (
        f"CREATE TABLE IF NOT EXISTS {table_name} (\n"
        + ",\n".join(col_defs)
        + "\n)"
    )
