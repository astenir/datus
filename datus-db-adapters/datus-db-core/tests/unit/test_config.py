# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Unit tests for config module."""

import pytest
from datus_db_core.config import ConnectionConfig
from pydantic import ValidationError


class TestConnectionConfig:
    def test_default_timeout(self):
        config = ConnectionConfig()
        assert config.timeout_seconds == 30

    def test_custom_timeout(self):
        config = ConnectionConfig(timeout_seconds=60)
        assert config.timeout_seconds == 60

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            ConnectionConfig(timeout_seconds=30, unknown_field="value")

    def test_subclass_inherits_config(self):
        class MyConfig(ConnectionConfig):
            host: str = "localhost"
            port: int = 5432

        config = MyConfig(host="db.example.com", port=3306)
        assert config.host == "db.example.com"
        assert config.port == 3306
        assert config.timeout_seconds == 30
