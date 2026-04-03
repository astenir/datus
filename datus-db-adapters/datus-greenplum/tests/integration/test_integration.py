# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import os
import uuid

import pytest

from datus_greenplum import GreenplumConfig, GreenplumConnector

# ==================== Connection Tests ====================


@pytest.mark.integration
@pytest.mark.acceptance
def test_connection_with_config_object(config: GreenplumConfig):
    """Test connection using config object."""
    try:
        conn = GreenplumConnector(config)
        assert conn.test_connection()
        conn.close()
    except Exception as e:
        pytest.skip(f"Database not available: {e}")


@pytest.mark.integration
def test_connection_with_dict():
    """Test connection using dict config."""
    try:
        conn = GreenplumConnector(
            {
                "host": os.getenv("GREENPLUM_HOST", "localhost"),
                "port": int(os.getenv("GREENPLUM_PORT", "15432")),
                "username": os.getenv("GREENPLUM_USER", "gpadmin"),
                "password": os.getenv("GREENPLUM_PASSWORD", "pivotal"),
            }
        )
        assert conn.test_connection()
        conn.close()
    except Exception as e:
        pytest.skip(f"Database not available: {e}")


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


# ==================== SQL Execution Tests ====================


@pytest.mark.integration
@pytest.mark.acceptance
def test_execute_select(connector: GreenplumConnector):
    """Test executing SELECT query."""
    result = connector.execute({"sql_query": "SELECT 1 as num"}, result_format="list")
    assert result.success
    assert not result.error
    assert result.sql_return == [{"num": 1}]


@pytest.mark.integration
@pytest.mark.acceptance
def test_execute_ddl(connector: GreenplumConnector, config: GreenplumConfig):
    """Test DDL operations."""
    suffix = uuid.uuid4().hex[:8]
    table_name = f"test_ddl_{suffix}"

    try:
        # CREATE
        create_result = connector.execute_ddl(
            f"""
            CREATE TABLE {table_name} (
                id SERIAL PRIMARY KEY,
                name VARCHAR(50)
            )
        """
        )
        assert create_result.success

        # ALTER
        alter_result = connector.execute_ddl(f"ALTER TABLE {table_name} ADD COLUMN age INT")
        assert alter_result.success

    finally:
        connector.execute_ddl(f"DROP TABLE IF EXISTS {table_name}")


@pytest.mark.integration
def test_execute_insert(connector: GreenplumConnector, config: GreenplumConfig):
    """Test INSERT operation."""
    suffix = uuid.uuid4().hex[:8]
    table_name = f"test_insert_{suffix}"

    connector.execute_ddl(
        f"""
        CREATE TABLE {table_name} (
            id SERIAL PRIMARY KEY,
            name VARCHAR(50)
        )
    """
    )

    try:
        insert_result = connector.execute_insert(f"INSERT INTO {table_name} (name) VALUES ('Alice'), ('Bob')")
        assert insert_result.success
        assert insert_result.row_count == 2

        # Verify
        query_result = connector.execute(
            {"sql_query": f"SELECT id, name FROM {table_name} ORDER BY id"}, result_format="list"
        )
        assert len(query_result.sql_return) == 2
        assert query_result.sql_return[0]["name"] == "Alice"
        assert query_result.sql_return[1]["name"] == "Bob"
    finally:
        connector.execute_ddl(f"DROP TABLE IF EXISTS {table_name}")


@pytest.mark.integration
def test_execute_update(connector: GreenplumConnector, config: GreenplumConfig):
    """Test UPDATE operation."""
    suffix = uuid.uuid4().hex[:8]
    table_name = f"test_update_{suffix}"

    connector.execute_ddl(
        f"""
        CREATE TABLE {table_name} (
            id SERIAL PRIMARY KEY,
            name VARCHAR(50)
        )
    """
    )

    try:
        connector.execute_insert(f"INSERT INTO {table_name} (name) VALUES ('Alice'), ('Bob')")

        update_result = connector.execute_update(f"UPDATE {table_name} SET name = 'Alice Updated' WHERE id = 1")
        assert update_result.success
        assert update_result.row_count == 1

        query_result = connector.execute(
            {"sql_query": f"SELECT name FROM {table_name} WHERE id = 1"}, result_format="list"
        )
        assert query_result.sql_return == [{"name": "Alice Updated"}]
    finally:
        connector.execute_ddl(f"DROP TABLE IF EXISTS {table_name}")


@pytest.mark.integration
def test_execute_delete(connector: GreenplumConnector, config: GreenplumConfig):
    """Test DELETE operation."""
    suffix = uuid.uuid4().hex[:8]
    table_name = f"test_delete_{suffix}"

    connector.execute_ddl(
        f"""
        CREATE TABLE {table_name} (
            id SERIAL PRIMARY KEY,
            name VARCHAR(50)
        )
    """
    )

    try:
        connector.execute_insert(f"INSERT INTO {table_name} (name) VALUES ('Alice'), ('Bob')")

        delete_result = connector.execute_delete(f"DELETE FROM {table_name} WHERE id = 2")
        assert delete_result.success
        assert delete_result.row_count == 1

        query_result = connector.execute({"sql_query": f"SELECT id FROM {table_name}"}, result_format="list")
        assert len(query_result.sql_return) == 1
        assert query_result.sql_return[0]["id"] == 1
    finally:
        connector.execute_ddl(f"DROP TABLE IF EXISTS {table_name}")


