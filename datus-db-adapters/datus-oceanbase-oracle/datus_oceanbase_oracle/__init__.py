# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

from .config import OceanBaseOracleConfig
from .connector import OceanBaseOracleConnector

__version__ = "0.1.0"
__all__ = ["OceanBaseOracleConnector", "OceanBaseOracleConfig", "register"]


def register():
    """Register OceanBase Oracle mode connector with Datus registry."""
    from datus_db_core import connector_registry

    connector_registry.register(
        "oceanbase-oracle",
        OceanBaseOracleConnector,
        config_class=OceanBaseOracleConfig,
        capabilities={"database", "schema"},
    )
