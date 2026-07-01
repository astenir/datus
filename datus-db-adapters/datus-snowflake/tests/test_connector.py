# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import os
from typing import Generator

import pytest

from datus_snowflake import SnowflakeConfig, SnowflakeConnector

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not (
            os.getenv("SNOWFLAKE_ACCOUNT")
            and os.getenv("SNOWFLAKE_USER")
            and os.getenv("SNOWFLAKE_WAREHOUSE")
            and (os.getenv("SNOWFLAKE_PASSWORD") or os.getenv("SNOWFLAKE_PRIVATE_KEY_FILE"))
        ),
        reason="Snowflake live credentials not provided in environment variables",
    ),
]


@pytest.fixture
def config_dict() -> dict:
    """Create Snowflake configuration from environment."""
    cfg = {
        "account": os.getenv("SNOWFLAKE_ACCOUNT", ""),
        "username": os.getenv("SNOWFLAKE_USER", ""),
        "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", ""),
        "database": os.getenv("SNOWFLAKE_DATABASE"),
        "schema": os.getenv("SNOWFLAKE_SCHEMA"),
        "role": os.getenv("SNOWFLAKE_ROLE"),
    }
    if os.getenv("SNOWFLAKE_PRIVATE_KEY_FILE"):
        cfg["private_key_file"] = os.getenv("SNOWFLAKE_PRIVATE_KEY_FILE")
        cfg["private_key_file_pwd"] = os.getenv("SNOWFLAKE_PRIVATE_KEY_FILE_PWD")
    else:
        cfg["password"] = os.getenv("SNOWFLAKE_PASSWORD", "")
    return {key: value for key, value in cfg.items() if value is not None}


@pytest.fixture
def config(config_dict: dict) -> SnowflakeConfig:
    return SnowflakeConfig(**config_dict)


@pytest.fixture
def connector(config: SnowflakeConfig) -> Generator[SnowflakeConnector, None, None]:
    """Create and cleanup Snowflake connector."""
    conn = SnowflakeConnector(config)
    yield conn
    conn.close()


@pytest.fixture
def database_name(config: SnowflakeConfig) -> str:
    if not config.database:
        pytest.skip("SNOWFLAKE_DATABASE not provided")
    return config.database


@pytest.fixture
def schema_name(config: SnowflakeConfig) -> str:
    if not config.schema_name:
        pytest.skip("SNOWFLAKE_SCHEMA not provided")
    return config.schema_name


# ==================== Connection Tests ====================


def test_connection_with_config_object(config: SnowflakeConfig):
    """Test connection using config object."""
    conn = SnowflakeConnector(config)
    result = conn.test_connection()
    assert result["success"] is True
    conn.close()


def test_connection_with_dict(config_dict: dict):
    """Test connection using dict config."""
    conn = SnowflakeConnector(config_dict)
    result = conn.test_connection()
    assert result["success"] is True
    conn.close()


# ==================== Database Tests ====================


def test_get_databases(connector: SnowflakeConnector):
    """Test getting list of databases."""
    databases = connector.get_databases()
    assert isinstance(databases, list)
    assert len(databases) > 0


def test_get_databases_exclude_system(connector: SnowflakeConnector):
    """Test that system databases are excluded by default."""
    databases = connector.get_databases(include_sys=False)
    system_dbs = {"SNOWFLAKE"}
    for db in databases:
        assert db.upper() not in system_dbs


# ==================== Schema Tests (SchemaNamespaceMixin) ====================


def test_get_schemas(connector: SnowflakeConnector, database_name: str):
    """Test getting list of schemas."""
    schemas = connector.get_schemas(database_name=database_name)
    assert isinstance(schemas, list)


def test_get_schemas_exclude_system(connector: SnowflakeConnector, database_name: str):
    """Test that system schemas are excluded by default."""
    schemas = connector.get_schemas(database_name=database_name, include_sys=False)
    for schema in schemas:
        assert schema.upper() != "INFORMATION_SCHEMA"


# ==================== Table Metadata Tests ====================


def test_get_tables(connector: SnowflakeConnector, database_name: str):
    """Test getting table list."""
    tables = connector.get_tables(database_name=database_name)
    assert isinstance(tables, list)


def test_get_tables_with_ddl(connector: SnowflakeConnector, database_name: str, schema_name: str):
    """Test getting tables with DDL."""
    tables = connector.get_tables_with_ddl(database_name=database_name, schema_name=schema_name)

    if len(tables) > 0:
        table = tables[0]
        assert "table_name" in table
        assert "definition" in table
        assert table["table_type"] == "table"
        assert "database_name" in table
        assert "schema_name" in table
        assert "identifier" in table


