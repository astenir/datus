"""OceanBase MySQL mode vector backend adapter for datus-agent."""

from datus_storage_oceanbase_mysql.vector.backend import OceanBaseMySQLVectorBackend


def register():
    """Register the OceanBase MySQL vector backend with the datus registry."""
    from datus_storage_base.vector.registry import VectorRegistry

    VectorRegistry.register("oceanbase-mysql", OceanBaseMySQLVectorBackend)


__all__ = ["OceanBaseMySQLVectorBackend", "register"]
