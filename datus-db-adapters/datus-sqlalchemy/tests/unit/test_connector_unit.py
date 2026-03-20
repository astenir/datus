# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

from unittest.mock import MagicMock, patch

from datus_sqlalchemy import SQLAlchemyConnector


class DummySQLAlchemyConnector(SQLAlchemyConnector):
    def get_databases(self, catalog_name: str = "", include_sys: bool = False):
        return []


def test_execute_content_set_and_query_share_persistent_connection():
    """USE/SET statements must affect later queries executed by the connector."""
    connector = DummySQLAlchemyConnector("sqlite://", dialect="mysql")
    persistent_conn = MagicMock()
    query_result = MagicMock()
    query_result.fetchall.return_value = [MagicMock(_asdict=lambda: {"id": 1})]

    engine = MagicMock()
    engine.connect.return_value = persistent_conn
    persistent_conn.execute.side_effect = [MagicMock(), query_result]

    with patch("datus_sqlalchemy.connector.create_engine", return_value=engine):
        set_result = connector.execute_content_set("USE analytics")
        query_rows = connector._execute_query("SELECT id FROM users")

    assert set_result.success is True
    assert query_rows == [{"id": 1}]
    assert engine.connect.call_count == 1
    assert persistent_conn.execute.call_count == 2
