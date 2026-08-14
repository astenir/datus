"""Business-datasource read-only decisions shared by API and Agent tools."""

from __future__ import annotations

import re
from dataclasses import dataclass

import sqlglot
from sqlglot import expressions

from datus.utils.constants import SQLType
from datus.utils.sql_utils import (
    _normalize_expression,
    _split_sql_statements,
    parse_dialect,
    parse_sql_statement_kind,
    strip_sql_comments,
)

ENTERPRISE_BUSINESS_DATASOURCE_READ_ONLY = "ENTERPRISE_BUSINESS_DATASOURCE_READ_ONLY"
_READ_ONLY_KINDS = {SQLType.SELECT.value, SQLType.METADATA_SHOW.value, SQLType.EXPLAIN.value}
_EXPLAIN_PREFIX_RE = re.compile(
    r"^EXPLAIN\s+(?:(?:ANALYZE|ANALYSE|VERBOSE)\s+|\([^)]*\)\s+)*(?P<statement>.+)$",
    flags=re.IGNORECASE | re.DOTALL,
)
_LEADING_KEYWORD_RE = re.compile(r"^\s*([A-Za-z_]+)")
_MUTATING_SELECT_FUNCTIONS = {
    "GET_LOCK",
    "NEXTVAL",
    "PG_ADVISORY_LOCK",
    "PG_ADVISORY_XACT_LOCK",
    "RELEASE_LOCK",
    "SETVAL",
}


@dataclass(frozen=True)
class BusinessDatasourceReadOnlyDecision:
    """Whether one SQL input is safe for an enterprise business datasource."""

    allowed: bool
    statement_kind: str
    operation: str
    reason: str


def evaluate_business_datasource_read_only_sql(
    sql: str,
    dialect: str = "",
) -> BusinessDatasourceReadOnlyDecision:
    """Fail closed unless every statement in ``sql`` is a read-only statement.

    Multi-statement input is allowed only when *each* statement is read-only;
    any write / DDL / context mutation among the statements denies the whole
    batch (with that statement's operation, so the denial message stays specific).
    """

    if not isinstance(sql, str) or not sql.strip():
        return _deny(SQLType.UNKNOWN.value, "UNKNOWN", "empty_or_invalid")

    cleaned = strip_sql_comments(sql).strip()
    normalized = cleaned.rstrip(";").strip()
    if not normalized:
        return _deny(SQLType.UNKNOWN.value, "UNKNOWN", "empty_or_invalid")

    statements = _split_sql_statements(normalized)
    if len(statements) > 1:
        for statement in statements:
            decision = _evaluate_single_read_only(statement, dialect)
            if not decision.allowed:
                return decision
        return BusinessDatasourceReadOnlyDecision(True, SQLType.SELECT.value, "SELECT", "read_only")

    return _evaluate_single_read_only(normalized, dialect)


def _evaluate_single_read_only(normalized: str, dialect: str) -> BusinessDatasourceReadOnlyDecision:
    """Evaluate one non-empty, single statement for read-only safety."""

    kind = parse_sql_statement_kind(normalized, dialect)
    operation = _operation_label(normalized, kind)
    if kind not in _READ_ONLY_KINDS:
        return _deny(kind, operation, "non_read_statement")

    if kind == SQLType.METADATA_SHOW.value:
        if operation == "PRAGMA" and "=" in normalized:
            return _deny(kind, operation, "writable_pragma")
        return BusinessDatasourceReadOnlyDecision(True, kind, operation, "read_only")

    if kind == SQLType.EXPLAIN.value:
        match = _EXPLAIN_PREFIX_RE.match(normalized)
        if match is None:
            return _deny(SQLType.UNKNOWN.value, "EXPLAIN", "unparseable_explain")
        inner = evaluate_business_datasource_read_only_sql(match.group("statement"), dialect)
        if not inner.allowed:
            return _deny(inner.statement_kind, inner.operation, "explain_non_read_statement")
        return BusinessDatasourceReadOnlyDecision(True, kind, "EXPLAIN", "read_only")

    side_effect_operation = _select_side_effect_operation(normalized, dialect)
    if side_effect_operation is not None:
        return _deny(kind, side_effect_operation or operation, "select_has_side_effect")
    return BusinessDatasourceReadOnlyDecision(True, kind, operation, "read_only")