# ==================== View Tests ====================


def test_get_views(connector: SnowflakeConnector, database_name: str):
    """Test getting view list."""
    views = connector.get_views(database_name=database_name)
    assert isinstance(views, list)


def test_get_views_with_ddl(connector: SnowflakeConnector, database_name: str, schema_name: str):
    """Test getting views with DDL."""
    views = connector.get_views_with_ddl(database_name=database_name, schema_name=schema_name)

    if len(views) > 0:
        view = views[0]
        assert "table_name" in view
        assert "definition" in view
        assert view["table_type"] == "view"


# ==================== Materialized View Tests (MaterializedViewSupportMixin) ====================


def test_get_materialized_views(connector: SnowflakeConnector, database_name: str):
    """Test getting materialized view list."""
    mvs = connector.get_materialized_views(database_name=database_name)
    assert isinstance(mvs, list)


def test_get_materialized_views_with_ddl(connector: SnowflakeConnector, database_name: str, schema_name: str):
    """Test getting materialized views with DDL."""
    mvs = connector.get_materialized_views_with_ddl(database_name=database_name, schema_name=schema_name)

    if len(mvs) > 0:
        mv = mvs[0]
        assert "table_name" in mv
        assert "definition" in mv
        assert mv["table_type"] == "mv"


# ==================== Schema Structure Tests ====================


def test_get_schema(connector: SnowflakeConnector, database_name: str, schema_name: str):
    """Test getting table schema."""
    tables = connector.get_tables(database_name=database_name, schema_name=schema_name)

    if len(tables) > 0:
        table_name = tables[0]
        schema = connector.get_schema(
            database_name=database_name,
            schema_name=schema_name,
            table_name=table_name,
        )

        assert isinstance(schema, list)
        if len(schema) > 0:
            for col in schema:
                if isinstance(col, dict) and "name" in col:
                    assert "type" in col
                    assert "nullable" in col


# ==================== Sample Data Tests ====================


def test_get_sample_rows(connector: SnowflakeConnector, database_name: str, schema_name: str):
    """Test getting sample rows."""
    sample_rows = connector.get_sample_rows(database_name=database_name, schema_name=schema_name, top_n=3)

    if len(sample_rows) > 0:
        item = sample_rows[0]
        assert "database_name" in item
        assert "table_name" in item
        assert "schema_name" in item
        assert "sample_rows" in item


# ==================== SQL Execution Tests ====================


def test_execute_query_csv(connector: SnowflakeConnector):
    """Test executing query with CSV format."""
    result = connector.execute_query('SELECT 1 AS "num"', result_format="csv")
    assert result.success
    assert not result.error
    assert "num" in result.sql_return


def test_execute_query_list(connector: SnowflakeConnector):
    """Test executing query with list format."""
    result = connector.execute_query('SELECT 1 AS "num"', result_format="list")
    assert result.success
    assert not result.error
    assert result.sql_return == [{"num": 1}]


def test_execute_query_arrow(connector: SnowflakeConnector):
    """Test executing query with Arrow format."""
    result = connector.execute_query('SELECT 1 AS "num"', result_format="arrow")
    assert result.success
    assert not result.error
    assert result.sql_return is not None


def test_execute_query_pandas(connector: SnowflakeConnector):
    """Test executing query with pandas format."""
    result = connector.execute_query('SELECT 1 AS "num"', result_format="pandas")
    assert result.success
    assert not result.error
    assert len(result.sql_return) == 1


def test_execute_show_databases(connector: SnowflakeConnector):
    """Test executing SHOW DATABASES."""
    result = connector.execute_query("SHOW DATABASES", result_format="list")
    assert result.success
    assert isinstance(result.sql_return, list)


def test_execute_show_schemas(connector: SnowflakeConnector, database_name: str):
    """Test executing SHOW SCHEMAS."""
    result = connector.execute_query(f'SHOW SCHEMAS IN DATABASE "{database_name}"', result_format="list")
    assert result.success
    assert isinstance(result.sql_return, list)


# ==================== Error Handling Tests ====================


def test_execute_invalid_sql(connector: SnowflakeConnector):
    """Test exception on invalid SQL."""
    result = connector.execute_query("INVALID SQL SYNTAX")
    assert not result.success
    assert result.error is not None


def test_execute_nonexistent_table(connector: SnowflakeConnector):
    """Test exception on non-existent table."""
    result = connector.execute_query("SELECT * FROM nonexistent_table_xyz")
    assert not result.success
    assert result.error is not None
