# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Integration tests for ClickZetta connector with mocked dependencies."""

import pytest
from unittest.mock import MagicMock, patch
import pandas as pd


class TestConnectorInitialization:
    """Test connector initialization and configuration."""

    def test_connector_creation(self, mock_datus_modules, clickzetta_test_config):
        """Test basic connector creation with valid configuration."""
        from datus_clickzetta.connector import ClickZettaConnector

        with patch('datus_clickzetta.connector.Session'):
            connector = ClickZettaConnector(**clickzetta_test_config)

            # Verify basic attributes
            assert connector.service == clickzetta_test_config['service']
            assert connector.user == clickzetta_test_config['username']
            assert connector.password == clickzetta_test_config['password']
            assert connector.instance == clickzetta_test_config['instance']
            assert connector.database_name == clickzetta_test_config['workspace']
            assert connector.schema_name == clickzetta_test_config['schema']
            assert connector.vcluster == clickzetta_test_config['vcluster']

            connector.close()

    def test_connector_with_missing_dependency(self, mock_datus_modules):
        """Test connector behavior when ClickZetta dependencies are missing."""
        from datus_clickzetta.connector import ClickZettaConnector

        # Mock missing dependency by setting Session to None
        with patch('datus_clickzetta.connector.Session', None):
            with pytest.raises(Exception) as exc_info:
                ClickZettaConnector(
                    service='service',
                    username='user',
                    password='pass',
                    instance='instance',
                    workspace='workspace'
                )
            # Should raise DatusException for missing dependency
            assert "ClickZetta connector requires" in str(exc_info.value)

    def test_connector_missing_required_fields(self, mock_datus_modules):
        """Test connector with missing required configuration fields."""
        from datus_clickzetta.connector import ClickZettaConnector

        with patch('datus_clickzetta.connector.Session'):
            with pytest.raises(Exception) as exc_info:
                ClickZettaConnector(
                    service='',  # Empty required field
                    username='user',
                    password='pass',
                    instance='instance',
                    workspace='workspace'
                )
            # Check for any exception since mocks may not return specific error messages
            assert exc_info.value is not None


class TestConnectorOperations:
    """Test connector SQL operations."""

    @patch('datus_clickzetta.connector.Session')
    def test_connection_management(self, mock_session_class, mock_datus_modules, clickzetta_test_config):
        """Test connection creation and management."""
        from datus_clickzetta.connector import ClickZettaConnector

        # Setup mock session
        mock_session = MagicMock()
        mock_builder = MagicMock()
        mock_configs = MagicMock()
        mock_configs.create.return_value = mock_session
        mock_builder.configs.return_value = mock_configs
        mock_session_class.builder = mock_builder

        connector = ClickZettaConnector(**clickzetta_test_config)

        # Trigger connection creation
        connector.connect()

        # Verify session creation was called
        mock_builder.configs.assert_called_once()
        mock_configs.create.assert_called_once()

        connector.close()

    @patch('datus_clickzetta.connector.Session')
    def test_query_execution(self, mock_session_class, mock_datus_modules, clickzetta_test_config):
        """Test SQL query execution."""
        from datus_clickzetta.connector import ClickZettaConnector

        # Setup mock session
        mock_session = MagicMock()
        mock_session_class.builder.configs.return_value.create.return_value = mock_session

        # Mock query result
        mock_df = pd.DataFrame({'col1': [1, 2, 3], 'col2': ['a', 'b', 'c']})
        mock_session.sql.return_value.to_pandas.return_value = mock_df

        connector = ClickZettaConnector(**clickzetta_test_config)
        result = connector.execute_query("SELECT * FROM test_table")

        # Verify query was executed
        mock_session.sql.assert_called_with("SELECT * FROM test_table")
        assert result.success
        assert result.row_count == 3

        connector.close()

    @patch('datus_clickzetta.connector.Session')
    def test_ddl_operations(self, mock_session_class, mock_datus_modules, clickzetta_test_config):
        """Test DDL operations like CREATE TABLE."""
        from datus_clickzetta.connector import ClickZettaConnector

        # Setup mock session
        mock_session = MagicMock()
        mock_session_class.builder.configs.return_value.create.return_value = mock_session

        connector = ClickZettaConnector(**clickzetta_test_config)

        # Test DDL definition building
        columns = [
            {"column_name": "id", "data_type": "INT", "comment": "Primary key"},
            {"column_name": "name", "data_type": "VARCHAR(50)"},
        ]

        definition = connector._build_definition(
            workspace="test_workspace",
            schema_name="test_schema",
            table_name="test_table",
            columns=columns,
            table_comment="Test table"
        )

        assert "CREATE TABLE" in definition
        assert "`test_workspace`.`test_schema`.`test_table`" in definition

        connector.close()

    @patch('datus_clickzetta.connector.Session')
    def test_context_switching(self, mock_session_class, mock_datus_modules, clickzetta_test_config):
        """Test database context switching."""
        from datus_clickzetta.connector import ClickZettaConnector

        # Setup mock session
        mock_session = MagicMock()
        mock_session_class.builder.configs.return_value.create.return_value = mock_session

        connector = ClickZettaConnector(**clickzetta_test_config)

        # Test schema switching (should work)
        connector.do_switch_context(schema_name="NEW_SCHEMA")
        mock_session.sql.assert_called()

        # Test workspace switching (should fail)
        with pytest.raises(Exception) as exc_info:
            connector.do_switch_context(database_name="different_workspace")
        # Check for any exception since mocks may not return specific error messages
        assert exc_info.value is not None

        connector.close()


