# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Join policy post-processing for OSI metric queries."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from datus_semantic_core.models import QueryResult

from datus_semantic_osi.query_utils import (
    dimension_output_column,
    is_null_metric_value,
)

MATCH_ONLY_JOIN_POLICIES = {None, "", "auto", "match_only"}
FACT_PRESERVING_JOIN_POLICIES = {"fact_preserving", "include_unmatched"}
DIMENSION_PRESERVING_JOIN_POLICIES = {"dimension_preserving"}
UNMATCHED_ONLY_JOIN_POLICIES = {"unmatched_only"}


def normalize_join_policy(join_policy: Optional[str]) -> str:
    """Normalize supported join policies to one canonical string."""
    policy = str(join_policy or "auto").strip().lower()
    if policy in MATCH_ONLY_JOIN_POLICIES:
        return "match_only"
    if policy in FACT_PRESERVING_JOIN_POLICIES:
        return "fact_preserving"
    if policy in DIMENSION_PRESERVING_JOIN_POLICIES:
        return "dimension_preserving"
    if policy in UNMATCHED_ONLY_JOIN_POLICIES:
        return "unmatched_only"
    raise ValueError(
        "join_policy must be one of: auto, match_only, fact_preserving, "
        "dimension_preserving, unmatched_only"
    )


def joined_dimension_columns(
    dimensions: Sequence[str],
    result_columns: Sequence[str],
) -> List[str]:
    """Return joined-dimension output columns present in a query result."""
    columns: List[str] = []
    for dimension in dimensions:
        if "__" not in dimension:
            continue
        column = dimension_output_column(dimension, result_columns)
        if column and column not in columns:
            columns.append(column)
    return columns


def apply_join_policy(
    result: QueryResult,
    *,
    dimensions: Sequence[str],
    join_policy: Optional[str],
) -> QueryResult:
    """Filter joined rows according to the requested join policy."""
    policy = normalize_join_policy(join_policy)
    joined_columns = joined_dimension_columns(dimensions, result.columns)
    if not joined_columns or policy in {"fact_preserving", "dimension_preserving"}:
        return result

    def row_has_unmatched_join(row: Dict[str, Any]) -> bool:
        return any(is_null_metric_value(row.get(column)) for column in joined_columns)

    if policy == "match_only":
        filtered = [row for row in result.data if not row_has_unmatched_join(row)]
    elif policy == "unmatched_only":
        filtered = [row for row in result.data if row_has_unmatched_join(row)]
    else:
        return result

    metadata = dict(result.metadata)
    metadata["join_policy"] = policy
    metadata["join_policy_filtered_rows"] = len(result.data) - len(filtered)
    return QueryResult(columns=list(result.columns), data=filtered, metadata=metadata)
