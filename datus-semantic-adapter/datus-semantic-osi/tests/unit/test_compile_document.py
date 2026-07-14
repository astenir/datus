# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.

"""Tests for compiling a whole OSI authoring document into a SemanticModelIR."""

import pytest

from datus_semantic_osi.compiler import compile_document
from datus_semantic_osi.errors import OSIValidationError
from datus_semantic_osi.ir import Aggregation, MetricKind
from datus_semantic_osi.profile import parse_osi_profile as parse_osi

OSI_YAML = """
semantic_model:
  name: order_model
datasets:
  - name: completed_orders
    source:
      query: "SELECT * FROM orders WHERE status = 'completed'"
    primary_key: order_id
    time_dimension:
      name: order_date
      granularity: day
    dimensions:
      - name: status
        expr: status
metrics:
  - name: completed_order_count
    description: "Completed order count"
    expression: "COUNT(DISTINCT order_id)"
    dataset: completed_orders
    time_dimension: order_date
"""


def test_compile_document_builds_query_backed_dataset():
    model = compile_document(parse_osi(OSI_YAML))
    assert len(model.datasets) == 1
    ds = model.datasets[0]
    assert ds.name == "completed_orders"
    assert ds.sql_query == "SELECT * FROM orders WHERE status = 'completed'"
    assert ds.primary_time_dimension == "order_date"


def test_compile_document_builds_metric_with_backing_measure():
    model = compile_document(parse_osi(OSI_YAML))
    assert len(model.metrics) == 1
    metric = model.metrics[0]
    assert metric.name == "completed_order_count"
    assert metric.kind is MetricKind.AGGREGATE
    assert metric.dataset == "completed_orders"
    assert metric.time_dimension == "order_date"
    assert metric.measures[0].agg is Aggregation.COUNT_DISTINCT
    assert metric.measures[0].expr == "order_id"


def test_measure_metric_requires_dataset_when_model_has_multiple_datasets():
    osi = """
semantic_model:
  name: multi_dataset_model
datasets:
  - name: orders
    source:
      table: orders
    primary_key: order_id
  - name: refunds
    source:
      table: refunds
    primary_key: refund_id
metrics:
  - name: order_count
    expression: "COUNT(DISTINCT order_id)"
"""
    with pytest.raises(OSIValidationError, match="must declare `dataset`"):
        compile_document(parse_osi(osi))


def test_compile_document_rejects_reserved_metric_metadata_keys():
    osi = """
semantic_model:
  name: order_model
datasets:
  - name: orders
    source:
      table: orders
    primary_key: order_id
metrics:
  - name: order_count
    expression: "COUNT(DISTINCT order_id)"
    dataset: orders
    metadata:
      dataset: other_orders
"""
    with pytest.raises(OSIValidationError, match="reserved metric key"):
        compile_document(parse_osi(osi))
