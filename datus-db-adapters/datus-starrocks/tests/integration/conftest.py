# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import logging
import os
from typing import Generator

import pytest

from datus_starrocks import StarRocksConfig, StarRocksConnector
from datus_starrocks.tpch_data import TPCH_DATA, TPCH_DDL, TPCH_TABLES

logger = logging.getLogger(__name__)


@pytest.fixture
def config() -> StarRocksConfig:
    """Create StarRocks configuration from environment or defaults for integration tests."""
    return StarRocksConfig(
        host=os.getenv("STARROCKS_HOST", "localhost"),
        port=int(os.getenv("STARROCKS_PORT", "9030")),
        username=os.getenv("STARROCKS_USER", "root"),
        password=os.getenv("STARROCKS_PASSWORD", ""),
        catalog=os.getenv("STARROCKS_CATALOG", "default_catalog"),
        database=os.getenv("STARROCKS_DATABASE", "test"),
    )


@pytest.fixture
def connector(config: StarRocksConfig) -> Generator[StarRocksConnector, None, None]:
    """Create and cleanup StarRocks connector for integration tests."""
    conn = None
    try:
        conn = StarRocksConnector(config)
        if not conn.test_connection():
            pytest.skip("Database connection test failed")
        yield conn
    except Exception as e:
        pytest.skip(f"Database not available: {e}")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                logger.warning("Failed to close connector during teardown", exc_info=True)


@pytest.fixture(scope="session")
def tpch_setup() -> Generator[StarRocksConnector, None, None]:
    """Session-scoped fixture: create TPC-H tables, insert data, yield connector, cleanup."""
    tpch_config = StarRocksConfig(
        host=os.getenv("STARROCKS_HOST", "localhost"),
        port=int(os.getenv("STARROCKS_PORT", "9030")),
        username=os.getenv("STARROCKS_USER", "root"),
        password=os.getenv("STARROCKS_PASSWORD", ""),
        catalog=os.getenv("STARROCKS_CATALOG", "default_catalog"),
        database=os.getenv("STARROCKS_DATABASE", "test"),
    )

    conn = None
    # Only skip on connection failures; DDL/DML errors should propagate and fail
    # the suite so they are not silently hidden.
    try:
        conn = StarRocksConnector(tpch_config)
        if not conn.test_connection():
            pytest.skip("Database connection test failed")
    except Exception as e:
        pytest.skip(f"Database not available: {e}")

    try:
        # Drop tables first for deterministic setup.
        # Errors here are real failures and must not be swallowed.
        for table in TPCH_TABLES:
            conn.execute_ddl(f"DROP TABLE IF EXISTS `{table}`")

        # Create tables
        for ddl in TPCH_DDL:
            conn.execute_ddl(ddl)

        # Insert data
        for data in TPCH_DATA:
            conn.execute_insert(data)

        yield conn
    finally:
        if conn is not None:
            try:
                for table in TPCH_TABLES:
                    conn.execute_ddl(f"DROP TABLE IF EXISTS `{table}`")
            except Exception:
                logger.warning("Failed to drop TPC-H tables during teardown", exc_info=True)
            try:
                conn.close()
            except Exception:
                logger.warning("Failed to close connection during teardown", exc_info=True)
