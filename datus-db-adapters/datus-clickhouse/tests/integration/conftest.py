# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import os
from typing import Generator

import pytest
from datus_clickhouse import ClickHouseConfig, ClickHouseConnector


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
        if not init_conn.test_connection():
            pytest.skip("Database connection test failed")
        if config.database:
            init_conn.execute_ddl(f"CREATE DATABASE IF NOT EXISTS `{config.database}`")
        init_conn.close()

        conn = ClickHouseConnector(config)
        yield conn
    except Exception as e:
        pytest.skip(f"Database not available: {e}")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
