# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

from abc import ABC, abstractmethod
from typing import Any, List, Optional

from .models import (
    DimensionInfo,
    MetricDefinition,
    QueryResult,
    SemanticModelInfo,
    ValidationResult,
)


class BaseSemanticAdapter(ABC):
    """
    Base class for all semantic layer adapters.

    This is the minimal interface that backend adapters must implement.
    Adapters translate these standardized calls to backend-specific APIs
    (MetricFlow, dbt Semantic Layer, Cube, etc.).
    """

    def __init__(self, config: Any, service_type: str = ""):
        self.config = config
        self.service_type = service_type or getattr(config, "service_type", "")
        self.datasource = getattr(config, "datasource", None)

    # ==================== Semantic Model Interface ====================

    def get_semantic_model(
        self,
        table_name: str,
        catalog_name: str = "",
        database_name: str = "",
        schema_name: str = "",
    ) -> Optional[SemanticModelInfo]:
        """
        Get semantic model for a specific table.

        Returns a SemanticModelInfo with typed metadata, or None if not supported.
        Default implementation returns None (not all adapters support semantic models).
        """
        return None

    def list_semantic_models(
        self,
        catalog_name: str = "",
        database_name: str = "",
        schema_name: str = "",
    ) -> List[SemanticModelInfo]:
        """
        List all available semantic models (optional, for discovery).
        Default implementation returns empty list.
        """
        return []

    # ==================== Metrics Interface ====================

    @abstractmethod
    async def list_metrics(
        self,
        path: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[MetricDefinition]:
        """List available metrics from the semantic layer."""
        raise NotImplementedError()

    @abstractmethod
    async def get_dimensions(
        self,
        metric_name: str,
        path: Optional[List[str]] = None,
    ) -> List[DimensionInfo]:
        """Get queryable dimensions for a specific metric."""
        raise NotImplementedError()

    @abstractmethod
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
        """Execute a metric query or explain the execution plan."""
        raise NotImplementedError()

    @abstractmethod
    async def validate_semantic(self, scope: str = "all") -> ValidationResult:
        """Validate the semantic layer configuration files."""
        raise NotImplementedError()
