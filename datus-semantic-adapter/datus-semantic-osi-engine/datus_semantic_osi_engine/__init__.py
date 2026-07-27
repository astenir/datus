# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Datus semantic adapter over osi-engine (native Rust OSI engine).

A thin protocol translator: the OSI YAML is loaded, planned, compiled to
dialect SQL, and executed entirely inside the Rust engine (via the
``datus-osi-engine`` pyo3 bindings); this package only maps the Datus
semantic-adapter contract onto the engine's API and its structured errors
onto ``SemanticValidationError``.
"""

__version__ = "0.1.0"


def register() -> None:
    """Register the OSI Engine semantic adapter with the core registry.

    Imported lazily; the datus-osi-engine bindings themselves are only
    imported at first adapter use, so registration works without the wheel.
    """
    from datus_semantic_core.registry import SemanticAdapterRegistry

    from datus_semantic_osi_engine.adapter import OSIEngineAdapter
    from datus_semantic_osi_engine.config import OSIEngineConfig

    SemanticAdapterRegistry.register(
        service_type="osi_engine",
        adapter_class=OSIEngineAdapter,
        config_class=OSIEngineConfig,
        display_name="OSI Engine",
    )
