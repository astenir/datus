# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

import threading
from unittest.mock import MagicMock, patch

from datus_sqlalchemy import SQLAlchemyConnector


class DummySQLAlchemyConnector(SQLAlchemyConnector):
    def get_databases(self, catalog_name: str = "", include_sys: bool = False):
        return []

    def do_switch_context(self, conn, catalog_name="", database_name="", schema_name=""):
        if database_name:
            from sqlalchemy import text

            conn.execute(text(f"USE {database_name}"))
            conn.commit()


def test_conn_checks_out_and_returns_connection():
    """Each _conn() call checks out a connection from pool and returns it."""
    connector = DummySQLAlchemyConnector("sqlite://", dialect="sqlite")
    mock_conn = MagicMock()
    engine = MagicMock()
    engine.connect.return_value = mock_conn

    with patch("datus_sqlalchemy.connector.create_engine", return_value=engine):
        connector._ensure_engine()
        with connector._conn() as conn:
            assert conn is mock_conn
        mock_conn.close.assert_called_once()


def test_conn_applies_context_per_checkout():
    """Each _conn() checkout calls do_switch_context with current thread's context."""
    connector = DummySQLAlchemyConnector("sqlite://", dialect="sqlite")
    connector.switch_context(database_name="analytics")

    mock_conn = MagicMock()
    engine = MagicMock()
    engine.connect.return_value = mock_conn

    with patch("datus_sqlalchemy.connector.create_engine", return_value=engine):
        connector._ensure_engine()
        with connector._conn():
            pass

    # Verify USE was executed on the checked-out connection
    mock_conn.execute.assert_called()
    mock_conn.commit.assert_called()


def test_execute_content_set_updates_thread_local_context():
    """USE db via execute_content_set updates the calling thread's context."""
    connector = DummySQLAlchemyConnector("sqlite://", dialect="mysql")
    mock_conn = MagicMock()
    engine = MagicMock()
    engine.connect.return_value = mock_conn

    with patch("datus_sqlalchemy.connector.create_engine", return_value=engine):
        result = connector.execute_content_set("USE analytics")

    assert result.success is True
    assert connector.database_name == "analytics"


def test_per_operation_connections_are_independent():
    """Two operations get independent connections from the pool."""
    connector = DummySQLAlchemyConnector("sqlite://", dialect="sqlite")
    conn1, conn2 = MagicMock(), MagicMock()
    engine = MagicMock()
    engine.connect.side_effect = [conn1, conn2]

    query_result = MagicMock()
    query_result.fetchall.return_value = [MagicMock(_asdict=lambda: {"id": 1})]
    conn1.execute.return_value = MagicMock()  # for do_switch_context
    conn2.execute.return_value = query_result  # for the actual query

    with patch("datus_sqlalchemy.connector.create_engine", return_value=engine):
        connector.execute_content_set("USE analytics")
        rows = connector._execute_query("SELECT id FROM users")

    assert engine.connect.call_count == 2
    assert rows == [{"id": 1}]


def test_thread_local_context_isolation_with_conn():
    """Two threads using the same connector get isolated contexts."""
    connector = DummySQLAlchemyConnector("sqlite://", dialect="sqlite")
    results = {}

    def worker(thread_id, db_name):
        connector.switch_context(database_name=db_name)
        import time

        time.sleep(0.05)
        results[thread_id] = connector.database_name

    t1 = threading.Thread(target=worker, args=(1, "db1"))
    t2 = threading.Thread(target=worker, args=(2, "db2"))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert results[1] == "db1"
    assert results[2] == "db2"
