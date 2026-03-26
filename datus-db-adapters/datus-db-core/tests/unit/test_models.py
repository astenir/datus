# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Unit tests for models module."""

import pandas as pd
import pytest
from datus_db_core.models import (
    BaseInput,
    BaseResult,
    ExecuteSQLInput,
    ExecuteSQLResult,
)
from pydantic import ValidationError


class TestBaseInput:
    def test_get_existing_field(self):
        class MyInput(BaseInput):
            name: str = "test"

        inp = MyInput()
        assert inp.get("name") == "test"

    def test_get_missing_field_default(self):
        class MyInput(BaseInput):
            name: str = "test"

        inp = MyInput()
        assert inp.get("missing", "default") == "default"

    def test_getitem(self):
        class MyInput(BaseInput):
            name: str = "test"

        inp = MyInput()
        assert inp["name"] == "test"

    def test_to_str_and_from_str(self):
        class MyInput(BaseInput):
            name: str = "hello"

        inp = MyInput()
        json_str = inp.to_str()
        restored = MyInput.from_str(json_str)
        assert restored.name == "hello"


class TestBaseResult:
    def test_success_result(self):
        result = BaseResult(success=True)
        assert result.success is True
        assert result.error is None

    def test_error_result(self):
        result = BaseResult(success=False, error="Something failed")
        assert result.success is False
        assert result.error == "Something failed"

    def test_get_method(self):
        result = BaseResult(success=True, error="msg")
        assert result.get("success") is True
        assert result.get("error") == "msg"
        assert result.get("missing", "default") == "default"


class TestExecuteSQLInput:
    def test_basic_creation(self):
        inp = ExecuteSQLInput(sql_query="SELECT 1")
        assert inp.sql_query == "SELECT 1"
        assert inp.database_name == ""
        assert inp.result_format == "csv"

    def test_with_all_fields(self):
        inp = ExecuteSQLInput(
            sql_query="SELECT * FROM t",
            database_name="my_db",
            result_format="arrow",
        )
        assert inp.database_name == "my_db"
        assert inp.result_format == "arrow"

    def test_sql_query_required(self):
        with pytest.raises(ValidationError):
            ExecuteSQLInput()


class TestExecuteSQLResult:
    def test_basic_creation(self):
        result = ExecuteSQLResult(
            success=True, sql_query="SELECT 1", row_count=1, sql_return="1"
        )
        assert result.success is True
        assert result.row_count == 1
        assert result.sql_return == "1"

    def test_compact_result_with_string(self):
        result = ExecuteSQLResult(
            success=True,
            sql_query="SELECT 1",
            row_count=5,
            sql_return="col1,col2\n1,a\n2,b",
        )
        compact = result.compact_result()
        assert "Row count: 5" in compact
        assert "col1,col2" in compact

    def test_compact_result_with_dataframe(self):
        df = pd.DataFrame({"col1": [1, 2], "col2": ["a", "b"]})
        result = ExecuteSQLResult(
            success=True,
            sql_query="SELECT *",
            row_count=2,
            sql_return=df,
        )
        compact = result.compact_result()
        assert "Row count: 2" in compact
        assert "col1" in compact

    def test_compact_result_truncation(self):
        long_string = "x" * 5000
        result = ExecuteSQLResult(
            success=True,
            sql_query="SELECT *",
            row_count=1,
            sql_return=long_string,
        )
        compact = result.compact_result()
        assert compact.endswith("...")
        assert len(compact) < 5000

    def test_compact_result_none_sql_return(self):
        result = ExecuteSQLResult(
            success=True,
            sql_query="CREATE TABLE t(id INT)",
            row_count=0,
            sql_return=None,
        )
        compact = result.compact_result()
        assert "Row count: 0" in compact

    def test_error_result(self):
        result = ExecuteSQLResult(
            success=False,
            error="Syntax error",
            sql_query="SELCT 1",
            row_count=0,
            sql_return="",
        )
        assert result.success is False
        assert result.error == "Syntax error"

    def test_arbitrary_types_allowed(self):
        import pyarrow as pa

        table = pa.table({"col": [1, 2, 3]})
        result = ExecuteSQLResult(
            success=True,
            sql_query="SELECT *",
            row_count=3,
            sql_return=table,
        )
        assert isinstance(result.sql_return, pa.Table)
