# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import os
import uuid
from typing import Generator

import pytest
from datus.tools.db_tools.mixins import CatalogSupportMixin, MaterializedViewSupportMixin
from datus.utils.exceptions import DatusException, ErrorCode
from datus_starrocks import StarRocksConfig, StarRocksConnector


@pytest.fixture
def config() -> StarRocksConfig:
    """Create StarRocks configuration from environment or defaults."""
    return StarRocksConfig(
        host=os.getenv("STARROCKS_HOST", "localhost"),
        port=int(os.getenv("STARROCKS_PORT", "9030")),
        username=os.getenv("STARROCKS_USER", "root"),
        password=os.getenv("STARROCKS_PASSWORD", ""),
        catalog=os.getenv("STARROCKS_CATALOG", "default_catalog"),
        database=os.getenv("STARROCKS_DATABASE", "quickstart"),
    )


@pytest.fixture
def connector(config: StarRocksConfig) -> Generator[StarRocksConnector, None, None]:
    """Create and cleanup StarRocks connector."""
    conn = StarRocksConnector(config)
    yield conn
    conn.close()


# ==================== Mixin Tests ====================


def test_connector_implements_catalog_mixin(connector: StarRocksConnector):
    """Verify StarRocks connector implements CatalogSupportMixin."""
    assert isinstance(connector, CatalogSupportMixin)


def test_connector_implements_materialized_view_mixin(connector: StarRocksConnector):
    """Verify StarRocks connector implements MaterializedViewSupportMixin."""
    assert isinstance(connector, MaterializedViewSupportMixin)


# ==================== Connection Tests ====================


def test_connection_with_config_object(config: StarRocksConfig):
    """Test connection using config object."""
    conn = StarRocksConnector(config)
    assert conn.test_connection()
    conn.close()


def test_connection_with_dict():
    """Test connection using dict config."""
    conn = StarRocksConnector(
        {
            "host": os.getenv("STARROCKS_HOST", "localhost"),
            "port": int(os.getenv("STARROCKS_PORT", "9030")),
            "username": os.getenv("STARROCKS_USER", "root"),
            "password": os.getenv("STARROCKS_PASSWORD", ""),
        }
    )
    assert conn.test_connection()
    conn.close()


def test_context_manager(config: StarRocksConfig):
    """Test connector as context manager."""
    with StarRocksConnector(config) as conn:
        assert conn.test_connection()


# ==================== Catalog Tests (CatalogSupportMixin) ====================


def test_get_catalogs(connector: StarRocksConnector):
    """Test getting list of catalogs."""
    catalogs = connector.get_catalogs()
    assert len(catalogs) > 0
    assert connector.default_catalog() in catalogs


def test_default_catalog(connector: StarRocksConnector):
    """Test default catalog."""
    assert connector.default_catalog() == "default_catalog"


def test_switch_catalog(connector: StarRocksConnector):
    """Test switching catalogs."""
    original_catalog = connector.catalog_name
    catalogs = connector.get_catalogs()

    if len(catalogs) > 1:
        target_catalog = [c for c in catalogs if c != original_catalog][0]
        connector.switch_catalog(target_catalog)
        assert connector.catalog_name == target_catalog

        # Switch back
        connector.switch_catalog(original_catalog)
        assert connector.catalog_name == original_catalog


# ==================== Database Tests ====================


def test_get_databases(connector: StarRocksConnector):
    """Test getting list of databases."""
    databases = connector.get_databases()
    assert len(databases) > 0


# ==================== Table Metadata Tests ====================


def test_get_tables(connector: StarRocksConnector):
    """Test getting table list."""
    tables = connector.get_tables()
    assert isinstance(tables, list)


def test_get_tables_with_ddl(connector: StarRocksConnector, config: StarRocksConfig):
    """Test getting tables with DDL."""
    tables = connector.get_tables_with_ddl(catalog_name=config.catalog)

    if len(tables) > 0:
        table = tables[0]
        assert "table_name" in table
        assert "definition" in table
        assert table["table_type"] == "table"
        assert "database_name" in table
        assert table["schema_name"] == ""
        assert table["catalog_name"] == config.catalog
        assert "identifier" in table
        assert len(table["identifier"].split(".")) == 3


# ==================== View Tests ====================


def test_get_views(connector: StarRocksConnector):
    """Test getting view list."""
    views = connector.get_views()
    assert isinstance(views, list)