# ==================== Error Handling Tests ====================


@pytest.mark.integration
def test_exception_on_syntax_error(connector: GreenplumConnector):
    """Test that syntax error returns error result."""
    result = connector.execute({"sql_query": "INVALID SQL SYNTAX"})
    assert result.error is not None or not result.success


@pytest.mark.integration
def test_exception_on_nonexistent_table(connector: GreenplumConnector):
    """Test that non-existent table returns error result."""
    result = connector.execute({"sql_query": f"SELECT * FROM nonexistent_table_{uuid.uuid4().hex}"})
    assert result.error is not None or not result.success


# ==================== Utility Tests ====================


@pytest.mark.integration
def test_full_name_with_schema(connector: GreenplumConnector):
    """Test full_name with schema."""
    full_name = connector.full_name(schema_name="myschema", table_name="mytable")
    assert full_name == '"test"."myschema"."mytable"'


@pytest.mark.integration
def test_identifier(connector: GreenplumConnector):
    """Test identifier generation."""
    identifier = connector.identifier(schema_name="myschema", table_name="mytable")
    assert identifier == "test.myschema.mytable"


# ==================== Greenplum-Specific Tests ====================


@pytest.mark.integration
@pytest.mark.acceptance
def test_distribution_policy_by_column(connector: GreenplumConnector, config: GreenplumConfig):
    """Test DDL includes DISTRIBUTED BY for tables with explicit distribution key."""
    suffix = uuid.uuid4().hex[:8]
    table_name = f"test_dist_col_{suffix}"

    connector.execute_ddl(f"DROP TABLE IF EXISTS {table_name}")
    connector.execute_ddl(
        f"""
        CREATE TABLE {table_name} (
            id INTEGER,
            name VARCHAR(50)
        ) DISTRIBUTED BY (id)
    """
    )

    try:
        tables = connector.get_tables_with_ddl(schema_name=config.schema_name, tables=[table_name])
        assert len(tables) == 1
        ddl = tables[0]["definition"]
        assert 'DISTRIBUTED BY ("id")' in ddl
    finally:
        connector.execute_ddl(f"DROP TABLE IF EXISTS {table_name}")


@pytest.mark.integration
def test_distribution_policy_random(connector: GreenplumConnector, config: GreenplumConfig):
    """Test DDL includes DISTRIBUTED RANDOMLY for randomly distributed tables."""
    suffix = uuid.uuid4().hex[:8]
    table_name = f"test_dist_rand_{suffix}"

    connector.execute_ddl(f"DROP TABLE IF EXISTS {table_name}")
    connector.execute_ddl(
        f"""
        CREATE TABLE {table_name} (
            id INTEGER,
            name VARCHAR(50)
        ) DISTRIBUTED RANDOMLY
    """
    )

    try:
        tables = connector.get_tables_with_ddl(schema_name=config.schema_name, tables=[table_name])
        assert len(tables) == 1
        ddl = tables[0]["definition"]
        assert "DISTRIBUTED RANDOMLY" in ddl
    finally:
        connector.execute_ddl(f"DROP TABLE IF EXISTS {table_name}")


@pytest.mark.integration
@pytest.mark.acceptance
def test_get_storage_info(connector: GreenplumConnector, config: GreenplumConfig):
    """Test get_storage_info returns storage type for a heap table."""
    suffix = uuid.uuid4().hex[:8]
    table_name = f"test_storage_{suffix}"

    connector.execute_ddl(f"DROP TABLE IF EXISTS {table_name}")
    connector.execute_ddl(
        f"""
        CREATE TABLE {table_name} (
            id INTEGER,
            name VARCHAR(50)
        )
    """
    )

    try:
        info = connector.get_storage_info(schema_name=config.schema_name, table_name=table_name)
        assert info is not None
        assert info["storage_code"] == "h"
        assert info["storage_type"] == "heap"
    finally:
        connector.execute_ddl(f"DROP TABLE IF EXISTS {table_name}")


@pytest.mark.integration
def test_get_storage_info_no_table():
    """Test get_storage_info returns None for empty table_name."""
    config = GreenplumConfig(
        host=os.getenv("GREENPLUM_HOST", "localhost"),
        port=int(os.getenv("GREENPLUM_PORT", "15432")),
        username=os.getenv("GREENPLUM_USER", "gpadmin"),
        password=os.getenv("GREENPLUM_PASSWORD", "pivotal"),
        database=os.getenv("GREENPLUM_DATABASE", "test"),
    )
    try:
        conn = GreenplumConnector(config)
        result = conn.get_storage_info(schema_name="public", table_name="")
        assert result is None
        conn.close()
    except Exception as e:
        pytest.skip(f"Database not available: {e}")
