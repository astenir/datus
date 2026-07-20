# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event, Lock

import jpype
import pytest

from datus_oceanbase_oracle import connector as connector_module
from datus_oceanbase_oracle.connector import (
    OceanBaseOracleConnector,
    _JayDeBeApiCreator,
    _parse_base_username,
    _parse_tenant,
)


def make_connector_without_pool(schema_name="APP"):
    connector = OceanBaseOracleConnector.__new__(OceanBaseOracleConnector)
    connector._default_catalog = ""
    connector._default_database = "oracle_tenant"
    connector._default_schema = schema_name
    connector._pool = None
    connector.dialect = "oceanbase-oracle"
    return connector


class TestParseUsername:
    def test_parse_oceanbase_username_parts(self):
        assert _parse_base_username("app@tenant#cluster") == "app"
        assert _parse_tenant("app@tenant#cluster") == "tenant"
        assert _parse_base_username("app@tenant") == "app"
        assert _parse_tenant("app@tenant") == "tenant"
        assert _parse_base_username("app") == "app"
        assert _parse_tenant("app") == ""

    def test_parse_username_with_special_chars(self):
        assert _parse_base_username("app_user@tenant#cluster") == "app_user"
        assert _parse_tenant("app_user@tenant#cluster") == "tenant"


class TestConnectionPool:
    def test_jaydebeapi_creator_calls_connect_with_positional_args(self, monkeypatch):
        calls = []
        sentinel_connection = object()

        def fake_connect(*args, **kwargs):
            calls.append((args, kwargs))
            return sentinel_connection

        monkeypatch.setattr(connector_module.jaydebeapi, "connect", fake_connect)

        connection = _JayDeBeApiCreator.connect(
            driver_class="com.oceanbase.jdbc.Driver",
            jdbc_url="jdbc:oceanbase://db.example.com:2883/APP?useSSL=false",
            username="app@tenant#cluster",
            password="secret",
            jar_path="/opt/oceanbase-client.jar",
            ping_timeout_seconds=5,
        )

        assert connection._connection is sentinel_connection
        assert calls == [
            (
                (
                    "com.oceanbase.jdbc.Driver",
                    "jdbc:oceanbase://db.example.com:2883/APP?useSSL=false",
                    ["app@tenant#cluster", "secret"],
                    "/opt/oceanbase-client.jar",
                    None,
                ),
                {},
            )
        ]

    def test_jaydebeapi_creator_serializes_initial_jvm_start(self, monkeypatch):
        workers_ready = Barrier(2)
        startup_entered = Event()
        release_startup = Event()
        duplicate_start = Event()
        state_lock = Lock()
        state = {"jvm_started": False, "startup_attempts": 0}

        monkeypatch.setattr(jpype, "isJVMStarted", lambda: state["jvm_started"])

        def fake_connect(*_args, **_kwargs):
            with state_lock:
                if not state["jvm_started"]:
                    state["startup_attempts"] += 1
                    if state["startup_attempts"] > 1:
                        duplicate_start.set()
                    startup_entered.set()
            release_startup.wait(timeout=1)
            state["jvm_started"] = True
            return object()

        monkeypatch.setattr(connector_module.jaydebeapi, "connect", fake_connect)

        def connect():
            workers_ready.wait(timeout=1)
            return _JayDeBeApiCreator.connect(
                driver_class="com.oceanbase.jdbc.Driver",
                jdbc_url="jdbc:oceanbase://db.example.com:2883/APP?useSSL=false",
                username="app@tenant#cluster",
                password="secret",
                jar_path="/opt/oceanbase-client.jar",
                ping_timeout_seconds=5,
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(connect) for _ in range(2)]
            assert startup_entered.wait(timeout=1)
            duplicate_start.wait(timeout=0.1)
            release_startup.set()
            connections = [future.result(timeout=1) for future in futures]

        assert duplicate_start.is_set() is False
        assert state["startup_attempts"] == 1
        assert len(connections) == 2

    def test_connector_uses_pool_creator_adapter(self, monkeypatch):
        captured = {}

        class FakePool:
            def __init__(self, *args, **kwargs):
                captured["args"] = args
                captured["kwargs"] = kwargs

        monkeypatch.setattr(connector_module, "PooledDB", FakePool)

        OceanBaseOracleConnector(
            {
                "host": "db.example.com",
                "port": 2883,
                "username": "app@tenant#cluster",
                "password": "secret",
                "schema": "app",
                "jar_path": "/opt/oceanbase-client.jar",
                "pool_mincached": 0,
            }
        )

        assert captured["args"] == ()
        assert captured["kwargs"]["creator"] is _JayDeBeApiCreator
        assert captured["kwargs"]["driver_class"] == "com.oceanbase.jdbc.Driver"
        assert captured["kwargs"]["jdbc_url"].startswith("jdbc:oceanbase://db.example.com:2883/APP?")
        assert captured["kwargs"]["username"] == "app@tenant#cluster"
        assert captured["kwargs"]["password"] == "secret"
        assert captured["kwargs"]["jar_path"] == "/opt/oceanbase-client.jar"
        assert captured["kwargs"]["ping"] == 1
        assert captured["kwargs"]["ping_timeout_seconds"] == 5
        assert "driver" not in captured["kwargs"]
        assert "url" not in captured["kwargs"]
        assert "driver_args" not in captured["kwargs"]
        assert "jars" not in captured["kwargs"]
        assert "libs" not in captured["kwargs"]

    def test_stale_cached_connection_is_replaced(self, monkeypatch):
        created = []

        class FakeCursor:
            def __init__(self, connection):
                self.connection = connection

            def execute(self, _sql):
                if not self.connection.valid or self.connection._closed:
                    raise connector_module.jaydebeapi.DatabaseError("Connection is closed")

            def fetchall(self):
                return [(1,)]

            def close(self):
                pass

        class FakeConnection:
            Error = connector_module.jaydebeapi.Error
            OperationalError = connector_module.jaydebeapi.OperationalError
            InterfaceError = connector_module.jaydebeapi.InterfaceError
            InternalError = connector_module.jaydebeapi.InternalError

            def __init__(self):
                self.jconn = self
                self.valid = True
                self._closed = False
                created.append(self)

            def isClosed(self):
                return self._closed

            def isValid(self, _timeout_seconds):
                return self.valid and not self._closed

            def cursor(self):
                return FakeCursor(self)

            def rollback(self):
                pass

            def close(self):
                self._closed = True

        monkeypatch.setattr(connector_module.jaydebeapi, "connect", lambda *_args, **_kwargs: FakeConnection())

        connector = OceanBaseOracleConnector(
            {
                "username": "app@tenant#cluster",
                "password": "secret",
                "schema": "app",
                "jar_path": "/opt/oceanbase-client.jar",
                "pool_mincached": 0,
                "pool_maxcached": 1,
            }
        )

        assert connector.test_connection() is True
        assert len(created) == 1

        created[0].valid = False

        assert connector.test_connection() is True
        assert len(created) == 2
        assert created[0]._closed is True


