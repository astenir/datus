from metricflow.sql_clients.sqlite import SqliteSqlClient
from metricflow.sql_clients.sql_utils import make_sql_client


def test_sqlite_client_creation() -> None:
    """Test that we can create a SQLite client."""
    client = SqliteSqlClient()
    assert client is not None


def test_sqlite_client_from_connection_details() -> None:
    """Test that we can create a SQLite client from connection details."""
    client = SqliteSqlClient.from_connection_details("sqlite:///:memory:")
    assert client is not None


def test_make_sql_client_with_sqlite() -> None:
    """Test that we can create a SQLite client using make_sql_client."""
    client = make_sql_client("sqlite:///:memory:", "")
    assert client is not None
    assert isinstance(client, SqliteSqlClient)
