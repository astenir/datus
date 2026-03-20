# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Unit tests for constants module."""

from datus_db_core.constants import SQLType


class TestSQLType:
    def test_all_sql_types_exist(self):
        expected = {
            "SELECT",
            "INSERT",
            "UPDATE",
            "DELETE",
            "MERGE",
            "DDL",
            "METADATA_SHOW",
            "EXPLAIN",
            "CONTENT_SET",
            "UNKNOWN",
        }
        actual = {member.name for member in SQLType}
        assert actual == expected

    def test_sql_type_values(self):
        assert SQLType.SELECT == "select"
        assert SQLType.INSERT == "insert"
        assert SQLType.UPDATE == "update"
        assert SQLType.DELETE == "delete"
        assert SQLType.MERGE == "merge"
        assert SQLType.DDL == "ddl"
        assert SQLType.METADATA_SHOW == "metadata"
        assert SQLType.EXPLAIN == "explain"
        assert SQLType.CONTENT_SET == "context_set"
        assert SQLType.UNKNOWN == "unknown"

    def test_sql_type_is_str_enum(self):
        assert isinstance(SQLType.SELECT, str)
        assert SQLType.SELECT.upper() == "SELECT"
