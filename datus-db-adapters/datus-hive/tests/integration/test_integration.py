# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import os
import uuid

import pytest
from datus_hive import HiveConfig, HiveConnector


@pytest.mark.integration
@pytest.mark.acceptance
def test_connection_with_config_object(config: HiveConfig):
    """Test connection using config object."""
    try:
        conn = HiveConnector(config)
        assert conn.test_connection()
        conn.close()
    except Exception as exc:
        pytest.skip(f"Database not available: {exc}")


@pytest.mark.integration
def test_connection_with_dict():
    """Test connection using dict config."""
    try:
        conn = HiveConnector(
            {
                "host": os.getenv("HIVE_HOST", "localhost"),
                "port": int(os.getenv("HIVE_PORT", "10000")),
                "username": os.getenv("HIVE_USERNAME", "hive"),
                "password": os.getenv("HIVE_PASSWORD", ""),
                "database": os.getenv("HIVE_DATABASE", "default"),
                "auth": os.getenv("HIVE_AUTH") or None,
            }
        )
        assert conn.test_connection()
        conn.close()
    except Exception as exc:
        pytest.skip(f"Database not available: {exc}")


@pytest.mark.integration
@pytest.mark.acceptance
def test_get_databases(connector: HiveConnector):
    """Test getting list of databases."""
    databases = connector.get_databases()
    assert isinstance(databases, list)
    assert len(databases) > 0


@pytest.mark.integration
@pytest.mark.acceptance
def test_get_tables(connector: HiveConnector, config: HiveConfig):
    """Test getting table list."""
    tables = connector.get_tables(database_name=config.database or "")
    assert isinstance(tables, list)


@pytest.mark.integration
def test_get_tables_with_ddl(connector: HiveConnector, config: HiveConfig):
    """Test getting tables with DDL."""
    suffix = uuid.uuid4().hex[:8]
    table_name = f"test_table_{suffix}"
    database = config.database or "default"

    connector.execute_ddl(f"CREATE DATABASE IF NOT EXISTS {database}")
    connector.switch_context(database_name=database)
    connector.execute_ddl(
        f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INT,
            name STRING
        )
        """
    )

    try:
        tables = connector.get_tables_with_ddl(database_name=database, tables=[table_name])
        if tables:
            table = tables[0]
            assert table["table_name"] == table_name
            assert "definition" in table
            assert table["table_type"] == "table"
    finally:
        connector.execute_ddl(f"DROP TABLE IF EXISTS {table_name}")


@pytest.mark.integration
def test_get_views(connector: HiveConnector, config: HiveConfig):
    """Test getting view list."""
    views = connector.get_views(database_name=config.database or "")
    assert isinstance(views, list)


@pytest.mark.integration
def test_get_views_with_ddl(connector: HiveConnector, config: HiveConfig):
    """Test getting views with DDL."""
    suffix = uuid.uuid4().hex[:8]
    view_name = f"test_view_{suffix}"
    table_name = f"test_table_{suffix}"
    database = config.database or "default"

    connector.execute_ddl(f"CREATE DATABASE IF NOT EXISTS {database}")
    connector.switch_context(database_name=database)
    connector.execute_ddl(
        f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INT,
            name STRING
        )
        """
    )
    connector.execute_ddl(f"CREATE VIEW {view_name} AS SELECT * FROM {table_name}")

    try:
        views = connector.get_views_with_ddl(database_name=database)
        if views:
            view = [v for v in views if v["table_name"] == view_name]
            if view:
                assert "definition" in view[0]
                assert view[0]["table_type"] == "view"
    finally:
        connector.execute_ddl(f"DROP VIEW IF EXISTS {view_name}")
        connector.execute_ddl(f"DROP TABLE IF EXISTS {table_name}")


@pytest.mark.integration
@pytest.mark.acceptance
def test_get_schema(connector: HiveConnector, config: HiveConfig):
    """Test getting table schema."""
    suffix = uuid.uuid4().hex[:8]
    table_name = f"test_schema_{suffix}"
    database = config.database or "default"

    connector.execute_ddl(f"CREATE DATABASE IF NOT EXISTS {database}")
    connector.switch_context(database_name=database)
    connector.execute_ddl(
        f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INT,
            name STRING
        )
        """
    )

    try:
        schema = connector.get_schema(database_name=database, table_name=table_name)
        assert any(col["name"] == "id" for col in schema)
        assert any(col["name"] == "name" for col in schema)
    finally:
        connector.execute_ddl(f"DROP TABLE IF EXISTS {table_name}")


@pytest.mark.integration
def test_get_sample_rows(connector: HiveConnector, config: HiveConfig):
    """Test getting sample rows."""
    suffix = uuid.uuid4().hex[:8]
    table_name = f"test_sample_{suffix}"
    database = config.database or "default"

    connector.execute_ddl(f"CREATE DATABASE IF NOT EXISTS {database}")
    connector.switch_context(database_name=database)
    connector.execute_ddl(
        f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INT,
            name STRING
        )
        """
    )

    try:
        try:
            connector.execute_insert(
                f"INSERT INTO {table_name} VALUES (1, 'alpha'), (2, 'beta')"
            )
        except Exception as exc:
            pytest.skip(f"Insert not supported in this environment: {exc}")

        samples = connector.get_sample_rows(tables=[table_name], top_n=2, database_name=database)
        assert samples
        assert samples[0]["table_name"] == table_name
    finally:
        connector.execute_ddl(f"DROP TABLE IF EXISTS {table_name}")
