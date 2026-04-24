# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Tests for the generic SQLAlchemy MigrationTargetMixin fallback.

This Mixin provides a conservative OLTP-style default. Adapters that inherit
from SQLAlchemyConnector (MySQL / Postgres / ClickHouse / ...) may override
any of the Mixin methods to encode their own dialect's contract — their
overrides take precedence over this generic baseline.
"""

import pytest

from datus_db_core import MigrationTargetMixin
from datus_sqlalchemy import SQLAlchemyConnector


class _ConcreteSQLA(SQLAlchemyConnector):
    """Minimal concrete subclass so we can exercise SQLAlchemyConnector's
    Mixin methods. ``SQLAlchemyConnector`` itself is abstract because it
    inherits several @abstractmethod declarations from ``BaseSqlConnector``
    (``get_databases``, ``get_tables``, etc). These stubs are never called
    by the Mixin methods under test."""

    def get_databases(self, *args, **kwargs):
        return []

    def get_tables(self, *args, **kwargs):
        return []

    def execute_insert(self, sql):
        raise NotImplementedError

    def execute_update(self, sql):
        raise NotImplementedError

    def execute_delete(self, sql):
        raise NotImplementedError

    def execute_query(self, *args, **kwargs):
        raise NotImplementedError

    def execute_pandas(self, sql):
        raise NotImplementedError

    def execute_ddl(self, sql):
        raise NotImplementedError

    def execute_csv(self, sql):
        raise NotImplementedError

    def test_connection(self):
        return True

    def execute_queries(self, queries):
        return []

    def execute_content_set(self, sql):
        raise NotImplementedError


@pytest.fixture
def connector():
    return _ConcreteSQLA.__new__(_ConcreteSQLA)


class TestMixinInheritance:
    def test_sqlalchemy_is_migration_target(self, connector):
        assert isinstance(connector, MigrationTargetMixin)


class TestDescribeMigrationCapabilities:
    def test_supported_true(self, connector):
        assert connector.describe_migration_capabilities()["supported"] is True

    def test_dialect_family_generic_sqlalchemy(self, connector):
        assert connector.describe_migration_capabilities()["dialect_family"] == "sqlalchemy-generic"

    def test_no_hard_requirements(self, connector):
        assert connector.describe_migration_capabilities()["requires"] == []

    def test_example_ddl_is_minimal_create_table(self, connector):
        ddl = connector.describe_migration_capabilities()["example_ddl"].upper()
        assert "CREATE TABLE" in ddl


class TestSuggestTableLayout:
    def test_returns_empty_dict_by_default(self, connector):
        """Generic SQLAlchemy fallback defers layout decisions to the LLM."""
        columns = [{"name": "id", "type": "BIGINT", "nullable": False}]
        assert connector.suggest_table_layout(columns) == {}


class TestValidateDdl:
    def test_accepts_plain_ddl(self, connector):
        assert connector.validate_ddl("CREATE TABLE t (id BIGINT)") == []

    def test_flags_starrocks_specific_syntax(self, connector):
        ddl = "CREATE TABLE t (id BIGINT) DUPLICATE KEY(id) DISTRIBUTED BY HASH(id) BUCKETS 10"
        errors = connector.validate_ddl(ddl)
        assert any(
            "DUPLICATE KEY" in e.upper() or "DISTRIBUTED BY" in e.upper() or "STARROCKS" in e.upper() for e in errors
        )


class TestInheritedOverridesWin:
    """Adapters that override Mixin methods must take precedence over this generic base."""

    def test_mysql_override_wins(self):
        from datus_mysql import MySQLConnector

        mysql = MySQLConnector.__new__(MySQLConnector)
        result = mysql.describe_migration_capabilities()
        # MySQL's own override sets dialect_family="mysql-like"
        assert result["dialect_family"] == "mysql-like"

    def test_postgres_override_wins(self):
        from datus_postgresql import PostgreSQLConnector

        pg = PostgreSQLConnector.__new__(PostgreSQLConnector)
        result = pg.describe_migration_capabilities()
        assert result["dialect_family"] == "postgres-like"
