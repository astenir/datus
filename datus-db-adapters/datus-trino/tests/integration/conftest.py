# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import os
from typing import Generator

import pytest
from datus_trino import TrinoConfig, TrinoConnector


@pytest.fixture
def config() -> TrinoConfig:
    """Create Trino configuration from environment or defaults for integration tests."""
    return TrinoConfig(
        host=os.getenv("TRINO_HOST", "localhost"),
        port=int(os.getenv("TRINO_PORT", "8080")),
        username=os.getenv("TRINO_USER", "trino"),
        password=os.getenv("TRINO_PASSWORD", ""),
        catalog=os.getenv("TRINO_CATALOG", "memory"),
        schema_name=os.getenv("TRINO_SCHEMA", "default"),
        http_scheme=os.getenv("TRINO_HTTP_SCHEME", "http"),
    )


@pytest.fixture
def connector(config: TrinoConfig) -> Generator[TrinoConnector, None, None]:
    """Create and cleanup Trino connector for integration tests."""
    conn = None
    try:
        conn = TrinoConnector(config)
        if not conn.test_connection():
            pytest.skip("Database connection test failed")
    except Exception as e:
        pytest.skip(f"Database not available: {e}")
    else:
        yield conn
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


@pytest.fixture
def tpch_connector(config: TrinoConfig) -> Generator[TrinoConnector, None, None]:
    """Create connector pointing to tpch catalog for TPC-H tests."""
    tpch_config = TrinoConfig(
        host=config.host,
        port=config.port,
        username=config.username,
        password=config.password,
        catalog="tpch",
        schema_name="tiny",
        http_scheme=config.http_scheme,
        verify=config.verify,
        timeout_seconds=config.timeout_seconds,
    )
    conn = None
    try:
        conn = TrinoConnector(tpch_config)
        if not conn.test_connection():
            pytest.skip("TPC-H connection test failed")
    except Exception as e:
        pytest.skip(f"TPC-H catalog not available: {e}")
    else:
        yield conn
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
