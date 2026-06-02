# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Pure-Pydantic SnowflakeConfig tests — no live Snowflake required."""

from unittest.mock import patch

import pytest

from datus_snowflake import SnowflakeConfig, SnowflakeConnector


def test_config_requires_password_or_key():
    with pytest.raises(ValueError, match="exactly one of `password` or `private_key_file`"):
        SnowflakeConfig(account="a", username="u", warehouse="w")


def test_config_rejects_both_password_and_key(tmp_path):
    key_file = tmp_path / "key.p8"
    key_file.write_text("dummy")
    with pytest.raises(ValueError, match="exactly one of `password` or `private_key_file`"):
        SnowflakeConfig(
            account="a",
            username="u",
            warehouse="w",
            password="p",
            private_key_file=str(key_file),
        )


def test_config_accepts_password_only():
    cfg = SnowflakeConfig(account="a", username="u", warehouse="w", password="p")
    assert cfg.password.get_secret_value() == "p"
    assert cfg.private_key_file is None


def test_config_accepts_key_pair_only(tmp_path):
    key_file = tmp_path / "key.p8"
    key_file.write_text("dummy")
    cfg = SnowflakeConfig(account="a", username="u", warehouse="w", private_key_file=str(key_file))
    assert cfg.private_key_file == str(key_file)
    assert cfg.password is None


def test_config_masks_secret_repr():
    """Secrets must not leak through repr/str of the config object."""
    cfg = SnowflakeConfig(account="a", username="u", warehouse="w", password="topsecret")
    assert "topsecret" not in repr(cfg)
    assert "topsecret" not in str(cfg)


def test_config_coerces_numeric_credentials(tmp_path):
    """YAML parses unquoted numeric secrets as int; they must coerce to str."""
    cfg_pwd = SnowflakeConfig(account="a", username="u", warehouse="w", password=1234)
    assert cfg_pwd.password.get_secret_value() == "1234"

    key_file = tmp_path / "key.p8"
    key_file.write_text("dummy")
    cfg_key = SnowflakeConfig(
        account="a", username="u", warehouse="w", private_key_file=str(key_file), private_key_file_pwd=5678
    )
    assert cfg_key.private_key_file_pwd.get_secret_value() == "5678"


def test_connector_passes_role_to_snowflake_connect():
    cfg = SnowflakeConfig(
        account="a",
        username="u",
        warehouse="w",
        password="p",
        role="ANALYST",
    )

    with patch("datus_snowflake.connector.Connect") as connect:
        SnowflakeConnector(cfg)

    assert connect.call_args.kwargs["role"] == "ANALYST"


def test_connector_uses_password_auth_kwargs():
    cfg = SnowflakeConfig(account="a", username="u", warehouse="w", password="p")

    with patch("datus_snowflake.connector.Connect") as connect:
        SnowflakeConnector(cfg)

    kwargs = connect.call_args.kwargs
    assert kwargs["password"] == "p"
    assert "authenticator" not in kwargs
    assert "private_key_file" not in kwargs


def test_connector_uses_key_pair_auth_kwargs(tmp_path):
    key_file = tmp_path / "key.p8"
    key_file.write_text("dummy")
    cfg = SnowflakeConfig(
        account="a",
        username="u",
        warehouse="w",
        private_key_file=str(key_file),
        private_key_file_pwd="secret",
        role="ANALYST",
    )

    with patch("datus_snowflake.connector.Connect") as connect:
        SnowflakeConnector(cfg)

    kwargs = connect.call_args.kwargs
    assert kwargs["authenticator"] == "SNOWFLAKE_JWT"
    assert kwargs["private_key_file"] == str(key_file)
    assert kwargs["private_key_file_pwd"] == "secret"
    assert kwargs["role"] == "ANALYST"
    assert "password" not in kwargs
