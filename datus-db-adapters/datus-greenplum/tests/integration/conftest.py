# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import os
from typing import Generator

import pytest

from datus_greenplum import GreenplumConfig, GreenplumConnector
from datus_greenplum.tpch_data import TPCH_DATA, TPCH_DDL, TPCH_TABLES


@pytest.fixture
def config() -> GreenplumConfig:
    """Create Greenplum configuration for integration tests from environment or defaults."""
    return GreenplumConfig(
        host=os.getenv("GREENPLUM_HOST", "localhost"),
        port=int(os.getenv("GREENPLUM_PORT", "15432")),
        username=os.getenv("GREENPLUM_USER", "gpadmin"),
        password=os.getenv("GREENPLUM_PASSWORD", "pivotal"),
        database=os.getenv("GREENPLUM_DATABASE", "test"),
        schema_name=os.getenv("GREENPLUM_SCHEMA", "public"),
    )


@pytest.fixture
def connector(config: GreenplumConfig) -> Generator[GreenplumConnector, None, None]:
    """Create and cleanup Greenplum connector for integration tests."""
    conn = None
    try:
        conn = GreenplumConnector(config)
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
def tpch_setup() -> Generator[GreenplumConnector, None, None]:
    """Session-scoped fixture: create TPC-H tables, insert data, yield connector, cleanup."""
    config = GreenplumConfig(
        host=os.getenv("GREENPLUM_HOST", "localhost"),
        port=int(os.getenv("GREENPLUM_PORT", "15432")),
        username=os.getenv("GREENPLUM_USER", "gpadmin"),
        password=os.getenv("GREENPLUM_PASSWORD", "pivotal"),
        database=os.getenv("GREENPLUM_DATABASE", "test"),
        schema_name=os.getenv("GREENPLUM_SCHEMA", "public"),
    )

    conn = None
    try:
        conn = GreenplumConnector(config)
        if not conn.test_connection():
            pytest.skip("Database connection test failed for TPC-H setup")

        # Drop tables first for deterministic setup
        for table in TPCH_TABLES:
            conn.execute_ddl(f'DROP TABLE IF EXISTS "{table}" CASCADE')

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
        # Cleanup: drop all TPC-H tables
        if conn is not None:
            for table in TPCH_TABLES:
                try:
                    conn.execute_ddl(f'DROP TABLE IF EXISTS "{table}" CASCADE')
                except Exception:
                    pass
            try:
                conn.close()
            except Exception:
                pass
