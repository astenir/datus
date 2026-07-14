# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class DimensionInfo(BaseModel):
    """Information about a dimension."""

    name: str = Field(..., description="Dimension name")
    description: Optional[str] = Field(None, description="Dimension description")
    type: Optional[str] = Field(
        None,
        description="Dimension type (platform-native value, e.g. 'string', 'number', 'time', 'boolean', 'categorical')",
    )
    is_primary_key: Optional[bool] = Field(
        None, description="Whether this dimension is a primary key"
    )


class SemanticModelInfo(BaseModel):
    """Typed semantic model metadata (thin model + extra dict for platform-specific data)."""

    name: str = Field(
        ..., description="Model name (cube name, explore name, semantic model name)"
    )
    description: Optional[str] = Field(None, description="Model description")
    table_name: Optional[str] = Field(
        None, description="Physical table name backing this semantic model"
    )
    catalog_name: Optional[str] = Field(
        None, description="Physical catalog name for the backing table"
    )
    database_name: Optional[str] = Field(
        None, description="Physical database name for the backing table"
    )
    schema_name: Optional[str] = Field(
        None, description="Physical schema name for the backing table"
    )
    platform_type: Optional[str] = Field(
        None,
        description="Platform-native type (e.g. 'cube', 'view', 'explore', 'semantic_model')",
    )
    dimensions: List[DimensionInfo] = Field(
        default_factory=list, description="Dimensions in this model"
    )
    measures: List[str] = Field(
        default_factory=list, description="Measure/metric names in this model"
    )
    extra: Dict[str, Any] = Field(
        default_factory=dict,
        description="Platform-specific metadata (joins, segments, etc.)",
    )


class MetricDefinition(BaseModel):
    """Metadata about a specific metric."""

    name: str = Field(..., description="Metric name")
    description: Optional[str] = Field(None, description="Metric description")
    type: Optional[str] = Field(
        None, description="Metric type (simple, ratio, derived, etc.)"
    )
    dimensions: List[str] = Field(
        default_factory=list, description="Available dimensions for this metric"
    )
    measures: List[str] = Field(
        default_factory=list, description="Underlying measures used"
    )
    unit: Optional[str] = Field(
        None, description="Unit of measurement (e.g., 'USD', 'count', 'percent')"
    )
    format: Optional[str] = Field(
        None, description="Display format (e.g., ',.2f', '0.00%')"
    )
    path: Optional[List[str]] = Field(
        None,
        description="Subject tree hierarchy path (e.g., ['domain', 'layer1', 'layer2'])",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


class QueryResult(BaseModel):
    """Standardized query response for both actual execution and dry-run."""

    columns: List[str] = Field(default_factory=list, description="Column names")
    data: List[Dict[str, Any]] = Field(
        default_factory=list, description="Query result rows"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (execution_time, warnings, etc.)",
    )


class ValidationIssue(BaseModel):
    """A single validation issue."""

    severity: Literal["error", "warning", "info"] = Field(
        ..., description="Severity level: error, warning, info"
    )
    message: str = Field(..., description="Issue description")
    location: Optional[str] = Field(
        None, description="Location in config where issue was found"
    )


class ValidationResult(BaseModel):
    """Result of a semantic configuration validation check."""

    valid: bool = Field(..., description="Whether the configuration is valid")
    issues: List[ValidationIssue] = Field(
        default_factory=list, description="List of validation issues"
    )


class SemanticValidationError(BaseModel):
    """Backend-neutral structured payload for a deterministic query validation failure.

    Adapters map their engine-specific validation rejections onto this shape so
    callers can revise query arguments from stable fields instead of parsing raw
    exception text. Engine specifics live only in the *values* (``code`` and the
    dimension strings), never in the type. Unknown rejections still surface here
    with ``code='validation_error'`` and a human-readable ``message``.
    """

    error_type: Literal["semantic_validation_error"] = "semantic_validation_error"
    code: str = Field(
        "validation_error",
        description="Validation category, e.g. 'cumulative_requires_metric_time', 'time_grain_required'",
    )
    metrics: List[str] = Field(
        default_factory=list, description="Affected metric names"
    )
    required_dimensions: List[str] = Field(
        default_factory=list,
        description="Dimensions the caller must add, e.g. ['metric_time__day']",
    )
    required_time_granularity: Optional[str] = Field(
        None, description="Required or corrected time granularity, e.g. 'day'"
    )
    unsupported_dimensions: List[str] = Field(
        default_factory=list,
        description="Requested dimensions not supported by all selected metrics",
    )
    suggested_retry: Optional[Dict[str, Any]] = Field(
        None, description="Concrete query_metrics kwargs the caller can retry with"
    )
    message: str = Field("", description="Human-readable explanation")


class AnomalyContext(BaseModel):
    """Context information for anomaly detection in attribution analysis."""

    model_config = {"extra": "forbid"}

    rule: Optional[str] = Field(
        None, description="Anomaly detection rule name (e.g., 'wow_growth_gt_20pct')"
    )
    observed_change_pct: Optional[float] = Field(
        None, description="Observed percentage change"
    )
