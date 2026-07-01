# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Tests for Redshift MigrationTargetMixin implementation."""

import pytest

from datus_db_core import MigrationTargetMixin
from datus_redshift import RedshiftConnector


@pytest.fixture
def connector():
    return RedshiftConnector.__new__(RedshiftConnector)


class TestMixinInheritance:
    def test_redshift_is_migration_target(self, connector):
        assert isinstance(connector, MigrationTargetMixin)


class TestDescribeMigrationCapabilities:
    def test_supported_true(self, connector):
        assert connector.describe_migration_capabilities()["supported"] is True

    def test_dialect_family_redshift(self, connector):
        assert connector.describe_migration_capabilities()["dialect_family"] == "redshift"

    def test_type_hints_mention_distkey_sortkey(self, connector):
        hints = connector.describe_migration_capabilities()["type_hints"]
        hints_str = " ".join(hints.values()).upper()
        assert "DISTKEY" in hints_str or "SORTKEY" in hints_str

    def test_forbids_varchar_max(self, connector):
        """Redshift does not support VARCHAR(max); length must be explicit."""
        result = connector.describe_migration_capabilities()
        forbids_str = " ".join(result["forbids"]).upper()
        assert "VARCHAR(MAX)" in forbids_str or "VARCHAR MAX" in forbids_str

    def test_example_ddl_references_distkey(self, connector):
        ddl = connector.describe_migration_capabilities()["example_ddl"].upper()
        assert "DISTKEY" in ddl


class TestValidateDdl:
    def test_accepts_standard_redshift_ddl(self, connector):
        ddl = """CREATE TABLE public.t (
          id BIGINT IDENTITY(1,1),
          dt DATE
        ) DISTKEY(id) SORTKEY(dt)"""
        assert connector.validate_ddl(ddl) == []

    def test_rejects_serial(self, connector):
        """Redshift uses IDENTITY instead of SERIAL."""
        ddl = "CREATE TABLE public.t (id SERIAL PRIMARY KEY, name VARCHAR(255))"
        errors = connector.validate_ddl(ddl)
        assert any("SERIAL" in e.upper() or "IDENTITY" in e.upper() for e in errors)

    def test_rejects_varchar_max(self, connector):
        ddl = "CREATE TABLE public.t (id BIGINT, name VARCHAR(MAX))"
        errors = connector.validate_ddl(ddl)
        assert any("VARCHAR" in e.upper() and "MAX" in e.upper() for e in errors)

    def test_rejects_starrocks_distributed_by(self, connector):
        ddl = "CREATE TABLE t (id BIGINT) DUPLICATE KEY(id) DISTRIBUTED BY HASH(id) BUCKETS 10"
        errors = connector.validate_ddl(ddl)
        assert any("DUPLICATE KEY" in e.upper() or "STARROCKS" in e.upper() for e in errors)

    def test_rejects_engine_clickhouse(self, connector):
        ddl = "CREATE TABLE t (id BIGINT) ENGINE = MergeTree() ORDER BY id"
        errors = connector.validate_ddl(ddl)
        assert any("ENGINE" in e.upper() or "CLICKHOUSE" in e.upper() for e in errors)


class TestSuggestTableLayout:
    def test_suggests_distkey_id_and_sortkey_date(self, connector):
        columns = [
            {"name": "id", "type": "BIGINT", "nullable": False},
            {"name": "event_date", "type": "DATE", "nullable": False},
            {"name": "amount", "type": "DECIMAL(10,2)", "nullable": True},
        ]
        layout = connector.suggest_table_layout(columns)
        assert layout["distkey"] == "id"
        assert "event_date" in layout.get("sortkey", [])

    def test_distkey_falls_back_to_first_column(self, connector):
        columns = [
            {"name": "region", "type": "VARCHAR", "nullable": False},
            {"name": "city", "type": "VARCHAR", "nullable": True},
        ]
        layout = connector.suggest_table_layout(columns)
        assert layout["distkey"] == "region"

    def test_empty_columns_returns_dict(self, connector):
        assert isinstance(connector.suggest_table_layout([]), dict)


class TestMapSourceType:
    def test_hugeint_to_numeric(self, connector):
        assert connector.map_source_type("duckdb", "HUGEINT") == "NUMERIC(38,0)"

    def test_json_to_super(self, connector):
        """Redshift has SUPER for semi-structured data."""
        assert connector.map_source_type("postgresql", "JSON") == "SUPER"

    def test_jsonb_to_super(self, connector):
        assert connector.map_source_type("postgresql", "JSONB") == "SUPER"

    def test_unknown_returns_none(self, connector):
        assert connector.map_source_type("duckdb", "VARCHAR") is None
