"""Downstream SQL source-table detection used by database scope enforcement."""

from __future__ import annotations

import re

_SQL_IDENTIFIER_RE = (
    r"(?:`[^`]+`|\"[^\"]+\"|\[[^\]]+\]|[A-Za-z_][A-Za-z0-9_$]*)"
    r"(?:\s*\.\s*(?:`[^`]+`|\"[^\"]+\"|\[[^\]]+\]|[A-Za-z_][A-Za-z0-9_$]*))*"
)
_SQL_IDENTIFIER_END_RE = r"(?=\s|$|;)"


def supplemental_table_names(sql: str) -> list[str]:
    """Return table names missed by generic SQL table extraction."""

    names: list[str] = []
    for name in (
        *_parenthesized_table_expression_names(sql),
        *_insert_table_expression_names(sql),
        *_ddl_as_table_names(sql),
        *_ddl_partition_table_names(sql),
    ):
        if name not in names:
            names.append(name)
    return names


def write_sql_reads_from_source(sql: str, dialect: str) -> bool:
    """Return whether an INSERT/UPDATE/DELETE statement reads source tables."""

    try:
        import sqlglot
        from sqlglot import expressions as exp

        from datus.utils.sql_utils import parse_read_dialect

        parsed = sqlglot.parse_one(
            sql,
            read=parse_read_dialect(dialect),
            error_level=sqlglot.ErrorLevel.IGNORE,
        )
        if not isinstance(parsed, (exp.Insert, exp.Update, exp.Delete)):
            return False
        if any(True for _ in parsed.find_all(exp.Select)):
            return True
        if _insert_table_expression_names(sql) or _parenthesized_table_expression_names(sql):
            return True
        if isinstance(parsed, (exp.Update, exp.Delete)):
            return sum(1 for _ in parsed.find_all(exp.Table)) > 1
        return False
    except Exception:
        return bool(
            re.search(r"\bSELECT\b", sql, re.IGNORECASE)
            or _insert_table_expression_names(sql)
            or _parenthesized_table_expression_names(sql)
            or re.search(r"^\s*UPDATE\b[\s\S]*\b(?:FROM|JOIN)\b", sql, re.IGNORECASE)
            or re.search(r"^\s*DELETE\b[\s\S]*\bUSING\b", sql, re.IGNORECASE)
        )


def ddl_sql_reads_from_source(sql: str, dialect: str) -> bool:
    """Return whether a DDL statement reads from an existing table."""

    try:
        import sqlglot
        from sqlglot import expressions as exp

        from datus.utils.sql_utils import parse_read_dialect

        parsed = sqlglot.parse_one(
            sql,
            read=parse_read_dialect(dialect),
            error_level=sqlglot.ErrorLevel.IGNORE,
        )
        if _parenthesized_table_expression_names(sql):
            return True
        if not isinstance(parsed, exp.Create):
            return bool(re.search(r"\bAS\s+(?:SELECT|TABLE)\b", sql, re.IGNORECASE))
        return any(any(True for _ in select.find_all(exp.Table)) for select in parsed.find_all(exp.Select))
    except Exception:
        return bool(
            re.search(r"\bAS\s+(?:SELECT|TABLE)\b", sql, re.IGNORECASE) or _parenthesized_table_expression_names(sql)
        )


def _ddl_as_table_names(sql: str) -> list[str]:
    match = re.search(
        rf"^\s*CREATE\s+(?:OR\s+REPLACE\s+)?(?:(?:TEMPORARY|TEMP)\s+)?(?:TABLE|VIEW)\s+"
        rf"(?:IF\s+NOT\s+EXISTS\s+)?(?P<target>{_SQL_IDENTIFIER_RE})(?:\s*\([^)]*\))?\s+"
        rf"AS\s+TABLE\s+(?:ONLY\s+)?(?P<source>{_SQL_IDENTIFIER_RE}){_SQL_IDENTIFIER_END_RE}",
        sql,
        re.IGNORECASE,
    )
    if not match:
        return []
    return [match.group("target"), match.group("source")]


def _ddl_partition_table_names(sql: str) -> list[str]:
    match = re.search(
        rf"^\s*ALTER\s+TABLE\s+(?P<target>{_SQL_IDENTIFIER_RE})\s+"
        rf"(?:ATTACH|DETACH)\s+PARTITION\s+(?P<partition>{_SQL_IDENTIFIER_RE}){_SQL_IDENTIFIER_END_RE}",
        sql,
        re.IGNORECASE,
    )
    if match:
        return [match.group("target"), match.group("partition")]
    match = re.search(
        rf"^\s*ALTER\s+TABLE\s+(?P<target>{_SQL_IDENTIFIER_RE})\s+"
        rf"EXCHANGE\s+PARTITION\s+{_SQL_IDENTIFIER_RE}\s+WITH\s+TABLE\s+"
        rf"(?P<table>{_SQL_IDENTIFIER_RE}){_SQL_IDENTIFIER_END_RE}",
        sql,
        re.IGNORECASE,
    )
    if match:
        return [match.group("target"), match.group("table")]
    return []


def _parenthesized_table_expression_names(sql: str) -> list[str]:
    return [
        match.group("source")
        for match in re.finditer(
            rf"\(\s*TABLE\s+(?P<source>{_SQL_IDENTIFIER_RE})(?=\s|\)|$|;)",
            sql,
            re.IGNORECASE,
        )
    ]


def _insert_table_expression_names(sql: str) -> list[str]:
    match = re.search(
        rf"^\s*INSERT\s+INTO\s+{_SQL_IDENTIFIER_RE}(?:\s*\([^)]*\))?\s+TABLE\s+"
        rf"(?P<source>{_SQL_IDENTIFIER_RE}){_SQL_IDENTIFIER_END_RE}",
        sql,
        re.IGNORECASE,
    )
    if not match:
        return []
    return [match.group("source")]