def test_get_views_with_ddl(connector: StarRocksConnector, config: StarRocksConfig):
    """Test getting views with DDL."""
    views = connector.get_views_with_ddl(catalog_name=config.catalog)

    if len(views) > 0:
        view = views[0]
        assert "table_name" in view
        assert "definition" in view
        assert view["table_type"] == "view"
        assert "database_name" in view
        assert view["schema_name"] == ""
        assert "catalog_name" in view

        identifier_parts = view["identifier"].split(".")
        assert len(identifier_parts) == 3
        assert identifier_parts[0] == view["catalog_name"]
        assert identifier_parts[1] == view["database_name"]
        assert identifier_parts[2] == view["table_name"]


# ==================== Materialized View Tests (MaterializedViewSupportMixin) ====================


def test_get_materialized_views(connector: StarRocksConnector, config: StarRocksConfig):
    """Test getting materialized view list."""
    mvs = connector.get_materialized_views(catalog_name=config.catalog)
    assert isinstance(mvs, list)


def test_get_materialized_views_with_ddl(connector: StarRocksConnector):
    """Test getting materialized views with DDL."""
    mvs = connector.get_materialized_views_with_ddl()

    if len(mvs) > 0:
        mv = mvs[0]
        assert "table_name" in mv
        assert "definition" in mv
        assert mv["table_type"] == "mv"
        assert "database_name" in mv
        assert mv["schema_name"] == ""
        assert "catalog_name" in mv

        identifier_parts = mv["identifier"].split(".")
        assert len(identifier_parts) == 3


# ==================== Sample Data Tests ====================


def test_get_sample_rows_default(connector: StarRocksConnector):
    """Test getting sample rows with defaults."""
    sample_rows = connector.get_sample_rows()
    assert isinstance(sample_rows, list)


def test_get_sample_rows_with_database(connector: StarRocksConnector, config: StarRocksConfig):
    """Test getting sample rows for specific database."""
    sample_rows = connector.get_sample_rows(catalog_name=config.catalog, database_name=config.database)

    if len(sample_rows) > 0:
        item = sample_rows[0]
        assert "database_name" in item
        assert "table_name" in item
        assert "catalog_name" in item
        assert item["schema_name"] == ""
        assert "identifier" in item
        assert len(item["identifier"].split(".")) == 3
        assert "sample_rows" in item


def test_get_sample_rows_specific_tables(connector: StarRocksConnector, config: StarRocksConfig):
    """Test getting sample rows for specific tables."""
    # First get available tables
    tables = connector.get_tables(catalog_name=config.catalog, database_name=config.database)

    if len(tables) > 0:
        table_name = tables[0]
        sample_rows = connector.get_sample_rows(
            catalog_name=config.catalog, database_name=config.database, tables=[table_name], top_n=3
        )

        assert len(sample_rows) == 1
        assert sample_rows[0]["table_name"] == table_name


# ==================== SQL Execution Tests ====================


def test_execute_query(connector: StarRocksConnector):
    """Test executing simple query."""
    result = connector.execute({"sql_query": "SELECT 1 as num"}, result_format="list")
    assert result.success
    assert not result.error
    assert result.sql_return == [{"num": 1}]


def test_execute_explain(connector: StarRocksConnector, config: StarRocksConfig):
    """Test executing EXPLAIN query."""
    tables = connector.get_tables(catalog_name=config.catalog, database_name=config.database)

    if len(tables) > 0:
        table_name = tables[0]
        full_name = connector.full_name(
            catalog_name=config.catalog, database_name=config.database, table_name=table_name
        )

        result = connector.execute({"sql_query": f"EXPLAIN SELECT * FROM {full_name} LIMIT 1"})
        assert result.success
        assert not result.error
        assert result.sql_return


