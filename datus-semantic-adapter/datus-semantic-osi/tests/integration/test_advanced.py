# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.

"""Advanced modeling: multi-hop join and semi-additive measures.

All validated against real MetricFlow (parse + semantic) and DuckDB explain.
"""

import tempfile

import pytest

pytest.importorskip("metricflow")

from datus_semantic_osi.compiler import compile_document
from datus_semantic_osi.metricflow_backend import lower_to_metricflow
from datus_semantic_osi.profile import parse_osi_profile as parse_osi


def _build_and_validate(osi: str):
    model = compile_document(parse_osi(osi))
    d = tempfile.mkdtemp()
    lower_to_metricflow(model).write(d)
    from metricflow.model.model_validator import ModelValidator
    from metricflow.model.parsing.dir_to_model import (
        parse_directory_of_yaml_files_to_model,
    )

    build = parse_directory_of_yaml_files_to_model(d)
    parse_errors = [str(e) for e in build.issues.errors]
    semantic = ModelValidator().validate_model(build.model)
    semantic_errors = [str(e) for e in semantic.issues.errors]
    return model, build, parse_errors, semantic_errors


def _explain(build, metrics, dimensions=None):
    from metricflow.api.metricflow_client import MetricFlowClient
    from metricflow.sql_clients.duckdb import DuckDbSqlClient

    client = MetricFlowClient(
        sql_client=DuckDbSqlClient(),
        user_configured_model=build.model,
        system_schema="main",
    )
    return client.explain(
        metrics=metrics, dimensions=dimensions or []
    ).rendered_sql_without_descriptions.sql_query


MULTI_HOP = """
semantic_model: {name: shop}
datasets:
  - {name: orders, source: {table: orders}, primary_key: order_id, time_dimension: {name: order_date, granularity: day}}
  - {name: customers, source: {table: customers}, primary_key: customer_id, dimensions: [{name: region_id, expr: region_id}]}
  - {name: regions, source: {table: regions}, primary_key: region_id, dimensions: [{name: region_name, expr: region_name}]}
relationships:
  - {name: o2c, from: orders, to: customers, from_columns: [customer_id], to_columns: [customer_id]}
  - {name: c2r, from: customers, to: regions, from_columns: [region_id], to_columns: [region_id]}
metrics:
  - {name: order_count, expression: "COUNT(DISTINCT order_id)", dataset: orders}
"""

SEMI_ADDITIVE = """
semantic_model: {name: bank}
datasets:
  - name: balances
    source: {table: account_balances}
    primary_key: account_id
    time_dimension: {name: ds, granularity: day}
metrics:
  - name: total_balance
    description: "balance: sum across accounts, last value over time"
    expression: "SUM(balance)"
    dataset: balances
    non_additive_dimension: {name: ds, window_choice: max}
"""

def test_multi_hop_join_resolves_two_joins():
    _model, build, parse_errors, sem_errors = _build_and_validate(MULTI_HOP)
    assert parse_errors == [], parse_errors
    assert sem_errors == [], sem_errors
    sql = _explain(build, ["order_count"], ["customer_id__region_id__region_name"])
    assert sql.upper().count("JOIN") == 2


def test_semi_additive_measure_lowers_and_validates():
    model, _build, parse_errors, sem_errors = _build_and_validate(SEMI_ADDITIVE)
    assert parse_errors == [], parse_errors
    assert sem_errors == [], sem_errors
    art = lower_to_metricflow(model)
    measure = art.data_source_docs[0]["data_source"]["measures"][0]
    assert measure["non_additive_dimension"]["name"] == "ds"
    assert measure["non_additive_dimension"]["window_choice"] == "max"
