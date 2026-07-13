# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.

"""Tests for ratio / expression metric inference."""

import pytest

from datus_semantic_osi.compiler import compile_metric_expression
from datus_semantic_osi.errors import OSIValidationError
from datus_semantic_osi.ir import MetricKind


def test_division_of_two_aggregates_becomes_ratio():
    m = compile_metric_expression(
        "avg_order_amount", "SUM(amount) / COUNT(DISTINCT order_id)"
    )
    assert m.kind is MetricKind.RATIO
    assert {x.name for x in m.measures} == {"amount_sum", "order_id_count_distinct"}
    assert m.numerator == "amount_sum"
    assert m.denominator == "order_id_count_distinct"


def test_difference_of_aggregates_becomes_expression():
    m = compile_metric_expression("net_revenue", "SUM(revenue) - SUM(cost)")
    assert m.kind is MetricKind.EXPRESSION
    assert {x.name for x in m.measures} == {"revenue_sum", "cost_sum"}
    # the lowered expression references backing measure names, not raw SUM(...)
    assert "revenue_sum" in m.expression
    assert "cost_sum" in m.expression
    # no raw aggregate function call should remain in the lowered expression
    assert "sum(" not in m.expression.lower()


def test_bare_named_division_requires_hints():
    with pytest.raises(OSIValidationError) as exc:
        compile_metric_expression("paid_rate", "revenue / order_count")
    msg = str(exc.value).lower()
    assert "numerator" in msg or "denominator" in msg
