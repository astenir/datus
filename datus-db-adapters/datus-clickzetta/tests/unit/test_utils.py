# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Unit tests for utility functions in ClickZetta connector."""

import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
import sys


class TestUtilityFunctions:
    """Test suite for standalone utility functions."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Setup mock environment for testing."""
        # Mock datus modules to avoid import errors
        mock_datus = MagicMock()

        # Mock required modules
        sys.modules['datus'] = mock_datus
        sys.modules['datus.schemas'] = MagicMock()
        sys.modules['datus.schemas.base'] = MagicMock()
        sys.modules['datus.schemas.node_models'] = MagicMock()
        sys.modules['datus.tools'] = MagicMock()
        sys.modules['datus.tools.db_tools'] = MagicMock()
        sys.modules['datus.tools.db_tools.base'] = MagicMock()
        sys.modules['datus.utils'] = MagicMock()
        sys.modules['datus.utils.constants'] = MagicMock()
        sys.modules['datus.utils.exceptions'] = MagicMock()
        sys.modules['datus.utils.loggings'] = MagicMock()
        sys.modules['datus.utils.sql_utils'] = MagicMock()

    def test_safe_escape(self):
        """Test SQL string escaping function."""
        from datus_clickzetta.connector import _safe_escape

        # Test normal string
        assert _safe_escape("test") == "test"

        # Test string with single quotes
        assert _safe_escape("test'quote") == "test''quote"

        # Test string with multiple quotes
        assert _safe_escape("test'multiple'quotes'here") == "test''multiple''quotes''here"

        # Test None input
        assert _safe_escape(None) == ""

        # Test empty string
        assert _safe_escape("") == ""

    def test_safe_escape_identifier(self):
        """Test SQL identifier escaping function."""
        from datus_clickzetta.connector import _safe_escape_identifier

        # Test normal identifier
        assert _safe_escape_identifier("test") == "test"

        # Test identifier with backticks
        assert _safe_escape_identifier("test`backtick") == "test``backtick"

        # Test identifier with multiple backticks
        assert _safe_escape_identifier("test`multi`backticks") == "test``multi``backticks"

        # Test None input
        assert _safe_escape_identifier(None) == ""

        # Test empty string
        assert _safe_escape_identifier("") == ""

    def test_extract_row_count(self):
        """Test row count extraction from DataFrame."""
        from datus_clickzetta.connector import ClickZettaConnector

        # Test with 'rows' column
        df = pd.DataFrame({"rows": [5], "other": [10]})
        count = ClickZettaConnector._extract_row_count(df)
        assert count == 5

        # Test with 'row_count' column
        df = pd.DataFrame({"row_count": [3], "other": [10]})
        count = ClickZettaConnector._extract_row_count(df)
        assert count == 3

        # Test with 'rows_affected' column
        df = pd.DataFrame({"rows_affected": [7], "other": [10]})
        count = ClickZettaConnector._extract_row_count(df)
        assert count == 7

        # Test with empty DataFrame
        df = pd.DataFrame()
        count = ClickZettaConnector._extract_row_count(df)
        assert count == 0

        # Test with no count columns (fallback to len)
        df = pd.DataFrame({"col1": [1, 2, 3], "col2": [4, 5, 6]})
        count = ClickZettaConnector._extract_row_count(df)
        assert count == 3

        # Test with None input
        count = ClickZettaConnector._extract_row_count(None)
        assert count == 0

    def test_normalize_volume_uri(self):
        """Test volume URI normalization."""
        from datus_clickzetta.connector import ClickZettaConnector

        # Test volume: format
        uri = ClickZettaConnector._normalize_volume_uri("volume:user://my_volume", "path/file.yaml")
        assert uri == "volume:user://my_volume/path/file.yaml"

        # Test @ format (stage)
        uri = ClickZettaConnector._normalize_volume_uri("@my_stage", "path/file.yaml")
        assert uri == "@my_stage/path/file.yaml"

        # Test with empty relative path
        uri = ClickZettaConnector._normalize_volume_uri("volume:user://my_volume", "")
        assert uri == "volume:user://my_volume"

        # Test with slash trimming
        uri = ClickZettaConnector._normalize_volume_uri("volume:user://my_volume/", "/path/file.yaml")
        assert uri == "volume:user://my_volume/path/file.yaml"

        # Test error cases
        with pytest.raises(ValueError, match="Volume name must not be empty"):
            ClickZettaConnector._normalize_volume_uri("", "file.yaml")

        with pytest.raises(ValueError, match="Unsupported volume/stage format"):
            ClickZettaConnector._normalize_volume_uri("invalid_format", "file.yaml")

    @patch('datus_clickzetta.connector.Session')
    def test_ddl_definition_building(self, mock_session_class):
        """Test DDL definition building functionality."""
        from datus_clickzetta.connector import ClickZettaConnector

        # Setup mock session
        mock_session = MagicMock()
        mock_session_class.builder.configs.return_value.create.return_value = mock_session

        # Create connector instance
        connector = ClickZettaConnector(
            service="service", username="user", password="pass",
            instance="instance", workspace="workspace"
        )

        # Test simple table definition
        columns = [
            {"column_name": "id", "data_type": "INT", "comment": "Primary key"},
            {"column_name": "name", "data_type": "VARCHAR(50)"},
        ]

        definition = connector._build_definition(
            workspace="workspace",
            schema_name="schema",
            table_name="test_table",
            columns=columns,
            table_comment="Test table"
        )

        # Verify DDL components
        assert "CREATE TABLE" in definition
        assert "`workspace`.`schema`.`test_table`" in definition
        assert "`id` INT COMMENT 'Primary key'" in definition
        assert "`name` VARCHAR(50)" in definition
        assert "COMMENT = 'Test table'" in definition

        # Test definition without comments
        columns_no_comment = [
            {"column_name": "id", "data_type": "INT"},
            {"column_name": "name", "data_type": "VARCHAR(50)"},
        ]

        definition = connector._build_definition(
            workspace="workspace",
            schema_name="schema",
            table_name="simple_table",
            columns=columns_no_comment
        )

        assert "CREATE TABLE" in definition
        assert "`workspace`.`schema`.`simple_table`" in definition
        assert "`id` INT" in definition
        assert "COMMENT 'Primary key'" not in definition

        # Test view definition
        definition = connector._build_definition(
            workspace="workspace",
            schema_name="schema",
            table_name="test_view",
            columns=columns,
            table_type="view"
        )

        assert "CREATE VIEW" in definition

        connector.close()


class TestVolumeOperations:
    """Test suite for volume-related operations."""

    def test_volume_uri_edge_cases(self):
        """Test edge cases for volume URI handling."""
        from datus_clickzetta.connector import ClickZettaConnector

        # Test with trailing slashes
        uri = ClickZettaConnector._normalize_volume_uri("volume:user://test/", "file.txt")
        assert uri == "volume:user://test/file.txt"

        # Test with leading slashes in path
        uri = ClickZettaConnector._normalize_volume_uri("volume:user://test", "/file.txt")
        assert uri == "volume:user://test/file.txt"

        # Test stage with trailing slash
        uri = ClickZettaConnector._normalize_volume_uri("@stage/", "file.txt")
        assert uri == "@stage/file.txt"

        # Test nested paths
        uri = ClickZettaConnector._normalize_volume_uri("volume:user://vol", "dir1/dir2/file.txt")
        assert uri == "volume:user://vol/dir1/dir2/file.txt"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])