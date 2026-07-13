# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.

"""Cumulative and derived (incl. period-over-period offset) metric kinds."""

import pytest

from datus_semantic_osi.compiler import compile_document
from datus_semantic_osi.errors import OSIValidationError
from datus_semantic_osi.ir import MetricKind
from datus_semantic_osi.metricflow_backend import lower_to_metricflow
from datus_semantic_osi.profile import parse_osi_profile as parse_osi
from datus_semantic_osi.validator import validate_profile

CUMULATIVE = """
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
  - name: revenue_l7d
    description: "trailing 7-day revenue"
    expression: "SUM(amount)"
    dataset: orders
    time_dimension: order_date
    window: "7 days"
"""

DERIVED = """
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
  - name: order_count
    expression: "COUNT(DISTINCT order_id)"
    dataset: orders
  - name: revenue
    expression: "SUM(amount)"
    dataset: orders
  - name: avg_order_value
    description: "revenue per order"
    metric_kind: derived
    expression: "revenue * 1.0 / NULLIF(order_count, 0)"
    inputs:
      - revenue
      - order_count
  - name: revenue_mom
    description: "month-over-month revenue change"
    metric_kind: derived
    expression: "(revenue - revenue_prev) / NULLIF(revenue_prev, 0)"
    inputs:
      - name: revenue
      - name: revenue
        alias: revenue_prev
        offset_window: "1 month"
"""

PERIOD_OVER_PERIOD = """
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
  - name: order_count_month_yoy
    description: "monthly year-over-year order count"
    expression: "COUNT(DISTINCT order_id)"
    dataset: orders
    time_dimension: order_date
    period_over_period:
      time_grain: month
      offset_window: "1 year"
      calculation: percent_change
"""


def test_cumulative_metric_compiles_with_window():
    model = compile_document(parse_osi(CUMULATIVE))
    metric = model.metrics[0]
    assert metric.kind is MetricKind.CUMULATIVE
    assert metric.window == "7 days"
    assert metric.measures[0].agg.value == "sum"


def test_cumulative_lowers_to_cumulative_type():
    art = lower_to_metricflow(compile_document(parse_osi(CUMULATIVE)))
    metric = art.metric_docs[0]["metric"]
    assert metric["type"] == "cumulative"
    assert metric["type_params"]["window"] == "7 days"
    assert metric["type_params"]["measures"]


def test_derived_metric_references_other_metrics():
    model = compile_document(parse_osi(DERIVED))
    derived = {m.name: m for m in model.metrics}["avg_order_value"]
    assert derived.kind is MetricKind.DERIVED
    assert {i.name for i in derived.inputs} == {"revenue", "order_count"}


def test_derived_lowers_to_derived_type_with_metric_inputs():
    art = lower_to_metricflow(compile_document(parse_osi(DERIVED)))
    metrics = {d["metric"]["name"]: d["metric"] for d in art.metric_docs}
    derived = metrics["avg_order_value"]
    assert derived["type"] == "derived"
    assert "revenue" in derived["type_params"]["expr"]
    names = {m["name"] for m in derived["type_params"]["metrics"]}
    assert names == {"revenue", "order_count"}


def test_derived_with_sql_window_function_is_rejected():
    # Period-over-period must use offset_window, not a SQL window function.
    osi = """
semantic_model: {name: shop}
datasets:
  - name: monthly
    source: {table: orders}
    primary_key: order_id
    time_dimension: {name: order_date, granularity: month}
metrics:
  - name: order_count
    expression: "COUNT(DISTINCT order_id)"
    dataset: monthly
  - name: order_count_mom
    metric_kind: derived
    expression: "order_count - LAG(order_count) OVER (ORDER BY order_date)"
    dataset: monthly
"""
    with pytest.raises(OSIValidationError) as exc:
        compile_document(parse_osi(osi))
    msg = str(exc.value).lower()
    assert "window" in msg
    assert "offset_window" in msg


def test_derived_offset_window_is_carried_to_input_metric():
    art = lower_to_metricflow(compile_document(parse_osi(DERIVED)))
    metrics = {d["metric"]["name"]: d["metric"] for d in art.metric_docs}
    mom = metrics["revenue_mom"]
    offset_inputs = [m for m in mom["type_params"]["metrics"] if m.get("offset_window")]
    assert offset_inputs and offset_inputs[0]["offset_window"] == "1 month"
    assert offset_inputs[0]["alias"] == "revenue_prev"


def test_period_over_period_compiles_as_fixed_metric_semantics():
    model = compile_document(parse_osi(PERIOD_OVER_PERIOD))
    metric = model.metrics[0]
    assert metric.kind is MetricKind.AGGREGATE
    assert metric.period_over_period is not None
    assert metric.period_over_period.time_grain == "month"
    assert metric.period_over_period.offset_window == "1 year"
    assert metric.period_over_period.calculation == "percent_change"


