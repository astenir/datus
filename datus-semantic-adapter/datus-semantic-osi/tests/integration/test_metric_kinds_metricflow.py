# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.

"""Cumulative and derived metrics must pass real MetricFlow validation."""

import pytest

pytest.importorskip("metricflow")

from datus_semantic_osi.compiler import compile_document
from datus_semantic_osi.metricflow_backend import lower_to_metricflow
from datus_semantic_osi.profile import parse_osi_profile as parse_osi

OSI_YAML = """
semantic_model:
  name: shop
datasets:
  - name: orders
    source:
      table: orders
    primary_key: order_id
    time_dimension:
      name: order_date
      granularity: day
metrics:
  - name: revenue
    expression: "SUM(amount)"
    dataset: orders
  - name: order_count
    expression: "COUNT(DISTINCT order_id)"
    dataset: orders
  - name: revenue_l7d
    description: "trailing 7-day revenue"
    expression: "SUM(amount)"
    dataset: orders
    time_dimension: order_date
    window: "7 days"
  - name: avg_order_value
    description: "revenue per order"
    metric_kind: derived
    expression: "revenue * 1.0 / NULLIF(order_count, 0)"
    inputs:
      - revenue
      - order_count
"""


def test_cumulative_and_derived_pass_metricflow_validation(tmp_path):
    art = lower_to_metricflow(compile_document(parse_osi(OSI_YAML)))
    art.write(tmp_path)

    from metricflow.model.model_validator import ModelValidator
    from metricflow.model.parsing.dir_to_model import (
        parse_directory_of_yaml_files_to_model,
    )

    build = parse_directory_of_yaml_files_to_model(str(tmp_path))
    parse_errors = [str(e) for e in build.issues.errors]
    assert parse_errors == [], f"parse errors: {parse_errors}"

    semantic = ModelValidator().validate_model(build.model)
    semantic_errors = [str(e) for e in semantic.issues.errors]
    assert semantic_errors == [], f"semantic errors: {semantic_errors}"

    names = {m.name for m in build.model.metrics}
    assert {"revenue_l7d", "avg_order_value"} <= names
