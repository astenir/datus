# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.

"""Tests for the Datus Semantic IR data model."""

import pytest

from datus_semantic_osi.ir import (
    Aggregation,
    DatasetIR,
    FieldIR,
    IdentifierIR,
    MeasureIR,
    MetricIR,
    MetricKind,
    SemanticModelIR,
)


def test_aggregate_metric_carries_backing_measure():
    metric = MetricIR(
        name="order_count",
        kind=MetricKind.AGGREGATE,
        measures=[
            MeasureIR(
                name="order_count", agg=Aggregation.COUNT_DISTINCT, expr="order_id"
            )
        ],
    )
    assert metric.kind is MetricKind.AGGREGATE
    assert metric.measures[0].agg is Aggregation.COUNT_DISTINCT
    assert metric.measures[0].expr == "order_id"


def test_ratio_metric_records_numerator_and_denominator():
    metric = MetricIR(
        name="paid_rate",
        kind=MetricKind.RATIO,
        numerator="paid_revenue",
        denominator="order_count",
    )
    assert metric.numerator == "paid_revenue"
    assert metric.denominator == "order_count"


def test_dataset_holds_fields_and_identifiers():
    ds = DatasetIR(
        name="orders",
        sql_table="db.orders",
        fields=[FieldIR(name="amount", expr="amount", type="numeric")],
        identifiers=[IdentifierIR(name="order", type="primary", expr="order_id")],
    )
    assert ds.sql_table == "db.orders"
    assert ds.identifiers[0].type == "primary"
    assert ds.fields[0].name == "amount"


def test_semantic_model_aggregates_datasets_and_metrics():
    model = SemanticModelIR(
        datasets=[DatasetIR(name="orders", sql_table="db.orders")],
        metrics=[MetricIR(name="m", kind=MetricKind.AGGREGATE)],
    )
    assert model.datasets[0].name == "orders"
    assert model.metrics[0].name == "m"


def test_unknown_aggregation_is_rejected():
    with pytest.raises(ValueError):
        MeasureIR(name="x", agg="median", expr="amount")
