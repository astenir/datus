# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""DatusOSIAdapter: a BaseSemanticAdapter backed by OSI authoring + a backend.

Flow per call: load OSI YAML (source of truth) -> compile to Datus Semantic IR
-> backend lowering / validation / SQL rendering. The OSI files are the only
thing users edit; backend artifacts are generated and disposable.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
import os
import re
from typing import Any, Dict, List, Optional, Sequence

import sqlglot
from sqlglot import expressions as exp

from datus_semantic_core import BaseSemanticAdapter
from datus_semantic_core.models import (
    DimensionInfo,
    MetricDefinition,
    QueryResult,
    SemanticValidationError,
    ValidationIssue,
    ValidationResult,
)

from datus_semantic_osi.backend import make_backend
from datus_semantic_osi.compiler import compile_document
from datus_semantic_osi.config import DatusOSIConfig
from datus_semantic_osi.dialects import resolve_sqlglot_dialect
from datus_semantic_osi.errors import (
    OSIError,
    OSIValidationError,
    SemanticValidationException,
)
from datus_semantic_osi.ir import (
    Aggregation,
    DatasetIR,
    FieldIR,
    MetricIR,
    MetricKind,
    RelationshipIR,
    SemanticModelIR,
)
from datus_semantic_osi.metricflow_backend import (
    is_period_over_period_base_metric_name,
    period_over_period_base_metric_name,
)
from datus_semantic_osi.normalizer import NormalizationResult, normalize_document
from datus_semantic_osi.profile import OSIDocument, load_osi_path
from datus_semantic_osi.query_join import apply_join_policy, normalize_join_policy
from datus_semantic_osi.query_utils import (
    dimension_output_column,
    is_metric_time_dimension,
    is_null_metric_value,
    metric_time_dimension_for_granularity,
)
from datus_semantic_osi.query_window import (
    can_postprocess_window_metrics,
    query_window_metrics,
)
from datus_semantic_osi.validator import (
    detect_nonportable_functions,
    validate_authoring_quality,
    validate_capabilities,
    validate_ir,
    validate_mutation_guard,
    validate_profile,
)


_SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SAFE_DATE_LITERAL_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}:\d{2})?$")
_DISALLOWED_WHERE_EXPRESSIONS = tuple(
    candidate
    for candidate in (
        getattr(exp, "Select", None),
        getattr(exp, "Subquery", None),
        getattr(exp, "Union", None),
        getattr(exp, "Command", None),
        getattr(exp, "Create", None),
        getattr(exp, "Drop", None),
        getattr(exp, "Insert", None),
        getattr(exp, "Delete", None),
        getattr(exp, "Update", None),
    )
    if candidate is not None
)
_DEFAULT_VALIDATE_CHECKS = ("profile", "ir", "capability", "backend")
_SUPPORTED_VALIDATE_CHECKS = {
    "profile",
    "ir",
    "capability",
    "backend",
    "authoring_quality",
    "mutation_guard",
}
_TIME_GRAINS = {"day", "week", "month", "quarter", "year"}
_OFFSET_WINDOW_UNITS_RE = "|".join(sorted(_TIME_GRAINS, key=len, reverse=True))
_OFFSET_WINDOW_RE = re.compile(
    rf"^\s*(\d+)\s+({_OFFSET_WINDOW_UNITS_RE})s?\s*$", re.IGNORECASE
)


def _normalize_validate_checks(checks: Optional[List[str] | str]) -> List[str]:
    if checks is None:
        return list(_DEFAULT_VALIDATE_CHECKS)
    raw_items: List[Any]
    if isinstance(checks, str):
        raw_items = [item.strip() for item in checks.split(",")]
    else:
        raw_items = list(checks)
    normalized: List[str] = []
    seen: set[str] = set()
    for item in raw_items:
        check = str(item).strip().lower()
        if not check or check in seen:
            continue
        seen.add(check)
        normalized.append(check)
    return normalized


