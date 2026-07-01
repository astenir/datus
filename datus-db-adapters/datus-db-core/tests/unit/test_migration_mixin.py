# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Tests for MigrationTargetMixin interface contract."""

import pytest

from datus_db_core.migration import MigrationTargetMixin


class _MinimalImpl(MigrationTargetMixin):
    """Minimal concrete implementation for testing default method behavior."""

    def describe_migration_capabilities(self) -> dict:
        return {"supported": True, "dialect_family": "test"}


class _FullImpl(MigrationTargetMixin):
    """Concrete impl that overrides every optional method."""

    def describe_migration_capabilities(self) -> dict:
        return {"supported": True, "dialect_family": "custom"}

    def map_source_type(self, source_dialect: str, source_type: str):
        return f"{source_dialect}->{source_type}"

    def suggest_table_layout(self, columns):
        return {"primary_key": [columns[0]["name"]]} if columns else {}

    def validate_ddl(self, ddl: str):
        return ["has DROP TABLE"] if "DROP TABLE" in ddl else []

    def dry_run_ddl(self, ddl: str, target_table: str):
        return []


class TestAbstractContract:
    def test_cannot_instantiate_without_describe(self):
        """MigrationTargetMixin requires describe_migration_capabilities."""
        with pytest.raises(TypeError):
            MigrationTargetMixin()  # abstract

    def test_concrete_impl_can_be_instantiated(self):
        impl = _MinimalImpl()
        assert isinstance(impl, MigrationTargetMixin)


class TestDefaultMethodBehavior:
    """Optional methods must have sensible defaults so adapters can skip them."""

    def test_map_source_type_returns_none_by_default(self):
        impl = _MinimalImpl()
        assert impl.map_source_type("duckdb", "VARCHAR") is None

    def test_suggest_table_layout_returns_empty_dict(self):
        impl = _MinimalImpl()
        assert impl.suggest_table_layout([{"name": "id", "type": "INT"}]) == {}

    def test_validate_ddl_returns_empty_list(self):
        impl = _MinimalImpl()
        assert impl.validate_ddl("CREATE TABLE t (id INT)") == []

    def test_dry_run_ddl_raises_not_implemented(self):
        impl = _MinimalImpl()
        with pytest.raises(NotImplementedError):
            impl.dry_run_ddl("CREATE TABLE t (id INT)", "t")


class TestDescribeContract:
    def test_describe_returns_dict(self):
        impl = _MinimalImpl()
        result = impl.describe_migration_capabilities()
        assert isinstance(result, dict)

    def test_describe_should_have_supported_key(self):
        impl = _MinimalImpl()
        result = impl.describe_migration_capabilities()
        assert "supported" in result


class TestFullOverride:
    """If an adapter overrides everything, its overrides win."""

    def test_map_source_type_override(self):
        impl = _FullImpl()
        assert impl.map_source_type("mysql", "BIGINT") == "mysql->BIGINT"

    def test_suggest_table_layout_override(self):
        impl = _FullImpl()
        assert impl.suggest_table_layout([{"name": "pk", "type": "BIGINT"}]) == {"primary_key": ["pk"]}

    def test_validate_ddl_override(self):
        impl = _FullImpl()
        assert impl.validate_ddl("DROP TABLE t") == ["has DROP TABLE"]
        assert impl.validate_ddl("CREATE TABLE t (id INT)") == []

    def test_dry_run_ddl_override_does_not_raise(self):
        impl = _FullImpl()
        assert impl.dry_run_ddl("CREATE TABLE t (id INT)", "t") == []
