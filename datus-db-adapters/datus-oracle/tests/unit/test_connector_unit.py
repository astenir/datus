# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

from unittest.mock import MagicMock, patch

import pytest

from datus_oracle import OracleConfig, OracleConnector


def test_connector_initialization_with_config_object():
    config = OracleConfig(username="app", password="secret", service_name="FREEPDB1", schema="reporting")

    with patch("datus_sqlalchemy.SQLAlchemyConnector.__init__", return_value=None) as mock_init:
        connector = OracleConnector(config)

    assert connector.config == config
    assert connector.host == "127.0.0.1"
    assert connector.port == 1521
    assert connector.username == "app"
    assert connector.password == "secret"
    assert connector.database_name == "FREEPDB1"
    assert connector.schema_name == "REPORTING"
    mock_init.assert_called_once()
    assert mock_init.call_args.kwargs["dialect"] == "oracle"


def test_connector_initialization_with_dict():
    with patch("datus_sqlalchemy.SQLAlchemyConnector.__init__", return_value=None):
        connector = OracleConnector({"username": "app", "sid": "XE", "service_name": None})

    assert connector.database_name == "XE"
    assert connector.schema_name == "APP"


def test_connector_initialization_invalid_type():
    with pytest.raises(TypeError, match="config must be OracleConfig or dict"):
        OracleConnector("invalid")


def test_connection_string_uses_service_name_query():
    config = OracleConfig(host="db.example.com", port=1522, username="app", password="p@ss", service_name="SALES")

    with patch("datus_sqlalchemy.SQLAlchemyConnector.__init__") as mock_init:
        OracleConnector(config)

    connection_string = mock_init.call_args.args[0]
    assert connection_string.startswith("oracle+oracledb://app:p%40ss@db.example.com:1522/")
    assert "service_name=SALES" in connection_string


def test_quote_identifier_uses_ansi_double_quotes():
    assert OracleConnector.quote_identifier(MagicMock(), "table_name") == '"table_name"'


def test_quote_identifier_escapes_double_quotes():
    assert OracleConnector.quote_identifier(MagicMock(), 'a"b') == '"a""b"'


def test_full_name_uses_schema_and_table_only():
    with patch("datus_sqlalchemy.SQLAlchemyConnector.__init__", return_value=None):
        connector = OracleConnector(OracleConfig(username="app", schema="sales"))

    assert connector.full_name(schema_name="HR", table_name="EMP") == '"HR"."EMP"'
