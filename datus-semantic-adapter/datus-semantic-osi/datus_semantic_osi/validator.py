# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Datus OSI validation: Profile rules, IR rules, and backend capability checks.

All issues are phrased as business semantics, never backend syntax. ``ensure_valid``
turns a list of issues into an :class:`OSIValidationError`.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import sqlglot
from sqlglot import expressions as exp

from datus_semantic_osi.dialects import DEFAULT_SQLGLOT_DIALECT
from datus_semantic_osi.errors import OSIValidationError
from datus_semantic_osi.ir import MetricKind, SemanticModelIR
from datus_semantic_osi.metricflow_backend import lowered_element_types
from datus_semantic_osi.normalizer import normalization_errors
from datus_semantic_osi.profile import OSIDocument, to_core_schema_document
from datus_semantic_osi.window_semantics import (
    WINDOW_AGGREGATION_METADATA_KEYS,
    base_metric_for_window_metric,
    metadata_str,
    window_aggregation,
)


def detect_nonportable_functions(
    doc: OSIDocument, *, dialect: str = DEFAULT_SQLGLOT_DIALECT
) -> List[str]:
    """Warn about metric expressions using functions sqlglot cannot transpile.

    sqlglot parses unknown functions as ``Anonymous`` nodes and emits them
    unchanged for every target dialect, so they break on engines that lack the
    function (e.g. ``FIND_IN_SET`` outside the MySQL family). These are the
    expressions that are not portable across datasources.
    """
    warnings: List[str] = []
    for metric in doc.metrics:
        expression = getattr(metric, "expression", None)
        if not expression:
            continue
        try:
            tree = sqlglot.parse_one(expression, read=dialect)
        except Exception:  # noqa: BLE001 - parse errors surface elsewhere
            continue
        if tree is None:
            continue
        names = sorted({node.name.upper() for node in tree.find_all(exp.Anonymous) if node.name})
        if names:
            warnings.append(
                f"Metric `{metric.name}` uses function(s) {names} that sqlglot cannot "
                f"translate across dialects; the expression is bound to the `{dialect}` "
                "engine and will not port to other datasources without a manual equivalent."
            )
    return warnings


def validate_profile(doc: OSIDocument) -> List[str]:
    """Validate the executable OSI Profile subset (authoring-level rules)."""
    issues: List[str] = []
    datasets_by_name = {d.name: d for d in doc.datasets}
    dataset_names = set(datasets_by_name)

    if not doc.datasets:
        issues.append("Document declares no datasets; at least one is required.")

    for ds in doc.datasets:
        if not (ds.source and (ds.source.table or ds.source.query)):
            issues.append(f"Dataset `{ds.name}` has no source table or query.")
        field_names = {dim.name for dim in ds.dimensions}
        if ds.time_dimension:
            field_names.add(ds.time_dimension.name)

    for metric in doc.metrics:
        if metric.dataset and metric.dataset not in dataset_names:
            issues.append(
                f"Metric `{metric.name}` references dataset `{metric.dataset}` which is not declared."
            )
        has_expr = bool(metric.expression)
        has_ratio = (
            (metric.metric_kind == "ratio")
            and bool(metric.numerator)
            and bool(metric.denominator)
        )
        if not has_expr and not has_ratio:
            issues.append(
                f"Metric `{metric.name}` needs an `expression` or explicit ratio numerator/denominator."
            )
        if metric.period_over_period is not None:
            if (metric.kind or "").lower() in {"derived", "ratio"}:
                issues.append(
                    f"Metric `{metric.name}` declares period_over_period with an incompatible metric_kind."
                )
            if not metric.dataset:
                issues.append(
                    f"Metric `{metric.name}` declares period_over_period but has no dataset."
                )
            if not metric.time_dimension:
                issues.append(
                    f"Metric `{metric.name}` declares period_over_period but has no time_dimension."
                )
            if metric.inputs:
                issues.append(
                    f"Metric `{metric.name}` declares period_over_period and inputs; "
                    "fixed period-over-period metrics must be self-contained."
                )
            if metric.numerator or metric.denominator:
                issues.append(
                    f"Metric `{metric.name}` declares period_over_period with numerator/denominator."
                )
            if metric.window or metric.grain_to_date:
                issues.append(
                    f"Metric `{metric.name}` declares period_over_period with window/grain_to_date."
                )
        # time_dimension must be declared on the metric's dataset
        if metric.time_dimension and metric.dataset in dataset_names:
            ds = datasets_by_name[metric.dataset]
            declared = {dim.name for dim in ds.dimensions}
            if ds.time_dimension:
                declared.add(ds.time_dimension.name)
            if metric.time_dimension not in declared:
                issues.append(
                    f"Metric `{metric.name}` uses time dimension `{metric.time_dimension}` "
                    f"not declared on dataset `{metric.dataset}`."
                )
    issues.extend(normalization_errors(doc))
    return issues


