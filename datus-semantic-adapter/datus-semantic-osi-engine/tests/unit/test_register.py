# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Registry integration for service_type osi_engine."""

from datus_semantic_core.registry import SemanticAdapterRegistry

import datus_semantic_osi_engine
from datus_semantic_osi_engine.adapter import OSIEngineAdapter
from datus_semantic_osi_engine.config import OSIEngineConfig


def test_register_binds_service_type():
    datus_semantic_osi_engine.register()
    metadata = SemanticAdapterRegistry.get_metadata("osi_engine")
    assert metadata is not None
    assert metadata.adapter_class is OSIEngineAdapter
    assert metadata.config_class is OSIEngineConfig
    assert metadata.display_name == "OSI Engine"


def test_create_adapter_roundtrip(model_file):
    datus_semantic_osi_engine.register()
    adapter = SemanticAdapterRegistry.create_adapter(
        "osi_engine", OSIEngineConfig(semantic_model_path=str(model_file))
    )
    assert isinstance(adapter, OSIEngineAdapter)
    assert adapter.service_type == "osi_engine"
