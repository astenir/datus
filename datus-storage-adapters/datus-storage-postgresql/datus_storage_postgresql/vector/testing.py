"""pgvector test environment provider.

Uses testcontainers to spin up a PostgreSQL container with pgvector for testing.
Registered as an entry point: datus.storage.vector.testing:postgresql
"""

import logging
import threading
import uuid
from typing import Any, Dict, Optional

from datus_storage_base.testing import TestEnvConfig, VectorTestEnv

logger = logging.getLogger(__name__)


class _SharedContainer:
    """Manages a single shared PostgreSQL container across all PgvectorTestEnv instances."""

    _container = None
    _ref_count: int = 0
    _host: Optional[str] = None
    _port: Optional[int] = None
    _lock = threading.Lock()

    @classmethod
    def acquire(cls):
        """Start the container if not already running, increment ref count."""
        with cls._lock:
            if cls._ref_count == 0:
                from testcontainers.postgres import PostgresContainer

                cls._container = PostgresContainer(
                    image="pgvector/pgvector:pg17",
                    username="datus_test",
                    password="datus_test",
                    dbname="datus_test",
                )
                cls._container.start()
                cls._host = cls._container.get_container_host_ip()
                cls._port = int(cls._container.get_exposed_port(5432))
                logger.info("Started shared PostgreSQL test container")
            cls._ref_count += 1
            return cls._host, cls._port

    @classmethod
    def release(cls):
        """Decrement ref count; stop the container when no more users."""
        with cls._lock:
            cls._ref_count -= 1
            if cls._ref_count <= 0:
                cls._ref_count = 0
                if cls._container is not None:
                    try:
                        cls._container.stop()
                        logger.info("Stopped shared PostgreSQL test container")
                    except Exception:
                        logger.exception("Failed to stop shared PostgreSQL test container")
                    finally:
                        cls._container = None
                        cls._host = None
                        cls._port = None

    @classmethod
    def admin_conninfo(cls) -> str:
        return (
            f"host={cls._host} port={cls._port} "
            f"user=datus_test password=datus_test dbname=datus_test"
        )


class PgvectorTestEnv(VectorTestEnv):
    """VectorTestEnv implementation using a shared testcontainers PostgreSQL + pgvector instance.

    Each instance gets its own randomly-named database for data isolation.
    """

    def __init__(self):
        self._dbname: Optional[str] = None
        self._config: Optional[Dict[str, Any]] = None

    def setup(self) -> None:
        import psycopg
        from psycopg import sql

        host, port = _SharedContainer.acquire()
        self._dbname = "test_" + uuid.uuid4().hex[:12]

        try:
            with psycopg.connect(_SharedContainer.admin_conninfo(), autocommit=True) as conn:
                conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(self._dbname)))
        except Exception:
            self._dbname = None
            self._config = None
            _SharedContainer.release()
            raise

        self._config = {
            "host": host,
            "port": port,
            "user": "datus_test",
            "password": "datus_test",
            "dbname": self._dbname,
        }
        logger.info("Created test database %s", self._dbname)

    def teardown(self) -> None:
        if self._dbname is not None:
            import psycopg
            from psycopg import sql

            try:
                with psycopg.connect(_SharedContainer.admin_conninfo(), autocommit=True) as conn:
                    conn.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(self._dbname)))
                logger.info("Dropped test database %s", self._dbname)
            except Exception:
                logger.exception("Failed to drop test database %s", self._dbname)
            finally:
                self._dbname = None
                self._config = None

        _SharedContainer.release()

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


def create_test_env() -> PgvectorTestEnv:
    """Factory function for entry point registration."""
    return PgvectorTestEnv()