# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

from unittest.mock import MagicMock, patch

import pandas as pd
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


def make_connector():
    with patch("datus_sqlalchemy.SQLAlchemyConnector.__init__", return_value=None):
        connector = OracleConnector(OracleConfig(username="app", service_name="FREEPDB1", schema="APP"))
    connector.connect = MagicMock()
    connector.database_name = "FREEPDB1"
    connector.schema_name = "APP"
    return connector


def test_connection_uses_oracle_dual_probe():
    connector = make_connector()
    conn = MagicMock()
    conn.__enter__.return_value = conn
    conn.__exit__.return_value = None
    connector._conn = MagicMock(return_value=conn)

    assert connector.test_connection() is True

    sql = str(conn.execute.call_args.args[0])
    assert "SELECT 1 FROM DUAL" in sql


def test_get_tables_queries_all_tables_for_owner():
    connector = make_connector()
    connector._execute_pandas = MagicMock(return_value=pd.DataFrame({"OWNER": ["APP"], "TABLE_NAME": ["CUSTOMERS"]}))

    assert connector.get_tables(schema_name="APP") == ["CUSTOMERS"]
    sql = connector._execute_pandas.call_args.args[0]
    assert "FROM ALL_TABLES" in sql
    assert "OWNER = 'APP'" in sql
    assert "DROPPED = 'NO'" in sql


def test_get_views_queries_all_views_for_owner():
    connector = make_connector()
    connector._execute_pandas = MagicMock(
        return_value=pd.DataFrame({"OWNER": ["APP"], "VIEW_NAME": ["ACTIVE_CUSTOMERS"]})
    )

    assert connector.get_views(schema_name="APP") == ["ACTIVE_CUSTOMERS"]
    assert "FROM ALL_VIEWS" in connector._execute_pandas.call_args.args[0]


def test_get_materialized_views_queries_all_mviews_for_owner():
    connector = make_connector()
    connector._execute_pandas = MagicMock(
        return_value=pd.DataFrame({"OWNER": ["APP"], "MVIEW_NAME": ["CUSTOMER_SUMMARY"]})
    )

    assert connector.get_materialized_views(schema_name="APP") == ["CUSTOMER_SUMMARY"]
    assert "FROM ALL_MVIEWS" in connector._execute_pandas.call_args.args[0]


def test_get_schemas_filters_system_schemas():
    connector = make_connector()
    connector._execute_pandas = MagicMock(return_value=pd.DataFrame({"USERNAME": ["SYS", "APP", "REPORTING"]}))

    assert connector.get_schemas() == ["APP", "REPORTING"]


def test_get_schemas_handles_lowercase_result_columns():
    connector = make_connector()
    connector._execute_pandas = MagicMock(return_value=pd.DataFrame({"username": ["SYS", "APP", "REPORTING"]}))

    assert connector.get_schemas() == ["APP", "REPORTING"]


def test_get_databases_returns_configured_service_name():
    connector = make_connector()

    assert connector.get_databases() == ["FREEPDB1"]


def test_get_schema_returns_columns_with_pk_and_comments():
    connector = make_connector()
    connector._execute_pandas = MagicMock(
        return_value=pd.DataFrame(
            {
                "COLUMN_ID": [1],
                "COLUMN_NAME": ["ID"],
                "DATA_TYPE": ["NUMBER"],
                "DATA_PRECISION": [10],
                "DATA_SCALE": [0],
                "NULLABLE": ["N"],
                "DATA_DEFAULT": [None],
                "IS_PK": [1],
                "COMMENTS": ["primary id"],
            }
        )
    )

    assert connector.get_schema(schema_name="APP", table_name="CUSTOMERS") == [
        {
            "cid": 0,
            "name": "ID",
            "type": "NUMBER(10,0)",
            "nullable": False,
            "default_value": None,
            "pk": True,
            "comment": "primary id",
        }
    ]


def test_do_switch_context_sets_current_schema():
    connector = make_connector()
    conn = MagicMock()

    connector.do_switch_context(conn, schema_name="REPORTING")

    sql = str(conn.execute.call_args.args[0])
    assert 'ALTER SESSION SET CURRENT_SCHEMA = "REPORTING"' in sql
    conn.commit.assert_called_once()


def test_get_ddl_calls_dbms_metadata():
    connector = make_connector()
    connector._execute_pandas = MagicMock(
        return_value=pd.DataFrame({"DDL": ['CREATE TABLE "APP"."CUSTOMERS" ("ID" NUMBER)']})
    )

    assert connector._get_ddl("APP", "CUSTOMERS", "TABLE").startswith("CREATE TABLE")
    assert "DBMS_METADATA.GET_DDL" in connector._execute_pandas.call_args.args[0]


def test_sample_rows_uses_fetch_first():
    connector = make_connector()
    connector._execute_pandas = MagicMock(return_value=pd.DataFrame({"ID": [1]}))

    rows = connector.get_sample_rows(tables=["CUSTOMERS"], top_n=3, schema_name="APP")

    assert rows[0]["table_name"] == "CUSTOMERS"
    assert "ID" in rows[0]["sample_rows"]
    assert "FETCH FIRST 3 ROWS ONLY" in connector._execute_pandas.call_args.args[0]