def test_period_over_period_lowers_to_hidden_base_and_public_metric():
    art = lower_to_metricflow(compile_document(parse_osi(PERIOD_OVER_PERIOD)))
    metrics = {d["metric"]["name"]: d["metric"] for d in art.metric_docs}
    hidden_name = "datus_pop_base_order_count_month_yoy"

    assert hidden_name in metrics
    assert metrics[hidden_name]["type"] == "measure_proxy"

    public = metrics["order_count_month_yoy"]
    assert public["type"] == "derived"
    assert public["type_params"]["metrics"] == [
        {"name": hidden_name},
        {
            "name": hidden_name,
            "alias": f"{hidden_name}_previous",
            "offset_window": "1 year",
        },
    ]
    assert public["type_params"]["expr"] == (
        f"({hidden_name} - {hidden_name}_previous) / NULLIF({hidden_name}_previous, 0)"
    )


def test_period_over_period_previous_value_lowers_to_offset_only_input():
    osi = PERIOD_OVER_PERIOD.replace(
        "order_count_month_yoy", "previous_month_order_count"
    ).replace("calculation: percent_change", "calculation: previous_value")
    art = lower_to_metricflow(compile_document(parse_osi(osi)))
    metrics = {d["metric"]["name"]: d["metric"] for d in art.metric_docs}
    hidden_name = "datus_pop_base_previous_month_order_count"

    public = metrics["previous_month_order_count"]
    assert public["type"] == "derived"
    assert public["type_params"]["metrics"] == [
        {
            "name": hidden_name,
            "alias": f"{hidden_name}_previous",
            "offset_window": "1 year",
        }
    ]
    assert public["type_params"]["expr"] == f"{hidden_name}_previous"


def test_period_over_period_delta_and_ratio_lower_to_expected_expressions():
    cases = [
        (
            "order_count_month_delta",
            "delta",
            "datus_pop_base_order_count_month_delta - "
            "datus_pop_base_order_count_month_delta_previous",
        ),
        (
            "order_count_month_ratio",
            "ratio",
            "datus_pop_base_order_count_month_ratio / "
            "NULLIF(datus_pop_base_order_count_month_ratio_previous, 0)",
        ),
    ]

    for metric_name, calculation, expected_expr in cases:
        osi = PERIOD_OVER_PERIOD.replace("order_count_month_yoy", metric_name).replace(
            "calculation: percent_change", f"calculation: {calculation}"
        )
        art = lower_to_metricflow(compile_document(parse_osi(osi)))
        metrics = {d["metric"]["name"]: d["metric"] for d in art.metric_docs}
        hidden_name = f"datus_pop_base_{metric_name}"

        public = metrics[metric_name]
        assert public["type"] == "derived"
        assert public["type_params"]["metrics"] == [
            {"name": hidden_name},
            {
                "name": hidden_name,
                "alias": f"{hidden_name}_previous",
                "offset_window": "1 year",
            },
        ]
        assert public["type_params"]["expr"] == expected_expr


def test_period_over_period_rejects_derived_inputs():
    osi = """
semantic_model: {name: shop}
datasets:
  - name: orders
    source: {table: orders}
    primary_key: order_id
    time_dimension: {name: order_date, granularity: day}
metrics:
  - name: order_count_month_yoy
    expression: "COUNT(DISTINCT order_id)"
    dataset: orders
    time_dimension: order_date
    inputs:
      - order_count
    period_over_period:
      time_grain: month
      offset_window: "1 year"
      calculation: percent_change
"""
    with pytest.raises(OSIValidationError) as exc:
        compile_document(parse_osi(osi))
    assert "period_over_period" in str(exc.value)
    assert "inputs" in str(exc.value)


@pytest.mark.parametrize("metric_kind", ["derived", "ratio"])
def test_validate_profile_rejects_period_over_period_metric_kind_conflict(metric_kind):
    doc = parse_osi(
        f"""
semantic_model: {{name: shop}}
datasets:
  - name: orders
    source: {{table: orders}}
    primary_key: order_id
    time_dimension: {{name: order_date, granularity: day}}
metrics:
  - name: order_count_month_yoy
    metric_kind: {metric_kind}
    expression: "COUNT(DISTINCT order_id)"
    dataset: orders
    time_dimension: order_date
    period_over_period:
      time_grain: month
      offset_window: "1 year"
      calculation: percent_change
"""
    )

    issues = validate_profile(doc)

    assert any("incompatible metric_kind" in issue for issue in issues)
