"""Downstream DBManager concurrency and adapter-config coverage."""

import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from datus.tools.db_tools.db_manager import DBManager


def _cfg(**kwargs):
    defaults = {
        "type": None,
        "host": None,
        "port": None,
        "username": None,
        "password": None,
        "database": None,
        "schema": None,
        "catalog": None,
        "uri": None,
        "extra": None,
        "path_pattern": None,
    }
    defaults.update(kwargs)
    config = SimpleNamespace(**defaults)
    config.to_dict = lambda: dict(defaults)
    return config


def test_get_conn_builds_connector_once_under_concurrency():
    manager = DBManager({"ns": _cfg(type="sqlite", uri="sqlite:///test.db")})
    workers_ready = Barrier(8)
    count_lock = Lock()
    connector = MagicMock()
    build_count = 0

    def build(_config):
        nonlocal build_count
        with count_lock:
            build_count += 1
        time.sleep(0.05)
        return connector

    def get_conn():
        workers_ready.wait(timeout=1)
        return manager.get_conn("ns")

    with patch.object(manager, "_build_conn", side_effect=build):
        with ThreadPoolExecutor(max_workers=8) as executor:
            connections = list(executor.map(lambda _index: get_conn(), range(8)))

    assert build_count == 1
    assert all(connection is connector for connection in connections)


def test_adapter_config_excludes_datasource_display_name():
    manager = DBManager({})
    config = _cfg(
        type="postgresql",
        display_name="基金数据库",
        host="127.0.0.1",
        database="ccks_fund",
        extra={"sslmode": "prefer", "timeout_seconds": 30},
    )

    result = manager._db_config_to_connection_config(config)

    assert "display_name" not in result
    assert result["sslmode"] == "prefer"
    assert result["timeout_seconds"] == 30