class TestQueryExecution:
    def test_execute_sql_converts_jdbc_clob_to_text(self, monkeypatch):
        connector = make_connector_without_pool()
        calls = []

        class FakeClob:
            def __init__(self, value):
                self.value = value

            def length(self):
                return len(self.value)

            def getSubString(self, position, length):
                assert calls[-1] != ("cursor_close", None)
                return self.value[position - 1 : position - 1 + length]

            def __str__(self):
                return "com.oceanbase.jdbc.Clob@59608db2"

        class FakeCursor:
            description = [("ID",), ("CONTENT",)]

            def execute(self, sql):
                calls.append(("execute", sql))

            def fetchall(self):
                return [(1, FakeClob("CLOB contents"))]

            def close(self):
                calls.append(("cursor_close", None))

        class FakeConnection:
            def cursor(self):
                return FakeCursor()

            def close(self):
                calls.append(("connection_close", None))

        monkeypatch.setattr(connector, "_get_raw_connection", lambda: FakeConnection())

        df = connector._execute_sql("SELECT ID, CONTENT FROM APP.T")

        assert df.to_dict(orient="records") == [{"ID": 1, "CONTENT": "CLOB contents"}]
        assert calls == [
            ("execute", "SELECT ID, CONTENT FROM APP.T"),
            ("cursor_close", None),
            ("connection_close", None),
        ]

    def test_execute_sql_uses_cursor_dataframe_reader(self, monkeypatch):
        connector = make_connector_without_pool()
        calls = []

        class FakeCursor:
            description = [("ID",), ("NAME",)]

            def execute(self, sql):
                calls.append(("execute", sql))

            def fetchall(self):
                return [(1, "alpha")]

            def close(self):
                calls.append(("cursor_close", None))

        class FakeConnection:
            def cursor(self):
                return FakeCursor()

            def close(self):
                calls.append(("connection_close", None))

        monkeypatch.setattr(connector, "_get_raw_connection", lambda: FakeConnection())
        monkeypatch.setattr(
            connector_module.pd,
            "read_sql",
            lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("pd.read_sql should not be called")),
        )

        df = connector._execute_sql("SELECT ID, NAME FROM APP.T")

        assert df.to_dict(orient="records") == [{"ID": 1, "NAME": "alpha"}]
        assert calls == [
            ("execute", "SELECT ID, NAME FROM APP.T"),
            ("cursor_close", None),
            ("connection_close", None),
        ]

    def test_execute_queries_select_uses_cursor_dataframe_reader(self, monkeypatch):
        connector = make_connector_without_pool()
        calls = []

        class FakeCursor:
            description = [("ID",)]
            rowcount = -1

            def execute(self, sql):
                calls.append(("execute", sql))

            def fetchall(self):
                return [(1,), (2,)]

            def close(self):
                calls.append(("cursor_close", None))

        class FakeConnection:
            def cursor(self):
                return FakeCursor()

            def commit(self):
                calls.append(("commit", None))

            def rollback(self):
                calls.append(("rollback", None))

            def close(self):
                calls.append(("connection_close", None))

        monkeypatch.setattr(connector, "_get_raw_connection", lambda: FakeConnection())
        monkeypatch.setattr(
            connector_module.pd,
            "read_sql",
            lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("pd.read_sql should not be called")),
        )

        results = connector.execute_queries(["SELECT ID FROM APP.T"])

        assert results == [[{"ID": 1}, {"ID": 2}]]
        assert calls == [
            ("execute", "SELECT ID FROM APP.T"),
            ("cursor_close", None),
            ("commit", None),
            ("connection_close", None),
        ]


