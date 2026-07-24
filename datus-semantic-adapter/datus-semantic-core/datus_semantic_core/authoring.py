# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Authoring interface for semantic adapters.

This is a *backend / editor* surface that reads and mutates the semantic
layer's YAML source files (the source of truth), keyed by metric name. It is
deliberately separate from the query interface (`list_metrics`, `query_metrics`,
...) and MUST NOT be exposed as an agent/LLM function tool: these methods write
to disk and are meant for the product's explorer/editor flows only.

The methods live on ``BaseSemanticAdapter`` as *non-abstract* defaults that
raise :class:`AuthoringNotSupportedError`, so third-party adapters can ignore
them entirely and only the adapters that own a file-based source (OSI,
MetricFlow) need implement them.
"""

from typing import List, Optional

from pydantic import BaseModel, Field

from .exceptions import SemanticCoreException


class AuthoringNotSupportedError(SemanticCoreException):
    """Raised when an adapter does not implement the authoring interface."""


class MetricSource(BaseModel):
    """The source-of-truth YAML for a single metric.

    ``text`` is round-trippable: feeding it back to
    :meth:`BaseSemanticAdapter.write_metric_source` reproduces the metric. Its
    concrete shape is format-specific (OSI metric node vs. MetricFlow ``metric:``
    document); ``format`` tells the caller which one it is.
    """

    name: str = Field(..., description="Metric name")
    format: str = Field(..., description="Source format, e.g. 'osi' | 'metricflow'")
    text: str = Field(..., description="YAML text of the metric definition")
    semantic_model: Optional[str] = Field(
        None, description="Owning semantic model name (OSI); None for MetricFlow"
    )
    file_path: Optional[str] = Field(
        None, description="Absolute path of the source file"
    )


class MetricMutationResult(BaseModel):
    """Outcome of a write/delete so callers can re-sync only what changed."""

    name: str = Field(..., description="Metric name")
    format: str = Field(..., description="Source format, e.g. 'osi' | 'metricflow'")
    file_path: str = Field(..., description="File that was written/removed from")
    semantic_model: Optional[str] = Field(
        None, description="Owning semantic model name (OSI)"
    )
    created: bool = Field(False, description="True if the metric was newly created")
    deleted: bool = Field(False, description="True if the metric was removed")
    affected_paths: List[str] = Field(
        default_factory=list,
        description="Source files that changed; re-index these into the KB",
    )
