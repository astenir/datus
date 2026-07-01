# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

from .config import TrinoConfig
from .connector import TrinoConnector

__version__ = "0.1.0"
__all__ = ["TrinoConnector", "TrinoConfig", "register"]


def register():
    """Register Trino connector with Datus registry."""
    from datus_db_core import connector_registry

    connector_registry.register(
        "trino",
        TrinoConnector,
        config_class=TrinoConfig,
        capabilities={"catalog", "schema"},
    )
