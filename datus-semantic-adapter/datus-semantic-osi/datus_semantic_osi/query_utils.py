# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Common query helpers shared by OSI adapter planning modules."""

from __future__ import annotations

import math
from typing import Any, Optional, Sequence


def is_null_metric_value(value: Any) -> bool:
    """Return true when a metric or joined dimension value should count as null."""
    if value is None:
        return True
    if isinstance(value, str) and value.strip().lower() in {"", "nan", "none", "null"}:
        return True
    try:
        return bool(math.isnan(value))
    except (TypeError, ValueError):
        pass
    try:
        return bool(value != value)
    except Exception:
        return False


def dimension_output_column(
    dimension: str,
    columns: Sequence[str],
) -> Optional[str]:
    """Find the output column corresponding to a requested dimension."""
    if dimension in columns:
        return dimension
    leaf = dimension.split("__")[-1]
    if leaf in columns:
        return leaf
    return None


def is_metric_time_dimension(dimension: str) -> bool:
    """Return true for the synthetic metric_time dimensions used by MetricFlow."""
    return dimension == "metric_time" or dimension.startswith("metric_time__")


def metric_time_dimension_for_granularity(
    time_granularity: Optional[str],
) -> Optional[str]:
    """Return the synthetic metric_time dimension for a requested granularity."""
    granularity = str(time_granularity or "").strip()
    return f"metric_time__{granularity}" if granularity else None
