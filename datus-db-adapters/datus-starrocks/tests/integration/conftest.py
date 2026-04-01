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

HIVE_CATALOG_NAME = "hive_test_catalog"


@pytest.fixture(scope="session")
def hive_catalog_setup() -> Generator[str, None, None]:
    """Session-scoped fixture: create a Hive external catalog in StarRocks for catalog tests."""
    metastore_uri = os.getenv("HIVE_METASTORE_URI", "thrift://host.docker.internal:9083")
    sr_config = StarRocksConfig(
        host=os.getenv("STARROCKS_HOST", "localhost"),
        port=int(os.getenv("STARROCKS_PORT", "9030")),
        username=os.getenv("STARROCKS_USER", "root"),
        password=os.getenv("STARROCKS_PASSWORD", ""),
        catalog=os.getenv("STARROCKS_CATALOG", "default_catalog"),
        database="information_schema",
    )

    conn = None
    try:
        conn = StarRocksConnector(sr_config)
        if not conn.test_connection():
            pytest.skip("StarRocks not available for Hive catalog setup")
    except Exception as e:
        pytest.skip(f"StarRocks not available: {e}")

    try:
        conn.execute_ddl(f"DROP CATALOG IF EXISTS `{HIVE_CATALOG_NAME}`")
        conn.execute_ddl(
            f"""
            CREATE EXTERNAL CATALOG `{HIVE_CATALOG_NAME}`
            PROPERTIES (
                "type" = "hive",
                "hive.metastore.uris" = "{metastore_uri}"
            )
            """
        )
        yield HIVE_CATALOG_NAME
    except Exception as e:
        pytest.skip(f"Failed to create Hive catalog: {e}")
    finally:
        if conn is not None:
            try:
                conn.execute_ddl(f"DROP CATALOG IF EXISTS `{HIVE_CATALOG_NAME}`")
            except Exception:
                logger.warning("Failed to drop Hive catalog during teardown", exc_info=True)
            try:
                conn.close()
            except Exception:
                pass


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
        # Ensure test database exists (connect without database first)
        init_config = StarRocksConfig(
            host=config.host,
            port=config.port,
            username=config.username,
            password=config.password,
            catalog=config.catalog,
            database="information_schema",
        )
        init_conn = StarRocksConnector(init_config)
        try:
            if not init_conn.test_connection():
                pytest.skip("Database connection test failed")
            if config.database:
                init_conn.execute_ddl(f"CREATE DATABASE IF NOT EXISTS `{config.database}`")
        finally:
            init_conn.close()

        conn = StarRocksConnector(config)
        yield conn
    except Exception as e:
        pytest.skip(f"Database not available: {e}")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                logger.warning(
                    "Failed to close connector during teardown", exc_info=True
                )


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
        # Ensure test database exists
        init_config = StarRocksConfig(
            host=tpch_config.host,
            port=tpch_config.port,
            username=tpch_config.username,
            password=tpch_config.password,
            catalog=tpch_config.catalog,
            database="information_schema",
        )
        init_conn = StarRocksConnector(init_config)
        try:
            if not init_conn.test_connection():
                pytest.skip("Database connection test failed")
            if tpch_config.database:
                init_conn.execute_ddl(f"CREATE DATABASE IF NOT EXISTS `{tpch_config.database}`")
        finally:
            init_conn.close()

        conn = StarRocksConnector(tpch_config)
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
                logger.warning(
                    "Failed to drop TPC-H tables during teardown", exc_info=True
                )
            try:
                conn.close()
            except Exception:
                logger.warning(
                    "Failed to close connection during teardown", exc_info=True
                )
