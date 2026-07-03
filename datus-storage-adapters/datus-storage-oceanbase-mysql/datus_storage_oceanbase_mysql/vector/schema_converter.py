"""PyArrow schema to OceanBase MySQL DDL conversion with VECTOR support."""

from __future__ import annotations

from typing import List, Optional, Tuple

import pyarrow as pa

from datus_storage_oceanbase_mysql.rdb.backend import _INDEXABLE_TEXT_TYPE, _quote_ident, _validate_identifier

_PA_TO_OB = {
    pa.string(): "LONGTEXT",
    pa.large_string(): "LONGTEXT",
    pa.utf8(): "LONGTEXT",
    pa.bool_(): "TINYINT(1)",
    pa.int8(): "SMALLINT",
    pa.int16(): "SMALLINT",
    pa.int32(): "INT",
    pa.int64(): "BIGINT",
    pa.uint8(): "SMALLINT UNSIGNED",
    pa.uint16(): "INT UNSIGNED",
    pa.uint32(): "BIGINT UNSIGNED",
    pa.uint64(): "DECIMAL(20,0)",
    pa.float16(): "FLOAT",
    pa.float32(): "FLOAT",
    pa.float64(): "DOUBLE",
    pa.date32(): "DATE",
    pa.date64(): "DATE",
}


def _pa_type_to_ob(pa_type: pa.DataType, *, indexed: bool = False) -> str:
    if isinstance(pa_type, pa.FixedSizeListType) and pa.types.is_floating(pa_type.value_type):
        return f"VECTOR({pa_type.list_size})"
    if isinstance(pa_type, pa.ListType) and pa.types.is_floating(pa_type.value_type):
        return "VECTOR"
    if isinstance(pa_type, pa.TimestampType):
        return "TIMESTAMP"
    if indexed and (pa.types.is_string(pa_type) or pa.types.is_large_string(pa_type)):
        return _INDEXABLE_TEXT_TYPE
    return _PA_TO_OB.get(pa_type, "LONGTEXT")


def schema_to_columns(schema: pa.Schema, indexed_columns: Optional[set[str]] = None) -> List[Tuple[str, str]]:
    indexed_columns = indexed_columns or set()
    columns = []
    for field in schema:
        _validate_identifier(field.name)
        columns.append((field.name, _pa_type_to_ob(field.type, indexed=field.name in indexed_columns)))
    return columns


def schema_to_create_table_sql(
    database_name: str,
    table_name: str,
    schema: pa.Schema,
    indexed_columns: Optional[set[str]] = None,
) -> str:
    _validate_identifier(database_name)
    _validate_identifier(table_name)
    col_defs = [f"    {_quote_ident(name)} {ob_type}" for name, ob_type in schema_to_columns(schema, indexed_columns)]
    qualified = f"{_quote_ident(database_name)}.{_quote_ident(table_name)}"
    return f"CREATE TABLE IF NOT EXISTS {qualified} (\n" + ",\n".join(col_defs) + "\n) ORGANIZATION HEAP"
