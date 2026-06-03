# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import os

import pytest

from datus_oracle import OracleConfig, OracleConnector


@pytest.fixture(scope="session")
def oracle_config():
    username = os.getenv("DATUS_ORACLE_USERNAME")
    password = os.getenv("DATUS_ORACLE_PASSWORD")
    service_name = os.getenv("DATUS_ORACLE_SERVICE_NAME", "FREEPDB1")
    if not username:
        pytest.skip("Set DATUS_ORACLE_USERNAME to run Oracle integration tests")
    return OracleConfig(
        host=os.getenv("DATUS_ORACLE_HOST", "127.0.0.1"),
        port=int(os.getenv("DATUS_ORACLE_PORT", "1521")),
        username=username,
        password=password or "",
        service_name=service_name,
        schema=os.getenv("DATUS_ORACLE_SCHEMA", username),
    )


@pytest.fixture
def oracle_connector(oracle_config):
    connector = OracleConnector(oracle_config)
    try:
        yield connector
    finally:
        connector.close()
