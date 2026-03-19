"""Shared fixtures for PostgreSQL + pgvector integration tests."""

import pytest
from testcontainers.postgres import PostgresContainer

from datus_storage_base.vector.base import EmbeddingFunction


@pytest.fixture(scope="session")
def pg_container():
    """Start a PostgreSQL container for the test session."""
    with PostgresContainer(
        image="pgvector/pgvector:pg17",
        username="testuser",
        password="testpass",
        dbname="testdb",
    ) as pg:
        yield pg


@pytest.fixture
def pg_config(pg_container):
    """Return a config dict suitable for the PostgreSQL backends."""
    host = pg_container.get_container_host_ip()
    port = pg_container.get_exposed_port(5432)
    return {
        "host": host,
        "port": int(port),
        "user": "testuser",
        "password": "testpass",
        "dbname": "testdb",
    }


class MockEmbeddingFunction(EmbeddingFunction):
    """Mock embedding function for testing without a real model."""

    name = "mock"

    def ndims(self):
        return 4

    def generate_embeddings(self, texts, *args, **kwargs):
        return [[0.1, 0.2, 0.3, 0.4]] * len(texts)