class TestMetadataQueries:
    def test_get_ddl_reads_jdbc_clob_contents(self, monkeypatch):
        connector = make_connector_without_pool()
        ddl = 'CREATE TABLE "APP"."ORDERS" ("ID" NUMBER)'

        class FakeClob:
            def length(self):
                return len(ddl)

            def getSubString(self, position, length):
                return ddl[position - 1 : position - 1 + length]

            def __str__(self):
                return "com.oceanbase.jdbc.Clob@59608db2"

        class FakeCursor:
            description = [("DDL",)]

            def execute(self, sql):
                assert "DBMS_METADATA.GET_DDL('TABLE', 'ORDERS', 'APP')" in sql

            def fetchall(self):
                return [(FakeClob(),)]

            def close(self):
                pass

        class FakeConnection:
            def cursor(self):
                return FakeCursor()

            def close(self):
                pass

        monkeypatch.setattr(connector, "_get_raw_connection", lambda: FakeConnection())

        assert connector._get_ddl("APP", "ORDERS") == ddl

    def test_metadata_queries_use_all_views(self, monkeypatch):
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

    def test_get_views_uses_all_views(self, monkeypatch):
        connector = make_connector_without_pool()
        sql_calls = []

        def fake_execute_sql(sql):
            sql_calls.append(sql.upper())

            class FakeSeries(list):
                def tolist(self):
                    return list(self)

            class FakeFrame:
                columns = ["VIEW_NAME"]

                def __getitem__(self, key):
                    assert key == "VIEW_NAME"
                    return FakeSeries()

            return FakeFrame()

        monkeypatch.setattr(connector, "_execute_sql", fake_execute_sql)
        assert connector.get_views(schema_name="APP") == []
        assert "FROM ALL_VIEWS" in sql_calls[0]

    def test_get_schemas_queries_all_users(self, monkeypatch):
        connector = make_connector_without_pool()
        sql_calls = []

        def fake_execute_sql(sql):
            sql_calls.append(sql.upper())

            class FakeSeries(list):
                def tolist(self):
                    return list(self)

            class FakeFrame:
                columns = ["USERNAME"]

                def __getitem__(self, key):
                    assert key == "USERNAME"
                    return FakeSeries(["SYS", "SYSTEM", "APP"])

            return FakeFrame()

        monkeypatch.setattr(connector, "_execute_sql", fake_execute_sql)
        schemas = connector.get_schemas()
        assert "FROM ALL_USERS" in sql_calls[0]
        # System schemas should be filtered out
        assert "SYS" not in schemas
        assert "SYSTEM" not in schemas
        assert "APP" in schemas

    def test_get_schema_uses_all_tab_columns_without_view_fallback(self, monkeypatch):
        connector = make_connector_without_pool()
        sql_calls = []

        def fake_execute_sql(sql):
            sql_calls.append(sql)
            return connector_module.pd.DataFrame(
                [
                    {
                        "COLUMN_ID": 1,
                        "COLUMN_NAME": "ID",
                        "DATA_TYPE": "NUMBER",
                        "DATA_LENGTH": 22,
                        "DATA_PRECISION": 10,
                        "DATA_SCALE": 0,
                        "NULLABLE": "N",
                        "DATA_DEFAULT": None,
                        "IS_PK": 1,
                        "COMMENTS": "identifier",
                    }
                ]
            )

        monkeypatch.setattr(connector, "_execute_sql", fake_execute_sql)
        monkeypatch.setattr(
            connector,
            "_get_raw_connection",
            lambda: (_ for _ in ()).throw(AssertionError("view fallback should not run")),
        )

        assert connector.get_schema(schema_name="APP", table_name="ORDERS") == [
            {
                "cid": 1,
                "name": "ID",
                "type": "NUMBER(10,0)",
                "nullable": False,
                "default_value": None,
                "pk": True,
                "comment": "identifier",
            }
        ]
        assert len(sql_calls) == 1
        assert "FROM ALL_TAB_COLUMNS" in sql_calls[0]

    def test_get_schema_falls_back_to_zero_row_query_for_confirmed_view(self, monkeypatch):
        connector = make_connector_without_pool()
        sql_calls = []
        connection_calls = []

        def fake_execute_sql(sql):
            sql_calls.append(sql)
            if "FROM ALL_TAB_COLUMNS" in sql:
                return connector_module.pd.DataFrame()
            if "FROM ALL_VIEWS" in sql:
                return connector_module.pd.DataFrame([{"VIEW_NAME": "ORDER_VIEW"}])
            raise AssertionError(f"unexpected metadata query: {sql}")

        class FakeCursor:
            description = [
                ("ID", connector_module.jaydebeapi.DECIMAL, 20, 20, 10, 0, 0),
                ("DISPLAY_NAME", connector_module.jaydebeapi.STRING, 128, 128, 0, 0, 1),
                ("CREATED_AT", connector_module.jaydebeapi.DATETIME, 26, 26, 0, 6, 2),
            ]

            def execute(self, sql):
                connection_calls.append(("execute", sql))

            def close(self):
                connection_calls.append(("cursor_close", None))

        class FakeConnection:
            def cursor(self):
                return FakeCursor()

            def close(self):
                connection_calls.append(("connection_close", None))

        monkeypatch.setattr(connector, "_execute_sql", fake_execute_sql)
        monkeypatch.setattr(connector, "_get_raw_connection", lambda: FakeConnection())

        assert connector.get_schema(schema_name="APP", table_name="ORDER_VIEW") == [
            {
                "cid": 1,
                "name": "ID",
                "type": "NUMBER(10,0)",
                "nullable": False,
                "default_value": None,
                "pk": False,
                "comment": None,
            },
            {
                "cid": 2,
                "name": "DISPLAY_NAME",
                "type": "VARCHAR2(128)",
                "nullable": True,
                "default_value": None,
                "pk": False,
                "comment": None,
            },
            {
                "cid": 3,
                "name": "CREATED_AT",
                "type": "TIMESTAMP",
                "nullable": True,
                "default_value": None,
                "pk": False,
                "comment": None,
            },
        ]
        assert "FROM ALL_VIEWS" in sql_calls[1]
        assert "OWNER = 'APP'" in sql_calls[1]
        assert "VIEW_NAME = 'ORDER_VIEW'" in sql_calls[1]
        assert connection_calls == [
            ("execute", 'SELECT * FROM "APP"."ORDER_VIEW" WHERE 1 = 0'),
            ("cursor_close", None),
            ("connection_close", None),
        ]

    def test_get_schema_does_not_probe_missing_object(self, monkeypatch):
        connector = make_connector_without_pool()
        sql_calls = []

        def fake_execute_sql(sql):
            sql_calls.append(sql)
            return connector_module.pd.DataFrame()

        monkeypatch.setattr(connector, "_execute_sql", fake_execute_sql)
        monkeypatch.setattr(
            connector,
            "_get_raw_connection",
            lambda: (_ for _ in ()).throw(AssertionError("missing objects must not be probed")),
        )

        assert connector.get_schema(schema_name="APP", table_name="MISSING") == []
        assert len(sql_calls) == 2
        assert "FROM ALL_TAB_COLUMNS" in sql_calls[0]
        assert "FROM ALL_VIEWS" in sql_calls[1]


