# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.

"""Tests for OSI metric-expression inference (expression -> MetricIR)."""

import pytest

from datus_semantic_osi.compiler import compile_metric_expression
from datus_semantic_osi.errors import OSIValidationError
from datus_semantic_osi.ir import Aggregation, MetricKind


def test_count_distinct_becomes_aggregate_with_one_measure():
    metric = compile_metric_expression("order_count", "COUNT(DISTINCT order_id)")
    assert metric.kind is MetricKind.AGGREGATE
    assert len(metric.measures) == 1
    m = metric.measures[0]
    assert m.agg is Aggregation.COUNT_DISTINCT
    assert m.expr == "order_id"
    assert m.name == "order_id_count_distinct"


def test_count_distinct_multiple_columns_is_rejected():
    with pytest.raises(OSIValidationError, match="exactly one expression"):
        compile_metric_expression(
            "order_count", "COUNT(DISTINCT order_id, customer_id)"
        )


def test_sum_becomes_aggregate():
    metric = compile_metric_expression("total_amount", "SUM(amount)")
    assert metric.kind is MetricKind.AGGREGATE
    assert metric.measures[0].agg is Aggregation.SUM
    assert metric.measures[0].expr == "amount"
    assert metric.measures[0].name == "amount_sum"


def test_avg_becomes_average_aggregate():
    metric = compile_metric_expression("avg_order_amount", "AVG(amount)")
    assert metric.measures[0].agg is Aggregation.AVERAGE
    assert metric.measures[0].name == "amount_average"


def test_count_star_becomes_row_count():
    metric = compile_metric_expression("row_count", "COUNT(*)")
    assert metric.kind is MetricKind.AGGREGATE
    assert metric.measures[0].agg is Aggregation.COUNT
    assert metric.measures[0].name == "rows_count"


def test_window_function_is_rejected_as_metric():
    with pytest.raises(OSIValidationError) as exc:
        compile_metric_expression("ranked", "RANK() OVER (ORDER BY amount DESC)")
    # business-semantic error, not a backend error
    assert "window" in str(exc.value).lower() or "rank" in str(exc.value).lower()


def test_non_aggregate_column_is_rejected():
    with pytest.raises(OSIValidationError):
        compile_metric_expression("just_a_column", "order_id")


def test_aggregate_name_collision_is_rejected():
    with pytest.raises(OSIValidationError, match="same backing measure name"):
        compile_metric_expression("ambiguous", "SUM(a - b) + SUM(a_b)")
