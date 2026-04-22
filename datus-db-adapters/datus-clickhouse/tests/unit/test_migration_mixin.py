# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Tests for ClickHouse MigrationTargetMixin implementation."""

import pytest

from datus_clickhouse import ClickHouseConnector
from datus_db_core import MigrationTargetMixin


@pytest.fixture
def connector():
    return ClickHouseConnector.__new__(ClickHouseConnector)


class TestMixinInheritance:
    def test_clickhouse_is_migration_target(self, connector):
        assert isinstance(connector, MigrationTargetMixin)


class TestDescribeMigrationCapabilities:
    def test_supported_true(self, connector):
        assert connector.describe_migration_capabilities()["supported"] is True

    def test_dialect_family_clickhouse(self, connector):
        assert connector.describe_migration_capabilities()["dialect_family"] == "clickhouse"

    def test_requires_engine_and_order_by(self, connector):
        result = connector.describe_migration_capabilities()
        requires_str = " ".join(result["requires"]).upper()
        assert "ENGINE" in requires_str
        assert "ORDER BY" in requires_str

    def test_forbids_varchar_and_boolean(self, connector):
        """ClickHouse has String/UInt8 instead of VARCHAR/BOOLEAN."""
        result = connector.describe_migration_capabilities()
        forbids_str = " ".join(result["forbids"]).upper()
        assert "VARCHAR" in forbids_str
        assert "BOOLEAN" in forbids_str or "BOOL" in forbids_str

    def test_type_hints_reference_string_uint8(self, connector):
        hints = connector.describe_migration_capabilities()["type_hints"]
        hints_str = " ".join(hints.values())
        assert "String" in hints_str
        assert "UInt8" in hints_str

    def test_example_ddl_has_engine_merge_tree_and_order_by(self, connector):
        ddl = connector.describe_migration_capabilities()["example_ddl"]
        assert "MergeTree" in ddl
        upper = ddl.upper()
        assert "ORDER BY" in upper


class TestValidateDdl:
    def test_accepts_valid_merge_tree_ddl(self, connector):
        ddl = """CREATE TABLE db.t (
          id Int64,
          name String
        ) ENGINE = MergeTree() ORDER BY id"""
        assert connector.validate_ddl(ddl) == []

    def test_rejects_missing_engine(self, connector):
        ddl = """CREATE TABLE db.t (
          id Int64,
          name String
        ) ORDER BY id"""
        errors = connector.validate_ddl(ddl)
        assert any("ENGINE" in e.upper() for e in errors)

    def test_rejects_missing_order_by(self, connector):
        ddl = """CREATE TABLE db.t (
          id Int64,
          name String
        ) ENGINE = MergeTree()"""
        errors = connector.validate_ddl(ddl)
        assert any("ORDER BY" in e.upper() for e in errors)

    def test_rejects_varchar(self, connector):
        ddl = """CREATE TABLE db.t (
          id Int64,
          name VARCHAR(255)
        ) ENGINE = MergeTree() ORDER BY id"""
        errors = connector.validate_ddl(ddl)
        assert any("VARCHAR" in e.upper() or "STRING" in e.upper() for e in errors)

    def test_rejects_boolean_type(self, connector):
        ddl = """CREATE TABLE db.t (
          id Int64,
          active BOOLEAN
        ) ENGINE = MergeTree() ORDER BY id"""
        errors = connector.validate_ddl(ddl)
        assert any("BOOLEAN" in e.upper() or "UINT8" in e.upper() for e in errors)

    def test_rejects_starrocks_distributed_by(self, connector):
        ddl = """CREATE TABLE db.t (id Int64)
        DUPLICATE KEY(id)
        DISTRIBUTED BY HASH(id) BUCKETS 10"""
        errors = connector.validate_ddl(ddl)
        assert any("DUPLICATE KEY" in e.upper() or "DISTRIBUTED BY" in e.upper() for e in errors)


class TestSuggestTableLayout:
    def test_returns_engine_and_order_by(self, connector):
        columns = [
            {"name": "id", "type": "BIGINT", "nullable": False},
            {"name": "name", "type": "VARCHAR", "nullable": True},
        ]
        layout = connector.suggest_table_layout(columns)
        assert layout.get("engine") == "MergeTree()"
        assert "order_by" in layout
        assert layout["order_by"] == ["id"]

    def test_fallback_first_column_when_no_integer(self, connector):
        columns = [
            {"name": "code", "type": "VARCHAR", "nullable": False},
            {"name": "name", "type": "VARCHAR", "nullable": True},
        ]
        layout = connector.suggest_table_layout(columns)
        assert layout["order_by"] == ["code"]


class TestMapSourceType:
    def test_varchar_to_string(self, connector):
        assert connector.map_source_type("duckdb", "VARCHAR") == "String"

    def test_varchar_with_length_to_string(self, connector):
        assert connector.map_source_type("duckdb", "VARCHAR(255)") == "String"

    def test_text_to_string(self, connector):
        assert connector.map_source_type("duckdb", "TEXT") == "String"

    def test_boolean_to_uint8(self, connector):
        assert connector.map_source_type("duckdb", "BOOLEAN") == "UInt8"

    def test_timestamp_to_datetime64(self, connector):
        assert connector.map_source_type("duckdb", "TIMESTAMP") == "DateTime64(3)"

    def test_integer_to_int32(self, connector):
        assert connector.map_source_type("duckdb", "INTEGER") == "Int32"

    def test_bigint_to_int64(self, connector):
        assert connector.map_source_type("duckdb", "BIGINT") == "Int64"

    def test_unknown_returns_none(self, connector):
        assert connector.map_source_type("duckdb", "GEOMETRY") is None
