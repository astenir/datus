# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

from .config import PostgreSQLConfig
from .connector import PostgreSQLConnector

__version__ = "0.1.0"
__all__ = ["PostgreSQLConnector", "PostgreSQLConfig", "register"]


def register():
    """Register PostgreSQL connector with Datus registry."""
    from datus_db_core import connector_registry

    from .handlers import build_postgresql_uri, resolve_postgresql_context

    connector_registry.register(
        "postgresql",
        PostgreSQLConnector,
        config_class=PostgreSQLConfig,
        capabilities={"database", "schema"},
        uri_builder=build_postgresql_uri,
        context_resolver=resolve_postgresql_context,
    )
