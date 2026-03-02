# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import pandas as pd
import pytest
from datus_hive import HiveConfig
from datus_hive.connector import HiveConnector


@pytest.fixture
def connector():
    return HiveConnector(
        HiveConfig(
            host="localhost",
            port=10000,
            database="default",
            username="hue",
            password="pass",
            auth="CUSTOM",
            configuration={"spark.app.name": "datacenter_carrier", "spark.sql.shuffle.partitions": 100},
        )
    )


def test_build_connect_args_normalizes_configuration(connector):
    connect_args = connector._build_connect_args(connector.config)

    assert connect_args["configuration"]["spark.sql.shuffle.partitions"] == "100"


def test_get_databases_parses_results(monkeypatch, connector):
    monkeypatch.setattr(connector, "connect", lambda: None)
    monkeypatch.setattr(connector, "_execute_pandas", lambda sql: pd.DataFrame({"database_name": ["default", "test"]}))

    assert connector.get_databases() == ["default", "test"]


def test_get_tables_parses_results(monkeypatch, connector):
    monkeypatch.setattr(connector, "connect", lambda: None)
    monkeypatch.setattr(
        connector,
        "_execute_pandas",
        lambda sql: pd.DataFrame({"database": ["default"], "tableName": ["table_a"], "isTemporary": [False]}),
    )

    assert connector.get_tables(database_name="default") == ["table_a"]


def test_get_schema_ignores_partition_section(monkeypatch, connector):
    monkeypatch.setattr(connector, "connect", lambda: None)
    monkeypatch.setattr(
        connector,
        "_execute_pandas",
        lambda sql: pd.DataFrame(
            {
                "col_name": ["id", "name", "# Partition Information", "dt"],
                "data_type": ["int", "string", "", "string"],
                "comment": ["", "", "", ""],
            }
        ),
    )

    schema = connector.get_schema(database_name="default", table_name="table_a")
    assert [col["name"] for col in schema] == ["id", "name"]


def test_get_tables_with_ddl(monkeypatch, connector):
    monkeypatch.setattr(connector, "connect", lambda: None)
    monkeypatch.setattr(connector, "get_tables", lambda **kwargs: ["table_a"])
    monkeypatch.setattr(connector, "_show_create", lambda full_name: "CREATE TABLE table_a (id INT)")

    ddl_list = connector.get_tables_with_ddl(database_name="default")
    assert ddl_list
    assert ddl_list[0]["table_name"] == "table_a"
    assert "CREATE TABLE" in ddl_list[0]["definition"]


def test_get_views_parses_results(monkeypatch, connector):
    monkeypatch.setattr(connector, "connect", lambda: None)
    monkeypatch.setattr(
        connector,
        "_execute_pandas",
        lambda sql: pd.DataFrame({"database": ["default"], "viewName": ["view_a"], "isTemporary": [False]}),
    )

    assert connector.get_views(database_name="default") == ["view_a"]