def validate_ir(model: SemanticModelIR) -> List[str]:
    """Validate the compiled IR (structural / semantic invariants)."""
    issues: List[str] = []
    dataset_names = {d.name for d in model.datasets}

    # Dataset names must be unique across the merged model. The same physical
    # table may back many datasets, but each must have a distinct name (it
    # becomes a separate backend data source); a duplicate name would emit two
    # conflicting data sources and collide their namespaced measures.
    seen_datasets: dict = {}
    for ds in model.datasets:
        seen_datasets[ds.name] = seen_datasets.get(ds.name, 0) + 1
    for name, count in seen_datasets.items():
        if count > 1:
            issues.append(
                f"Dataset name `{name}` is declared {count} times; dataset names must be "
                f"unique across the model (rename one, or merge them)."
            )

    # Metric names must be unique across the merged model (each lowers to one
    # backend metric); a duplicate name would emit two conflicting metrics.
    seen_metrics: dict = {}
    for metric in model.metrics:
        seen_metrics[metric.name] = seen_metrics.get(metric.name, 0) + 1
    for name, count in seen_metrics.items():
        if count > 1:
            issues.append(
                f"Metric name `{name}` is declared {count} times; metric names must be "
                f"unique across the model (rename one)."
            )

    measure_owner: dict = {}
    for metric in model.metrics:
        if metric.dataset and metric.dataset not in dataset_names:
            issues.append(
                f"Metric `{metric.name}` references dataset `{metric.dataset}` which is not declared."
            )
        if metric.kind is MetricKind.AGGREGATE and len(metric.measures) != 1:
            issues.append(
                f"Aggregate metric `{metric.name}` must have exactly one backing measure."
            )
        if metric.kind is MetricKind.RATIO and not (
            metric.numerator and metric.denominator
        ):
            issues.append(
                f"Ratio metric `{metric.name}` must declare both numerator and denominator."
            )
        if metric.kind is MetricKind.EXPRESSION and not metric.expression:
            issues.append(
                f"Expression metric `{metric.name}` must carry an expression."
            )
        if metric.kind is MetricKind.CUMULATIVE and not (
            metric.window or metric.grain_to_date
        ):
            issues.append(
                f"Cumulative metric `{metric.name}` must declare a window or grain_to_date."
            )
        if metric.period_over_period is not None:
            if not metric.dataset:
                issues.append(
                    f"Period-over-period metric `{metric.name}` must declare a dataset."
                )
            if not metric.time_dimension:
                issues.append(
                    f"Period-over-period metric `{metric.name}` must declare a time_dimension."
                )
            if metric.inputs:
                issues.append(
                    f"Period-over-period metric `{metric.name}` must not declare derived inputs."
                )
            if metric.window or metric.grain_to_date:
                issues.append(
                    f"Period-over-period metric `{metric.name}` must not declare window/grain_to_date."
                )
        if metric.window or metric.grain_to_date:
            explicit_window_aggregation = metadata_str(
                metric,
                *WINDOW_AGGREGATION_METADATA_KEYS,
            )
            normalized_window_aggregation = window_aggregation(metric)
            if not explicit_window_aggregation:
                issues.append(
                    f"Window metric `{metric.name}` must declare explicit "
                    "`window_aggregation` metadata."
                )
            elif not normalized_window_aggregation:
                issues.append(
                    f"Window metric `{metric.name}` declares unsupported "
                    f"`window_aggregation` `{explicit_window_aggregation}`. "
                    "Supported values: avg, count, max, min, row_count, sum."
                )
            elif (
                normalized_window_aggregation != "row_count"
                and base_metric_for_window_metric(model, metric) is None
            ):
                issues.append(
                    f"Window metric `{metric.name}` must have a separately declared "
                    "aggregate base metric with the same dataset and measure expression."
                )
        for measure in metric.measures:
            owner = measure_owner.get(measure.name)
            if owner is not None and owner != metric.dataset:
                issues.append(
                    f"Measure `{measure.name}` appears in multiple datasets "
                    f"(`{owner}` and `{metric.dataset}`); measure names must be globally unique."
                )
            measure_owner[measure.name] = metric.dataset

    for rel in model.relationships:
        if rel.from_dataset not in dataset_names:
            issues.append(
                f"Relationship `{rel.name}` from unknown dataset `{rel.from_dataset}`."
            )
        if rel.to_dataset not in dataset_names:
            issues.append(
                f"Relationship `{rel.name}` to unknown dataset `{rel.to_dataset}`."
            )

    # An element name must lower to one consistent MetricFlow type model-wide:
    # MetricFlow rejects e.g. `start_date` being a time dimension in one data
    # source and categorical in another, or a column being an identifier in one
    # and a dimension in another. The classification mirrors the lowering
    # (identifier auto-resolution, relationship-derived foreign identifiers,
    # same-dataset shadowing) so only conflicts the backend would reject are
    # reported, with a structural fix instead of a type-toggling one.
    try:
        element_types = lowered_element_types(model)
    except OSIValidationError as exc:
        # Relationship lowering itself can be structurally invalid (duplicate
        # foreign identifiers with different expressions); surface it as an
        # issue instead of escaping the validator.
        issues.append(str(exc))
        return issues
    for name, types in sorted(element_types.items()):
        if len(types) > 1:
            issues.append(
                f"Element `{name}` lowers to multiple MetricFlow element types "
                f"{sorted(types)} across datasets; one name must map to one type "
                f"model-wide. Fix structurally: if `{name}` is a join or grain key, "
                f"declare it in `primary_key`/`unique_keys` (or a relationship) in "
                f"every dataset that carries it; if it is a grouping attribute, "
                f"declare it as a field with a `dimension:` block everywhere and "
                f"remove it from keys; if a dataset only aggregates it, drop the "
                f"field there — metric expressions may reference physical columns "
                f"directly."
            )
    return issues


