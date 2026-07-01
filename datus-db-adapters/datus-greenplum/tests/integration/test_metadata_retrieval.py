# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import uuid

import pytest

from datus_greenplum import GreenplumConfig, GreenplumConnector

# ==================== Database Tests ====================


@pytest.mark.integration
@pytest.mark.acceptance
def test_get_databases(connector: GreenplumConnector):
    """Test getting list of databases."""
    databases = connector.get_databases()
    assert isinstance(databases, list)
    assert len(databases) > 0


@pytest.mark.integration
def test_get_databases_exclude_system(connector: GreenplumConnector):
    """Test that system databases are excluded by default."""
    databases = connector.get_databases(include_sys=False)
    system_dbs = {"template0", "template1", "gpperfmon"}
    for db in databases:
        assert db not in system_dbs


# ==================== Schema Tests ====================


@pytest.mark.integration
@pytest.mark.acceptance
def test_get_schemas(connector: GreenplumConnector):
    """Test getting list of schemas."""
    schemas = connector.get_schemas()
    assert isinstance(schemas, list)
    assert len(schemas) > 0
    assert "public" in schemas


@pytest.mark.integration
def test_get_schemas_exclude_system(connector: GreenplumConnector):
    """Test that system schemas are excluded by default."""
    schemas = connector.get_schemas(include_sys=False)
    system_schemas = {"pg_catalog", "information_schema", "pg_toast", "gp_toolkit", "pg_aoseg", "pg_bitmapindex"}
    for schema in schemas:
        assert schema not in system_schemas


# ==================== Table Metadata Tests ====================


@pytest.mark.integration
@pytest.mark.acceptance
def test_get_tables(connector: GreenplumConnector, config: GreenplumConfig):
    """Test getting table list."""
    tables = connector.get_tables(schema_name=config.schema_name)
    assert isinstance(tables, list)


@pytest.mark.integration
def test_get_tables_with_ddl(connector: GreenplumConnector, config: GreenplumConfig):
    """Test getting tables with DDL."""
    suffix = uuid.uuid4().hex[:8]
    table_name = f"test_table_{suffix}"

    connector.execute_ddl(f"DROP TABLE IF EXISTS {table_name}")
    connector.execute_ddl(
        f"""
        CREATE TABLE {table_name} (
            id SERIAL PRIMARY KEY,
            name VARCHAR(50)
        )
    """
    )

    try:
        tables = connector.get_tables_with_ddl(schema_name=config.schema_name, tables=[table_name])

        if len(tables) > 0:
            table = tables[0]
            assert "table_name" in table
            assert "definition" in table
            assert table["table_type"] == "table"
            assert "schema_name" in table
            assert "identifier" in table
    finally:
        connector.execute_ddl(f"DROP TABLE IF EXISTS {table_name}")


# ==================== View Tests ====================


@pytest.mark.integration
def test_get_views(connector: GreenplumConnector, config: GreenplumConfig):
    """Test getting view list."""
    views = connector.get_views(schema_name=config.schema_name)
    assert isinstance(views, list)


@pytest.mark.integration
def test_get_views_with_ddl(connector: GreenplumConnector, config: GreenplumConfig):
    """Test getting views with DDL."""
    suffix = uuid.uuid4().hex[:8]
    view_name = f"test_view_{suffix}"
    table_name = f"test_table_{suffix}"

    connector.execute_ddl(f"DROP VIEW IF EXISTS {view_name}")
    connector.execute_ddl(f"DROP TABLE IF EXISTS {table_name}")
    connector.execute_ddl(
        f"""
        CREATE TABLE {table_name} (
            id SERIAL PRIMARY KEY,
            name VARCHAR(50)
        )
    """
    )

    try:
        connector.execute_ddl(f"CREATE VIEW {view_name} AS SELECT * FROM {table_name}")

        views = connector.get_views_with_ddl(schema_name=config.schema_name)

        if len(views) > 0:
            view = [v for v in views if v["table_name"] == view_name]
            if view:
                assert "definition" in view[0]
                assert view[0]["table_type"] == "view"
    finally:
        connector.execute_ddl(f"DROP VIEW IF EXISTS {view_name}")
        connector.execute_ddl(f"DROP TABLE IF EXISTS {table_name}")


# ==================== Column Schema Tests ====================


@pytest.mark.integration
@pytest.mark.acceptance
def test_get_schema(connector: GreenplumConnector, config: GreenplumConfig):
    """Test getting table schema."""
    suffix = uuid.uuid4().hex[:8]
    table_name = f"test_schema_{suffix}"

    connector.execute_ddl(f"DROP TABLE IF EXISTS {table_name}")
    connector.execute_ddl(
        f"""
        CREATE TABLE {table_name} (
            id SERIAL PRIMARY KEY,
            name VARCHAR(50) NOT NULL,
            email VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    try:
        schema = connector.get_schema(schema_name=config.schema_name, table_name=table_name)

        assert len(schema) == 4

        # Check id column
        id_col = [col for col in schema if col["name"] == "id"][0]
        assert id_col["pk"] is True
        assert "int" in id_col["type"].lower()

        # Check name column
        name_col = [col for col in schema if col["name"] == "name"][0]
        assert name_col["nullable"] is False
    finally:
        connector.execute_ddl(f"DROP TABLE IF EXISTS {table_name}")


# ==================== Sample Data Tests ====================


@pytest.mark.integration
def test_get_sample_rows(connector: GreenplumConnector, config: GreenplumConfig):
    """Test getting sample rows."""
    suffix = uuid.uuid4().hex[:8]
    table_name = f"test_sample_{suffix}"

    connector.execute_ddl(f"DROP TABLE IF EXISTS {table_name}")
    connector.execute_ddl(
        f"""
        CREATE TABLE {table_name} (
            id SERIAL PRIMARY KEY,
            name VARCHAR(50)
        )
    """
    )

    try:
        connector.execute_insert(
            f"""
            INSERT INTO {table_name} (name) VALUES
            ('Alice'),
            ('Bob'),
            ('Charlie')
        """
        )

        sample_rows = connector.get_sample_rows(schema_name=config.schema_name, tables=[table_name], top_n=2)

        assert len(sample_rows) == 1
        assert sample_rows[0]["table_name"] == table_name
        assert "sample_rows" in sample_rows[0]
    finally:
        connector.execute_ddl(f"DROP TABLE IF EXISTS {table_name}")
