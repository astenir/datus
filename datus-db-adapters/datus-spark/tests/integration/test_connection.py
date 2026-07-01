# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import os

import pytest

from datus_spark import SparkConfig, SparkConnector

# ==================== Connection Tests ====================


@pytest.mark.integration
@pytest.mark.acceptance
def test_connection_with_config_object(config: SparkConfig):
    """Test connection using SparkConfig object."""
    conn = SparkConnector(config)
    assert conn.test_connection()
    conn.close()


@pytest.mark.integration
@pytest.mark.acceptance
def test_connection_with_dict():
    """Test connection using dict config."""
    conn = SparkConnector(
        {
            "host": os.getenv("SPARK_HOST", "localhost"),
            "port": int(os.getenv("SPARK_PORT", "10000")),
            "username": os.getenv("SPARK_USER", "spark"),
            "password": os.getenv("SPARK_PASSWORD", ""),
        }
    )
    assert conn.test_connection()
    conn.close()


@pytest.mark.integration
@pytest.mark.acceptance
def test_context_manager(config: SparkConfig):
    """Test connector as context manager."""
    with SparkConnector(config) as conn:
        assert conn.test_connection()


@pytest.mark.integration
def test_test_connection_method(connector: SparkConnector):
    """Test the test_connection method."""
    result = connector.test_connection()
    assert result is True


@pytest.mark.integration
def test_connection_cleanup(config: SparkConfig):
    """Test connection cleanup."""
    conn = SparkConnector(config)

    try:
        conn.connect()
        assert conn.test_connection()
    finally:
        conn.close()

    # Should not raise exception on re-close
    conn.close()
