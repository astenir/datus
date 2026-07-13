# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.

"""Datasource-derived sqlglot dialect: resolution, threading, and portability."""

import pytest

from datus_semantic_osi.compiler import compile_metric_expression
from datus_semantic_osi.dialects import DEFAULT_SQLGLOT_DIALECT, resolve_sqlglot_dialect
from datus_semantic_osi.ir import MetricKind


@pytest.mark.parametrize(
    "datasource, expected",
    [
        ("starrocks", "starrocks"),
        ("mysql", "mysql"),
        ("postgresql", "postgres"),  # alias
        ("greenplum", "postgres"),  # alias
        ("duckdb", "duckdb"),
        ("snowflake", "snowflake"),
        ("STARROCKS", "starrocks"),  # case-insensitive
        ("", DEFAULT_SQLGLOT_DIALECT),
        (None, DEFAULT_SQLGLOT_DIALECT),
        ("not_a_real_engine", DEFAULT_SQLGLOT_DIALECT),  # unknown -> fallback
    ],
)
def test_resolve_sqlglot_dialect(datasource, expected):
    assert resolve_sqlglot_dialect(datasource) == expected


def test_compile_parses_datasource_native_function_under_its_dialect():
    # FIND_IN_SET is StarRocks/MySQL-specific; it must parse+compile under the
    # datasource dialect rather than a hardcoded one.
    metric = compile_metric_expression(
        "tagged_activity",
        "COUNT(DISTINCT CASE WHEN FIND_IN_SET('1', tags) THEN id END)",
        dialect="starrocks",
    )
    assert metric.kind is MetricKind.AGGREGATE
    assert "FIND_IN_SET" in metric.measures[0].expr


def test_adapter_dialect_uses_datasource_type_not_config_name(tmp_path):
    # A snowflake source named "prod_wh" must resolve to snowflake, not the default.
    from datus_semantic_osi.adapter import DatusOSIAdapter
    from datus_semantic_osi.config import DatusOSIConfig

    adapter = DatusOSIAdapter(
        DatusOSIConfig(
            semantic_models_path=str(tmp_path),
            datasource="prod_wh",
            db_config={"type": "snowflake"},
        )
    )
    assert adapter._dialect == "snowflake"
