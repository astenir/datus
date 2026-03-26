# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

from .config import SparkConfig
from .connector import SparkConnector

__version__ = "0.1.0"
__all__ = ["SparkConnector", "SparkConfig", "register"]


def register():
    """Register Spark connector with Datus registry."""
    from datus_db_core import connector_registry

    connector_registry.register(
        "spark", SparkConnector, config_class=SparkConfig, capabilities={"database"}
    )