def test_execute_ddl_create_drop(connector: StarRocksConnector, config: StarRocksConfig):
    """Test DDL operations (CREATE/DROP)."""
    suffix = uuid.uuid4().hex[:8]
    table_name = f"datus_test_{suffix}"

    connector.switch_context(database_name=config.database)

    create_sql = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        `id` BIGINT NOT NULL,
        `name` VARCHAR(64)
    ) ENGINE=OLAP
    PRIMARY KEY (`id`)
    DISTRIBUTED BY HASH(`id`) BUCKETS 1
    PROPERTIES (
        "replication_num" = "1"
    );
    """

    try:
        create_result = connector.execute_ddl(create_sql)
        assert create_result.success, f"Failed to create table: {create_result.error}"
    finally:
        connector.execute_ddl(f"DROP TABLE IF EXISTS {table_name}")


def test_execute_insert(connector: StarRocksConnector, config: StarRocksConfig):
    """Test INSERT operation."""
    suffix = uuid.uuid4().hex[:8]
    table_name = f"datus_insert_test_{suffix}"

    connector.switch_context(database_name=config.database)

    create_sql = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        `id` BIGINT NOT NULL,
        `name` VARCHAR(64)
    ) ENGINE=OLAP
    PRIMARY KEY (`id`)
    DISTRIBUTED BY HASH(`id`) BUCKETS 1
    PROPERTIES (
        "replication_num" = "1"
    );
    """

    try:
        create_result = connector.execute_ddl(create_sql)
        if not create_result.success:
            pytest.skip(f"Unable to create test table: {create_result.error}")

        # Insert data
        insert_result = connector.execute_insert(f"INSERT INTO {table_name} (id, name) VALUES (1, 'Alice'), (2, 'Bob')")
        assert insert_result.success

        # Verify
        query_result = connector.execute(
            {"sql_query": f"SELECT id, name FROM {table_name} ORDER BY id"}, result_format="list"
        )
        assert query_result.success
        assert query_result.sql_return == [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
    finally:
        connector.execute_ddl(f"DROP TABLE IF EXISTS {table_name}")


def test_execute_update(connector: StarRocksConnector, config: StarRocksConfig):
    """Test UPDATE operation."""
    suffix = uuid.uuid4().hex[:8]
    table_name = f"datus_update_test_{suffix}"

    connector.switch_context(database_name=config.database)

    create_sql = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        `id` BIGINT NOT NULL,
        `name` VARCHAR(64)
    ) ENGINE=OLAP
    PRIMARY KEY (`id`)
    DISTRIBUTED BY HASH(`id`) BUCKETS 1
    PROPERTIES (
        "replication_num" = "1"
    );
    """

    try:
        create_result = connector.execute_ddl(create_sql)
        if not create_result.success:
            pytest.skip(f"Unable to create test table: {create_result.error}")

        # Insert initial data
        connector.execute_insert(f"INSERT INTO {table_name} (id, name) VALUES (1, 'Alice'), (2, 'Bob')")

        # Update
        update_result = connector.execute(
            {"sql_query": f"UPDATE {table_name} SET name = 'Alice Updated' WHERE id = 1"}, result_format="list"
        )
        assert update_result.success

        # Verify
        query_result = connector.execute(
            {"sql_query": f"SELECT id, name FROM {table_name} ORDER BY id"}, result_format="list"
        )
        assert query_result.sql_return == [{"id": 1, "name": "Alice Updated"}, {"id": 2, "name": "Bob"}]
    finally:
        connector.execute_ddl(f"DROP TABLE IF EXISTS {table_name}")


def test_execute_delete(connector: StarRocksConnector, config: StarRocksConfig):
    """Test DELETE operation."""
    suffix = uuid.uuid4().hex[:8]
    table_name = f"datus_delete_test_{suffix}"

    connector.switch_context(database_name=config.database)

    create_sql = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        `id` BIGINT NOT NULL,
        `name` VARCHAR(64)
    ) ENGINE=OLAP
    PRIMARY KEY (`id`)
    DISTRIBUTED BY HASH(`id`) BUCKETS 1
    PROPERTIES (
        "replication_num" = "1"
    );
    """

    try:
        create_result = connector.execute_ddl(create_sql)
        if not create_result.success:
            pytest.skip(f"Unable to create test table: {create_result.error}")

        # Insert initial data
        connector.execute_insert(f"INSERT INTO {table_name} (id, name) VALUES (1, 'Alice'), (2, 'Bob')")

        # Delete
        delete_result = connector.execute({"sql_query": f"DELETE FROM {table_name} WHERE id = 2"}, result_format="list")
        assert delete_result.success

        # Verify
        query_result = connector.execute(
            {"sql_query": f"SELECT id, name FROM {table_name} ORDER BY id"}, result_format="list"
        )
        assert query_result.sql_return == [{"id": 1, "name": "Alice"}]
    finally:
        connector.execute_ddl(f"DROP TABLE IF EXISTS {table_name}")


# ==================== Error Handling Tests ====================


def test_exception_on_nonexistent_table(connector: StarRocksConnector, config: StarRocksConfig):
    """Test exception handling for non-existent table."""
    with pytest.raises(DatusException, match=ErrorCode.DB_EXECUTION_ERROR.code):
        connector.get_sample_rows(catalog_name=config.catalog, tables=["nonexistent_table_" + uuid.uuid4().hex])


def test_execute_merge_returns_error(connector: StarRocksConnector):
    """Test MERGE statement error handling."""
    merge_sql = (
        "MERGE INTO nonexistent_target AS t USING nonexistent_source AS s ON t.id = s.id "
        "WHEN MATCHED THEN UPDATE SET t.value = s.value "
        "WHEN NOT MATCHED THEN INSERT (id, value) VALUES (s.id, s.value)"
    )

    result = connector.execute({"sql_query": merge_sql})
    assert result.sql_query == merge_sql
    assert not result.success or result.error  # Either fails or returns error
