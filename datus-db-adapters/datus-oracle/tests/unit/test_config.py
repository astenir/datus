# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import pytest
from pydantic import ValidationError

from datus_oracle import OracleConfig


def test_config_defaults_to_service_name_and_username_schema():
    config = OracleConfig(username="app_user")

    assert config.host == "127.0.0.1"
    assert config.port == 1521
    assert config.username == "app_user"
    assert config.password == ""
    assert config.service_name == "FREEPDB1"
    assert config.sid is None
    assert config.database == "FREEPDB1"
    assert config.schema_name == "APP_USER"
    assert config.oracle_client_lib_dir is None
    assert config.timeout_seconds == 30


def test_config_accepts_database_alias_for_service_name():
    config = OracleConfig(username="app", database="ORCLPDB1")

    assert config.service_name == "ORCLPDB1"
    assert config.database == "ORCLPDB1"


def test_config_prefers_explicit_service_name_over_database_alias():
    config = OracleConfig(username="app", database="ignored", service_name="SALES")

    assert config.service_name == "SALES"
    assert config.database == "SALES"


def test_config_accepts_schema_alias():
    config = OracleConfig(username="app", schema="reporting")

    assert config.schema_name == "REPORTING"


def test_config_forbids_service_name_and_sid_together():
    with pytest.raises(ValidationError) as exc_info:
        OracleConfig(username="app", service_name="FREEPDB1", sid="XE")

    assert any(error["type"] == "value_error" for error in exc_info.value.errors())


def test_config_forbids_extra_fields():
    with pytest.raises(ValidationError) as exc_info:
        OracleConfig(username="app", extra_field="nope")

    assert any(error["type"] == "extra_forbidden" for error in exc_info.value.errors())


def test_config_accepts_oracle_client_lib_dir_alias(tmp_path):
    config = OracleConfig(username="app", thick_mode=True, lib_dir=str(tmp_path))

    assert config.oracle_client_lib_dir == str(tmp_path)


def test_config_rejects_oracle_client_lib_dir_without_thick_mode(tmp_path):
    with pytest.raises(ValidationError, match="oracle_client_lib_dir requires thick_mode=true"):
        OracleConfig(username="app", oracle_client_lib_dir=str(tmp_path))


def test_config_rejects_relative_oracle_client_lib_dir():
    with pytest.raises(ValidationError, match="oracle_client_lib_dir must be an absolute path"):
        OracleConfig(username="app", thick_mode=True, oracle_client_lib_dir="instantclient")


def test_config_rejects_missing_oracle_client_lib_dir(tmp_path):
    missing = tmp_path / "missing"

    with pytest.raises(ValidationError, match="oracle_client_lib_dir is not a directory"):
        OracleConfig(username="app", thick_mode=True, oracle_client_lib_dir=str(missing))
