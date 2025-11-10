# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import os
from typing import Generator

import pytest
from datus.tools.db_tools.mixins import MaterializedViewSupportMixin, SchemaNamespaceMixin
from datus_snowflake import SnowflakeConfig, SnowflakeConnector

# Skip all tests if Snowflake credentials are not provided
pytestmark = pytest.mark.skipif(
    not all(
        [
            os.getenv("SNOWFLAKE_ACCOUNT"),
            os.getenv("SNOWFLAKE_USER"),
            os.getenv("SNOWFLAKE_PASSWORD"),
            os.getenv("SNOWFLAKE_WAREHOUSE"),
        ]
    ),
    reason="Snowflake credentials not provided in environment variables",
)


@pytest.fixture
def config() -> SnowflakeConfig:
    """Create Snowflake configuration from environment."""
    return SnowflakeConfig(
        account=os.getenv("SNOWFLAKE_ACCOUNT", ""),
        username=os.getenv("SNOWFLAKE_USER", ""),
        password=os.getenv("SNOWFLAKE_PASSWORD", ""),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE", ""),
        database=os.getenv("SNOWFLAKE_DATABASE"),
        schema=os.getenv("SNOWFLAKE_SCHEMA"),
    )


@pytest.fixture
def connector(config: SnowflakeConfig) -> Generator[SnowflakeConnector, None, None]:
    """Create and cleanup Snowflake connector."""
    conn = SnowflakeConnector(config)
    yield conn
    conn.close()


# ==================== Mixin Tests ====================


def test_connector_implements_schema_namespace_mixin(connector: SnowflakeConnector):
    """Verify Snowflake connector implements SchemaNamespaceMixin."""
    assert isinstance(connector, SchemaNamespaceMixin)


def test_connector_implements_materialized_view_mixin(connector: SnowflakeConnector):
    """Verify Snowflake connector implements MaterializedViewSupportMixin."""
    assert isinstance(connector, MaterializedViewSupportMixin)


# ==================== Connection Tests ====================


def test_connection_with_config_object(config: SnowflakeConfig):
    """Test connection using config object."""
    conn = SnowflakeConnector(config)
    result = conn.test_connection()
    assert result["success"] is True
    conn.close()


def test_connection_with_dict():
    """Test connection using dict config."""
    conn = SnowflakeConnector(
        {
            "account": os.getenv("SNOWFLAKE_ACCOUNT", ""),
            "username": os.getenv("SNOWFLAKE_USER", ""),
            "password": os.getenv("SNOWFLAKE_PASSWORD", ""),
            "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", ""),
        }
    )
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
    system_dbs = {"SNOWFLAKE", "SNOWFLAKE_SAMPLE_DATA"}
    for db in databases:
        assert db.upper() not in system_dbs


# ==================== Schema Tests (SchemaNamespaceMixin) ====================


def test_get_schemas(connector: SnowflakeConnector, config: SnowflakeConfig):
    """Test getting list of schemas."""
    if config.database:
        schemas = connector.get_schemas(database_name=config.database)
        assert isinstance(schemas, list)


def test_get_schemas_exclude_system(connector: SnowflakeConnector, config: SnowflakeConfig):
    """Test that system schemas are excluded by default."""
    if config.database:
        schemas = connector.get_schemas(database_name=config.database, include_sys=False)
        for schema in schemas:
            assert schema.upper() != "INFORMATION_SCHEMA"


# ==================== Table Metadata Tests ====================


def test_get_tables(connector: SnowflakeConnector, config: SnowflakeConfig):
    """Test getting table list."""
    if config.database:
        tables = connector.get_tables(database_name=config.database)
        assert isinstance(tables, list)


def test_get_tables_with_ddl(connector: SnowflakeConnector, config: SnowflakeConfig):
    """Test getting tables with DDL."""
    if config.database and config.schema_name:
        tables = connector.get_tables_with_ddl(database_name=config.database, schema_name=config.schema_name)

        if len(tables) > 0:
            table = tables[0]
            assert "table_name" in table
            assert "definition" in table
            assert table["table_type"] == "table"
            assert "database_name" in table
            assert "schema_name" in table
            assert "identifier" in table


# ==================== View Tests ====================


def test_get_views(connector: SnowflakeConnector, config: SnowflakeConfig):
    """Test getting view list."""
    if config.database:
        views = connector.get_views(database_name=config.database)
        assert isinstance(views, list)


