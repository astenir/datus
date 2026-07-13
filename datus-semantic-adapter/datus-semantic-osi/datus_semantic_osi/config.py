# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Configuration for the OSI semantic adapter."""

from typing import Dict, Optional

from datus_semantic_core import SemanticAdapterConfig
from pydantic import Field


class DatusOSIConfig(SemanticAdapterConfig):
    """Configuration for :class:`DatusOSIAdapter`.

    ``execution_backend`` is NOT the registry ``service_type`` (which is always
    ``osi``). It selects which :class:`SemanticExecutionBackend` the adapter uses
    internally; the default ``metricflow`` wraps the existing MetricFlow adapter.
    """

    service_type: str = Field(default="osi", description="Service type")
    semantic_models_path: Optional[str] = Field(
        default=None,
        description="Directory of OSI authoring YAML files (the source of truth)",
    )
    generated_path: Optional[str] = Field(
        default=None,
        description="Directory for generated backend artifacts. Disposable; defaults to a temp dir.",
    )
    execution_backend: str = Field(
        default="metricflow", description="Execution backend: metricflow"
    )
    timeout: int = Field(default=300, description="Query timeout in seconds")
    db_config: Optional[Dict[str, str]] = Field(
        default=None, description="Database config dict for live query execution"
    )
