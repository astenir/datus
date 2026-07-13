# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.

"""Tests for OSI execution backend helpers."""

from datus_semantic_osi.backend import _db_config_value


def test_db_config_value_supports_runtime_context_aliases():
    assert (
        _db_config_value(
            {
                "database_name": "college_exam",
                "db_schema": "runtime_schema",
                "catalog_name": "runtime_catalog",
            },
            "database",
            "database_name",
        )
        == "college_exam"
    )


def test_db_config_value_skips_blank_values():
    assert (
        _db_config_value(
            {
                "database": " ",
                "database_name": "runtime_db",
            },
            "database",
            "database_name",
        )
        == "runtime_db"
    )
