"""pgvector Vector backend adapter for datus-agent."""

from datus_storage_postgresql.vector.backend import PgvectorBackend


def register():
    """Register the pgvector backend with the datus registry."""
    from datus_storage_base.vector.registry import VectorRegistry

    VectorRegistry.register("postgresql", PgvectorBackend)


__all__ = ["PgvectorBackend", "register"]
