# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.

"""Acceptance: OSI -> IR -> MetricFlow YAML must pass real MetricFlow validation.

These run the genuine MetricFlow parser + semantic validator (no DB needed for
parse/semantic) plus an in-memory DuckDB explain for dry-run SQL rendering.
"""

import pytest

from datus_semantic_osi.compiler import compile_document
from datus_semantic_osi.metricflow_backend import lower_to_metricflow
from datus_semantic_osi.profile import parse_osi_profile as parse_osi

pytest.importorskip("metricflow")

# A multi-metric model over the orders table, exercising
# aggregate / count-distinct / average / ratio metric kinds.
OSI_YAML = """
semantic_model:
  name: order_model
datasets:
  - name: orders
    source:
      table: orders
    primary_key: order_id
    time_dimension:
      name: order_date
      granularity: day
    dimensions:
      - name: status
        expr: status
      - name: amount
        expr: amount
  - name: completed_orders
    source:
      query: "SELECT * FROM orders WHERE status = 'completed'"
    primary_key: order_id
    time_dimension:
      name: order_date
      granularity: day
metrics:
  - name: order_count
    description: "Order count"
    expression: "COUNT(DISTINCT order_id)"
    dataset: orders
  - name: completed_order_count
    description: "Completed order count"
    expression: "COUNT(DISTINCT order_id)"
    dataset: completed_orders
  - name: avg_order_amount
    description: "Average order amount"
    expression: "AVG(amount)"
    dataset: orders
  - name: total_order_amount
    description: "Total order amount"
    expression: "SUM(amount)"
    dataset: orders
"""


def _validate(directory):
    from metricflow.model.parsing.dir_to_model import (
        parse_directory_of_yaml_files_to_model,
    )
    from metricflow.model.model_validator import ModelValidator

    build = parse_directory_of_yaml_files_to_model(str(directory))
    parse_errors = [str(e) for e in build.issues.errors]
    semantic = ModelValidator().validate_model(build.model)
    semantic_errors = [str(e) for e in semantic.issues.errors]
    return build, parse_errors, semantic_errors


def test_generated_yaml_passes_metricflow_validation(tmp_path):
    art = lower_to_metricflow(compile_document(parse_osi(OSI_YAML)))
    art.write(tmp_path)

    build, parse_errors, semantic_errors = _validate(tmp_path)

    assert parse_errors == [], f"parse errors: {parse_errors}"
    assert semantic_errors == [], f"semantic errors: {semantic_errors}"
    # all four metrics made it into the model
    metric_names = {m.name for m in build.model.metrics}
    assert {
        "order_count",
        "completed_order_count",
        "avg_order_amount",
        "total_order_amount",
    } <= metric_names


def test_dry_run_renders_sql_for_each_metric(tmp_path):
    art = lower_to_metricflow(compile_document(parse_osi(OSI_YAML)))
    art.write(tmp_path)
    build, parse_errors, semantic_errors = _validate(tmp_path)
    assert parse_errors == [], f"parse errors: {parse_errors}"
    assert semantic_errors == [], f"semantic errors: {semantic_errors}"

    from metricflow.sql_clients.duckdb import DuckDbSqlClient
    from metricflow.api.metricflow_client import MetricFlowClient

    client = MetricFlowClient(
        sql_client=DuckDbSqlClient(),
        user_configured_model=build.model,
        system_schema="main",
    )
    for metric in [
        "order_count",
        "completed_order_count",
        "avg_order_amount",
        "total_order_amount",
    ]:
        sql = client.explain(
            metrics=[metric]
        ).rendered_sql_without_descriptions.sql_query
        assert "orders" in sql
        assert "SELECT" in sql.upper()

    # the query-backed dataset keeps its authored WHERE clause in rendered SQL
    filtered_sql = client.explain(
        metrics=["completed_order_count"]
    ).rendered_sql_without_descriptions.sql_query
    assert "status" in filtered_sql
