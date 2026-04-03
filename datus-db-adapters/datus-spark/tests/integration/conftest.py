# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import os
from typing import Generator

import pytest

from datus_spark import SparkConfig, SparkConnector
from datus_spark.tpch_data import TPCH_DATA, TPCH_DDL, TPCH_TABLES


@pytest.fixture
def config() -> SparkConfig:
    """Create Spark configuration from environment or defaults for integration tests."""
    return SparkConfig(
        host=os.getenv("SPARK_HOST", "localhost"),
        port=int(os.getenv("SPARK_PORT", "10000")),
        username=os.getenv("SPARK_USER", "spark"),
        password=os.getenv("SPARK_PASSWORD", ""),
        database=os.getenv("SPARK_DATABASE", "default"),
        auth_mechanism=os.getenv("SPARK_AUTH_MECHANISM", "NONE"),
    )


@pytest.fixture
def connector(config: SparkConfig) -> Generator[SparkConnector, None, None]:
    """Create and cleanup Spark connector for integration tests."""
    conn = None
    try:
        conn = SparkConnector(config)
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


@pytest.fixture(scope="session")
def tpch_setup():
    """Create TPC-H tables with sample data for integration tests (session-scoped)."""
    config = SparkConfig(
        host=os.getenv("SPARK_HOST", "localhost"),
        port=int(os.getenv("SPARK_PORT", "10000")),
        username=os.getenv("SPARK_USER", "spark"),
        password=os.getenv("SPARK_PASSWORD", ""),
        database=os.getenv("SPARK_DATABASE", "default"),
        auth_mechanism=os.getenv("SPARK_AUTH_MECHANISM", "NONE"),
    )
    conn = None
    try:
        conn = SparkConnector(config)
        if not conn.test_connection():
            pytest.skip("Database connection test failed for TPC-H setup")

        # Drop tables first for deterministic setup
        for table in TPCH_TABLES:
            conn.execute_ddl(f"DROP TABLE IF EXISTS `default`.`{table}`")

        # Create tables and insert data
        for ddl in TPCH_DDL:
            conn.execute_ddl(ddl)
        for data in TPCH_DATA:
            conn.execute_ddl(data)
    except Exception as e:
        pytest.skip(f"TPC-H setup failed: {e}")
    else:
        yield conn
    finally:
        # Cleanup: drop all TPC-H tables
        if conn is not None:
            for table in TPCH_TABLES:
                try:
                    conn.execute_ddl(f"DROP TABLE IF EXISTS `default`.`{table}`")
                except Exception:
                    pass
            try:
                conn.close()
            except Exception:
                pass
