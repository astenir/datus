# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import pytest

from datus_spark import SparkConfig, SparkConnector

# ==================== Database Tests ====================


@pytest.mark.integration
@pytest.mark.acceptance
def test_get_databases(connector: SparkConnector):
    """Test getting list of databases."""
    databases = connector.get_databases()
    assert isinstance(databases, list)
    assert len(databases) > 0


@pytest.mark.integration
def test_get_databases_exclude_system(connector: SparkConnector):
    """Test that system databases are excluded by default."""
    databases = connector.get_databases(include_sys=False)
    assert "information_schema" not in databases


@pytest.mark.integration
def test_get_schemas_returns_empty(connector: SparkConnector):
    """Test that get_schemas returns empty list."""
    schemas = connector.get_schemas()
    assert schemas == []


# ==================== Table Metadata Tests ====================


@pytest.mark.integration
@pytest.mark.acceptance
def test_get_tables(connector: SparkConnector, config: SparkConfig):
    """Test getting table list."""
    db = config.database or "default"
    tables = connector.get_tables(database_name=db)
    assert isinstance(tables, list)


@pytest.mark.integration
def test_get_views(connector: SparkConnector, config: SparkConfig):
    """Test getting view list."""
    db = config.database or "default"
    views = connector.get_views(database_name=db)
    assert isinstance(views, list)


# ==================== Sample Data Tests ====================


@pytest.mark.integration
@pytest.mark.acceptance
def test_get_sample_rows(connector: SparkConnector):
    """Test getting sample rows."""
    sample_rows = connector.get_sample_rows()
    assert isinstance(sample_rows, list)
