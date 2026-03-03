# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import pytest
from datus_trino import TrinoConnector

TPCH_TABLES = {"customer", "lineitem", "nation", "orders", "part", "partsupp", "region", "supplier"}

# ==================== Metadata Tests ====================


@pytest.mark.integration
def test_tpch_get_schemas(tpch_connector: TrinoConnector):
    """Test that tpch catalog contains expected schemas like tiny and sf1."""
    schemas = tpch_connector.get_schemas(catalog_name="tpch")
    assert "tiny" in schemas
    assert "sf1" in schemas


@pytest.mark.integration
def test_tpch_get_tables(tpch_connector: TrinoConnector):
    """Test that tpch.tiny schema contains all 8 standard TPC-H tables."""
    tables = tpch_connector.get_tables(catalog_name="tpch", schema_name="tiny")
    table_set = set(tables)
    assert TPCH_TABLES.issubset(table_set), f"Missing tables: {TPCH_TABLES - table_set}"


@pytest.mark.integration
def test_tpch_get_columns(tpch_connector: TrinoConnector):
    """Test getting column schema for tpch.tiny.customer table."""
    columns = tpch_connector.get_schema(catalog_name="tpch", schema_name="tiny", table_name="customer")
    assert len(columns) > 0
    column_names = {col["name"] for col in columns}
    assert "custkey" in column_names or "c_custkey" in column_names
    assert "name" in column_names or "c_name" in column_names
    for col in columns:
        assert "name" in col
        assert "type" in col
        assert "nullable" in col


# ==================== Data Query Tests ====================


@pytest.mark.integration
@pytest.mark.acceptance
def test_tpch_execute_query(tpch_connector: TrinoConnector):
    """Test querying tpch.tiny.nation - should have 25 nations."""
    result = tpch_connector.execute(
        {"sql_query": 'SELECT * FROM "tpch"."tiny"."nation"'},
        result_format="list",
    )
    assert result.success
    assert len(result.sql_return) == 25


@pytest.mark.integration
def test_tpch_execute_join(tpch_connector: TrinoConnector):
    """Test a JOIN query across TPC-H tables (customer + orders)."""
    result = tpch_connector.execute(
        {
            "sql_query": (
                "SELECT c.name, COUNT(o.orderkey) AS order_count "
                'FROM "tpch"."tiny"."customer" c '
                'JOIN "tpch"."tiny"."orders" o ON c.custkey = o.custkey '
                "GROUP BY c.name "
                "ORDER BY order_count DESC "
                "LIMIT 5"
            )
        },
        result_format="list",
    )
    assert result.success
    assert len(result.sql_return) == 5
    assert "order_count" in result.sql_return[0]


@pytest.mark.integration
def test_tpch_execute_aggregation(tpch_connector: TrinoConnector):
    """Test aggregation query - count nations per region."""
    result = tpch_connector.execute(
        {
            "sql_query": (
                "SELECT r.name AS region_name, COUNT(n.nationkey) AS nation_count "
                'FROM "tpch"."tiny"."region" r '
                'JOIN "tpch"."tiny"."nation" n ON r.regionkey = n.regionkey '
                "GROUP BY r.name "
                "ORDER BY r.name"
            )
        },
        result_format="list",
    )
    assert result.success
    assert len(result.sql_return) == 5  # 5 regions in TPC-H
    total_nations = sum(row["nation_count"] for row in result.sql_return)
    assert total_nations == 25  # 25 nations total


# ==================== Cross-Catalog Tests ====================


@pytest.mark.integration
def test_switch_to_tpch_catalog(tpch_connector: TrinoConnector):
    """Test switching catalog to tpch and back."""
    original_catalog = tpch_connector.catalog_name
    assert original_catalog == "tpch"

    catalogs = tpch_connector.get_catalogs()
    assert "tpch" in catalogs

    if "memory" in catalogs:
        tpch_connector.switch_catalog("memory")
        assert tpch_connector.catalog_name == "memory"
        tpch_connector.switch_catalog("tpch")
        assert tpch_connector.catalog_name == "tpch"


@pytest.mark.integration
def test_cross_catalog_query(tpch_connector: TrinoConnector):
    """Test querying tpch catalog with fully-qualified table names."""
    result = tpch_connector.execute(
        {"sql_query": 'SELECT COUNT(*) AS cnt FROM "tpch"."tiny"."region"'},
        result_format="list",
    )
    assert result.success
    assert result.sql_return[0]["cnt"] == 5