def detect_measure_columns_modeled_as_dimensions(
    model: SemanticModelIR, *, dialect: str = DEFAULT_SQLGLOT_DIALECT
) -> List[str]:
    """Warn when a metric aggregates a column its dataset also exposes as a dimension.

    Grouping by a measure's raw row-level value (a balance, an amount, a
    precomputed rate) is almost never intended; it usually means the author
    added a ``dimension:`` block to every field instead of opting in only the
    grouping attributes.
    """
    warnings: List[str] = []
    dims_by_ds: Dict[str, set] = {
        ds.name: {f.name for f in ds.fields if f.is_dimension and f.type != "time"}
        for ds in model.datasets
    }
    default_ds = model.datasets[0].name if model.datasets else None
    seen: set = set()
    for metric in model.metrics:
        ds_name = metric.dataset or default_ds
        if ds_name is None:
            continue
        for measure in metric.measures:
            try:
                tree = sqlglot.parse_one(measure.expr, read=dialect)
            except Exception:  # noqa: BLE001 - unparseable exprs surface elsewhere
                continue
            if tree is None:
                continue
            for column in tree.find_all(exp.Column):
                col_name = column.name
                if col_name in dims_by_ds.get(ds_name, set()) and (ds_name, col_name) not in seen:
                    seen.add((ds_name, col_name))
                    warnings.append(
                        f"Metric `{metric.name}` aggregates column `{col_name}` which "
                        f"dataset `{ds_name}` also models as a dimension; grouping by a "
                        f"measure's raw value is usually unintended. Drop the field's "
                        f"`dimension:` block (or the field itself) unless it is "
                        f"genuinely used for grouping or filtering."
                    )
    return warnings


