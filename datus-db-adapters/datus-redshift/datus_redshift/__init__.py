"""
Redshift adapter for Datus Agent.

This module provides the RedshiftConnector class that enables Datus to connect
to Amazon Redshift databases and perform queries, metadata retrieval, and
other database operations.
"""

# Import our configuration and connector classes
from .config import RedshiftConfig
from .connector import RedshiftConnector

# Version of this adapter
__version__ = "0.1.0"

# Export these classes so they can be imported with: from datus_redshift import RedshiftConnector, RedshiftConfig
__all__ = ["RedshiftConnector", "RedshiftConfig", "register"]


def register():
    """
    Register Redshift connector with Datus registry.

    This function registers the RedshiftConnector class with the Datus connector
    registry under the name "redshift". This allows Datus to automatically discover
    and use this connector when configured to connect to Redshift databases.
    """
    from datus_db_core import connector_registry

    connector_registry.register(
        "redshift",
        RedshiftConnector,
        config_class=RedshiftConfig,
        capabilities={"database", "schema"},
    )
