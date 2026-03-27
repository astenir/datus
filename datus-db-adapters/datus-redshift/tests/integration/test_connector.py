# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""
Integration tests for Redshift connector.

These tests require a running Redshift cluster with proper credentials.
Set these environment variables to run the tests:
- REDSHIFT_HOST
- REDSHIFT_USERNAME
- REDSHIFT_PASSWORD
- REDSHIFT_DATABASE (optional, defaults to 'dev')
"""

import os

import pytest
from datus_redshift import RedshiftConnector

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("REDSHIFT_HOST"),
        reason="Redshift credentials not available in environment variables",
    ),
]


class TestRedshiftConnector:
    """Integration test cases for RedshiftConnector class."""

    def test_connector_creation(self, config):
        """Test that connector can be created successfully."""
        connector = RedshiftConnector(config)
        assert connector is not None
        assert connector.get_type() == "redshift"
        connector.close()

    def test_connection(self, connector):
        """Test that connection works."""
        result = connector.test_connection()

        assert result["success"] is True
        assert "message" in result
        assert result["message"] == "Connection successful"

    def test_simple_query(self, connector):
        """Test executing a simple query."""
        result = connector.execute_query("SELECT 1 as test_column")

        assert result.success is True
        assert result.row_count == 1
        assert "test_column" in result.sql_return

    def test_query_with_parameters(self, connector):
        """Test executing a query with parameters."""
        result = connector.execute_arrow("SELECT %s as value", [42])

        assert result.success is True
        assert result.row_count == 1

    def test_get_databases(self, connector):
        """Test getting list of databases."""
        databases = connector.get_databases(include_sys=False)

        assert isinstance(databases, list)
        assert len(databases) > 0
        assert connector.database_name in databases

    def test_get_schemas(self, connector):
        """Test getting list of schemas."""
        schemas = connector.get_schemas(include_sys=False)

        assert isinstance(schemas, list)
        assert len(schemas) > 0
        assert "public" in schemas

    def test_get_tables(self, connector):
        """Test getting list of tables."""
        tables = connector.get_tables(schema_name="public")

        assert isinstance(tables, list)

    def test_execute_different_formats(self, connector):
        """Test executing query with different output formats."""
        sql = "SELECT 1 as num, 'test' as str"

        result_csv = connector.execute_query(sql, result_format="csv")
        assert result_csv.success is True
        assert result_csv.result_format == "csv"
        assert isinstance(result_csv.sql_return, str)

        result_pandas = connector.execute_query(sql, result_format="pandas")
        assert result_pandas.success is True
        assert result_pandas.result_format == "pandas"

        result_arrow = connector.execute_query(sql, result_format="arrow")
        assert result_arrow.success is True
        assert result_arrow.result_format == "arrow"

        result_list = connector.execute_query(sql, result_format="list")
        assert result_list.success is True
        assert result_list.result_format == "list"
        assert isinstance(result_list.sql_return, list)

    def test_error_handling(self, connector):
        """Test that errors are handled properly."""
        result = connector.execute_query("SELECT * FROM nonexistent_table_xyz")

        assert result.success is False
        assert result.error is not None
        assert len(result.error) > 0


class TestRedshiftMetadata:
    """Integration test cases for metadata retrieval."""

    def test_full_name_generation(self, connector):
        """Test generating fully qualified table names."""
        full_name = connector.full_name(database_name="mydb", schema_name="myschema", table_name="mytable")
        assert full_name == '"mydb"."myschema"."mytable"'

        full_name = connector.full_name(schema_name="myschema", table_name="mytable")
        assert full_name == '"myschema"."mytable"'

        full_name = connector.full_name(table_name="mytable")
        assert full_name == '"mytable"'

    def test_identifier_generation(self, connector):
        """Test generating table identifiers."""
        identifier = connector.identifier(database_name="mydb", schema_name="myschema", table_name="mytable")
        assert "mydb" in identifier
        assert "myschema" in identifier
        assert "mytable" in identifier
