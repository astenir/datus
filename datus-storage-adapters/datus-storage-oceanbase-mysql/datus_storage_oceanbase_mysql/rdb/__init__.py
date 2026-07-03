"""OceanBase MySQL mode RDB backend adapter for datus-agent."""

from datus_storage_oceanbase_mysql.rdb.backend import OceanBaseMySQLRdbBackend


def register():
    """Register the OceanBase MySQL RDB backend with the datus registry."""
    from datus_storage_base.rdb.registry import RdbRegistry

    RdbRegistry.register("oceanbase-mysql", OceanBaseMySQLRdbBackend)


__all__ = ["OceanBaseMySQLRdbBackend", "register"]
