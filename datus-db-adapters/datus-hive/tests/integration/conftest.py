# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import json
import os
from typing import Generator

import pytest

from datus_hive import HiveConfig, HiveConnector
from datus_hive.tpch_data import TPCH_DATA, TPCH_DDL, TPCH_TABLES


def _load_configuration() -> dict:
    raw = os.getenv("HIVE_CONFIGURATION_JSON")
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        pytest.skip(f"Invalid HIVE_CONFIGURATION_JSON: {exc}")
    if not isinstance(data, dict):
        pytest.skip("HIVE_CONFIGURATION_JSON must be a JSON object")
    return data


def _build_hive_config() -> HiveConfig:
    """Build HiveConfig from environment variables."""
    auth = os.getenv("HIVE_AUTH")
    return HiveConfig(
        host=os.getenv("HIVE_HOST", "localhost"),
        port=int(os.getenv("HIVE_PORT", "10000")),
        database=os.getenv("HIVE_DATABASE", "default"),
        username=os.getenv("HIVE_USERNAME", "hive"),
        password=os.getenv("HIVE_PASSWORD", ""),
        auth=auth if auth else None,
        configuration=_load_configuration(),
    )


@pytest.fixture
def config() -> HiveConfig:
    """Create Hive configuration for integration tests from environment or defaults."""
    return _build_hive_config()


@pytest.fixture
def connector(config: HiveConfig) -> Generator[HiveConnector, None, None]:
    """Create and cleanup Hive connector for integration tests."""
    conn = None
    try:
        conn = HiveConnector(config)
        if not conn.test_connection():
            pytest.skip("Database connection test failed")
    except Exception as exc:
        pytest.skip(f"Database not available: {exc}")
    try:
        yield conn
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


@pytest.fixture(scope="session")
def tpch_setup() -> Generator[HiveConnector, None, None]:
    """Session-scoped fixture: create TPC-H tables, insert data, yield connector, cleanup."""
    hive_config = _build_hive_config()

    conn = None
    try:
        conn = HiveConnector(hive_config)
        if not conn.test_connection():
            pytest.skip("Database connection test failed")

        # Drop existing tables first to ensure clean state
        for table in TPCH_TABLES:
            conn.execute_ddl(f"DROP TABLE IF EXISTS {table}")

        # Create tables
        for ddl in TPCH_DDL:
            conn.execute_ddl(ddl)

        # Insert data
        for data in TPCH_DATA:
            conn.execute_insert(data)

    except Exception as exc:
        pytest.skip(f"TPC-H setup failed: {exc}")
    else:
        yield conn
    finally:
        if conn is not None:
            try:
                for table in TPCH_TABLES:
                    conn.execute_ddl(f"DROP TABLE IF EXISTS {table}")
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass
