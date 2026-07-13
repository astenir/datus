# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""datus-semantic-core: Core interfaces for Datus semantic adapters."""

from datus_semantic_core.base import BaseSemanticAdapter
from datus_semantic_core.config import SemanticAdapterConfig
from datus_semantic_core.exceptions import SemanticCoreException
from datus_semantic_core.models import (
    AnomalyContext,
    DimensionInfo,
    MetricDefinition,
    QueryResult,
    SemanticModelInfo,
    ValidationIssue,
    ValidationResult,
)
from datus_semantic_core.registry import (
    AdapterMetadata,
    SemanticAdapterRegistry,
    semantic_adapter_registry,
)

__all__ = [
    "BaseSemanticAdapter",
    "SemanticAdapterConfig",
    "SemanticCoreException",
    "AnomalyContext",
    "DimensionInfo",
    "MetricDefinition",
    "QueryResult",
    "SemanticModelInfo",
    "ValidationIssue",
    "ValidationResult",
    "AdapterMetadata",
    "SemanticAdapterRegistry",
    "semantic_adapter_registry",
]
