# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Window metric query planning and post-processing."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence

from datus_semantic_core.models import QueryResult

from datus_semantic_osi.ir import MetricIR, SemanticModelIR
from datus_semantic_osi.query_utils import (
    dimension_output_column,
    is_metric_time_dimension,
    is_null_metric_value,
    metric_time_dimension_for_granularity,
)
from datus_semantic_osi.window_semantics import (
    base_metric_for_window_metric,
    window_aggregation,
)


def result_time_column(
    dimensions: Sequence[str],
    columns: Sequence[str],
    time_granularity: Optional[str],
) -> Optional[str]:
    """Find the output time column used to order window calculations."""
    candidates: List[str] = []
    inferred = metric_time_dimension_for_granularity(time_granularity)
    if inferred:
        candidates.append(inferred)
    candidates.extend(
        dimension for dimension in dimensions if is_metric_time_dimension(dimension)
    )
    candidates.extend(column for column in columns if is_metric_time_dimension(column))
    for candidate in candidates:
        column = dimension_output_column(candidate, columns)
        if column:
            return column
    return None


def window_metrics(
    model: SemanticModelIR, metrics: Sequence[str]
) -> Dict[str, MetricIR]:
    """Return requested metrics that declare executable window semantics."""
    result: Dict[str, MetricIR] = {}
    metrics_by_name = {metric.name: metric for metric in model.metrics}
    for metric_name in metrics:
        metric = metrics_by_name.get(metric_name)
        if metric is None:
            continue
        if window_aggregation(metric):
            result[metric_name] = metric
    return result


def parse_window_size(window: Optional[str]) -> int:
    """Parse a window size like '3 months' into a row count."""
    if not window:
        return 0
    match = re.search(r"\d+", str(window))
    return max(int(match.group(0)), 1) if match else 1


def aggregate_window_values(values: List[Any], aggregation: str) -> Any:
    """Aggregate ordered base-period values for a post-processed window metric."""
    clean_values = [value for value in values if not is_null_metric_value(value)]
    if aggregation == "row_count":
        return len(values)
    if not clean_values:
        return None
    if aggregation == "avg":
        return sum(clean_values) / len(clean_values)
    if aggregation == "min":
        return min(clean_values)
    if aggregation == "max":
        return max(clean_values)
    if aggregation == "count":
        return len(clean_values)
    return sum(clean_values)


def apply_window_metrics(
    result: QueryResult,
    *,
    requested_metrics: Sequence[str],
    window_metric_map: Dict[str, MetricIR],
    base_metric_by_window_metric: Dict[str, Optional[str]],
    dimensions: Sequence[str],
    time_granularity: Optional[str],
) -> QueryResult:
    """Replace base metric values with requested window metric values."""
    if not window_metric_map or not result.data:
        return result

    time_column = result_time_column(dimensions, result.columns, time_granularity)
    if not time_column:
        return result

    dimension_columns = [
        dimension_output_column(dimension, result.columns) or dimension
        for dimension in dimensions
    ]
    partition_columns = [
        column
        for column in dimension_columns
        if column in result.columns and column != time_column
    ]

    grouped: Dict[tuple[Any, ...], List[tuple[int, Dict[str, Any]]]] = defaultdict(list)
    for index, row in enumerate(result.data):
        grouped[tuple(row.get(column) for column in partition_columns)].append(
            (index, row)
        )

    window_values_by_index: Dict[int, Dict[str, Any]] = defaultdict(dict)
    for indexed_rows in grouped.values():
        indexed_rows = sorted(
            indexed_rows,
            key=lambda item: str(item[1].get(time_column) or ""),
        )
        running_values: Dict[str, List[Any]] = {
            metric_name: [] for metric_name in window_metric_map
        }
        for index, row in indexed_rows:
            for metric_name, metric in window_metric_map.items():
                aggregation = window_aggregation(metric)
                if not aggregation:
                    continue
                base_metric = base_metric_by_window_metric.get(metric_name)
                if aggregation == "row_count":
                    value = 1
                elif base_metric:
                    value = row.get(base_metric)
                else:
                    value = row.get(metric_name)
                running_values[metric_name].append(value)
                if metric.window:
                    window_size = parse_window_size(metric.window)
                    values = running_values[metric_name][-window_size:]
                else:
                    values = running_values[metric_name]
                window_values_by_index[index][metric_name] = aggregate_window_values(
                    values, aggregation
                )

    output_rows: List[Dict[str, Any]] = []
    for index, row in enumerate(result.data):
        output_row = dict(row)
        output_row.update(window_values_by_index.get(index, {}))
        output_rows.append(output_row)

    requested_columns: List[str] = []
    for column in result.columns:
        if column in requested_metrics or column in dimension_columns:
            if column not in requested_columns:
                requested_columns.append(column)
    for metric_name in requested_metrics:
        if metric_name in window_metric_map and metric_name not in requested_columns:
            requested_columns.append(metric_name)
        elif metric_name in result.columns and metric_name not in requested_columns:
            requested_columns.append(metric_name)

    metadata = dict(result.metadata)
    metadata["osi_window_postprocessed_metrics"] = list(window_metric_map)
    return QueryResult(
        columns=requested_columns,
        data=[
            {column: row.get(column) for column in requested_columns}
            for row in output_rows
        ],
        metadata=metadata,
    )


