from datus_semantic_core import BaseSemanticAdapter
from .adapter import MetricFlowAdapter
from .config import MetricFlowConfig
from .models import (
    MetricDefinition,
    MetricType,
    QueryResult,
    ValidationIssue,
    ValidationResult,
)


def register():
    """
    Register MetricFlow adapter with Datus semantic adapter registry.

    This function is called via entry_point by Datus when discovering adapters.
    """
    # Import Datus registry at runtime to avoid circular dependencies
    from datus_semantic_core import semantic_adapter_registry

    semantic_adapter_registry.register(
        service_type="metricflow",
        adapter_class=MetricFlowAdapter,
        config_class=MetricFlowConfig,
        display_name="MetricFlow",
    )


__all__ = [
    "MetricFlowAdapter",
    "BaseSemanticAdapter",
    "MetricFlowConfig",
    "MetricDefinition",
    "MetricType",
    "QueryResult",
    "ValidationIssue",
    "ValidationResult",
    "register",
]

__version__ = "0.1.6"
