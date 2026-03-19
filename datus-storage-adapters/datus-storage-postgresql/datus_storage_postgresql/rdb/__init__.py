"""PostgreSQL RDB backend adapter for datus-agent."""

from datus_storage_postgresql.rdb.backend import PostgresRdbBackend


def register():
    """Register the PostgreSQL RDB backend with the datus registry."""
    from datus_storage_base.rdb.registry import RdbRegistry

    RdbRegistry.register("postgresql", PostgresRdbBackend)


__all__ = ["PostgresRdbBackend", "register"]