def test_get_views_with_ddl(connector: SnowflakeConnector, config: SnowflakeConfig):
    """Test getting views with DDL."""
    if config.database and config.schema_name:
        views = connector.get_views_with_ddl(database_name=config.database, schema_name=config.schema_name)

        if len(views) > 0:
            view = views[0]
            assert "table_name" in view
            assert "definition" in view
            assert view["table_type"] == "view"


# ==================== Materialized View Tests (MaterializedViewSupportMixin) ====================


def test_get_materialized_views(connector: SnowflakeConnector, config: SnowflakeConfig):
    """Test getting materialized view list."""
    if config.database:
        mvs = connector.get_materialized_views(database_name=config.database)
        assert isinstance(mvs, list)


def test_get_materialized_views_with_ddl(connector: SnowflakeConnector, config: SnowflakeConfig):
    """Test getting materialized views with DDL."""
    if config.database and config.schema_name:
        mvs = connector.get_materialized_views_with_ddl(database_name=config.database, schema_name=config.schema_name)

        if len(mvs) > 0:
            mv = mvs[0]
            assert "table_name" in mv
            assert "definition" in mv
            assert mv["table_type"] == "mv"


# ==================== Schema Structure Tests ====================


def test_get_schema(connector: SnowflakeConnector, config: SnowflakeConfig):
    """Test getting table schema."""
    if config.database and config.schema_name:
        tables = connector.get_tables(database_name=config.database, schema_name=config.schema_name)

        if len(tables) > 0:
            table_name = tables[0]
            schema = connector.get_schema(
                database_name=config.database, schema_name=config.schema_name, table_name=table_name
            )

            assert isinstance(schema, list)
            if len(schema) > 0:
                # Check column structure
                for col in schema:
                    if isinstance(col, dict) and "name" in col:
                        assert "type" in col
                        assert "nullable" in col


# ==================== Sample Data Tests ====================


def test_get_sample_rows(connector: SnowflakeConnector, config: SnowflakeConfig):
    """Test getting sample rows."""
    if config.database and config.schema_name:
        sample_rows = connector.get_sample_rows(database_name=config.database, schema_name=config.schema_name, top_n=3)

        if len(sample_rows) > 0:
            item = sample_rows[0]
            assert "database_name" in item
            assert "table_name" in item
            assert "schema_name" in item
            assert "sample_rows" in item


# ==================== SQL Execution Tests ====================


def test_execute_query_csv(connector: SnowflakeConnector):
    """Test executing query with CSV format."""
    result = connector.execute_query("SELECT 1 as num", result_format="csv")
    assert result.success
    assert not result.error
    assert "num" in result.sql_return


def test_execute_query_list(connector: SnowflakeConnector):
    """Test executing query with list format."""
    result = connector.execute_query("SELECT 1 as num", result_format="list")
    assert result.success
    assert not result.error
    assert result.sql_return == [{"num": 1}]


def test_execute_query_arrow(connector: SnowflakeConnector):
    """Test executing query with Arrow format."""
    result = connector.execute_query("SELECT 1 as num", result_format="arrow")
    assert result.success
    assert not result.error
    assert result.sql_return is not None


def test_execute_query_pandas(connector: SnowflakeConnector):
    """Test executing query with pandas format."""
    result = connector.execute_query("SELECT 1 as num", result_format="pandas")
    assert result.success
    assert not result.error
    assert len(result.sql_return) == 1


def test_execute_show_databases(connector: SnowflakeConnector):
    """Test executing SHOW DATABASES."""
    result = connector.execute_query("SHOW DATABASES", result_format="list")
    assert result.success
    assert isinstance(result.sql_return, list)


def test_execute_show_schemas(connector: SnowflakeConnector, config: SnowflakeConfig):
    """Test executing SHOW SCHEMAS."""
    if config.database:
        result = connector.execute_query(f'SHOW SCHEMAS IN DATABASE "{config.database}"', result_format="list")
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


# ==================== Utility Tests ====================


def test_full_name_with_database_and_schema(connector: SnowflakeConnector):
    """Test full_name with database and schema."""
    full_name = connector.full_name(database_name="mydb", schema_name="myschema", table_name="mytable")
    assert full_name == '"mydb"."myschema"."mytable"'


def test_full_name_with_schema_only(connector: SnowflakeConnector):
    """Test full_name with schema only."""
    full_name = connector.full_name(schema_name="myschema", table_name="mytable")
    assert full_name == '"myschema"."mytable"'


def test_full_name_with_table_only(connector: SnowflakeConnector):
    """Test full_name with table only."""
    full_name = connector.full_name(table_name="mytable")
    assert full_name == '"mytable"'
