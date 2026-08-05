"""Compatibility imports for OceanBase MySQL storage helpers.

New code should import these helpers from
``datus_enterprise.storage.oceanbase.common``. The legacy module remains for
deployed imports and downstream callers.
"""

from datus_enterprise.storage.oceanbase.common import (
    OceanBaseMySQLConfig,
    OceanBaseMySQLPool,
    OceanBaseSchemaMixin,
    _split_sql_statements,
    quote_identifier,
)

__all__ = [
    "OceanBaseMySQLConfig",
    "OceanBaseMySQLPool",
    "OceanBaseSchemaMixin",
    "_split_sql_statements",
    "quote_identifier",
]
