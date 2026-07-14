# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Datus OSI semantic package: OSI authoring -> Datus Semantic IR -> backend lowering."""

__version__ = "0.1.0"


def register() -> None:
    """Register the OSI semantic adapter with the core registry.

    Imported lazily so that the OSI compiler / IR / lowering layers can be used
    without the (heavy) MetricFlow execution backend installed.
    """
    from datus_semantic_core.registry import SemanticAdapterRegistry

    from datus_semantic_osi.adapter import DatusOSIAdapter
    from datus_semantic_osi.config import DatusOSIConfig

    SemanticAdapterRegistry.register(
        service_type="osi",
        adapter_class=DatusOSIAdapter,
        config_class=DatusOSIConfig,
        display_name="OSI",
    )