class TestFullName:
    def test_full_name_quotes_embedded_double_quotes(self):
        connector = make_connector_without_pool(schema_name='A"P')
        assert connector.full_name(table_name='T"B') == '"A""P"."T""B"'

    def test_full_name_with_schema(self):
        connector = make_connector_without_pool(schema_name="MY_SCHEMA")
        assert connector.full_name(table_name="MY_TABLE") == '"MY_SCHEMA"."MY_TABLE"'

    def test_full_name_without_schema(self):
        connector = make_connector_without_pool(schema_name="")
        connector._default_schema = ""
        assert connector.full_name(table_name="MY_TABLE") == '"MY_TABLE"'


class TestMetricQueryPrimitives:
    def test_query_dataframe_passes_positional_parameters(self):
        connector = make_connector_without_pool()
        calls = []

        class FakeCursor:
            description = [("TOTAL",)]

            def execute(self, sql, parameters):
                calls.append((sql, parameters))

            def fetchall(self):
                return [(42,)]

            def close(self):
                calls.append(("close", None))

        class FakeConnection:
            def cursor(self):
                return FakeCursor()

            def close(self):
                calls.append(("connection_close", None))

        connector._get_raw_connection = lambda: FakeConnection()

        result = connector.query_dataframe("SELECT ? AS total FROM DUAL", (42,))

        assert result.to_dict(orient="records") == [{"TOTAL": 42}]
        assert calls == [
            ("SELECT ? AS total FROM DUAL", (42,)),
            ("close", None),
            ("connection_close", None),
        ]

    def test_execute_statement_commits_and_passes_parameters(self):
        connector = make_connector_without_pool()
        calls = []

        class FakeCursor:
            def execute(self, sql, parameters):
                calls.append((sql, parameters))

            def close(self):
                calls.append(("close", None))

        class FakeConnection:
            def cursor(self):
                return FakeCursor()

            def commit(self):
                calls.append(("commit", None))

            def close(self):
                calls.append(("connection_close", None))

        connector._get_raw_connection = lambda: FakeConnection()

        connector.execute_statement("UPDATE APP.ORDERS SET AMOUNT = ?", (42,))

        assert calls == [
            ("UPDATE APP.ORDERS SET AMOUNT = ?", (42,)),
            ("commit", None),
            ("close", None),
            ("connection_close", None),
        ]

    def test_execute_statement_rolls_back_and_closes_on_error(self):
        connector = make_connector_without_pool()
        calls = []

        class FakeCursor:
            def execute(self, sql, parameters):
                calls.append((sql, parameters))
                raise RuntimeError("write failed")

            def close(self):
                calls.append(("close", None))

        class FakeConnection:
            def cursor(self):
                return FakeCursor()

            def rollback(self):
                calls.append(("rollback", None))

            def close(self):
                calls.append(("connection_close", None))

        connector._get_raw_connection = lambda: FakeConnection()

        with pytest.raises(RuntimeError, match="write failed"):
            connector.execute_statement("UPDATE APP.ORDERS SET AMOUNT = ?", (42,))

        assert calls == [
            ("UPDATE APP.ORDERS SET AMOUNT = ?", (42,)),
            ("close", None),
            ("rollback", None),
            ("connection_close", None),
        ]