def validate_capabilities(model: SemanticModelIR, capabilities: dict) -> List[str]:
    """Check the IR against a backend's declared capabilities before lowering."""
    issues: List[str] = []
    supported_kinds = set(capabilities.get("metric_kinds", []))
    for metric in model.metrics:
        if supported_kinds and metric.kind.value not in supported_kinds:
            issues.append(
                f"Backend does not support metric kind `{metric.kind.value}` "
                f"used by metric `{metric.name}`. Supported: {sorted(supported_kinds)}."
            )
    return issues


def validate_authoring_quality(doc: OSIDocument) -> List[str]:
    """Validate LLM-facing authoring quality without adding non-OSI fields."""
    issues: List[str] = []
    for dataset in doc.datasets:
        if not str(dataset.description or "").strip():
            issues.append(f"Dataset `{dataset.name}` should include `description`.")
        if dataset.ai_context in (None, "", [], {}):
            issues.append(f"Dataset `{dataset.name}` should include `ai_context`.")
    for metric in doc.metrics:
        if not str(metric.description or "").strip():
            issues.append(f"Metric `{metric.name}` should include `description`.")
        if metric.ai_context in (None, "", [], {}):
            issues.append(f"Metric `{metric.name}` should include `ai_context`.")
    return issues


def validate_mutation_guard(
    doc: OSIDocument,
    baseline_artifact: Optional[Dict[str, Any]],
) -> List[str]:
    """Ensure a metrics update did not mutate existing OSI semantic objects."""
    if not baseline_artifact:
        return ["mutation_guard requires a baseline_artifact object."]
    try:
        current = _core_model(to_core_schema_document(doc))
        baseline = _core_model(baseline_artifact)
    except Exception as exc:
        return [f"mutation_guard baseline could not be compared: {exc}"]

    issues: List[str] = []
    for collection_name in ("datasets", "relationships", "metrics"):
        current_items = _items_by_name(current.get(collection_name) or [])
        baseline_items = _items_by_name(baseline.get(collection_name) or [])
        for name, baseline_item in baseline_items.items():
            if name not in current_items:
                issues.append(f"Existing {collection_name[:-1]} `{name}` was removed.")
                continue
            if _fingerprint(current_items[name]) != _fingerprint(baseline_item):
                issues.append(f"Existing {collection_name[:-1]} `{name}` was modified.")
    return issues


def _core_model(core_doc: Dict[str, Any]) -> Dict[str, Any]:
    models = core_doc.get("semantic_model") or []
    if len(models) != 1 or not isinstance(models[0], dict):
        raise ValueError("expected exactly one OSI semantic_model object")
    return models[0]


def _items_by_name(items: List[Any]) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    for item in items:
        if isinstance(item, dict) and item.get("name"):
            result[str(item["name"])] = item
    return result


def _fingerprint(value: Dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def ensure_valid(issues: List[str]) -> None:
    """Raise an OSIValidationError if there are any issues."""
    if issues:
        raise OSIValidationError(" ".join(issues))
