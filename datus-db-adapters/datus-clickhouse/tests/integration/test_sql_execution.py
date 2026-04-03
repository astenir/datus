# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import uuid

import pytest

from datus_clickhouse import ClickHouseConfig, ClickHouseConnector


@pytest.mark.integration
@pytest.mark.acceptance
def test_execute_select(connector: ClickHouseConnector):
    """Test executing SELECT query."""
    result = connector.execute({"sql_query": "SELECT 1 as num"}, result_format="list")
    assert result.success
    assert not result.error
    assert result.sql_return == [{"num": 1}]


@pytest.mark.integration
@pytest.mark.acceptance
def test_execute_ddl(connector: ClickHouseConnector, config: ClickHouseConfig):
    """Test DDL operations."""
    suffix = uuid.uuid4().hex[:8]
    table_name = f"test_ddl_{suffix}"

    connector.switch_context(database_name=config.database)

    try:
        # CREATE
        create_result = connector.execute_ddl(
            f"""
            CREATE TABLE {table_name} (
            `id` Int64,
            `name` Nullable(String)
            ) ENGINE = MergeTree()
            ORDER BY id
        """
        )
        assert create_result.success

        # ALTER
        alter_result = connector.execute_ddl(f"ALTER TABLE {table_name} ADD COLUMN age INT")
        assert alter_result.success

    finally:
        connector.execute_ddl(f"DROP TABLE IF EXISTS {table_name}")


@pytest.mark.integration
@pytest.mark.acceptance
def test_execute_insert(connector: ClickHouseConnector, config: ClickHouseConfig):
    """Test INSERT operation."""
    suffix = uuid.uuid4().hex[:8]
    table_name = f"test_insert_{suffix}"

    connector.switch_context(database_name=config.database)
    connector.execute_ddl(
        f"""
        CREATE TABLE {table_name} (
            `id` Int64,
            `name` Nullable(String)
        ) ENGINE = MergeTree()
        ORDER BY id
    """
    )

    try:
        insert_result = connector.execute_insert(f"INSERT INTO {table_name} (id, name) VALUES (1, 'Alice'), (2, 'Bob')")
        assert insert_result.success

        # Verify
        query_result = connector.execute(
            {"sql_query": f"SELECT id, name FROM {table_name} ORDER BY id"},
            result_format="list",
        )
        assert query_result.sql_return == [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
        ]
    finally:
        connector.execute_ddl(f"DROP TABLE IF EXISTS {table_name}")


@pytest.mark.integration
def test_execute_update(connector: ClickHouseConnector, config: ClickHouseConfig):
    """Test UPDATE operation."""
    suffix = uuid.uuid4().hex[:8]
    table_name = f"test_update_{suffix}"

    connector.switch_context(database_name=config.database)
    connector.execute_ddl(
        f"""
        CREATE TABLE {table_name} (
            `id` Int64,
            `name` Nullable(String)
        ) ENGINE = MergeTree()
        ORDER BY id
        SETTINGS enable_block_number_column = 1, enable_block_offset_column = 1
    """
    )

    try:
        # Insert initial data
        connector.execute_insert(f"INSERT INTO {table_name} (id, name) VALUES (1, 'Alice'), (2, 'Bob')")

        # Update (ClickHouse uses ALTER TABLE ... UPDATE syntax)
        update_result = connector.execute_update(
            f"ALTER TABLE {table_name} UPDATE name = 'Alice Updated' WHERE id = 1 SETTINGS mutations_sync = 1"
        )
        assert update_result.success

        # Verify
        query_result = connector.execute(
            {"sql_query": f"SELECT name FROM {table_name} WHERE id = 1"},
            result_format="list",
        )
        assert query_result.sql_return == [{"name": "Alice Updated"}]
    finally:
        connector.execute_ddl(f"DROP TABLE IF EXISTS {table_name}")


@pytest.mark.integration
def test_execute_delete(connector: ClickHouseConnector, config: ClickHouseConfig):
    """Test DELETE operation."""
    suffix = uuid.uuid4().hex[:8]
    table_name = f"test_delete_{suffix}"

    connector.switch_context(database_name=config.database)
    connector.execute_ddl(
        f"""
        CREATE TABLE {table_name} (
            `id` Int64,
            `name` Nullable(String)
        ) ENGINE = MergeTree()
        ORDER BY id
    """
    )

    try:
        # Insert initial data
        connector.execute_insert(f"INSERT INTO {table_name} (id, name) VALUES (1, 'Alice'), (2, 'Bob')")

        # Delete
        delete_result = connector.execute_delete(
            f"DELETE FROM {table_name} WHERE id = 2 SETTINGS lightweight_deletes_sync = 1"
        )
        assert delete_result.success

        # Verify
        query_result = connector.execute({"sql_query": f"SELECT id FROM {table_name}"}, result_format="list")
        assert query_result.sql_return == [{"id": 1}]
    finally:
        connector.execute_ddl(f"DROP TABLE IF EXISTS {table_name}")


# ==================== Error Handling Tests ====================


@pytest.mark.integration
def test_exception_on_syntax_error(connector: ClickHouseConnector):
    """Test exception on SQL syntax error."""
    result = connector.execute({"sql_query": "INVALID SQL SYNTAX"})
    assert result.error == "Unknown type of SQL"


@pytest.mark.integration
def test_exception_on_nonexistent_table(connector: ClickHouseConnector):
    """Test exception on non-existent table."""
    result = connector.execute({"sql_query": f"SELECT * FROM nonexistent_table_{uuid.uuid4().hex}"})
    assert "Unknown table expression" in result.error


# ==================== Utility Tests ====================


@pytest.mark.integration
def test_full_name_with_database(connector: ClickHouseConnector):
    """Test full_name with database."""
    full_name = connector.full_name(database_name="mydb", table_name="mytable")
    assert full_name == "`mydb`.`mytable`"


@pytest.mark.integration
def test_full_name_without_database(connector: ClickHouseConnector):
    """Test full_name without database."""
    full_name = connector.full_name(table_name="mytable")
    assert full_name == "`mytable`"


@pytest.mark.integration
def test_identifier(connector: ClickHouseConnector):
    """Test identifier generation."""
    identifier = connector.identifier(database_name="mydb", table_name="mytable")
    assert identifier == "mydb.mytable"
