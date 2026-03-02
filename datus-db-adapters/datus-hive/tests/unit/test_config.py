# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import pytest
from datus_hive import HiveConfig
from pydantic import ValidationError


def test_config_defaults_and_required_fields():
    config = HiveConfig(username="hue")

    assert config.host == "127.0.0.1"
    assert config.port == 10000
    assert config.database is None
    assert config.username == "hue"
    assert config.password == ""
    assert config.auth is None
    assert config.configuration == {}
    assert config.timeout_seconds == 30


def test_config_custom_values():
    config = HiveConfig(
        host="10.0.0.10",
        port=10009,
        database="test",
        username="hue",
        password="secret",
        auth="CUSTOM",
        configuration={"spark.app.name": "app"},
        timeout_seconds=60,
    )

    assert config.host == "10.0.0.10"
    assert config.port == 10009
    assert config.database == "test"
    assert config.username == "hue"
    assert config.password == "secret"
    assert config.auth == "CUSTOM"
    assert config.configuration == {"spark.app.name": "app"}
    assert config.timeout_seconds == 60


def test_config_requires_username():
    with pytest.raises(ValidationError):
        HiveConfig()


def test_config_forbids_extra_fields():
    with pytest.raises(ValidationError):
        HiveConfig(username="hue", extra_field="not_allowed")


def test_config_from_carrier_map_prefix():
    carrier_map = {
        "old_lackhouse.host": "10.85.24.173",
        "old_lackhouse.port": "10009",
        "old_lackhouse.database": "test",
        "old_lackhouse.username": "hue",
        "old_lackhouse.password": "pass",
        "old_lackhouse.auth": "CUSTOM",
        "old_lackhouse.configuration.spark.app.name": "datacenter_carrier",
        "old_lackhouse.configuration.spark.executor.instances": "1",
    }

    config = HiveConfig.from_config_map(carrier_map, prefix="old_lackhouse.")

    assert config.host == "10.85.24.173"
    assert config.port == 10009
    assert config.database == "test"
    assert config.username == "hue"
    assert config.password == "pass"
    assert config.auth == "CUSTOM"
    assert config.configuration == {
        "spark.app.name": "datacenter_carrier",
        "spark.executor.instances": "1",
    }
