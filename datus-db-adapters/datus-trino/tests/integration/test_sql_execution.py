# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import pytest

from datus_trino import TrinoConnector

# ==================== Query Execution Tests ====================


@pytest.mark.integration
@pytest.mark.acceptance
def test_execute_select_query(connector: TrinoConnector):
    """Test executing simple SELECT query."""
    result = connector.execute({"sql_query": "SELECT 1 as num"}, result_format="list")
    assert result.success
    assert not result.error
    assert result.sql_return == [{"num": 1}]


@pytest.mark.integration
def test_execute_select_with_multiple_rows(connector: TrinoConnector):
    """Test executing SELECT with multiple rows."""
    result = connector.execute(
        {"sql_query": "SELECT * FROM (VALUES (1, 'a'), (2, 'b'), (3, 'c')) AS t(id, name)"},
        result_format="list",
    )
    assert result.success
    assert len(result.sql_return) == 3


@pytest.mark.integration
def test_execute_select_csv_format(connector: TrinoConnector):
    """Test executing SELECT with CSV result format."""
    result = connector.execute({"sql_query": "SELECT 1 as num, 'hello' as msg"}, result_format="csv")
    assert result.success
    assert "num" in result.sql_return
    assert "hello" in result.sql_return


# ==================== Error Handling Tests ====================


@pytest.mark.integration
def test_execute_error_handling(connector: TrinoConnector):
    """Test SQL error handling."""
    result = connector.execute({"sql_query": "SELECT * FROM nonexistent_table_12345"})
    assert not result.success or result.error
