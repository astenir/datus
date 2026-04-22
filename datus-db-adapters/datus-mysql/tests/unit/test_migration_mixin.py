# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Tests for MySQL MigrationTargetMixin implementation."""

import pytest

from datus_db_core import MigrationTargetMixin
from datus_mysql import MySQLConnector


@pytest.fixture
def connector():
    return MySQLConnector.__new__(MySQLConnector)


class TestMixinInheritance:
    def test_mysql_is_migration_target(self, connector):
        assert isinstance(connector, MigrationTargetMixin)


class TestDescribeMigrationCapabilities:
    def test_supported_true(self, connector):
        assert connector.describe_migration_capabilities()["supported"] is True

    def test_dialect_family_mysql_like(self, connector):
        assert connector.describe_migration_capabilities()["dialect_family"] == "mysql-like"

    def test_no_hard_requirements(self, connector):
        assert connector.describe_migration_capabilities()["requires"] == []

    def test_type_hints_boolean_to_tinyint(self, connector):
        hints = connector.describe_migration_capabilities()["type_hints"]
        hints_str = " ".join(hints.values()).upper()
        assert "TINYINT" in hints_str

    def test_example_ddl_has_engine_innodb(self, connector):
        ddl = connector.describe_migration_capabilities()["example_ddl"].upper()
        assert "ENGINE=INNODB" in ddl.replace(" ", "") or "ENGINE = INNODB" in ddl


class TestValidateDdl:
    def test_accepts_standard_mysql_ddl(self, connector):
        ddl = "CREATE TABLE db.t (id BIGINT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(255)) ENGINE=InnoDB"
        assert connector.validate_ddl(ddl) == []

    def test_rejects_duplicate_key_starrocks(self, connector):
        ddl = """CREATE TABLE db.t (id BIGINT)
        DUPLICATE KEY(id)
        DISTRIBUTED BY HASH(id) BUCKETS 10"""
        errors = connector.validate_ddl(ddl)
        assert any("DUPLICATE KEY" in e.upper() or "STARROCKS" in e.upper() for e in errors)

    def test_rejects_distributed_by_buckets(self, connector):
        ddl = "CREATE TABLE db.t (id BIGINT) DISTRIBUTED BY HASH(id) BUCKETS 10"
        errors = connector.validate_ddl(ddl)
        assert any("BUCKETS" in e.upper() or "STARROCKS" in e.upper() for e in errors)


class TestSuggestTableLayout:
    def test_returns_empty_dict(self, connector):
        columns = [{"name": "id", "type": "BIGINT", "nullable": False}]
        assert connector.suggest_table_layout(columns) == {}


class TestMapSourceType:
    def test_hugeint_to_decimal(self, connector):
        assert connector.map_source_type("duckdb", "HUGEINT") == "DECIMAL(38,0)"

    def test_largeint_to_decimal(self, connector):
        assert connector.map_source_type("starrocks", "LARGEINT") == "DECIMAL(38,0)"

    def test_unknown_returns_none(self, connector):
        assert connector.map_source_type("duckdb", "VARCHAR") is None
