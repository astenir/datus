"""PostgreSQL RDB test environment provider.

Uses testcontainers to spin up a PostgreSQL container for testing.
Registered as an entry point: datus.storage.rdb.testing:postgresql
"""

import logging
from typing import Any, Dict, Optional

from datus_storage_base.testing import RdbTestEnv, TestEnvConfig

logger = logging.getLogger(__name__)


class PostgresRdbTestEnv(RdbTestEnv):
    """RdbTestEnv implementation using a testcontainers PostgreSQL instance."""

    def __init__(self):
        self._container = None
        self._config: Optional[Dict[str, Any]] = None

    def setup(self) -> None:
        from testcontainers.postgres import PostgresContainer

        self._container = PostgresContainer(
            image="pgvector/pgvector:pg17",
            username="datus_test",
            password="datus_test",
            dbname="datus_test",
        )
        self._container.start()
        self._config = {
            "host": self._container.get_container_host_ip(),
            "port": int(self._container.get_exposed_port(5432)),
            "user": "datus_test",
            "password": "datus_test",
            "dbname": "datus_test",
        }
        logger.info("Started PostgreSQL test container for RDB backend")

    def teardown(self) -> None:
        if self._container is not None:
            try:
                self._container.stop()
                logger.info("Stopped PostgreSQL test container for RDB backend")
                self._container = None
                self._config = None
            except Exception:
                logger.exception("Failed to stop PostgreSQL test container for RDB backend")
                raise

    def clear_data(self, namespace: str) -> None:
        if self._config is None:
            return

        import psycopg
        from psycopg import sql

        conninfo = (
            f"host={self._config['host']} port={self._config['port']} "
            f"user={self._config['user']} password={self._config['password']} "
            f"dbname={self._config['dbname']}"
        )
        with psycopg.connect(conninfo, autocommit=True) as conn:
            if namespace:
                conn.execute(
                    sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                        sql.Identifier(namespace)
                    )
                )
            else:
                # Drop all tables in public schema
                rows = conn.execute(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
                ).fetchall()
                for row in rows:
                    tbl = row[0] if not isinstance(row, dict) else row["tablename"]
                    conn.execute(
                        sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(
                            sql.Identifier(tbl)
                        )
                    )

    def get_config(self) -> TestEnvConfig:
        return TestEnvConfig(backend_type="postgresql", params=dict(self._config or {}))


def create_test_env() -> PostgresRdbTestEnv:
    """Factory function for entry point registration."""
    return PostgresRdbTestEnv()
