# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""The OSI Engine semantic adapter: a thin translator onto osi-engine.

All planning, SQL generation, and execution happen inside the Rust engine;
this class maps the Datus contract onto the engine API. Engine calls are
synchronous and GIL-releasing, so they run under ``asyncio.to_thread``.

Scope note: an engine instance serves ONE OSI model file, so the ``path``
(subject-tree) arguments are accepted and ignored.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from datus_semantic_core.authoring import MetricMutationResult, MetricSource
from datus_semantic_core.base import BaseSemanticAdapter
from datus_semantic_core.exceptions import SemanticCoreException
from datus_semantic_core.metric_author import MetricAuthor
from datus_semantic_core.models import (
    DimensionInfo,
    MetricDefinition,
    QueryResult,
    SemanticModelInfo,
    SemanticValidationError,
    ValidationIssue,
    ValidationResult,
)

from datus_semantic_osi_engine.config import OSIEngineConfig
from datus_semantic_osi_engine.dialects import resolve_engine_dialect
from datus_semantic_osi_engine.engine import EngineHandle, load_binding
from datus_semantic_osi_engine.errors import (
    SemanticValidationException,
    raise_mapped,
)


class OSIEngineAdapter(BaseSemanticAdapter):
    """Datus semantic adapter backed by the native Rust OSI engine."""

    def __init__(self, config: OSIEngineConfig):
        super().__init__(config, service_type="osi_engine")
        self.config: OSIEngineConfig = config
        self._handle = EngineHandle(config)

    # ==================== Semantic Model Interface ====================

    def list_semantic_models(
        self,
        catalog_name: str = "",
        database_name: str = "",
        schema_name: str = "",
    ) -> List[SemanticModelInfo]:
        return [self._model_info(row) for row in self._engine().datasets()]

    def get_semantic_model(
        self,
        table_name: str,
        catalog_name: str = "",
        database_name: str = "",
        schema_name: str = "",
    ) -> Optional[SemanticModelInfo]:
        for row in self._engine().datasets():
            source = str(row.get("source", ""))
            if table_name in (row.get("name"), source) or source.endswith(
                f".{table_name}"
            ):
                return self._model_info(row)
        return None

    # ==================== Metrics Interface ====================

    async def list_metrics(
        self,
        path: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[MetricDefinition]:
        engine = await asyncio.to_thread(self._engine)
        rows = await asyncio.to_thread(engine.metrics)
        dimension_names = [
            d["name"] for d in await asyncio.to_thread(engine.dimensions)
        ]
        metrics = [
            MetricDefinition(
                name=row["name"],
                description=row.get("description") or None,
                type=row.get("kind"),
                dimensions=dimension_names,
                measures=list(row.get("measures") or []),
                metadata={"datasets": list(row.get("datasets") or [])},
            )
            for row in rows
        ]
        return metrics[offset : offset + limit]

    async def get_dimensions(
        self,
        metric_name: str,
        path: Optional[List[str]] = None,
    ) -> List[DimensionInfo]:
        engine = await asyncio.to_thread(self._engine)
        metric_names = [m["name"] for m in await asyncio.to_thread(engine.metrics)]
        if metric_name not in metric_names:
            raise SemanticValidationException(
                SemanticValidationError(
                    code="unknown_metric",
                    metrics=[metric_name],
                    message=(
                        f"unknown metric {metric_name!r} | "
                        f"candidates: {', '.join(metric_names)}"
                    ),
                )
            )
        # v1: every dimension in the model. Relationship-reachable dimensions
        # from other datasets are genuinely queryable, so filtering to the
        # metric's own datasets would under-report; invalid combinations are
        # rejected by the planner with structured, retryable errors.
        return [
            DimensionInfo(
                name=row["name"],
                description=row.get("description") or None,
                type="time" if row.get("is_time") else None,
            )
            for row in await asyncio.to_thread(engine.dimensions)
        ]

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
        dry_run: bool = False,
    ) -> QueryResult:
        binding = await asyncio.to_thread(load_binding)
        engine = await asyncio.to_thread(self._engine)
        dimensions = list(dimensions or [])
        # Fetched off the event loop; _build_query stays pure (no engine I/O).
        dimension_rows = await asyncio.to_thread(engine.dimensions)
        metric_rows = await asyncio.to_thread(engine.metrics)

        query = self._build_query(
            dimension_rows,
            metric_rows,
            metrics=metrics,
            dimensions=dimensions,
            time_start=time_start,
            time_end=time_end,
            time_granularity=time_granularity,
            where=where,
            limit=limit,
            order_by=order_by,
        )
        connection = self._handle.profile_name
        try:
            if dry_run:
                compiled = await asyncio.to_thread(
                    engine.compile,
                    query,
                    dialect=self._dry_run_dialect(binding, connection),
                    connection=connection,
                )
                return QueryResult(
                    columns=["sql"],
                    data=[{"sql": compiled["sql"]}],
                    metadata={
                        "sql": compiled["sql"],
                        "dialect": compiled["dialect"],
                        "dry_run": True,
                        "explain": True,
                    },
                )
            result = await asyncio.to_thread(
                engine.execute,
                query,
                connection=connection,
                timeout_secs=float(self.config.timeout_seconds),
            )
            return QueryResult(
                columns=list(result["columns"]),
                data=list(result["rows"]),
                metadata={
                    "sql": result["sql"],
                    "dialect": result["dialect"],
                    "row_count": result["row_count"],
                },
            )
        except Exception as exc:  # noqa: BLE001 - mapped to typed errors below
            # A SemanticValidationException (raised only by _build_query, before
            # this try) is not an engine error; raise_mapped re-raises it as-is.
            raise_mapped(
                exc,
                binding,
                requested_metrics=metrics,
                requested_dimensions=dimensions,
            )
            raise  # unreachable; raise_mapped always raises

    async def validate_semantic(self, scope: str = "all") -> ValidationResult:
        binding = await asyncio.to_thread(load_binding)
        try:
            model_path = self._handle.model_file()
        except SemanticCoreException as exc:
            return ValidationResult(
                valid=False,
                issues=[ValidationIssue(severity="error", message=str(exc))],
            )

        def _validate() -> Dict[str, Any]:
            with open(model_path, encoding="utf-8") as fh:
                return binding.validate(fh.read())

        try:
            payload = await asyncio.to_thread(_validate)
        except OSError as exc:
            return ValidationResult(
                valid=False,
                issues=[
                    ValidationIssue(
                        severity="error",
                        message=f"cannot read semantic model {model_path!r}: {exc}",
                    )
                ],
            )

        issues = [
            ValidationIssue(
                severity=issue.get("severity") or "error",
                message=f"{issue.get('code', 'issue')}: {issue.get('message', '')}",
                location=issue.get("location") or None,
            )
            for issue in payload.get("issues", [])
        ]
        for err in payload.get("compile_errors", []):
            message = f"{err.get('code', 'compile_error')}: {err.get('message', '')}"
            if err.get("hint"):
                message = f"{message} | {err['hint']}"
            issues.append(
                ValidationIssue(
                    severity="error",
                    message=message,
                    location=err.get("location") or None,
                )
            )
        return ValidationResult(valid=bool(payload.get("valid")), issues=issues)

    # ==================== Authoring Interface ====================
    # Backend/editor surface; not an agent/LLM tool. osi_engine authors the same
    # OSI YAML files as the osi adapter, so the file read/write/validate logic is
    # reused from the shared core MetricAuthor — only the execution/query engine
    # differs (native Rust here vs the Python compiler there). Uses core's
    # default structural document validation (no dependency on datus-semantic-osi).

    def _authoring_root(self) -> str:
        """The OSI model path authoring operates on (mirrors resolve_model_file).

        An explicit ``semantic_model_path`` pins authoring to exactly that file
        so sibling models in the same directory are never touched; otherwise the
        configured ``semantic_models_path`` directory is scanned.
        """
        if self.config.semantic_model_path:
            return self.config.semantic_model_path
        if self.config.semantic_models_path:
            return self.config.semantic_models_path
        raise SemanticCoreException(
            "osi_engine authoring requires semantic_model_path or semantic_models_path"
        )

    def _author(self) -> MetricAuthor:
        return MetricAuthor(self._authoring_root())

    def read_metric_source(
        self,
        metric_name: str,
        *,
        subject_path: Optional[List[str]] = None,
    ) -> MetricSource:
        return self._author().read(metric_name)

    def write_metric_source(
        self,
        metric_name: str,
        source: str,
        *,
        subject_path: Optional[List[str]] = None,
        create: bool = False,
    ) -> MetricMutationResult:
        return self._author().write(
            metric_name, source, subject_path=subject_path, create=create
        )

    def delete_metric_source(
        self,
        metric_name: str,
        *,
        subject_path: Optional[List[str]] = None,
    ) -> MetricMutationResult:
        return self._author().delete(metric_name)

    def validate_metric_source(
        self,
        source: str,
        *,
        metric_name: Optional[str] = None,
    ) -> ValidationResult:
        return self._author().validate(source, metric_name=metric_name)

    # ==================== Internals ====================

    def _engine(self) -> Any:
        return self._handle.get()

    def _model_info(self, row: Dict[str, Any]) -> SemanticModelInfo:
        return SemanticModelInfo(
            name=str(row.get("name", "")),
            table_name=str(row.get("source", "")),
            platform_type="osi_engine",
            extra={k: v for k, v in row.items() if k not in ("name", "source")},
        )

    def _dry_run_dialect(
        self, binding: Any, connection: Optional[str]
    ) -> Optional[str]:
        """Dialect for compile-only calls: explicit config, else db_config type.

        With a connection profile the engine already knows the dialect; an
        agreeing explicit dialect is harmless, a conflicting one is a config
        error the engine reports. An explicitly configured dialect that the
        engine doesn't know is a config error (raise) — not silently dropped,
        which would emit DuckDB SQL for the wrong dialect. An unknown
        db_config *type* stays lenient (returns None → engine decides).
        """
        if self.config.dialect:
            resolved = resolve_engine_dialect(self.config.dialect, binding.DIALECTS)
            if resolved is None:
                raise SemanticCoreException(
                    f"unknown dialect {self.config.dialect!r}; "
                    f"supported: {', '.join(binding.DIALECTS)}"
                )
            return resolved
        db_config = self.config.db_config or {}
        return resolve_engine_dialect(db_config.get("type"), binding.DIALECTS)

    def _build_query(
        self,
        dimension_rows: List[Dict[str, Any]],
        metric_rows: List[Dict[str, Any]],
        *,
        metrics: List[str],
        dimensions: List[str],
        time_start: Optional[str],
        time_end: Optional[str],
        time_granularity: Optional[str],
        where: Optional[str],
        limit: Optional[int],
        order_by: Optional[List[str]],
    ) -> Dict[str, Any]:
        """Assemble the engine's MetricQuery dict. Pure: no engine I/O."""
        time_dimension_names = {
            row["name"] for row in dimension_rows if row.get("is_time")
        }

        def is_time_dimension(name: str) -> bool:
            return name in time_dimension_names or any(
                full.endswith(f".{name}") for full in time_dimension_names
            )

        group_by: List[Dict[str, Any]] = []
        grain_attached = False
        for dimension in dimensions:
            item: Dict[str, Any] = {"field": dimension}
            if time_granularity and is_time_dimension(dimension):
                item["grain"] = time_granularity
                grain_attached = True
            group_by.append(item)

        if time_granularity and not grain_attached:
            model_time_dims = sorted(time_dimension_names)
            raise SemanticValidationException(
                SemanticValidationError(
                    code="time_grain_required",
                    metrics=list(metrics),
                    required_dimensions=model_time_dims,
                    required_time_granularity=time_granularity,
                    suggested_retry=(
                        {
                            "metrics": list(metrics),
                            "dimensions": dimensions + model_time_dims[:1],
                            "time_granularity": time_granularity,
                        }
                        if model_time_dims
                        else None
                    ),
                    message=(
                        "time_granularity was given but no requested dimension is a "
                        f"time dimension | time dimensions: {', '.join(model_time_dims)}"
                    ),
                )
            )

        query: Dict[str, Any] = {"metrics": list(metrics), "group_by": group_by}
        if where:
            query["where_sql"] = where
        if time_start or time_end:
            time_range: Dict[str, Any] = {"start": time_start, "end": time_end}
            # The engine binds a time range to an explicit `dimension`, else the
            # single time dimension in the group-by, else it rejects the query
            # (S-TIME-3). Datus callers routinely time-filter without grouping
            # by time ("total for September"), so when the group-by carries no
            # time dimension, resolve the target from the queried metrics'
            # datasets and pass it explicitly.
            if not any(is_time_dimension(item["field"]) for item in group_by):
                metric_datasets = {
                    dataset
                    for row in metric_rows
                    if row.get("name") in metrics
                    for dataset in row.get("datasets") or []
                }
                candidates = sorted(
                    name
                    for name in time_dimension_names
                    if name.split(".", 1)[0] in metric_datasets
                )
                if len(candidates) == 1:
                    time_range["dimension"] = candidates[0]
                elif len(candidates) > 1:
                    raise SemanticValidationException(
                        SemanticValidationError(
                            code="time_range_needs_dimension",
                            metrics=list(metrics),
                            required_dimensions=candidates,
                            message=(
                                "the time range matches more than one time dimension of the "
                                f"queried metrics ({', '.join(candidates)}); group by the "
                                "intended one, or query metrics that share a single time "
                                "dimension"
                            ),
                        )
                    )
                # No candidate: leave the range unbound — the engine reports
                # time_range_needs_dimension with its own structured error.
            query["time_range"] = time_range
        if order_by:
            query["order_by"] = [
                {"key": key[1:], "desc": True}
                if key.startswith("-")
                else {"key": key, "desc": False}
                for key in order_by
            ]
        if limit is not None:
            query["limit"] = int(limit)
        return query
