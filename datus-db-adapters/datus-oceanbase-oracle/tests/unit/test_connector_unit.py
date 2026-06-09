from datus_oceanbase_oracle.connector import OceanBaseOracleConnector, _parse_base_username, _parse_tenant


def make_connector_without_pool(schema_name="APP"):
    connector = OceanBaseOracleConnector.__new__(OceanBaseOracleConnector)
    connector._default_catalog = ""
    connector._default_database = "oracle_tenant"
    connector._default_schema = schema_name
    connector._pool = None
    connector.dialect = "oceanbase-oracle"
    return connector


def test_parse_oceanbase_username_parts():
    assert _parse_base_username("app@tenant#cluster") == "app"
    assert _parse_tenant("app@tenant#cluster") == "tenant"
    assert _parse_base_username("app@tenant") == "app"
    assert _parse_tenant("app@tenant") == "tenant"
    assert _parse_base_username("app") == "app"
    assert _parse_tenant("app") == ""


def test_metadata_queries_use_all_views(monkeypatch):
    connector = make_connector_without_pool()
    sql_calls = []

    def fake_execute_sql(sql):
        sql_calls.append(sql.upper())

        class FakeSeries(list):
            def tolist(self):
                return list(self)

        class FakeFrame:
            columns = ["TABLE_NAME"]

            def __getitem__(self, key):
                assert key == "TABLE_NAME"
                return FakeSeries()

        return FakeFrame()

    monkeypatch.setattr(connector, "_execute_sql", fake_execute_sql)

    assert connector.get_tables(schema_name="APP") == []

    assert "FROM ALL_TABLES" in sql_calls[0]
    assert "DBA_TABLES" not in sql_calls[0]


def test_full_name_quotes_embedded_double_quotes():
    connector = make_connector_without_pool(schema_name='A"P')

    assert connector.full_name(table_name='T"B') == '"A""P"."T""B"'
