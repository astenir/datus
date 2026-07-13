# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.

"""OSI core documents may carry Datus hints via custom_extensions (vendor DATUS)."""

from datus_semantic_osi.compiler import compile_document
from datus_semantic_osi.ir import MetricKind
from datus_semantic_osi.profile import parse_osi_profile as parse_osi

# OSI-core-flavored doc: Datus execution hints live in custom_extensions, not inline.
OSI_YAML = """
semantic_model:
  name: shop
datasets:
  - name: paid_orders
    source:
      table: orders
    primary_key: order_id
    time_dimension:
      name: order_date
      granularity: day
metrics:
  - name: paid_rate
    description: "paid conversion"
    dataset: paid_orders
    custom_extensions:
      - vendor_name: DATUS
        data: >
          {"metric_kind": "ratio", "numerator": "paid_revenue",
           "denominator": "order_count", "time_dimension": "order_date",
           "format": "0.00%", "window_aggregation": "avg"}
"""


def test_custom_extensions_datus_hints_are_merged_into_metric():
    doc = parse_osi(OSI_YAML)
    metric = doc.metrics[0]
    assert metric.metric_kind == "ratio"
    assert metric.numerator == "paid_revenue"
    assert metric.denominator == "order_count"
    assert metric.time_dimension == "order_date"
    assert metric.format == "0.00%"
    assert metric.metadata["window_aggregation"] == "avg"


def test_ratio_hints_compile_to_ratio_ir():
    model = compile_document(parse_osi(OSI_YAML))
    metric = model.metrics[0]
    assert metric.kind is MetricKind.RATIO
    assert metric.numerator == "paid_revenue"
    assert metric.denominator == "order_count"
    assert metric.metadata["window_aggregation"] == "avg"


# SaaS attaches uid/owner identity hints to metrics; validation must allow them.
SAAS_YAML = """
semantic_model:
  name: shop
datasets:
  - name: paid_orders
    source:
      table: orders
    primary_key: order_id
    time_dimension:
      name: order_date
      granularity: day
metrics:
  - name: paid_rate
    description: "paid conversion"
    dataset: paid_orders
    custom_extensions:
      - vendor_name: DATUS
        data: >
          {"metric_kind": "ratio", "numerator": "paid_revenue",
           "denominator": "order_count", "uid": "m-123",
           "owner": "alice@datus.ai"}
"""


def test_saas_uid_owner_hints_pass_validation_and_compile():
    doc = parse_osi(SAAS_YAML)
    metric = doc.metrics[0]
    assert metric.metric_kind == "ratio"
    # Allowed through validation; not lowered onto the metric as execution hints.
    assert not hasattr(metric, "uid") or metric.uid is None
    assert not hasattr(metric, "owner") or metric.owner is None
    model = compile_document(doc)
    assert model.metrics[0].kind is MetricKind.RATIO
