# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import os
import uuid

import pytest

from datus_greenplum import GreenplumConfig, GreenplumConnector

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
