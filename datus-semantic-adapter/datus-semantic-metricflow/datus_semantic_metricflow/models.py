"""
Models for MetricFlow adapter.

Re-exports common models from datus_semantic_core.
"""

# Re-export common models from datus-semantic-core
from datus_semantic_core.models import (
    DimensionInfo,
    MetricDefinition,
    QueryResult,
    ValidationIssue,
    ValidationResult,
)

# Import MetricType directly from metricflow
from metricflow.model.objects.metric import MetricType

__all__ = [
    "MetricType",
    "MetricDefinition",
    "DimensionInfo",
    "QueryResult",
    "ValidationIssue",
    "ValidationResult",
]
