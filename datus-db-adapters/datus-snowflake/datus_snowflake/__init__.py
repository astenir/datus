"""Snowflake adapter for Datus Agent."""

from datus.tools.db_tools import connector_registry

from .config import SnowflakeConfig
from .connector import SnowflakeConnector

__version__ = "0.1.0"
__all__ = ["SnowflakeConnector", "SnowflakeConfig", "register"]


def register():
    """Register Snowflake connector with Datus registry."""
    connector_registry.register("snowflake", SnowflakeConnector)


# Auto-register when imported
register()
