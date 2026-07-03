"""OceanBase MySQL mode storage adapter for datus-agent."""

from datus_storage_oceanbase_mysql.rdb import OceanBaseMySQLRdbBackend, register

__all__ = ["OceanBaseMySQLRdbBackend", "register"]
