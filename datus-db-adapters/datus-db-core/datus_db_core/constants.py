# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

from enum import Enum


class SQLType(str, Enum):
    """SQL statement types."""

    SELECT = "select"
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    MERGE = "merge"
    DDL = "ddl"
    METADATA_SHOW = "metadata"
    EXPLAIN = "explain"
    CONTENT_SET = "context_set"
    UNKNOWN = "unknown"
