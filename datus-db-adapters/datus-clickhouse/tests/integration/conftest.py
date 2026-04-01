# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import os
from typing import Generator

import pytest

from datus_clickhouse import ClickHouseConfig, ClickHouseConnector
from datus_clickhouse.tpch_data import TPCH_DATA, TPCH_DDL, TPCH_TABLES


@pytest.fixture
def config() -> ClickHouseConfig:
    """Create ClickHouse configuration from environment or defaults."""
    return ClickHouseConfig(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
        username=os.getenv("CLICKHOUSE_USER", "default_user"),
        password=os.getenv("CLICKHOUSE_PASSWORD", "default_test"),
        database=os.getenv("CLICKHOUSE_DATABASE", "default_test"),
    )


@pytest.fixture
def connector(config: ClickHouseConfig) -> Generator[ClickHouseConnector, None, None]:
    """Create and cleanup ClickHouse connector for integration tests."""
    conn = None
    try:
        # Connect without database first to ensure test database exists
        init_config = ClickHouseConfig(
            host=config.host,
            port=config.port,
            username=config.username,
            password=config.password,
            database=None,
        )
        init_conn = ClickHouseConnector(init_config)
        try:
            if not init_conn.test_connection():
                pytest.skip("Database connection test failed")
            if config.database:
                init_conn.execute_ddl(
                    f"CREATE DATABASE IF NOT EXISTS `{config.database}`"
                )
        finally:
            init_conn.close()

        conn = ClickHouseConnector(config)
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


@pytest.fixture(scope="session")
def tpch_setup() -> Generator[ClickHouseConnector, None, None]:
    """Session-scoped fixture: create TPC-H tables, insert data, yield connector, cleanup."""
    config = ClickHouseConfig(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
        username=os.getenv("CLICKHOUSE_USER", "default_user"),
        password=os.getenv("CLICKHOUSE_PASSWORD", "default_test"),
        database=os.getenv("CLICKHOUSE_DATABASE", "default_test"),
    )

    conn = None
    try:
        # Ensure database exists
        init_config = ClickHouseConfig(
            host=config.host,
            port=config.port,
            username=config.username,
            password=config.password,
            database=None,
        )
        init_conn = ClickHouseConnector(init_config)
        try:
            if not init_conn.test_connection():
                pytest.skip("Database connection test failed")
            if config.database:
                init_conn.execute_ddl(
                    f"CREATE DATABASE IF NOT EXISTS `{config.database}`"
                )
        finally:
            init_conn.close()

        conn = ClickHouseConnector(config)

        # Drop tables first for deterministic setup
        for table in TPCH_TABLES:
            conn.execute_ddl(f"DROP TABLE IF EXISTS `{table}`")

        # Create tables
        for ddl in TPCH_DDL:
            conn.execute_ddl(ddl)

        # Insert data
        for data in TPCH_DATA:
            conn.execute_insert(data)

    except Exception as e:
        pytest.skip(f"TPC-H setup failed: {e}")
    else:
        yield conn
    finally:
        if conn is not None:
            try:
                for table in TPCH_TABLES:
                    conn.execute_ddl(f"DROP TABLE IF EXISTS `{table}`")
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass
