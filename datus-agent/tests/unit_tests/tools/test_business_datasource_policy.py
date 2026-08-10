"""Enterprise business-datasource read-only policy regressions."""

import pytest

from datus.tools.business_datasource_policy import (
    business_datasource_read_only_message,
    evaluate_business_datasource_read_only_sql,
)
from datus.tools.db_tools import connector_registry


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM users",
        "SHOW TABLES",
        "DESCRIBE users",
        "EXPLAIN SELECT * FROM users",
        "EXPLAIN ANALYZE SELECT * FROM users",
    ],
)
def test_allows_single_pure_read_statement(sql: str) -> None:
    assert evaluate_business_datasource_read_only_sql(sql).allowed is True


def test_allows_oceanbase_oracle_select_with_registered_parser_dialect(monkeypatch) -> None:
    original_get_parser_dialect = connector_registry.get_parser_dialect
    monkeypatch.setattr(
        connector_registry,
        "get_parser_dialect",
        lambda dialect: "oracle" if dialect == "oceanbase-oracle" else original_get_parser_dialect(dialect),
    )
    sql = (
        "SELECT DISTINCT DEPARTMENT_NAME FROM CRM_INST_CLIENT_DEPT_INFO "
        "WHERE IS_DELETED = 'O' OR IS_DELETED IS NULL ORDER BY DEPARTMENT_NAME"
    )

    first = evaluate_business_datasource_read_only_sql(sql, "oceanbase-oracle")
    following = evaluate_business_datasource_read_only_sql("SELECT 1 FROM DUAL", "oceanbase-oracle")

    assert first.allowed is True
    assert following.allowed is True


@pytest.mark.parametrize(
    ("database_dialect", "parser_dialect", "sql"),
    [
        (
            "greenplum",
            "postgres",
            "SELECT DISTINCT ON (department_id) department_id, name "
            "FROM departments ORDER BY department_id, updated_at DESC",
        ),
        ("clickzetta", "spark", "SELECT * EXCEPT(__change_type) FROM `orders_stream`"),
    ],
)
def test_registered_analytics_parser_allows_reads_and_rejects_writes(
    monkeypatch,
    database_dialect: str,
    parser_dialect: str,
    sql: str,
) -> None:
    original_get_parser_dialect = connector_registry.get_parser_dialect
    monkeypatch.setattr(
        connector_registry,
        "get_parser_dialect",
        lambda dialect: parser_dialect if dialect == database_dialect else original_get_parser_dialect(dialect),
    )

    read_decision = evaluate_business_datasource_read_only_sql(sql, database_dialect)
    write_decision = evaluate_business_datasource_read_only_sql("DELETE FROM orders", database_dialect)

    assert read_decision.allowed is True
    assert write_decision.allowed is False
    assert write_decision.operation == "DELETE"


@pytest.mark.parametrize(
    ("sql", "operation"),
    [
        ("INSERT INTO users VALUES (1)", "INSERT"),
        ("UPDATE users SET active = FALSE", "UPDATE"),
        ("DELETE FROM users WHERE id = 1", "DELETE"),
        ("MERGE INTO users USING staging ON users.id = staging.id", "MERGE"),
        ("REPLACE INTO users VALUES (1)", "REPLACE"),
        ("TRUNCATE TABLE users", "TRUNCATE"),
        ("CREATE TABLE archive (id INT)", "CREATE"),
        ("ALTER TABLE users ADD COLUMN note TEXT", "ALTER"),
        ("DROP TABLE users", "DROP"),
        ("CALL mutate_users()", "CALL"),
        ("SELECT 1; DELETE FROM users", "MULTI_STATEMENT"),
        ("EXPLAIN ANALYZE DELETE FROM users", "DELETE"),
        ("WITH removed AS (DELETE FROM users RETURNING *) SELECT * FROM removed", "DELETE"),
        ("SELECT * INTO archived_users FROM users", "SELECT"),
        ("SELECT * FROM users FOR UPDATE", "SELECT"),
        ("SELECT nextval('users_id_seq')", "SELECT"),
        ("FROBNICATE THE WIDGETS", "FROBNICATE"),
    ],
)
def test_rejects_mutating_or_unverifiable_statement(sql: str, operation: str) -> None:
    decision = evaluate_business_datasource_read_only_sql(sql)

    assert decision.allowed is False
    assert decision.operation == operation


def test_delete_message_matches_product_copy() -> None:
    assert business_datasource_read_only_message("DELETE") == (
        "企业模式下业务数据源仅支持只读查询，DELETE 操作未执行。如需删除业务数据，请通过受控的数据维护流程联系管理员。"
    )