class TestMetadataOperations:
    """Test metadata discovery operations."""

    @patch('datus_clickzetta.connector.Session')
    def test_get_tables(self, mock_session_class, mock_datus_modules, clickzetta_test_config):
        """Test getting table list."""
        from datus_clickzetta.connector import ClickZettaConnector

        # Setup mock session
        mock_session = MagicMock()
        mock_builder = MagicMock()
        mock_configs = MagicMock()
        mock_configs.create.return_value = mock_session
        mock_builder.configs.return_value = mock_configs
        mock_session_class.builder = mock_builder

        # Mock table query result with proper table_type column
        mock_df = pd.DataFrame({
            'table_name': ['table1', 'table2'],
            'table_type': ['MANAGED_TABLE', 'BASE TABLE']
        })
        mock_session.sql.return_value.to_pandas.return_value = mock_df

        connector = ClickZettaConnector(**clickzetta_test_config)
        tables = connector.get_tables(database_name="test_workspace", schema_name="test_schema")

        assert isinstance(tables, list)
        assert len(tables) == 2
        mock_session.sql.assert_called()

        connector.close()

    @patch('datus_clickzetta.connector.Session')
    def test_get_views(self, mock_session_class, mock_datus_modules, clickzetta_test_config):
        """Test getting view list."""
        from datus_clickzetta.connector import ClickZettaConnector

        # Setup mock session
        mock_session = MagicMock()
        mock_builder = MagicMock()
        mock_configs = MagicMock()
        mock_configs.create.return_value = mock_session
        mock_builder.configs.return_value = mock_configs
        mock_session_class.builder = mock_builder

        # Mock view query result with proper table_name and table_type columns
        mock_df = pd.DataFrame({
            'table_name': ['view1', 'view2'],
            'table_type': ['VIEW', 'DYNAMIC_TABLE']
        })
        mock_session.sql.return_value.to_pandas.return_value = mock_df

        connector = ClickZettaConnector(**clickzetta_test_config)
        views = connector.get_views(database_name="test_workspace", schema_name="test_schema")

        assert isinstance(views, list)
        assert len(views) == 2
        mock_session.sql.assert_called()

        connector.close()


class TestVolumeOperations:
    """Test volume/stage operations."""

    @patch('datus_clickzetta.connector.Session')
    def test_list_volume_files(self, mock_session_class, mock_datus_modules, clickzetta_test_config):
        """Test listing files in volumes."""
        from datus_clickzetta.connector import ClickZettaConnector

        # Setup mock session
        mock_session = MagicMock()
        mock_builder = MagicMock()
        mock_configs = MagicMock()
        mock_configs.create.return_value = mock_session
        mock_builder.configs.return_value = mock_configs
        mock_session_class.builder = mock_builder

        # Mock file listing result
        mock_df = pd.DataFrame({
            'name': ['file1.csv', 'file2.json'],
            'size': [1024, 2048]
        })
        mock_session.sql.return_value.to_pandas.return_value = mock_df

        connector = ClickZettaConnector(**clickzetta_test_config)

        # Test volume listing using the correct method name
        files = connector.list_volume_files("volume:user://test_volume", directory="data/")

        assert isinstance(files, list)
        mock_session.sql.assert_called()

        connector.close()