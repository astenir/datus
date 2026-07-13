# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Semantic execution backend.

A backend lowers a :class:`SemanticModelIR` into its own artifact, validates it,
and (optionally) executes / explains queries. ``MetricFlowBackend`` wraps the
existing ``datus-semantic-metricflow`` stack; future backends should implement
the same contract without changing OSI authoring or the LLM generation contract.
"""

from __future__ import annotations

import tempfile
from abc import ABC, abstractmethod
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, List, Optional

from datus_semantic_core.models import ValidationIssue, ValidationResult

from datus_semantic_osi.errors import OSIValidationError
from datus_semantic_osi.ir import SemanticModelIR
from datus_semantic_osi.metricflow_backend import (
    MetricFlowArtifact,
    lower_to_metricflow,
)


def _db_config_value(db_config: Optional[dict], *keys: str) -> str:
    if not db_config:
        return ""
    for key in keys:
        value = db_config.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


class SemanticExecutionBackend(ABC):
    """Contract every execution backend implements."""

    name: str = "abstract"
    capabilities: dict = {}

    @abstractmethod
    def lower(self, model: SemanticModelIR):
        """Lower the IR into a backend artifact."""

    @abstractmethod
    def validate(self, model: SemanticModelIR) -> ValidationResult:
        """Validate the lowered artifact (structure + semantics)."""

    @abstractmethod
    def render_sql(
        self,
        model: SemanticModelIR,
        metrics: List[str],
        dimensions: Optional[List[str]] = None,
        time_start: Optional[str] = None,
        time_end: Optional[str] = None,
        where: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> str:
        """Render the execution-plan SQL for a query (dry run)."""


class MetricFlowBackend(SemanticExecutionBackend):
    """IR -> legacy MetricFlow YAML -> MetricFlow parse/semantic + DuckDB explain.

    Thin wrapper over ``datus-semantic-metricflow``: lowering produces the YAML,
    while parse/semantic validation and SQL rendering reuse MetricFlow itself.
    """

    name = "metricflow"
    capabilities = {
        "metric_kinds": ["aggregate", "expression", "ratio", "cumulative", "derived"],
        "filtered_dataset": True,
        "runtime_where": True,
        "many_to_one_join": True,
        "time_bucket": ["day", "week", "month", "quarter", "year"],
        "dry_run": "sql",
        "artifact": "yaml",
    }

    def __init__(
        self,
        generated_path: Optional[str] = None,
        db_config: Optional[dict] = None,
        datasource: Optional[str] = None,
        timeout: int = 300,
    ):
        self._generated_path = generated_path
        self._db_config = db_config
        self._datasource = datasource
        self._timeout = timeout
        self._live_temp_dir: Optional[tempfile.TemporaryDirectory] = None

    @property
    def has_live_connection(self) -> bool:
        return bool(self._db_config)

    def make_executor(self, model: SemanticModelIR):
        """Build a live MetricFlowAdapter on the lowered YAML (requires db_config).

        This is the wrapping referred to in the design doc: the OSI backend
        delegates warehouse validation and query execution to the existing
        ``MetricFlowAdapter`` rather than reimplementing them.
        """
        if not self._db_config:
            raise RuntimeError("No db_config configured for live MetricFlow execution.")
        directory = self._write_persistent(model)
        try:
            from datus_semantic_metricflow.adapter import MetricFlowAdapter
            from datus_semantic_metricflow.config import MetricFlowConfig
        except ImportError as e:
            raise self._missing_metricflow_error() from e

        datasource = self._datasource or _db_config_value(
            self._db_config,
            "database",
            "database_name",
            "schema",
            "db_schema",
            "schema_name",
            "catalog",
            "catalog_name",
        )
        config = MetricFlowConfig(
            datasource=datasource,
            db_config=self._db_config,
            semantic_models_path=str(directory),
            timeout=self._timeout,
        )
        return MetricFlowAdapter(config)

    @staticmethod
    def _missing_metricflow_error() -> OSIValidationError:
        return OSIValidationError(
            "MetricFlow backend requires the optional MetricFlow dependency. "
            "Install with `pip install 'datus-semantic-osi[metricflow]'`."
        )

    @contextmanager
    def _artifact_dir(self) -> Iterator[Path]:
        if self._generated_path:
            d = Path(self._generated_path)
            d.mkdir(parents=True, exist_ok=True)
            yield d
            return
        with tempfile.TemporaryDirectory(prefix="osi_metricflow_") as directory:
            yield Path(directory)

    def _persistent_artifact_dir(self) -> Path:
        if self._generated_path:
            d = Path(self._generated_path)
            d.mkdir(parents=True, exist_ok=True)
            return d
        if self._live_temp_dir is None:
            self._live_temp_dir = tempfile.TemporaryDirectory(
                prefix="osi_metricflow_live_"
            )
        return Path(self._live_temp_dir.name)

    def lower(self, model: SemanticModelIR) -> MetricFlowArtifact:
        return lower_to_metricflow(model)

    def _write(self, model: SemanticModelIR, directory: Path) -> Path:
        self.lower(model).write(directory)
        return directory

    def _write_persistent(self, model: SemanticModelIR) -> Path:
        return self._write(model, self._persistent_artifact_dir())

    def validate(self, model: SemanticModelIR) -> ValidationResult:
        try:
            from metricflow.model.model_validator import ModelValidator
            from metricflow.model.parsing.dir_to_model import (
                parse_directory_of_yaml_files_to_model,
            )
        except ImportError:
            return ValidationResult(
                valid=False,
                issues=[
                    ValidationIssue(
                        severity="error", message=str(self._missing_metricflow_error())
                    )
                ],
            )

        issues: List[ValidationIssue] = []
        with self._artifact_dir() as directory:
            self._write(model, directory)
            build = parse_directory_of_yaml_files_to_model(str(directory))
        for e in build.issues.errors:
            issues.append(ValidationIssue(severity="error", message=str(e)))
        for w in build.issues.warnings:
            issues.append(ValidationIssue(severity="warning", message=str(w)))
        if build.issues.has_blocking_issues:
            return ValidationResult(valid=False, issues=issues)

        semantic = ModelValidator().validate_model(build.model)
        for e in semantic.issues.errors:
            issues.append(ValidationIssue(severity="error", message=str(e)))
        for w in semantic.issues.warnings:
            issues.append(ValidationIssue(severity="warning", message=str(w)))

        has_errors = any(i.severity == "error" for i in issues)
        return ValidationResult(valid=not has_errors, issues=issues)

    def _client(self, directory: Path):
        try:
            from metricflow.api.metricflow_client import MetricFlowClient
            from metricflow.model.parsing.dir_to_model import (
                parse_directory_of_yaml_files_to_model,
            )
            from metricflow.sql_clients.duckdb import DuckDbSqlClient
        except ImportError as e:
            raise self._missing_metricflow_error() from e

        build = parse_directory_of_yaml_files_to_model(str(directory))
        return MetricFlowClient(
            sql_client=DuckDbSqlClient(),
            user_configured_model=build.model,
            system_schema="main",
        )

    def render_sql(
        self,
        model: SemanticModelIR,
        metrics: List[str],
        dimensions: Optional[List[str]] = None,
        time_start: Optional[str] = None,
        time_end: Optional[str] = None,
        where: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> str:
        with self._artifact_dir() as directory:
            self._write(model, directory)
            client = self._client(directory)
            result = client.explain(
                metrics=metrics,
                dimensions=dimensions or [],
                start_time=time_start,
                end_time=time_end,
                where=where,
                limit=limit,
            )
        return result.rendered_sql_without_descriptions.sql_query


def make_backend(
    name: str,
    generated_path: Optional[str] = None,
    db_config: Optional[dict] = None,
    datasource: Optional[str] = None,
    timeout: int = 300,
) -> SemanticExecutionBackend:
    """Factory: resolve an execution backend by name."""
    if name == "metricflow":
        return MetricFlowBackend(
            generated_path=generated_path,
            db_config=db_config,
            datasource=datasource,
            timeout=timeout,
        )
    raise ValueError(f"Unknown execution backend: {name}")
