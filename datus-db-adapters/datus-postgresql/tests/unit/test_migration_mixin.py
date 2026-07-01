# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Tests for PostgreSQL MigrationTargetMixin implementation."""

import pytest

from datus_db_core import MigrationTargetMixin
from datus_postgresql import PostgreSQLConnector


@pytest.fixture
def connector():
    return PostgreSQLConnector.__new__(PostgreSQLConnector)


class TestMixinInheritance:
    def test_postgresql_is_migration_target(self, connector):
        assert isinstance(connector, MigrationTargetMixin)


class TestDescribeMigrationCapabilities:
    def test_supported_true(self, connector):
        result = connector.describe_migration_capabilities()
        assert result["supported"] is True

    def test_dialect_family_postgres_like(self, connector):
        result = connector.describe_migration_capabilities()
        assert result["dialect_family"] == "postgres-like"

    def test_no_hard_requirements(self, connector):
        """Postgres is OLTP — no distribution/partition required."""
        result = connector.describe_migration_capabilities()
        assert result["requires"] == []

    def test_type_hints_mention_text_over_varchar(self, connector):
        result = connector.describe_migration_capabilities()
        hints_str = " ".join(result["type_hints"].values()).upper()
        assert "TEXT" in hints_str

    def test_example_ddl_is_simple(self, connector):
        result = connector.describe_migration_capabilities()
        ddl = result["example_ddl"].upper()
        assert "CREATE TABLE" in ddl
        # Should NOT contain DUPLICATE KEY or BUCKETS
        assert "DUPLICATE KEY" not in ddl
        assert "BUCKETS" not in ddl


class TestValidateDdl:
    def test_accepts_standard_postgres_ddl(self, connector):
        ddl = "CREATE TABLE public.t (id BIGSERIAL PRIMARY KEY, name VARCHAR(255))"
        assert connector.validate_ddl(ddl) == []

    def test_rejects_duplicate_key_starrocks_syntax(self, connector):
        ddl = """CREATE TABLE public.t (id BIGINT)
        DUPLICATE KEY(id)
        DISTRIBUTED BY HASH(id) BUCKETS 10"""
        errors = connector.validate_ddl(ddl)
        assert any("DUPLICATE KEY" in e.upper() or "STARROCKS" in e.upper() for e in errors)

    def test_rejects_distributed_by_hash_buckets(self, connector):
        ddl = "CREATE TABLE public.t (id BIGINT) DISTRIBUTED BY HASH(id) BUCKETS 10"
        errors = connector.validate_ddl(ddl)
        assert any("BUCKETS" in e.upper() or "STARROCKS" in e.upper() for e in errors)


class TestSuggestTableLayout:
    def test_returns_empty_dict(self, connector):
        """Postgres doesn't need distribution keys — OLTP."""
        columns = [
            {"name": "id", "type": "BIGINT", "nullable": False},
            {"name": "name", "type": "VARCHAR", "nullable": True},
        ]
        layout = connector.suggest_table_layout(columns)
        assert layout == {}


class TestMapSourceType:
    def test_hugeint_to_numeric(self, connector):
        assert connector.map_source_type("duckdb", "HUGEINT") == "NUMERIC(38,0)"

    def test_largeint_to_numeric(self, connector):
        """StarRocks LARGEINT has no direct Postgres equivalent."""
        assert connector.map_source_type("starrocks", "LARGEINT") == "NUMERIC(38,0)"

    def test_unknown_returns_none(self, connector):
        assert connector.map_source_type("duckdb", "VARCHAR") is None
