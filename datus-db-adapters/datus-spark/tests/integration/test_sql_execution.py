# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import uuid

import pytest
from datus_spark import SparkConfig, SparkConnector

# ==================== Query Execution Tests ====================


@pytest.mark.integration
@pytest.mark.acceptance
def test_execute_select_query(connector: SparkConnector):
    """Test executing simple SELECT query."""
    result = connector.execute({"sql_query": "SELECT 1 as num"}, result_format="list")
    assert result.success
    assert not result.error


@pytest.mark.integration
def test_execute_select_csv_format(connector: SparkConnector):
    """Test executing SELECT with CSV result format."""
    result = connector.execute({"sql_query": "SELECT 1 as num, 'hello' as msg"}, result_format="csv")
    assert result.success
    assert "num" in result.sql_return


# ==================== DDL Operation Tests ====================


@pytest.mark.integration
@pytest.mark.acceptance
def test_execute_ddl_create_drop(connector: SparkConnector, config: SparkConfig):
    """Test DDL operations (CREATE/DROP table)."""
    suffix = uuid.uuid4().hex[:8]
    table_name = f"datus_test_{suffix}"

    db = config.database or "default"
    full_name = f"`{db}`.`{table_name}`"

    create_sql = f"""
    CREATE TABLE IF NOT EXISTS {full_name} (
        id BIGINT,
        name STRING
    ) USING PARQUET
    """

    try:
        create_result = connector.execute_ddl(create_sql)
        assert create_result.success, f"Failed to create table: {create_result.error}"
    finally:
        connector.execute_ddl(f"DROP TABLE IF EXISTS {full_name}")


# ==================== Error Handling Tests ====================


@pytest.mark.integration
def test_execute_error_handling(connector: SparkConnector):
    """Test SQL error handling."""
    result = connector.execute({"sql_query": "SELECT * FROM nonexistent_table_12345"})
    assert not result.success or result.error