class TestIdentifier:
    def test_identifier_with_database_and_schema(self):
        connector = make_connector_without_pool(schema_name="SCHEMA")
        result = connector.identifier(database_name="DB", schema_name="SCHEMA", table_name="TABLE")
        assert result == "DB.SCHEMA.TABLE"

    def test_identifier_with_schema_only(self):
        connector = make_connector_without_pool(schema_name="SCHEMA")
        connector._default_database = ""
        result = connector.identifier(schema_name="SCHEMA", table_name="TABLE")
        assert result == "SCHEMA.TABLE"

    def test_identifier_without_schema(self):
        connector = make_connector_without_pool(schema_name="")
        connector._default_schema = ""
        connector._default_database = ""
        result = connector.identifier(table_name="TABLE")
        assert result == "TABLE"


class TestFormatColumnType:
    def test_number_with_precision(self):
        connector = make_connector_without_pool()
        row = {"DATA_TYPE": "NUMBER", "DATA_PRECISION": 10, "DATA_SCALE": 2, "DATA_LENGTH": 22}
        assert connector._format_column_type(row) == "NUMBER(10,2)"

    def test_number_without_precision(self):
        connector = make_connector_without_pool()
        row = {"DATA_TYPE": "NUMBER", "DATA_PRECISION": None, "DATA_SCALE": None, "DATA_LENGTH": 22}
        assert connector._format_column_type(row) == "NUMBER"

    def test_varchar2_with_length(self):
        connector = make_connector_without_pool()
        row = {"DATA_TYPE": "VARCHAR2", "DATA_PRECISION": None, "DATA_SCALE": None, "DATA_LENGTH": 255}
        assert connector._format_column_type(row) == "VARCHAR2(255)"

    def test_timestamp_type(self):
        connector = make_connector_without_pool()
        row = {"DATA_TYPE": "TIMESTAMP", "DATA_PRECISION": None, "DATA_SCALE": None, "DATA_LENGTH": 11}
        assert connector._format_column_type(row) == "TIMESTAMP"


