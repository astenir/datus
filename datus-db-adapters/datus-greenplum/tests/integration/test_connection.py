# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import os

import pytest

from datus_greenplum import GreenplumConfig, GreenplumConnector


@pytest.mark.integration
@pytest.mark.acceptance
def test_connection_with_config_object(config: GreenplumConfig):
    """Test connection using config object."""
    conn = GreenplumConnector(config)
    assert conn.test_connection()
    conn.close()


@pytest.mark.integration
def test_connection_with_dict():
    """Test connection using dict config."""
    conn = GreenplumConnector(
        {
            "host": os.getenv("GREENPLUM_HOST", "localhost"),
            "port": int(os.getenv("GREENPLUM_PORT", "15432")),
            "username": os.getenv("GREENPLUM_USER", "gpadmin"),
            "password": os.getenv("GREENPLUM_PASSWORD", "pivotal"),
        }
    )
    assert conn.test_connection()
    conn.close()
