# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import os

import pytest

from datus_clickhouse import ClickHouseConfig, ClickHouseConnector


@pytest.mark.integration
@pytest.mark.acceptance
def test_connection_with_config_object(config: ClickHouseConfig):
    """Test connection using config object."""
    conn = ClickHouseConnector(config)
    assert conn.test_connection()
    conn.close()


@pytest.mark.integration
def test_connection_with_dict():
    """Test connection using dict config."""
    conn = ClickHouseConnector(
        {
            "host": os.getenv("CLICKHOUSE_HOST", "localhost"),
            "port": int(os.getenv("CLICKHOUSE_PORT", "8123")),
            "username": os.getenv("CLICKHOUSE_USER", "default_user"),
            "password": os.getenv("CLICKHOUSE_PASSWORD", "default_test"),
        }
    )
    assert conn.test_connection()
    conn.close()