def business_datasource_read_only_message(operation: str) -> str:
    """Return the user-safe, operation-specific enterprise denial copy."""

    normalized = str(operation or "UNKNOWN").strip().upper() or "UNKNOWN"
    if normalized == "DELETE":
        action = "删除业务数据"
    elif normalized == "INSERT":
        action = "新增业务数据"
    elif normalized == "UPDATE":
        action = "修改业务数据"
    elif normalized in {"MERGE", "REPLACE"}:
        action = "变更业务数据"
    elif normalized == "TRUNCATE":
        action = "清空业务数据"
    elif normalized == "DROP":
        action = "删除业务对象"
    elif normalized in {"CREATE", "ALTER", "RENAME"}:
        action = "变更业务库表结构"
    elif normalized == "MULTI_STATEMENT":
        return (
            "企业模式下业务数据源仅支持单条只读查询，当前多语句 SQL 未执行。"
            "请仅提交一条 SELECT、SHOW、DESCRIBE 或安全的 EXPLAIN 查询。"
        )
    elif normalized == "UNKNOWN":
        return (
            "企业模式下业务数据源仅支持只读查询。当前 SQL 无法确认为安全的只读查询，因此未执行。"
            "如需执行该操作，请通过受控的数据维护流程联系管理员。"
        )
    else:
        action = "执行数据写入或结构变更"

    return (
        f"企业模式下业务数据源仅支持只读查询，{normalized} 操作未执行。"
        f"如需{action}，请通过受控的数据维护流程联系管理员。"
    )


def _deny(kind: str, operation: str, reason: str) -> BusinessDatasourceReadOnlyDecision:
    return BusinessDatasourceReadOnlyDecision(False, kind, operation, reason)


def _operation_label(sql: str, kind: str) -> str:
    match = _LEADING_KEYWORD_RE.match(sql)
    keyword = match.group(1).upper() if match else ""
    if keyword == "WITH" and kind != SQLType.SELECT.value:
        return kind.upper()
    if keyword:
        return keyword
    return kind.upper() if kind and kind != SQLType.UNKNOWN.value else "UNKNOWN"


def _select_side_effect_operation(sql: str, dialect: str) -> str | None:
    try:
        parsed = sqlglot.parse_one(
            sql,
            dialect=parse_dialect(dialect),
            error_level=sqlglot.ErrorLevel.RAISE,
        )
    except Exception:
        return "UNKNOWN"

    root = _normalize_expression(parsed)
    if not isinstance(root, (expressions.Query, expressions.Values)):
        return "UNKNOWN"

    forbidden_operations = (
        ("Alter", "ALTER"),
        ("Copy", "COPY"),
        ("Create", "CREATE"),
        ("Delete", "DELETE"),
        ("Drop", "DROP"),
        ("Grant", "GRANT"),
        ("Insert", "INSERT"),
        ("Into", "SELECT"),
        ("Lock", "SELECT"),
        ("Merge", "MERGE"),
        ("Set", "SET"),
        ("TruncateTable", "TRUNCATE"),
        ("Update", "UPDATE"),
        ("Use", "USE"),
    )
    for name, operation in forbidden_operations:
        expression_type = getattr(expressions, name, None)
        if expression_type is not None and root.find(expression_type) is not None:
            return operation

    for node in root.find_all(expressions.Anonymous):
        if str(node.name or "").upper() in _MUTATING_SELECT_FUNCTIONS:
            return "SELECT"
    return None
