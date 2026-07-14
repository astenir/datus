# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Shared semantics for OSI window metrics."""

from __future__ import annotations

from typing import Optional

from datus_semantic_osi.ir import MetricIR, MetricKind, SemanticModelIR

WINDOW_AGGREGATION_METADATA_KEYS = (
    "window_aggregation",
    "window_function",
    "running_aggregation",
    "rolling_aggregation",
)


def metadata_str(metric: MetricIR, *names: str) -> str:
    """Return the first string metadata value for the supplied keys."""
    for name in names:
        value = metric.metadata.get(name)
        if value is None:
            continue
        text = str(value).strip().lower()
        if text:
            return text
    return ""


def normalize_window_aggregation(value: object) -> Optional[str]:
    """Normalize an explicit window aggregation hint."""
    normalized = str(value or "").strip().lower()
    if normalized in {"avg", "average", "mean"}:
        return "avg"
    if normalized in {"sum", "min", "max", "count", "row_count"}:
        return normalized
    return None


def window_aggregation(metric: MetricIR) -> Optional[str]:
    """Return the explicit aggregation used to combine base-period values."""
    if not (metric.window or metric.grain_to_date):
        return None
    return normalize_window_aggregation(
        metadata_str(metric, *WINDOW_AGGREGATION_METADATA_KEYS)
    )


def metric_measure_signature(
    metric: MetricIR,
) -> Optional[tuple[str, tuple[tuple[str, str, str], ...]]]:
    """Return the dataset + measure signature used to find window base metrics."""
    if not metric.dataset or not metric.measures:
        return None
    return (
        metric.dataset,
        tuple((measure.agg.value, measure.expr, "") for measure in metric.measures),
    )


def base_metric_for_window_metric(
    model: SemanticModelIR,
    metric: MetricIR,
) -> Optional[str]:
    """Return the reusable aggregate metric backing a window metric."""
    signature = metric_measure_signature(metric)
    if signature is None:
        return None
    for candidate in model.metrics:
        if candidate.name == metric.name:
            continue
        if candidate.kind is not MetricKind.AGGREGATE:
            continue
        if metric_measure_signature(candidate) == signature:
            return candidate.name
    return None