def can_postprocess_window_metrics(
    model: SemanticModelIR,
    metrics: Sequence[str],
) -> bool:
    """Return true when all requested window metrics can be computed locally."""
    window_metric_map = window_metrics(model, metrics)
    if not window_metric_map:
        return False
    return all(
        window_aggregation(metric) == "row_count"
        or base_metric_for_window_metric(model, metric) is not None
        for metric in window_metric_map.values()
    )


async def query_window_metrics(
    executor: Any,
    model: SemanticModelIR,
    *,
    metrics: List[str],
    dimensions: Sequence[str],
    path: Optional[List[str]],
    time_start: Optional[str],
    time_end: Optional[str],
    time_granularity: Optional[str],
    where: Optional[str],
    limit: Optional[int],
    order_by: Optional[List[str]],
) -> QueryResult:
    """Query base metrics and post-process requested window metrics."""
    requested_metrics = list(dict.fromkeys(metrics))
    window_metric_map = window_metrics(model, requested_metrics)
    base_metric_by_window_metric = {
        metric_name: base_metric_for_window_metric(model, metric)
        for metric_name, metric in window_metric_map.items()
    }

    query_metric_names: List[str] = []
    for metric_name in requested_metrics:
        if metric_name in window_metric_map:
            base_metric = base_metric_by_window_metric.get(metric_name)
            if base_metric:
                query_metric_names.append(base_metric)
            continue
        query_metric_names.append(metric_name)
    query_metric_names = list(dict.fromkeys(query_metric_names))
    if not query_metric_names:
        query_metric_names = [
            metric_name
            for metric_name, metric in window_metric_map.items()
            if window_aggregation(metric) == "row_count"
        ][:1]
    if not query_metric_names:
        return QueryResult(
            columns=list(dict.fromkeys([*dimensions, *requested_metrics])),
            data=[],
            metadata={"osi_window_postprocessed_metrics": list(window_metric_map)},
        )

    result = await executor.query_metrics(
        query_metric_names,
        dimensions=list(dimensions),
        path=path,
        time_start=time_start,
        time_end=time_end,
        time_granularity=time_granularity,
        where=where,
        limit=limit,
        order_by=order_by,
        dry_run=False,
    )
    return apply_window_metrics(
        result,
        requested_metrics=requested_metrics,
        window_metric_map=window_metric_map,
        base_metric_by_window_metric=base_metric_by_window_metric,
        dimensions=dimensions,
        time_granularity=time_granularity,
    )
