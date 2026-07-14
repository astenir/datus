"""Unit tests for the OceanBase Oracle MetricFlow SQL client."""

from unittest.mock import MagicMock

import datus_oceanbase_oracle
import pandas as pd
import pytest

from metricflow.configuration.dict_config_handler import DictConfigHandler, build_config_dict_from_datus_datasource
from metricflow.dataflow.sql_table import SqlTable
from metricflow.protocols.sql_client import SqlEngine
from metricflow.sql.sql_bind_parameters import SqlBindParameters
from metricflow.sql_clients.common_client import SqlDialect
from metricflow.sql_clients.oceanbase_oracle import OceanBaseOracleEngineAttributes, OceanBaseOracleSqlClient
from metricflow.sql_clients.sql_utils import make_sql_client_from_config


def test_oceanbase_oracle_engine_registration() -> None:
    assert SqlDialect.OCEANBASE_ORACLE.value == "oceanbase-oracle"
    assert SqlEngine.OCEANBASE_ORACLE.value == "OceanBase Oracle"
    assert OceanBaseOracleEngineAttributes.sql_engine_type is SqlEngine.OCEANBASE_ORACLE
    assert OceanBaseOracleEngineAttributes.full_outer_joins_supported is False


def test_query_converts_named_parameters_and_normalizes_column_labels() -> None:
    connector = MagicMock()
    connector.query_dataframe.return_value = pd.DataFrame([{"TOTAL": 42}])
    client = OceanBaseOracleSqlClient(connector)

    result = client.query(
        "SELECT :amount AS total FROM DUAL WHERE :label = :label",
        SqlBindParameters.create_from_dict({"amount": 42, "label": "ok"}),
    )

    assert result.to_dict(orient="records") == [{"total": 42}]
    connector.query_dataframe.assert_called_once_with(
        "SELECT ? AS total FROM DUAL WHERE ? = ?",
        (42, "ok", "ok"),
    )


def test_query_normalizes_missing_values_to_none() -> None:
    connector = MagicMock()
    connector.query_dataframe.return_value = pd.DataFrame([{"TOTAL": float("nan")}, {"TOTAL": 42}])
    client = OceanBaseOracleSqlClient(connector)

    result = client.query("SELECT total FROM orders")

    assert result.to_dict(orient="records") == [{"total": None}, {"total": 42.0}]


def test_parameter_conversion_ignores_literals_and_comments() -> None:
    statement, parameters = OceanBaseOracleSqlClient._to_jdbc_parameters(
        "SELECT ':not_a_param' AS value FROM DUAL -- :also_not\nWHERE id = :id",
        SqlBindParameters.create_from_dict({"id": 7}),
    )

    assert statement == "SELECT ':not_a_param' AS value FROM DUAL -- :also_not\nWHERE id = ?"
    assert parameters == (7,)


def test_dry_run_wraps_query_as_zero_row_select() -> None:
    connector = MagicMock()
    connector.query_dataframe.return_value = pd.DataFrame()
    client = OceanBaseOracleSqlClient(connector)

    client.dry_run("SELECT :amount AS total FROM DUAL;", SqlBindParameters.create_from_dict({"amount": 42}))

    connector.query_dataframe.assert_called_once_with(
        "SELECT * FROM (\nSELECT ? AS total FROM DUAL\n) mf_dry_run WHERE 1 = 0",
        (42,),
    )


def test_execute_is_rejected_by_read_only_profile() -> None:
    connector = MagicMock()
    client = OceanBaseOracleSqlClient(connector)

    with pytest.raises(NotImplementedError, match="read-only"):
        client.execute(
            "DELETE FROM APP.ORDERS WHERE ID = :order_id",
            SqlBindParameters.create_from_dict({"order_id": 7}),
        )

    connector.execute_statement.assert_not_called()


def test_schema_and_table_mutations_are_rejected_by_read_only_profile() -> None:
    connector = MagicMock()
    client = OceanBaseOracleSqlClient(connector)
    table = SqlTable(schema_name="APP", table_name="ORDERS")

    with pytest.raises(NotImplementedError, match="read-only"):
        client.create_table_from_dataframe(table, pd.DataFrame([{"ID": 1}]))
    with pytest.raises(NotImplementedError, match="read-only"):
        client.create_schema("APP")
    with pytest.raises(NotImplementedError, match="read-only"):
        client.drop_schema("APP")
    with pytest.raises(NotImplementedError, match="read-only"):
        client.drop_table(table)

    assert connector.method_calls == []


def test_close_delegates_to_connector() -> None:
    connector = MagicMock()
    OceanBaseOracleSqlClient(connector).close()

    connector.close.assert_called_once_with()


def test_factory_builds_client_from_datus_config(monkeypatch: pytest.MonkeyPatch) -> None:
    expected_client = MagicMock()
    factory = MagicMock(return_value=expected_client)
    monkeypatch.setattr(OceanBaseOracleSqlClient, "from_config", factory)
    handler = DictConfigHandler(
        build_config_dict_from_datus_datasource(
            {
                "type": "oceanbase-oracle",
                "host": "ob.example.com",
                "port": 2883,
                "username": "app@tenant#cluster",
                "password": "secret",
                "database": "tenant",
                "schema": "APP",
                "jar_path": "/opt/oceanbase-client.jar",
            }
        )
    )

    assert make_sql_client_from_config(handler) is expected_client
    factory.assert_called_once_with(handler)


def test_from_config_builds_datus_connector(monkeypatch: pytest.MonkeyPatch) -> None:
    connector = MagicMock()
    connector_factory = MagicMock(return_value=connector)
    monkeypatch.setattr(datus_oceanbase_oracle, "OceanBaseOracleConnector", connector_factory)
    handler = DictConfigHandler(
        build_config_dict_from_datus_datasource(
            {
                "type": "oceanbase-oracle",
                "host": "ob.example.com",
                "port": 2883,
                "username": "app@tenant#cluster",
                "password": "secret",
                "database": "tenant",
                "schema": "APP",
                "jar_path": "/opt/oceanbase-client.jar",
                "connect_timeout_seconds": 15,
                "query_timeout_seconds": 45,
            }
        )
    )

    client = OceanBaseOracleSqlClient.from_config(handler)

    assert client._connector is connector
    connector_factory.assert_called_once_with(
        {
            "host": "ob.example.com",
            "port": 2883,
            "username": "app@tenant#cluster",
            "password": "secret",
            "database": "tenant",
            "schema": "APP",
            "jar_path": "/opt/oceanbase-client.jar",
            "driver_class": "com.oceanbase.jdbc.Driver",
            "connection_mode": "odp",
            "use_ssl": False,
            "connect_timeout_seconds": 15,
            "query_timeout_seconds": 45,
        }
    )