class TestMapSourceType:
    def test_hugeint_to_number(self):
        connector = make_connector_without_pool()
        assert connector.map_source_type("duckdb", "HUGEINT") == "NUMBER(38,0)"

    def test_boolean_to_number(self):
        connector = make_connector_without_pool()
        assert connector.map_source_type("duckdb", "BOOLEAN") == "NUMBER(1)"

    def test_unknown_type_returns_none(self):
        connector = make_connector_without_pool()
        assert connector.map_source_type("duckdb", "UNKNOWN_TYPE") is None

    def test_type_with_precision_stripped(self):
        connector = make_connector_without_pool()
        assert connector.map_source_type("mysql", "BIGINT(20)") == "NUMBER(19)"


class TestValidateDdl:
    def test_accepts_standard_ddl(self):
        connector = make_connector_without_pool()
        ddl = 'CREATE TABLE "S"."T" ("ID" NUMBER PRIMARY KEY)'
        assert connector.validate_ddl(ddl) == []

    def test_rejects_auto_increment(self):
        connector = make_connector_without_pool()
        errors = connector.validate_ddl("CREATE TABLE t (id INT AUTO_INCREMENT)")
        assert len(errors) > 0
        assert any("AUTO_INCREMENT" in e for e in errors)

    def test_rejects_engine_clause(self):
        connector = make_connector_without_pool()
        errors = connector.validate_ddl("CREATE TABLE t (id INT) ENGINE=InnoDB")
        assert len(errors) > 0
        assert any("ENGINE" in e for e in errors)

    def test_rejects_duplicate_key(self):
        connector = make_connector_without_pool()
        errors = connector.validate_ddl('CREATE TABLE t (id BIGINT) DUPLICATE KEY("ID")')
        assert len(errors) > 0


class TestSysSchemas:
    def test_returns_set_with_known_system_schemas(self):
        connector = make_connector_without_pool()
        schemas = connector._sys_schemas()
        assert isinstance(schemas, set)
        assert "SYS" in schemas
        assert "SYSTEM" in schemas
        assert "LBACSYS" in schemas

    def test_includes_extended_schemas(self):
        connector = make_connector_without_pool()
        schemas = connector._sys_schemas()
        assert "DBFS_MOCA" in schemas
        assert "APEX_PUBLIC_USER" in schemas
