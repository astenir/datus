# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Configuration for the OSI Engine semantic adapter."""

from __future__ import annotations

from typing import Any, Dict, Optional

from datus_semantic_core.config import SemanticAdapterConfig


class OSIEngineConfig(SemanticAdapterConfig):
    """Adapter configuration.

    Connection precedence: an explicit ``connections_path`` (agent.yml or a
    standalone ``datasources:`` YAML, consumed verbatim by the engine) wins
    over an inline ``db_config`` (one agent.yml datasource entry, written to
    a temporary connections file). With neither, the engine falls back to
    its own discovery order and, failing that, local DuckDB.
    """

    service_type: str = "osi_engine"
    # Path to the OSI semantic model file (.yaml/.yml/.json). Takes precedence
    # over semantic_models_path.
    semantic_model_path: Optional[str] = None
    # Directory of OSI models (Datus convention, e.g. subject/semantic_models/
    # <datasource>). Used when semantic_model_path is unset: a single model
    # file inside is picked automatically; multiple require semantic_model_path.
    semantic_models_path: Optional[str] = None
    # Connections file passed to the engine verbatim (agent.yml vocabulary).
    connections_path: Optional[str] = None
    # Named connection profile; falls back to the base-class `datasource`.
    connection: Optional[str] = None
    # Inline datasource entry (agent.yml vocabulary: type/host/port/...).
    db_config: Optional[Dict[str, Any]] = None
    # Explicit SQL dialect for dry-run compilation without a connection.
    dialect: Optional[str] = None
    # Per-profile connection-pool cap inside the engine.
    pool_size: int = 8
