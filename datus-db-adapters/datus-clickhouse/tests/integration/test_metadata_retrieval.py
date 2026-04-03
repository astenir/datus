# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import uuid

import pytest

from datus_clickhouse import ClickHouseConfig, ClickHouseConnector

# ==================== Database Tests ====================


@pytest.mark.integration
@pytest.mark.acceptance
def test_get_databases(connector: ClickHouseConnector):
    """Test getting list of databases."""
    databases = connector.get_databases()
    assert isinstance(databases, list)
    assert len(databases) > 0


@pytest.mark.integration
def test_get_databases_exclude_system(connector: ClickHouseConnector):
    """Test that system databases are excluded by default."""
    databases = connector.get_databases(include_sys=False)
    system_dbs = {"INFORMATION_SCHEMA", "information_schema", "system"}
    for db in databases:
        assert db not in system_dbs


# ==================== Table Metadata Tests ====================


@pytest.mark.integration
@pytest.mark.acceptance
def test_get_tables(connector: ClickHouseConnector, config: ClickHouseConfig):
    """Test getting table list."""
    tables = connector.get_tables(database_name=config.database)
    assert isinstance(tables, list)


@pytest.mark.integration
def test_get_tables_with_ddl(connector: ClickHouseConnector, config: ClickHouseConfig):
    """Test getting tables with DDL."""
    suffix = uuid.uuid4().hex[:8]
    table_name = f"test_table_{suffix}"

    connector.switch_context(database_name=config.database)
    connector.execute_ddl(
        f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            `id` Int64,
            `name` Nullable(String)
            ) ENGINE = MergeTree()
            ORDER BY id
    """
    )

    try:
        tables = connector.get_tables_with_ddl(database_name=config.database, tables=[table_name])

        if len(tables) > 0:
            table = tables[0]
            assert "table_name" in table
            assert "definition" in table
            assert table["table_type"] == "table"
            assert "database_name" in table
            assert table["schema_name"] == ""
            assert "identifier" in table
    finally:
        connector.execute_ddl(f"DROP TABLE IF EXISTS {table_name}")


# ==================== View Tests ====================


@pytest.mark.integration
def test_get_views(connector: ClickHouseConnector, config: ClickHouseConfig):
    """Test getting view list."""
    views = connector.get_views(database_name=config.database)
    assert isinstance(views, list)


@pytest.mark.integration
def test_get_views_with_ddl(connector: ClickHouseConnector, config: ClickHouseConfig):
    """Test getting views with DDL."""
    suffix = uuid.uuid4().hex[:8]
    view_name = f"test_view_{suffix}"
    table_name = f"test_table_{suffix}"

    connector.switch_context(database_name=config.database)

    # Create base table
    connector.execute_ddl(
        f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
             `id` Int64,
            `name` Nullable(String)
            ) ENGINE = MergeTree()
            ORDER BY id
    """
    )

    # Create view
    connector.execute_ddl(f"CREATE VIEW {view_name} AS SELECT * FROM {table_name}")

    try:
        views = connector.get_views_with_ddl(database_name=config.database)

        if len(views) > 0:
            view = [v for v in views if v["table_name"] == view_name]
            if view:
                assert "definition" in view[0]
                assert view[0]["table_type"] == "view"
    finally:
        connector.execute_ddl(f"DROP VIEW IF EXISTS {view_name}")
        connector.execute_ddl(f"DROP TABLE IF EXISTS {table_name}")


# ==================== Schema Tests ====================


@pytest.mark.integration
def test_get_schema(connector: ClickHouseConnector, config: ClickHouseConfig):
    """Test getting table schema."""
    suffix = uuid.uuid4().hex[:8]
    table_name = f"test_schema_{suffix}"

    connector.switch_context(database_name=config.database)
    connector.execute_ddl(
        f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            `id` String,
            `type` Nullable(String),
            `flag` Nullable(Int64),
            `entry_type` Nullable(String),
            `cnt` Nullable(Int64),
            `dt` String DEFAULT '1971-01-01'
        ) ENGINE = MergeTree()
        ORDER BY id
    """
    )

    try:
        schema = connector.get_schema(database_name=config.database, table_name=table_name)

        assert len(schema) == 6

        # Check flag column
        flag_col = next(col for col in schema if col["name"] == "flag")
        assert flag_col["pk"] is False
        assert "int64" in flag_col["type"].lower()

        # Check type column
        type_col = next(col for col in schema if col["name"] == "type")
        assert type_col["nullable"] is True
        assert "string" in type_col["type"].lower()
    finally:
        connector.execute_ddl(f"DROP TABLE IF EXISTS {table_name}")


# ==================== Sample Data Tests ====================


@pytest.mark.integration
def test_get_sample_rows(connector: ClickHouseConnector, config: ClickHouseConfig):
    """Test getting sample rows."""
    suffix = uuid.uuid4().hex[:8]
    table_name = f"test_sample_{suffix}"

    connector.switch_context(database_name=config.database)
    connector.execute_ddl(
        f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
             `id` Int64,
            `name` Nullable(String)
            ) ENGINE = MergeTree()
            ORDER BY id
    """
    )

    # Insert test data
    connector.execute_insert(
        f"""
        INSERT INTO {table_name} (id, name) VALUES
        (1, 'Alice'),
        (2, 'Bob'),
        (3, 'Charlie')
    """
    )

    try:
        sample_rows = connector.get_sample_rows(database_name=config.database, tables=[table_name], top_n=2)

        assert len(sample_rows) == 1
        assert sample_rows[0]["table_name"] == table_name
        assert "sample_rows" in sample_rows[0]
    finally:
        connector.execute_ddl(f"DROP TABLE IF EXISTS {table_name}")
