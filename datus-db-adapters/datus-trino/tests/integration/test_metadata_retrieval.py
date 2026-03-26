# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import pytest
from datus_trino import TrinoConfig, TrinoConnector

# ==================== Catalog Tests ====================


@pytest.mark.integration
@pytest.mark.acceptance
def test_get_catalogs(connector: TrinoConnector):
    """Test getting list of catalogs."""
    catalogs = connector.get_catalogs()
    assert len(catalogs) > 0
    assert isinstance(catalogs, list)


@pytest.mark.integration
@pytest.mark.acceptance
def test_default_catalog(connector: TrinoConnector):
    """Test default catalog value."""
    default = connector.default_catalog()
    assert isinstance(default, str)
    assert len(default) > 0


@pytest.mark.integration
def test_switch_catalog(connector: TrinoConnector):
    """Test switching catalogs."""
    original_catalog = connector.catalog_name
    catalogs = connector.get_catalogs()

    if len(catalogs) > 1:
        target_catalog = [c for c in catalogs if c != original_catalog][0]
        connector.switch_catalog(target_catalog)
        assert connector.catalog_name == target_catalog

        connector.switch_catalog(original_catalog)
        assert connector.catalog_name == original_catalog
    else:
        pytest.skip("Only one catalog available")


# ==================== Schema/Database Tests ====================


@pytest.mark.integration
@pytest.mark.acceptance
def test_get_schemas(connector: TrinoConnector, config: TrinoConfig):
    """Test getting list of schemas."""
    schemas = connector.get_schemas(catalog_name=config.catalog)
    assert isinstance(schemas, list)


@pytest.mark.integration
def test_get_databases(connector: TrinoConnector, config: TrinoConfig):
    """Test getting databases (same as schemas in Trino)."""
    databases = connector.get_databases(catalog_name=config.catalog)
    assert isinstance(databases, list)


@pytest.mark.integration
def test_get_schemas_exclude_system(connector: TrinoConnector, config: TrinoConfig):
    """Test that system schemas are excluded by default."""
    schemas = connector.get_schemas(catalog_name=config.catalog, include_sys=False)
    assert "information_schema" not in schemas


# ==================== Table Metadata Tests ====================


@pytest.mark.integration
@pytest.mark.acceptance
def test_get_tables(connector: TrinoConnector, config: TrinoConfig):
    """Test getting table list."""
    tables = connector.get_tables(
        catalog_name=config.catalog, schema_name=config.schema_name
    )
    assert isinstance(tables, list)


@pytest.mark.integration
def test_get_views(connector: TrinoConnector, config: TrinoConfig):
    """Test getting view list."""
    views = connector.get_views(
        catalog_name=config.catalog, schema_name=config.schema_name
    )
    assert isinstance(views, list)


# ==================== Sample Data Tests ====================


@pytest.mark.integration
@pytest.mark.acceptance
def test_get_sample_rows(connector: TrinoConnector):
    """Test getting sample rows."""
    sample_rows = connector.get_sample_rows()
    assert isinstance(sample_rows, list)
