# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

from .config import GreenplumConfig
from .connector import GreenplumConnector

__version__ = "0.1.0"
__all__ = ["GreenplumConnector", "GreenplumConfig", "register"]


def register():
    """Register Greenplum connector with Datus registry."""
    from datus_db_core import connector_registry

    from .handlers import build_greenplum_uri, resolve_greenplum_context

    connector_registry.register(
        "greenplum",
        GreenplumConnector,
        config_class=GreenplumConfig,
        capabilities={"database", "schema"},
        uri_builder=build_greenplum_uri,
        context_resolver=resolve_greenplum_context,
    )
