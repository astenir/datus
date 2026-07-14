# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import pytest
from pydantic import ValidationError

from datus_oceanbase_oracle import OceanBaseOracleConfig


class TestSchemaNormalization:
    def test_config_accepts_schema_alias_and_uppercases_default_schema(self):
        config = OceanBaseOracleConfig(
            username="app@oracle_tenant#obcluster",
            password="secret",
            schema="app",
            jar_path="/opt/oceanbase-client.jar",
        )
        assert config.schema_name == "APP"

    def test_config_defaults_schema_to_base_username(self):
        config = OceanBaseOracleConfig(
            username="app@oracle_tenant#obcluster",
            password="secret",
            jar_path="/opt/oceanbase-client.jar",
        )
        assert config.schema_name == "APP"

    def test_schema_name_takes_priority_over_schema_alias(self):
        config = OceanBaseOracleConfig(
            username="app@oracle_tenant#obcluster",
            password="secret",
            schema="old_name",
            schema_name="new_name",
            jar_path="/opt/oceanbase-client.jar",
        )
        assert config.schema_name == "NEW_NAME"


class TestConnectionMode:
    def test_default_mode_is_odp(self):
        config = OceanBaseOracleConfig(
            username="app@oracle_tenant#obcluster",
            jar_path="/opt/oceanbase-client.jar",
        )
        assert config.connection_mode == "odp"
        assert config.port == 2883

    def test_direct_mode_defaults_port_to_2881(self):
        config = OceanBaseOracleConfig(
            username="app@oracle_tenant",
            connection_mode="direct",
            jar_path="/opt/oceanbase-client.jar",
        )
        assert config.port == 2881

    def test_direct_mode_with_explicit_port(self):
        config = OceanBaseOracleConfig(
            username="app@oracle_tenant",
            connection_mode="direct",
            port=2882,
            jar_path="/opt/oceanbase-client.jar",
        )
        assert config.port == 2882

    def test_invalid_mode_rejected(self):
        with pytest.raises(ValidationError):
            OceanBaseOracleConfig(
                username="app@oracle_tenant#obcluster",
                connection_mode="invalid",
                jar_path="/opt/oceanbase-client.jar",
            )


class TestSSL:
    def test_default_ssl_is_false(self):
        config = OceanBaseOracleConfig(
            username="app@oracle_tenant#obcluster",
            jar_path="/opt/oceanbase-client.jar",
        )
        assert config.use_ssl is False

    def test_ssl_can_be_enabled(self):
        config = OceanBaseOracleConfig(
            username="app@oracle_tenant#obcluster",
            use_ssl=True,
            jar_path="/opt/oceanbase-client.jar",
        )
        assert config.use_ssl is True


class TestTimeouts:
    def test_default_timeouts(self):
        config = OceanBaseOracleConfig(
            username="app@oracle_tenant#obcluster",
            jar_path="/opt/oceanbase-client.jar",
        )
        assert config.connect_timeout_seconds == 30
        assert config.query_timeout_seconds == 30
        assert config.timeout_seconds == 30

    def test_custom_timeouts(self):
        config = OceanBaseOracleConfig(
            username="app@oracle_tenant#obcluster",
            connect_timeout_seconds=10,
            query_timeout_seconds=60,
            jar_path="/opt/oceanbase-client.jar",
        )
        assert config.connect_timeout_seconds == 10
        assert config.query_timeout_seconds == 60

    def test_timeout_must_be_positive(self):
        with pytest.raises(ValidationError):
            OceanBaseOracleConfig(
                username="app@oracle_tenant#obcluster",
                connect_timeout_seconds=0,
                jar_path="/opt/oceanbase-client.jar",
            )


class TestPoolConfig:
    def test_default_pool_settings(self):
        config = OceanBaseOracleConfig(
            username="app@oracle_tenant#obcluster",
            jar_path="/opt/oceanbase-client.jar",
        )
        assert config.pool_maxconnections == 10
        assert config.pool_mincached == 2
        assert config.pool_maxcached == 5
        assert config.pool_blocking is True
        assert config.pool_ping_timeout_seconds == 5

    def test_custom_pool_settings(self):
        config = OceanBaseOracleConfig(
            username="app@oracle_tenant#obcluster",
            pool_maxconnections=20,
            pool_mincached=5,
            pool_maxcached=10,
            pool_blocking=False,
            pool_ping_timeout_seconds=3,
            jar_path="/opt/oceanbase-client.jar",
        )
        assert config.pool_maxconnections == 20
        assert config.pool_mincached == 5
        assert config.pool_maxcached == 10
        assert config.pool_blocking is False
        assert config.pool_ping_timeout_seconds == 3

    def test_pool_maxconnections_must_be_at_least_1(self):
        with pytest.raises(ValidationError):
            OceanBaseOracleConfig(
                username="app@oracle_tenant#obcluster",
                pool_maxconnections=0,
                jar_path="/opt/oceanbase-client.jar",
            )

    def test_pool_ping_timeout_must_be_positive(self):
        with pytest.raises(ValidationError):
            OceanBaseOracleConfig(
                username="app@oracle_tenant#obcluster",
                pool_ping_timeout_seconds=0,
                jar_path="/opt/oceanbase-client.jar",
            )


class TestExtraJdbcParams:
    def test_default_empty_params(self):
        config = OceanBaseOracleConfig(
            username="app@oracle_tenant#obcluster",
            jar_path="/opt/oceanbase-client.jar",
        )
        assert config.extra_jdbc_params == {}

    def test_custom_params(self):
        config = OceanBaseOracleConfig(
            username="app@oracle_tenant#obcluster",
            extra_jdbc_params={"useUnicode": "true", "characterEncoding": "utf-8"},
            jar_path="/opt/oceanbase-client.jar",
        )
        assert config.extra_jdbc_params["useUnicode"] == "true"


class TestExtraForbid:
    def test_rejects_unknown_fields(self):
        with pytest.raises(ValidationError):
            OceanBaseOracleConfig(
                username="app@oracle_tenant#obcluster",
                jar_path="/opt/oceanbase-client.jar",
                unknown_field="should_fail",
            )


class TestFromDict:
    def test_create_from_dict(self):
        data = {
            "username": "app@oracle_tenant#obcluster",
            "password": "secret",
            "schema": "my_schema",
            "jar_path": "/opt/oceanbase-client.jar",
        }
        config = OceanBaseOracleConfig(**data)
        assert config.schema_name == "MY_SCHEMA"