class DatusOSIAdapter(BaseSemanticAdapter):
    """OSI-native semantic adapter."""

    def __init__(self, config: DatusOSIConfig):
        super().__init__(config, service_type="osi")
        self.config = config
        # config.datasource is the name; the dialect comes from its type in db_config.
        db_config = getattr(config, "db_config", None)
        datasource_type = db_config.get("type") if isinstance(db_config, dict) else None
        self._dialect = resolve_sqlglot_dialect(datasource_type or config.datasource)
        self._backend = make_backend(
            config.execution_backend,
            generated_path=config.generated_path,
            db_config=config.db_config,
            datasource=config.datasource,
            timeout=config.timeout,
        )
        self._model_cache: Optional[SemanticModelIR] = None

    # ---- OSI loading / compilation -------------------------------------

    def _load_document(self) -> OSIDocument:
        return self._load_document_result().document

    def _load_document_result(self) -> NormalizationResult:
        path = self.config.semantic_models_path
        if not path or not os.path.isdir(path):
            raise OSIError(f"semantic_models_path is not a directory: {path}")
        result = normalize_document(load_osi_path(path))
        if result.errors:
            raise OSIValidationError(" ".join(result.errors))
        return result

    def _model(self) -> SemanticModelIR:
        if self._model_cache is None:
            self._model_cache = compile_document(self._load_document(), dialect=self._dialect)
        return self._model_cache

    def _find_metric(self, name: str) -> Optional[MetricIR]:
        return next((m for m in self._model().metrics if m.name == name), None)

    @staticmethod
    def _parse_date_boundary(
        value: Optional[str], *, label: str = "date boundary"
    ) -> Optional[date]:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        if not _SAFE_DATE_LITERAL_RE.match(text):
            raise ValueError(
                f"{label} must be a valid date literal in YYYY-MM-DD or "
                "YYYY-MM-DD HH:MM:SS format."
            )
        try:
            return datetime.fromisoformat(text.replace(" ", "T")).date()
        except ValueError:
            raise ValueError(
                f"{label} must be a valid date literal in YYYY-MM-DD or "
                "YYYY-MM-DD HH:MM:SS format."
            ) from None

    @staticmethod
    def _format_date_boundary(value: date) -> str:
        return value.isoformat()

    @staticmethod
    def _shift_months(value: date, months: int) -> date:
        month_index = value.month - 1 + months
        year = value.year + month_index // 12
        month = month_index % 12 + 1
        day = min(value.day, calendar.monthrange(year, month)[1])
        return date(year, month, day)

    @classmethod
    def _shift_date_by_offset(
        cls, value: date, offset_window: str, *, direction: int
    ) -> date:
        match = _OFFSET_WINDOW_RE.match(str(offset_window or ""))
        if not match:
            raise ValueError(
                f"Unsupported period_over_period offset_window `{offset_window}`. "
                "Use '<number> day|week|month|quarter|year'."
            )
        count = int(match.group(1)) * direction
        unit = match.group(2).lower()
        if unit == "day":
            return value + timedelta(days=count)
        if unit == "week":
            return value + timedelta(weeks=count)
        if unit == "month":
            return cls._shift_months(value, count)
        if unit == "quarter":
            return cls._shift_months(value, count * 3)
        if unit == "year":
            return cls._shift_months(value, count * 12)
        raise ValueError(
            f"Unsupported period_over_period offset_window `{offset_window}`. "
            "Use '<number> day|week|month|quarter|year'."
        )

    def _period_over_period_metrics(
        self, model: SemanticModelIR, metrics: List[str]
    ) -> List[MetricIR]:
        by_name = {metric.name: metric for metric in model.metrics}
        return [
            metric
            for metric_name in self._dedupe(metrics)
            if (metric := by_name.get(metric_name)) is not None
            and metric.period_over_period is not None
        ]

    @staticmethod
    def _period_over_period_metadata(metrics: List[MetricIR]) -> Dict[str, Any]:
        return {
            metric.name: metric.period_over_period.model_dump()
            for metric in metrics
            if metric.period_over_period is not None
        }

    @classmethod
    def _period_over_period_time_window(
        cls,
        metrics: List[MetricIR],
        time_start: Optional[str],
    ) -> Optional[str]:
        start = cls._parse_date_boundary(time_start, label="time_start")
        if start is None:
            return time_start
        shifted = [
            cls._shift_date_by_offset(
                start, metric.period_over_period.offset_window, direction=-1
            )
            for metric in metrics
            if metric.period_over_period is not None
        ]
        return cls._format_date_boundary(min(shifted)) if shifted else time_start

    @staticmethod
    def _period_row_date(value: Any) -> Optional[date]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        text = str(value).strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace(" ", "T")).date()
        except ValueError:
            try:
                return datetime.fromisoformat(text[:10]).date()
            except ValueError:
                return None

    def _apply_period_over_period_query_contract(
        self,
        metrics: List[MetricIR],
        dimensions: List[str],
        time_granularity: Optional[str],
        time_start: Optional[str],
        time_end: Optional[str],
    ) -> tuple[List[str], Optional[str], Optional[str]]:
        if not metrics:
            return dimensions, time_granularity, time_start

        grains = {
            metric.period_over_period.time_grain
            for metric in metrics
            if metric.period_over_period is not None
        }
        if len(grains) != 1:
            raise ValueError(
                "A single query cannot mix period_over_period metrics with different time_grain values."
            )
        grain = next(iter(grains))
        if grain not in _TIME_GRAINS:
            raise ValueError(f"Unsupported period_over_period time_grain `{grain}`.")
        normalized_requested_grain = str(time_granularity or "").strip().lower()
        if normalized_requested_grain and normalized_requested_grain != grain:
            raise ValueError(
                f"Metric period_over_period time_grain is `{grain}`, but query requested "
                f"time_granularity `{time_granularity}`."
            )

        period_dimension = f"metric_time__{grain}"
        updated_dimensions = list(dimensions)
        existing_metric_time = [
            dimension
            for dimension in updated_dimensions
            if is_metric_time_dimension(dimension)
        ]
        conflicting_metric_time = [
            dimension
            for dimension in existing_metric_time
            if dimension != period_dimension
        ]
        if conflicting_metric_time:
            raise ValueError(
                f"Metric period_over_period time_grain is `{grain}`, but query requested "
                f"dimension `{conflicting_metric_time[0]}`."
            )
        if not existing_metric_time:
            updated_dimensions.append(period_dimension)

        self._parse_date_boundary(time_end, label="time_end")
        expanded_start = self._period_over_period_time_window(metrics, time_start)
        return updated_dimensions, grain, expanded_start

    def _filter_period_over_period_rows(
        self,
        result: QueryResult,
        *,
        dimensions: List[str],
        time_start: Optional[str],
        time_end: Optional[str],
    ) -> QueryResult:
        start = self._parse_date_boundary(time_start, label="time_start")
        end = self._parse_date_boundary(time_end, label="time_end")
        if start is None and end is None:
            return result

        time_column = next(
            (
                column
                for dimension in dimensions
                if is_metric_time_dimension(dimension)
                and (column := dimension_output_column(dimension, result.columns))
            ),
            None,
        )
        if not time_column:
            return result

        filtered = []
        for row in result.data:
            row_date = self._period_row_date(row.get(time_column))
            if row_date is None:
                continue
            if start is not None and row_date < start:
                continue
            if end is not None and row_date > end:
                continue
            filtered.append(row)

        metadata = dict(result.metadata)
        removed_rows = len(result.data) - len(filtered)
        if removed_rows:
            metadata["period_over_period_filtered_rows"] = removed_rows
        return QueryResult(
            columns=list(result.columns), data=filtered, metadata=metadata
        )

    def _dataset_by_name(self) -> Dict[str, DatasetIR]:
        return {dataset.name: dataset for dataset in self._model().datasets}

    def _root_dataset_names_for_metric(
        self, metric: MetricIR, seen_metrics: Optional[set[str]] = None
    ) -> List[str]:
        if metric.dataset:
            return [metric.dataset]

        seen_metrics = seen_metrics or set()
        if metric.name in seen_metrics:
            return []
        seen_metrics.add(metric.name)

        dataset_names: List[str] = []
        for input_metric in metric.inputs:
            referenced = self._find_metric(input_metric.name)
            if referenced is None:
                continue
            dataset_names.extend(
                self._root_dataset_names_for_metric(referenced, seen_metrics)
            )

        if dataset_names:
            return self._dedupe(dataset_names)

        if metric.measures and self._model().datasets:
            # MetricFlow lowering places dataset-less backing measures on the
            # first declared dataset, so discovery follows the same fallback.
            return [self._model().datasets[0].name]

        return []

    @staticmethod
    def _dedupe(values: List[str]) -> List[str]:
        seen: set[str] = set()
        result: List[str] = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result

    def _metric_metadata(self, metric: MetricIR) -> Dict[str, Any]:
        dataset_names = self._root_dataset_names_for_metric(metric)
        metadata: Dict[str, Any] = {
            "dataset": metric.dataset
            or (dataset_names[0] if len(dataset_names) == 1 else None),
            "datasets": dataset_names if len(dataset_names) > 1 else None,
            "time_dimension": metric.time_dimension,
            "metric_kind": metric.kind.value,
        }

        if metric.expression:
            metadata["expr"] = metric.expression
        if metric.period_over_period is not None:
            metadata["period_over_period"] = metric.period_over_period.model_dump()

        if metric.inputs:
            inputs = []
            for input_metric in metric.inputs:
                item: Dict[str, Any] = {"name": input_metric.name}
                if input_metric.alias:
                    item["alias"] = input_metric.alias
                if input_metric.offset_window:
                    item["offset_window"] = input_metric.offset_window
                inputs.append(item)
            metadata["inputs"] = inputs
            offset_window = next(
                (
                    item.get("offset_window")
                    for item in inputs
                    if item.get("offset_window")
                ),
                None,
            )
            if offset_window:
                metadata["offset_window"] = offset_window
        elif metric.offset_window:
            metadata["offset_window"] = metric.offset_window

        if metric.window:
            metadata["window"] = metric.window
        if metric.grain_to_date:
            metadata["grain_to_date"] = metric.grain_to_date
        if metric.numerator:
            metadata["numerator"] = metric.numerator
        if metric.denominator:
            metadata["denominator"] = metric.denominator
        if metric.measures:
            metadata["measure"] = metric.measures[0].name

        reserved = sorted(set(metadata) & set(metric.metadata))
        if reserved:
            raise ValueError(
                f"Metric `{metric.name}` metadata uses reserved key(s): {reserved}"
            )
        metadata.update(metric.metadata)
        return {key: value for key, value in metadata.items() if value is not None}

    def _metric_has_offset_dependency(
        self, metric: MetricIR, seen_metrics: Optional[set[str]] = None
    ) -> bool:
        if metric.period_over_period is not None:
            return True
        if metric.kind is not MetricKind.DERIVED:
            return bool(metric.offset_window)

        if any(input_metric.offset_window for input_metric in metric.inputs):
            return True

        seen_metrics = seen_metrics or set()
        if metric.name in seen_metrics:
            return False
        seen_metrics.add(metric.name)

        for input_metric in metric.inputs:
            referenced = self._find_metric(input_metric.name)
            if referenced is None:
                continue
            if self._metric_has_offset_dependency(referenced, seen_metrics):
                return True
        return False

    _TIME_GRAINS = ("day", "week", "month", "quarter", "year")

    @classmethod
    def _time_grain_from_text(cls, value: Optional[str]) -> Optional[str]:
        """Extract a known time grain word from a definition string."""
        text = str(value or "").lower()
        for grain in cls._TIME_GRAINS:
            if grain in text:
                return grain
        return None

    def _requires_time_dimension(self, metric: MetricIR) -> bool:
        """Metrics whose definition mandates a metric_time group-by.

        A cumulative metric (window / grain_to_date), period-over-period
        metric, or any metric with an offset dependency is invalid in
        MetricFlow unless queried with metric_time. This is fully determined by
        the metric definition, so the adapter is responsible for satisfying it
        instead of the caller.
        """
        return (
            metric.kind is MetricKind.CUMULATIVE
            or self._metric_has_offset_dependency(metric)
        )

    def _static_required_grains(
        self, metric: MetricIR, seen_metrics: Optional[set[str]] = None
    ) -> set[str]:
        """Required time grains derivable from the metric definition.

        Window / cumulative metrics are post-processed over their base metric at
        the window's own grain (a ``3 months`` moving average rolls over monthly
        rows), so the window/grain_to_date unit is the correct grouping grain
        here, matching how the metric is executed.
        """
        grains: set[str] = set()
        if metric.period_over_period is not None:
            grain = metric.period_over_period.time_grain
            if grain:
                grains.add(grain)

        for source in (metric.grain_to_date, metric.window, metric.offset_window):
            grain = self._time_grain_from_text(source)
            if grain:
                grains.add(grain)

        seen_metrics = seen_metrics or set()
        if metric.name in seen_metrics:
            return grains
        seen_metrics.add(metric.name)

        for input_metric in metric.inputs:
            for source in (
                input_metric.offset_window,
                getattr(input_metric, "offset_to_grain", None),
            ):
                grain = self._time_grain_from_text(source)
                if grain:
                    grains.add(grain)

            referenced = self._find_metric(input_metric.name)
            if referenced is not None:
                grains.update(self._static_required_grains(referenced, seen_metrics))
        return grains

    def _ensure_time_grouping(
        self,
        metrics: List[str],
        dimensions: List[str],
        time_granularity: Optional[str],
    ) -> tuple[List[str], Optional[str]]:
        """Inject metric_time for metrics that require it when the caller omitted it.

        Only fires when no metric_time dimension was supplied, so an explicit
        caller grouping is always respected (idempotent). Turns an otherwise
        deterministic MetricFlow rejection into a valid, overridable query.
        """
        dims = list(dimensions or [])
        if any(is_metric_time_dimension(dimension) for dimension in dims):
            return dims, time_granularity

        required_metrics: List[str] = []
        required_grains: Dict[str, List[str]] = {}
        for name in metrics:
            metric = self._find_metric(name)
            if metric is not None and metric.period_over_period is not None:
                continue
            if metric is None or not self._requires_time_dimension(metric):
                continue
            required_metrics.append(name)
            for grain in self._static_required_grains(metric):
                required_grains.setdefault(grain, []).append(name)

        if not required_metrics:
            return dims, time_granularity
        if len(required_grains) > 1:
            details = ", ".join(
                f"{grain}: {', '.join(names)}"
                for grain, names in sorted(required_grains.items())
            )
            raise SemanticValidationException(
                SemanticValidationError(
                    code="metric_time_grain_conflict",
                    metrics=required_metrics,
                    message=(
                        "Requested metrics require incompatible metric_time grains "
                        f"({details}). Query compatible metric groups separately."
                    ),
                )
            )

        grain = next(iter(required_grains), None) or time_granularity
        dims.append(metric_time_dimension_for_granularity(grain) or "metric_time")
        return dims, time_granularity or grain

    # Class-name fragments of MetricFlow's deterministic query-validation
    # exception families. Matched against the exception MRO so the OSI layer
    # stays decoupled from MetricFlow (which the OSI compiler/IR layers do not
    # import). Deliberately excludes infra/runtime families such as
    # ExecutionException so transient failures propagate unwrapped.
    _QUERY_VALIDATION_EXC_FRAGMENTS = (
        "InvalidQuery",  # query parse/resolution rejections
        "RequestTimeGranularity",  # cumulative-metric grain rejections
        "UnableToSatisfyQuery",  # unsatisfiable metric/dimension combinations
        "CustomerFacingSemantic",  # base of user-facing semantic rejections
    )

    @classmethod
    def _is_query_validation_error(cls, exc: BaseException) -> bool:
        """True for backend query-validation rejections, not infra/SQL errors."""
        return any(
            fragment in klass.__name__
            for klass in type(exc).__mro__
            for fragment in cls._QUERY_VALIDATION_EXC_FRAGMENTS
        )

    def _semantic_validation_error_from(
        self, exc: BaseException, metrics: List[str]
    ) -> Optional[SemanticValidationError]:
        """Map a backend query rejection to a structured, backend-neutral payload.

        Returns ``None`` when ``exc`` is not a validation rejection, so the
        caller re-raises it unchanged instead of masking an infra/SQL failure.
        Known rejections get a specific ``code``; anything else still surfaces
        structured with ``code='validation_error'`` and the original message.
        """
        if not self._is_query_validation_error(exc):
            return None
        text = str(exc)
        lowered = text.lower()
        code = "validation_error"
        required_dimensions: List[str] = []
        required_grain: Optional[str] = None
        # Check the specific "wrong grain" rejection before the "missing
        # metric_time" ones: its message also mentions the cumulative metric and
        # metric_time, so it must win to avoid being mis-coded.
        if "granularity" in lowered and "must be" in lowered:
            code = "time_grain_required"
            required_grain = self._time_grain_from_text(lowered.split("must be", 1)[1])
            if required_grain:
                required_dimensions = [f"metric_time__{required_grain}"]
        elif "metric_time" in lowered and ("offset" in lowered or "derived" in lowered):
            code = "offset_requires_metric_time"
            required_dimensions = ["metric_time"]
        elif "metric_time" in lowered and (
            "cumulative" in lowered or "accumulat" in lowered
        ):
            code = "cumulative_requires_metric_time"
            required_dimensions = ["metric_time"]
        suggested = None
        if required_dimensions or required_grain:
            suggested = {
                "dimensions": required_dimensions,
                "time_granularity": required_grain,
            }
        return SemanticValidationError(
            code=code,
            metrics=list(metrics),
            required_dimensions=required_dimensions,
            required_time_granularity=required_grain,
            suggested_retry=suggested,
            message=text,
        )

    def _offset_anchor_metric_names(
        self, metric: MetricIR, seen_metrics: Optional[set[str]] = None
    ) -> List[str]:
        """Return current-period metrics that bound offset-derived output rows."""
        if metric.period_over_period is not None:
            return [period_over_period_base_metric_name(metric)]

        if metric.kind is not MetricKind.DERIVED:
            return []

        seen_metrics = seen_metrics or set()
        if metric.name in seen_metrics:
            return []
        seen_metrics.add(metric.name)

        anchors: List[str] = []
        offset_inputs = [
            input_metric for input_metric in metric.inputs if input_metric.offset_window
        ]
        if offset_inputs:
            current_inputs = [
                input_metric.name
                for input_metric in metric.inputs
                if not input_metric.offset_window
            ]
            anchors.extend(
                current_inputs or [input_metric.name for input_metric in offset_inputs]
            )

        for input_metric in metric.inputs:
            referenced = self._find_metric(input_metric.name)
            if referenced is None:
                continue
            anchors.extend(
                self._offset_anchor_metric_names(referenced, set(seen_metrics))
            )

        return self._dedupe(anchors)

    def _query_metrics_plan(
        self, metrics: List[str]
    ) -> tuple[List[str], List[str], List[str]]:
        requested = self._dedupe(list(metrics))
        anchor_metrics: List[str] = []
        filter_metrics: List[str] = []

        for metric_name in requested:
            metric = self._find_metric(metric_name)
            if metric is None:
                continue
            if self._metric_has_offset_dependency(metric):
                anchor_metrics.extend(self._offset_anchor_metric_names(metric))
            else:
                filter_metrics.append(metric_name)

        anchor_metrics = [
            metric_name
            for metric_name in self._dedupe(anchor_metrics)
            if self._find_metric(metric_name) is not None
            or is_period_over_period_base_metric_name(metric_name)
        ]
        hidden_anchor_metrics = [
            metric_name
            for metric_name in anchor_metrics
            if metric_name not in requested
        ]
        query_metrics = self._dedupe([*requested, *hidden_anchor_metrics])
        filter_anchor_metrics = self._dedupe([*filter_metrics, *anchor_metrics])
        return query_metrics, hidden_anchor_metrics, filter_anchor_metrics

    def _filter_offset_anchor_rows(
        self,
        result: QueryResult,
        *,
        hidden_anchor_metrics: List[str],
        filter_anchor_metrics: List[str],
    ) -> QueryResult:
        anchor_columns = [
            metric_name
            for metric_name in filter_anchor_metrics
            if metric_name in result.columns
        ]
        if not anchor_columns:
            return result

        filtered_data = [
            row
            for row in result.data
            if any(
                not is_null_metric_value(row.get(anchor_column))
                for anchor_column in anchor_columns
            )
        ]

        hidden_columns = set(hidden_anchor_metrics)
        visible_columns = [
            column for column in result.columns if column not in hidden_columns
        ]
        if hidden_columns:
            filtered_data = [
                {column: row.get(column) for column in visible_columns}
                for row in filtered_data
            ]

        metadata = dict(result.metadata)
        removed_rows = len(result.data) - len(filtered_data)
        if hidden_anchor_metrics:
            metadata["hidden_offset_anchor_metrics"] = list(hidden_anchor_metrics)
        if removed_rows:
            metadata["offset_anchor_filtered_rows"] = removed_rows

        return QueryResult(
            columns=visible_columns,
            data=filtered_data,
            metadata=metadata,
        )

    def _relationship_dimension(
        self, metric: MetricIR, dimension: str
    ) -> Optional[tuple[RelationshipIR, DatasetIR, FieldIR, str]]:
        dataset_names = self._root_dataset_names_for_metric(metric)
        if len(dataset_names) != 1 or "__" not in dimension:
            return None
        from_dataset = dataset_names[0]
        datasets = self._dataset_by_name()
        for relationship in self._model().relationships:
            if relationship.from_dataset != from_dataset:
                continue
            to_dataset = datasets.get(relationship.to_dataset)
            if to_dataset is None:
                continue
            join_name = self._relationship_join_name(
                to_dataset, relationship.to_identifier
            )
            prefix = f"{join_name}__"
            if not dimension.startswith(prefix):
                continue
            field_name = dimension[len(prefix) :]
            field = next(
                (
                    candidate
                    for candidate in to_dataset.fields
                    if candidate.name == field_name
                ),
                None,
            )
            if field is not None:
                return relationship, to_dataset, field, join_name
        return None

    @staticmethod
    def _dataset_source_sql(dataset: DatasetIR) -> str:
        if dataset.sql_table:
            return dataset.sql_table
        if dataset.sql_query:
            return f"({dataset.sql_query})"
        raise ValueError(f"Dataset `{dataset.name}` does not declare a SQL source.")

    @staticmethod
    def _metric_time_dimension(metric: MetricIR, dataset: DatasetIR) -> Optional[str]:
        return metric.time_dimension or dataset.primary_time_dimension

    @staticmethod
    def _sql_identifier(value: str, *, label: str = "identifier") -> str:
        identifier = str(value or "").strip().strip("`")
        if not _SAFE_IDENTIFIER_RE.fullmatch(identifier):
            raise ValueError(f"Unsafe SQL {label}: {value!r}")
        return identifier

    @staticmethod
    def _sql_date_literal(value: str, *, label: str) -> str:
        text = str(value or "").strip()
        if not _SAFE_DATE_LITERAL_RE.fullmatch(text):
            raise ValueError(f"{label} must be an ISO date or timestamp literal")
        return "'" + text.replace("'", "''") + "'"

    def _runtime_where_sql(self, where: Optional[str]) -> Optional[str]:
        if not where:
            return None
        text = str(where).strip()
        if text.lower().startswith("where "):
            text = text[6:].strip()
        parsed = sqlglot.parse(text, read=self._dialect)
        if len(parsed) != 1:
            raise ValueError("where must contain exactly one SQL predicate expression")
        expression = parsed[0]
        if isinstance(expression, _DISALLOWED_WHERE_EXPRESSIONS):
            raise ValueError(
                "where must be a SQL predicate expression, not a query or command"
            )
        if any(
            isinstance(node, _DISALLOWED_WHERE_EXPRESSIONS)
            for node in expression.walk()
        ):
            raise ValueError("where must not contain nested queries or SQL commands")
        return expression.sql(dialect=self._dialect)

    def _profile_sql_expression(self, value: str, *, label: str) -> str:
        text = str(value or "").strip()
        if _SAFE_IDENTIFIER_RE.fullmatch(text.strip("`")):
            return DatusOSIAdapter._sql_identifier(text, label=label)
        parsed = sqlglot.parse(text, read=self._dialect)
        if len(parsed) != 1:
            raise ValueError(f"{label} must contain exactly one SQL expression")
        expression = parsed[0]
        if isinstance(expression, _DISALLOWED_WHERE_EXPRESSIONS):
            raise ValueError(
                f"{label} must be a SQL expression, not a query or command"
            )
        if any(
            isinstance(node, _DISALLOWED_WHERE_EXPRESSIONS)
            for node in expression.walk()
        ):
            raise ValueError(f"{label} must not contain nested queries or SQL commands")
        return expression.sql(dialect=self._dialect)

    @staticmethod
    def _relationship_dimension_key(
        rel_dim: tuple[RelationshipIR, DatasetIR, FieldIR, str],
    ) -> tuple[str, ...]:
        relationship, to_dataset, field, join_name = rel_dim
        return (
            relationship.from_dataset,
            relationship.from_identifier,
            relationship.to_dataset,
            relationship.to_identifier,
            to_dataset.name,
            field.name,
            field.expr,
            join_name,
        )

    @staticmethod
    def _can_dimension_preserve_metric(metric: MetricIR) -> bool:
        return metric.kind is MetricKind.AGGREGATE and len(metric.measures) == 1

    def _metric_aggregate_sql(self, metric: MetricIR) -> str:
        if not metric.measures:
            raise ValueError(
                f"Metric `{metric.name}` is not backed by an aggregate measure."
            )
        measure = metric.measures[0]
        expr = measure.expr

        if measure.agg is Aggregation.SUM:
            return f"SUM({expr})"
        if measure.agg is Aggregation.COUNT:
            return f"COUNT({expr})"
        if measure.agg is Aggregation.COUNT_DISTINCT:
            return f"COUNT(DISTINCT {expr})"
        if measure.agg is Aggregation.AVERAGE:
            return f"AVG({expr})"
        if measure.agg is Aggregation.MIN:
            return f"MIN({expr})"
        if measure.agg is Aggregation.MAX:
            return f"MAX({expr})"
        raise ValueError(
            f"Unsupported aggregation `{measure.agg}` for metric `{metric.name}`."
        )

    def _dimension_preserving_sql(
        self,
        *,
        metrics: List[str],
        dimensions: Sequence[str],
        time_start: Optional[str],
        time_end: Optional[str],
        where: Optional[str],
        zero_fill: bool,
        order_by: Optional[List[str]],
        limit: Optional[int],
    ) -> Optional[str]:
        if len(dimensions) != 1 or is_metric_time_dimension(dimensions[0]):
            return None
        metric_objects = [self._find_metric(metric_name) for metric_name in metrics]
        if any(metric is None for metric in metric_objects):
            return None
        typed_metrics = [metric for metric in metric_objects if metric is not None]
        if not typed_metrics or any(
            not self._can_dimension_preserve_metric(metric) for metric in typed_metrics
        ):
            return None
        first_metric = typed_metrics[0]
        rel_dim = self._relationship_dimension(first_metric, dimensions[0])
        if rel_dim is None:
            return None
        relationship, to_dataset, field, _join_name = rel_dim
        rel_dim_key = self._relationship_dimension_key(rel_dim)
        for metric in typed_metrics[1:]:
            metric_rel_dim = self._relationship_dimension(metric, dimensions[0])
            if (
                metric_rel_dim is None
                or self._relationship_dimension_key(metric_rel_dim) != rel_dim_key
            ):
                return None

        datasets = self._dataset_by_name()
        fact_dataset = datasets.get(relationship.from_dataset)
        if fact_dataset is None:
            return None

        fact_source = self._dataset_source_sql(fact_dataset)
        dimension_source = self._dataset_source_sql(to_dataset)
        where_terms: List[str] = []
        time_dimension = self._metric_time_dimension(first_metric, fact_dataset)
        if time_start or time_end:
            if not time_dimension:
                return None
            if any(
                self._metric_time_dimension(metric, fact_dataset) != time_dimension
                for metric in typed_metrics[1:]
            ):
                return None
        if time_start and time_dimension:
            where_terms.append(
                f"{self._sql_identifier(time_dimension, label='time dimension')} >= "
                f"{self._sql_date_literal(time_start, label='time_start')}"
            )
        if time_end and time_dimension:
            where_terms.append(
                f"{self._sql_identifier(time_dimension, label='time dimension')} <= "
                f"{self._sql_date_literal(time_end, label='time_end')}"
            )
        if where:
            where_terms.append(f"({self._runtime_where_sql(where)})")
        where_sql = f"WHERE {' AND '.join(where_terms)}" if where_terms else ""

        select_metrics = [
            f"{self._metric_aggregate_sql(metric)} AS {self._sql_identifier(metric.name, label='metric alias')}"
            for metric in typed_metrics
        ]
        from_identifier = self._sql_identifier(
            relationship.from_identifier, label="relationship key"
        )
        to_identifier = self._sql_identifier(
            relationship.to_identifier, label="relationship key"
        )
        field_expr = self._profile_sql_expression(
            field.expr, label="dimension expression"
        )
        field_name = self._sql_identifier(field.name, label="dimension alias")
        fact_sql = (
            f"SELECT {from_identifier} AS __join_key, "
            f"{', '.join(select_metrics)} "
            f"FROM {fact_source} {where_sql} GROUP BY {from_identifier}"
        )
        dimension_sql = (
            f"SELECT {to_identifier} AS __join_key, {field_expr} AS {field_name} "
            f"FROM {dimension_source}"
        )
        metric_selects = []
        for metric in typed_metrics:
            metric_name = self._sql_identifier(metric.name, label="metric alias")
            expr = f"fact.{metric_name}"
            if zero_fill:
                expr = f"COALESCE({expr}, 0)"
            metric_selects.append(f"{expr} AS {metric_name}")

        order_sql = ""
        output_columns = {
            field_name,
            *(
                self._sql_identifier(metric.name, label="metric alias")
                for metric in typed_metrics
            ),
        }
        if order_by:
            order_parts = []
            for item in order_by:
                descending = str(item).startswith("-")
                name = str(item)[1:] if descending else str(item)
                column = dimension_output_column(name, [field_name]) or name
                column = self._sql_identifier(column, label="order_by column")
                if column not in output_columns:
                    raise ValueError(
                        f"order_by column is not part of the dimension-preserving result: {name!r}"
                    )
                order_parts.append(f"{column} {'DESC' if descending else 'ASC'}")
            if order_parts:
                order_sql = f" ORDER BY {', '.join(order_parts)}"
        else:
            order_sql = f" ORDER BY {field_name}"
        limit_sql = f" LIMIT {int(limit)}" if limit is not None else ""
        return (
            f"SELECT dim.{field_name} AS {field_name}, {', '.join(metric_selects)} "
            f"FROM ({dimension_sql}) dim "
            f"LEFT JOIN ({fact_sql}) fact "
            "ON fact.__join_key = dim.__join_key"
            f"{order_sql}{limit_sql}"
        )

    @staticmethod
    def _query_result_from_dataframe(
        df: Any, metadata: Optional[Dict[str, Any]] = None
    ) -> QueryResult:
        if df is None:
            return QueryResult(columns=[], data=[], metadata=metadata or {})
        if hasattr(df, "empty") and df.empty:
            return QueryResult(
                columns=list(getattr(df, "columns", [])),
                data=[],
                metadata=metadata or {},
            )
        if hasattr(df, "columns") and hasattr(df, "to_dict"):
            return QueryResult(
                columns=list(df.columns),
                data=df.to_dict(orient="records"),
                metadata=metadata or {},
            )
        rows = list(df)
        columns = list(rows[0].keys()) if rows and isinstance(rows[0], dict) else []
        return QueryResult(columns=columns, data=rows, metadata=metadata or {})

    async def _query_dimension_preserving(
        self,
        executor: Any,
        *,
        metrics: List[str],
        dimensions: Sequence[str],
        time_start: Optional[str],
        time_end: Optional[str],
        where: Optional[str],
        limit: Optional[int],
        order_by: Optional[List[str]],
        zero_fill: bool,
        dry_run: bool,
    ) -> Optional[QueryResult]:
        sql = self._dimension_preserving_sql(
            metrics=metrics,
            dimensions=dimensions,
            time_start=time_start,
            time_end=time_end,
            where=where,
            zero_fill=zero_fill,
            order_by=order_by,
            limit=limit,
        )
        if not sql:
            return None
        metadata = {
            "sql": sql,
            "join_policy": "dimension_preserving",
            "zero_fill": bool(zero_fill),
            "execution": "osi_dimension_preserving_sql",
        }
        if dry_run:
            return QueryResult(columns=["sql"], data=[{"sql": sql}], metadata=metadata)
        sql_client = getattr(getattr(executor, "client", None), "sql_client", None)
        if sql_client is None or not hasattr(sql_client, "query"):
            return None
        df = sql_client.query(sql)
        return self._query_result_from_dataframe(df, metadata=metadata)

    # ---- BaseSemanticAdapter interface ---------------------------------

    async def list_metrics(
        self, path: Optional[List[str]] = None, limit: int = 100, offset: int = 0
    ) -> List[MetricDefinition]:
        metrics = self._model().metrics
        if path:
            metrics = [
                m
                for m in metrics
                if isinstance(m.metadata.get("subject_path"), list)
                and m.metadata["subject_path"][: len(path)] == path
            ]
        metrics = metrics[offset : offset + limit]
        return [
            MetricDefinition(
                name=m.name,
                description=m.description or None,
                type=m.kind.value,
                dimensions=[d.name for d in self._dimensions_for_metric(m)],
                measures=[x.name for x in m.measures],
                unit=m.unit,
                format=m.format,
                path=m.metadata.get("subject_path")
                if isinstance(m.metadata.get("subject_path"), list)
                else None,
                metadata=self._metric_metadata(m),
            )
            for m in metrics
        ]

    @staticmethod
    def _dimension_info(field: FieldIR, name: Optional[str] = None) -> DimensionInfo:
        return DimensionInfo(
            name=name or field.name,
            description=field.description or None,
            type="time" if field.type == "time" else field.type,
            is_primary_key=False,
        )

    @staticmethod
    def _relationship_join_name(to_dataset: DatasetIR, fallback_identifier: str) -> str:
        primary = next((i for i in to_dataset.identifiers if i.type == "primary"), None)
        return primary.name if primary else fallback_identifier

    def _dimensions_for_dataset(
        self,
        dataset_name: str,
        prefix: Optional[List[str]] = None,
        visited: Optional[set[str]] = None,
    ) -> List[DimensionInfo]:
        datasets = self._dataset_by_name()
        dataset = datasets.get(dataset_name)
        if dataset is None:
            return []

        prefix = prefix or []
        visited = visited or set()
        visited.add(dataset_name)

        dimensions = [
            self._dimension_info(
                field,
                "__".join([*prefix, field.name]) if prefix else field.name,
            )
            for field in dataset.fields
        ]

        for relationship in self._model().relationships:
            if relationship.from_dataset != dataset_name:
                continue
            if relationship.to_dataset in visited:
                continue
            to_dataset = datasets.get(relationship.to_dataset)
            if to_dataset is None:
                continue
            join_name = self._relationship_join_name(
                to_dataset, relationship.to_identifier
            )
            dimensions.extend(
                self._dimensions_for_dataset(
                    relationship.to_dataset,
                    prefix=[*prefix, join_name],
                    visited=set(visited),
                )
            )
        return dimensions

    def _dimensions_for_metric(self, metric: MetricIR) -> List[DimensionInfo]:
        dimensions: List[DimensionInfo] = []
        seen: set[str] = set()
        for dataset_name in self._root_dataset_names_for_metric(metric):
            for dimension in self._dimensions_for_dataset(dataset_name):
                if dimension.name in seen:
                    continue
                seen.add(dimension.name)
                dimensions.append(dimension)
        return dimensions

    async def get_dimensions(
        self, metric_name: str, path: Optional[List[str]] = None
    ) -> List[DimensionInfo]:
        metric = self._find_metric(metric_name)
        if metric is None:
            return []
        return self._dimensions_for_metric(metric)

    async def query_metrics(
        self,
        metrics: List[str],
        dimensions: Optional[List[str]] = None,
        path: Optional[List[str]] = None,
        time_start: Optional[str] = None,
        time_end: Optional[str] = None,
        time_granularity: Optional[str] = None,
        where: Optional[str] = None,
        limit: Optional[int] = None,
        order_by: Optional[List[str]] = None,
        join_policy: Optional[str] = None,
        zero_fill: bool = False,
        dry_run: bool = False,
    ) -> QueryResult:
        model = self._model()
        period_over_period_metrics = self._period_over_period_metrics(model, metrics)
        live = getattr(self._backend, "has_live_connection", False)
        dimensions = dimensions or []
        dimensions, time_granularity = self._ensure_time_grouping(
            metrics, dimensions, time_granularity
        )
        policy = normalize_join_policy(join_policy)

        if zero_fill and policy != "dimension_preserving":
            raise ValueError("zero_fill requires join_policy='dimension_preserving'.")
        if period_over_period_metrics and policy == "dimension_preserving":
            raise ValueError(
                "period_over_period metrics are not supported with join_policy='dimension_preserving'."
            )

        original_time_start = time_start
        if period_over_period_metrics:
            dimensions, time_granularity, time_start = (
                self._apply_period_over_period_query_contract(
                    period_over_period_metrics,
                    dimensions,
                    time_granularity,
                    time_start,
                    time_end,
                )
            )

        if dry_run and not live:
            if policy == "dimension_preserving":
                sql = self._dimension_preserving_sql(
                    metrics=metrics,
                    dimensions=dimensions,
                    time_start=time_start,
                    time_end=time_end,
                    where=where,
                    zero_fill=zero_fill,
                    order_by=order_by,
                    limit=limit,
                )
                if not sql:
                    raise ValueError(
                        "join_policy='dimension_preserving' cannot plan this query."
                    )
                return QueryResult(
                    columns=["sql"],
                    data=[{"sql": sql}],
                    metadata={
                        "explain": True,
                        "sql": sql,
                        "join_policy": "dimension_preserving",
                        "zero_fill": bool(zero_fill),
                        "execution": "osi_dimension_preserving_sql",
                    },
                )
            sql = self._backend.render_sql(
                model,
                metrics=metrics,
                dimensions=dimensions,
                time_start=time_start,
                time_end=time_end,
                where=where,
                limit=limit,
            )
            metadata = {"explain": True, "sql": sql}
            if period_over_period_metrics:
                metadata["period_over_period"] = self._period_over_period_metadata(
                    period_over_period_metrics
                )
                if time_start != original_time_start:
                    metadata["period_over_period_expanded_time_start"] = time_start
            return QueryResult(
                columns=["sql"],
                data=[{"sql": sql}],
                metadata=metadata,
            )

        if not live:
            raise NotImplementedError(
                "Live query execution requires a configured db_config so the backend can "
                "delegate to its warehouse connection. Use dry_run=True for the plan."
            )

        query_metrics, hidden_anchor_metrics, filter_anchor_metrics = (
            self._query_metrics_plan(metrics)
        )

        # delegate live execution / explain to the wrapped MetricFlowAdapter
        executor = self._backend.make_executor(model)
        if policy == "dimension_preserving":
            dimension_preserving_result = await self._query_dimension_preserving(
                executor,
                metrics=metrics,
                dimensions=dimensions,
                time_start=time_start,
                time_end=time_end,
                where=where,
                limit=limit,
                order_by=order_by,
                zero_fill=zero_fill,
                dry_run=dry_run,
            )
            if dimension_preserving_result is not None:
                return dimension_preserving_result
            raise ValueError(
                "join_policy='dimension_preserving' cannot plan this query."
            )

        try:
            if not dry_run and can_postprocess_window_metrics(model, query_metrics):
                result = await query_window_metrics(
                    executor,
                    model,
                    metrics=query_metrics,
                    dimensions=dimensions,
                    path=path,
                    time_start=time_start,
                    time_end=time_end,
                    time_granularity=time_granularity,
                    where=where,
                    limit=limit,
                    order_by=order_by,
                )
            else:
                result = await executor.query_metrics(
                    query_metrics,
                    dimensions=dimensions,
                    path=path,
                    time_start=time_start,
                    time_end=time_end,
                    time_granularity=time_granularity,
                    where=where,
                    limit=limit,
                    order_by=order_by,
                    dry_run=dry_run,
                )
        except Exception as exc:
            payload = self._semantic_validation_error_from(exc, metrics)
            if payload is None:
                raise
            raise SemanticValidationException(payload) from exc
        if dry_run:
            if period_over_period_metrics:
                result.metadata["period_over_period"] = (
                    self._period_over_period_metadata(period_over_period_metrics)
                )
                if time_start != original_time_start:
                    result.metadata["period_over_period_expanded_time_start"] = (
                        time_start
                    )
            return result
        if period_over_period_metrics:
            result.metadata["period_over_period"] = self._period_over_period_metadata(
                period_over_period_metrics
            )
            if time_start != original_time_start:
                result.metadata["period_over_period_expanded_time_start"] = time_start
            result = self._filter_period_over_period_rows(
                result,
                dimensions=dimensions,
                time_start=original_time_start,
                time_end=time_end,
            )
        result = self._filter_offset_anchor_rows(
            result,
            hidden_anchor_metrics=hidden_anchor_metrics,
            filter_anchor_metrics=filter_anchor_metrics,
        )
        return apply_join_policy(
            result,
            dimensions=dimensions,
            join_policy=join_policy,
        )

    async def validate_semantic(
        self,
        scope: str = "all",
        checks: Optional[List[str] | str] = None,
        baseline_artifact: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        checks_list = _normalize_validate_checks(checks)
        unsupported = sorted(
            check for check in checks_list if check not in _SUPPORTED_VALIDATE_CHECKS
        )
        if unsupported:
            return ValidationResult(
                valid=False,
                issues=[
                    ValidationIssue(
                        severity="error",
                        message=(
                            f"Unsupported validate_semantic check(s): {unsupported}. "
                            f"Supported checks: {sorted(_SUPPORTED_VALIDATE_CHECKS)}."
                        ),
                    )
                ],
            )

        issues: List[ValidationIssue] = []

        # Stage 1: OSI Profile validation (authoring level).
        try:
            normalization = self._load_document_result()
            doc = normalization.document
        except OSIError as e:
            return ValidationResult(
                valid=False, issues=[ValidationIssue(severity="error", message=str(e))]
            )
        issues.extend(
            ValidationIssue(severity="warning", message=m)
            for m in [*normalization.warnings, *normalization.actions]
        )
        if "profile" in checks_list:
            issues.extend(
                ValidationIssue(severity="error", message=m)
                for m in validate_profile(doc)
            )
            issues.extend(
                ValidationIssue(severity="warning", message=m)
                for m in detect_nonportable_functions(doc, dialect=self._dialect)
            )
        if "authoring_quality" in checks_list:
            issues.extend(
                ValidationIssue(severity="error", message=m)
                for m in validate_authoring_quality(doc)
            )
        if "mutation_guard" in checks_list:
            issues.extend(
                ValidationIssue(severity="error", message=m)
                for m in validate_mutation_guard(doc, baseline_artifact)
            )

        if any(i.severity == "error" for i in issues):
            return ValidationResult(valid=False, issues=issues)

        needs_ir = bool({"ir", "capability", "backend"} & set(checks_list))
        if not needs_ir:
            return ValidationResult(valid=True, issues=issues)

        # Stage 2: compile to IR (business-semantic errors fail fast).
        try:
            model = compile_document(doc, dialect=self._dialect)
        except OSIValidationError as e:
            issues.append(ValidationIssue(severity="error", message=str(e)))
            return ValidationResult(valid=False, issues=issues)

        # Stage 3: IR + backend capability validation.
        if "ir" in checks_list:
            issues.extend(
                ValidationIssue(severity="error", message=m) for m in validate_ir(model)
            )
        if "capability" in checks_list:
            caps = getattr(self._backend, "capabilities", {}) or {}
            issues.extend(
                ValidationIssue(severity="error", message=m)
                for m in validate_capabilities(model, caps)
            )
        if any(i.severity == "error" for i in issues):
            return ValidationResult(valid=False, issues=issues)

        # Stage 4: backend validation. With a live connection, delegate to
        # MetricFlowAdapter for the full pipeline (lint + parse + semantic +
        # data-warehouse validation); otherwise run parse + semantic only.
        if "backend" in checks_list:
            if getattr(self._backend, "has_live_connection", False):
                executor = self._backend.make_executor(model)
                backend_result = await executor.validate_semantic(scope=scope)
            else:
                backend_result = self._backend.validate(model)
            issues.extend(backend_result.issues)
            valid = backend_result.valid and not any(
                i.severity == "error" for i in issues
            )
            return ValidationResult(valid=valid, issues=issues)
        return ValidationResult(
            valid=not any(i.severity == "error" for i in issues),
            issues=issues,
        )
