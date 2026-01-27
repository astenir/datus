# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

from .config import MySQLConfig
from .connector import MySQLConnector

__version__ = "0.1.0"
__all__ = ["MySQLConnector", "MySQLConfig", "register"]


def register():
    """Register MySQL connector with Datus registry."""
    from datus.tools.db_tools import connector_registry

    connector_registry.register("mysql", MySQLConnector, config_class=MySQLConfig)
