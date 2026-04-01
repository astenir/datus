# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import pytest
from pydantic import ValidationError

from datus_redshift import RedshiftConfig


@pytest.mark.acceptance
def test_config_with_all_required_fields():
    """Test config initialization with all required fields."""
    config = RedshiftConfig(
        host="my-cluster.us-west-2.redshift.amazonaws.com",
        username="testuser",
        password="testpass",
    )

    assert config.host == "my-cluster.us-west-2.redshift.amazonaws.com"
    assert config.username == "testuser"
    assert config.password == "testpass"


@pytest.mark.acceptance
def test_config_default_values():
    """Test that default values are set correctly."""
    config = RedshiftConfig(
        host="cluster.example.com", username="user", password="pass"
    )

    assert config.port == 5439
    assert config.database is None
    assert config.schema_name is None
    assert config.timeout_seconds == 30
    assert config.ssl is True
    assert config.iam is False
    assert config.cluster_identifier is None
    assert config.region is None
    assert config.access_key_id is None
    assert config.secret_access_key is None


@pytest.mark.acceptance
def test_config_with_custom_values():
    """Test config with all custom values."""
    config = RedshiftConfig(
        host="my-cluster.us-west-2.redshift.amazonaws.com",
        username="admin",
        password="secret123",
        port=5440,
        database="testdb",
        schema="testschema",
        timeout_seconds=60,
        ssl=False,
        iam=True,
        cluster_identifier="my-cluster",
        region="us-west-2",
        access_key_id="AKIAIOSFODNN7EXAMPLE",
        secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    )

    assert config.host == "my-cluster.us-west-2.redshift.amazonaws.com"
    assert config.username == "admin"
    assert config.password == "secret123"
    assert config.port == 5440
    assert config.database == "testdb"
    assert config.schema_name == "testschema"
    assert config.timeout_seconds == 60
    assert config.ssl is False
    assert config.iam is True
    assert config.cluster_identifier == "my-cluster"
    assert config.region == "us-west-2"
    assert config.access_key_id == "AKIAIOSFODNN7EXAMPLE"
    assert config.secret_access_key == "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"


def test_config_missing_host():
    """Test that validation fails when host is missing."""
    with pytest.raises(ValidationError) as exc_info:
        RedshiftConfig(username="user", password="pass")

    errors = exc_info.value.errors()
    assert any(error["loc"] == ("host",) for error in errors)


def test_config_missing_username():
    """Test that validation fails when username is missing."""
    with pytest.raises(ValidationError) as exc_info:
        RedshiftConfig(host="cluster.example.com", password="pass")

    errors = exc_info.value.errors()
    assert any(error["loc"] == ("username",) for error in errors)


@pytest.mark.acceptance
def test_config_iam_without_password():
    """Test that IAM auth works without password."""
    config = RedshiftConfig(
        host="cluster.example.com",
        username="user",
        iam=True,
        cluster_identifier="my-cluster",
        region="us-west-2",
    )

    assert config.iam is True
    assert config.password is None


def test_config_no_iam_no_password_raises():
    """Test that validation fails when iam=False and no password."""
    with pytest.raises(ValueError, match="Password is required"):
        RedshiftConfig(host="cluster.example.com", username="user")


def test_config_invalid_port_type():
    """Test that validation fails for invalid port type."""
    with pytest.raises(ValidationError) as exc_info:
        RedshiftConfig(
            host="cluster.example.com", username="user", password="pass", port="invalid"
        )

    errors = exc_info.value.errors()
    assert any(error["loc"] == ("port",) for error in errors)


def test_config_invalid_timeout_type():
    """Test that validation fails for invalid timeout type."""
    with pytest.raises(ValidationError) as exc_info:
        RedshiftConfig(
            host="cluster.example.com",
            username="user",
            password="pass",
            timeout_seconds="invalid",
        )

    errors = exc_info.value.errors()
    assert any(error["loc"] == ("timeout_seconds",) for error in errors)


@pytest.mark.acceptance
def test_config_forbids_extra_fields():
    """Test that extra fields are not allowed."""
    with pytest.raises(ValidationError) as exc_info:
        RedshiftConfig(
            host="cluster.example.com",
            username="user",
            password="pass",
            extra_field="not_allowed",
        )

    errors = exc_info.value.errors()
    assert any(error["type"] == "extra_forbidden" for error in errors)


def test_config_schema_alias():
    """Test that 'schema' alias maps to schema_name."""
    config = RedshiftConfig(
        host="cluster.example.com", username="user", password="pass", schema="my_schema"
    )

    assert config.schema_name == "my_schema"


def test_config_from_dict():
    """Test creating config from dictionary."""
    config_dict = {
        "host": "cluster.example.com",
        "username": "root",
        "password": "pass123",
        "database": "testdb",
        "port": 5439,
    }

    config = RedshiftConfig(**config_dict)

    assert config.host == "cluster.example.com"
    assert config.username == "root"
    assert config.password == "pass123"
    assert config.database == "testdb"
    assert config.port == 5439


def test_config_to_dict():
    """Test converting config to dictionary."""
    config = RedshiftConfig(
        host="cluster.example.com",
        username="root",
        password="pass123",
        database="testdb",
    )

    config_dict = config.model_dump()

    assert config_dict["host"] == "cluster.example.com"
    assert config_dict["username"] == "root"
    assert config_dict["password"] == "pass123"
    assert config_dict["database"] == "testdb"
    assert config_dict["port"] == 5439
    assert config_dict["timeout_seconds"] == 30


@pytest.mark.acceptance
def test_config_special_characters_in_password():
    """Test config with special characters in password."""
    special_password = "p@ss!w0rd#$%^&*()"
    config = RedshiftConfig(
        host="cluster.example.com", username="user", password=special_password
    )

    assert config.password == special_password


def test_config_special_characters_in_database():
    """Test config with special characters in database name."""
    special_db = "test-db_123"
    config = RedshiftConfig(
        host="cluster.example.com",
        username="user",
        password="pass",
        database=special_db,
    )

    assert config.database == special_db


def test_config_unicode_in_username():
    """Test config with unicode characters in username."""
    unicode_user = "用户名"
    config = RedshiftConfig(
        host="cluster.example.com", username=unicode_user, password="pass"
    )

    assert config.username == unicode_user


def test_config_none_database():
    """Test config with None as database."""
    config = RedshiftConfig(
        host="cluster.example.com", username="user", password="pass", database=None
    )

    assert config.database is None


def test_config_large_port_number():
    """Test config with large port number."""
    config = RedshiftConfig(
        host="cluster.example.com", username="user", password="pass", port=65535
    )

    assert config.port == 65535


def test_config_zero_timeout():
    """Test that zero timeout is allowed."""
    config = RedshiftConfig(
        host="cluster.example.com", username="user", password="pass", timeout_seconds=0
    )

    assert config.timeout_seconds == 0


def test_config_ssl_disabled():
    """Test config with SSL disabled."""
    config = RedshiftConfig(
        host="cluster.example.com", username="user", password="pass", ssl=False
    )

    assert config.ssl is False
