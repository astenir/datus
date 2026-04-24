# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Tests for Greenplum MigrationTargetMixin implementation."""

import pytest

from datus_db_core import MigrationTargetMixin
from datus_greenplum import GreenplumConnector


@pytest.fixture
def connector():
    return GreenplumConnector.__new__(GreenplumConnector)


class TestMixinInheritance:
    def test_greenplum_is_migration_target(self, connector):
        assert isinstance(connector, MigrationTargetMixin)


class TestDescribeMigrationCapabilities:
    def test_supported_true(self, connector):
        result = connector.describe_migration_capabilities()
        assert result["supported"] is True

    def test_dialect_family_postgres_like(self, connector):
        result = connector.describe_migration_capabilities()
        assert result["dialect_family"] == "postgres-like"

    def test_mentions_distributed_by_as_recommended(self, connector):
        """DISTRIBUTED BY should be recommended in type_hints or example, but NOT required."""
        result = connector.describe_migration_capabilities()
        haystack = " ".join(
            [
                " ".join(result.get("requires", [])),
                " ".join(result.get("forbids", [])),
                " ".join(result.get("type_hints", {}).values()),
                result.get("example_ddl", ""),
            ]
        ).upper()
        assert "DISTRIBUTED BY" in haystack

    def test_distributed_by_not_hard_required(self, connector):
        result = connector.describe_migration_capabilities()
        requires_str = " ".join(result.get("requires", [])).upper()
        assert "DISTRIBUTED BY" not in requires_str

    def test_example_ddl_has_create_table(self, connector):
        result = connector.describe_migration_capabilities()
        assert "CREATE TABLE" in result["example_ddl"].upper()


class TestValidateDdl:
    def test_accepts_ddl_without_distributed_by(self, connector):
        """DISTRIBUTED BY is recommended, not required; should accept without it."""
        ddl = "CREATE TABLE public.t (id BIGINT NOT NULL, name VARCHAR(255))"
        assert connector.validate_ddl(ddl) == []

    def test_accepts_ddl_with_distributed_by(self, connector):
        ddl = "CREATE TABLE public.t (id BIGINT NOT NULL) DISTRIBUTED BY (id)"
        assert connector.validate_ddl(ddl) == []

    def test_rejects_starrocks_specific_syntax(self, connector):
        """Guard against cross-dialect mistakes."""
        ddl = """CREATE TABLE public.t (id BIGINT)
        DUPLICATE KEY(id)
        DISTRIBUTED BY HASH(id) BUCKETS 10"""
        errors = connector.validate_ddl(ddl)
        assert any("DUPLICATE KEY" in e.upper() or "STARROCKS" in e.upper() for e in errors)


class TestSuggestTableLayout:
    def test_suggests_distributed_by_id_column(self, connector):
        columns = [
            {"name": "id", "type": "BIGINT", "nullable": False},
            {"name": "name", "type": "VARCHAR", "nullable": True},
        ]
        layout = connector.suggest_table_layout(columns)
        assert "distributed_by" in layout
        assert layout["distributed_by"] == ["id"]

    def test_fallback_first_column_when_no_integer_key(self, connector):
        columns = [
            {"name": "code", "type": "VARCHAR", "nullable": False},
            {"name": "name", "type": "VARCHAR", "nullable": True},
        ]
        layout = connector.suggest_table_layout(columns)
        assert layout["distributed_by"] == ["code"]

    def test_empty_columns(self, connector):
        layout = connector.suggest_table_layout([])
        assert isinstance(layout, dict)


class TestMapSourceType:
    def test_hugeint_to_numeric(self, connector):
        assert connector.map_source_type("duckdb", "HUGEINT") == "NUMERIC(38,0)"

    def test_unknown_returns_none(self, connector):
        assert connector.map_source_type("duckdb", "VARCHAR") is None
