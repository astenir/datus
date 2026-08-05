import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from datus.configuration.agent_config import DbConfig
from datus.utils.exceptions import DatusException
from datus_enterprise.services import connectivity_probe


def test_probe_datasource_connection_uses_flat_config_and_closes_manager(monkeypatch):
    captured = {}

    class FakeConnection:
        def test_connection(self):
            captured["tested"] = True

    class FakeDBManager:
        def __init__(self, db_configs):
            captured["db_configs"] = db_configs

        def get_conn(self, datasource):
            captured["datasource"] = datasource
            return FakeConnection()

        def close(self):
            captured["closed"] = True

    monkeypatch.setattr("datus.tools.db_tools.db_manager.DBManager", FakeDBManager)

    connectivity_probe.probe_datasource_connection({"type": "postgresql", "host": "localhost", "database": "postgres"})

    assert captured["datasource"] == "_probe_"
    assert captured["tested"] is True
    assert captured["closed"] is True
    assert set(captured["db_configs"]) == {"_probe_"}
    assert isinstance(captured["db_configs"]["_probe_"], DbConfig)


def test_probe_datasource_connection_closes_manager_after_failure(monkeypatch):
    manager = MagicMock()
    manager.get_conn.return_value.test_connection.side_effect = RuntimeError("unavailable")
    monkeypatch.setattr("datus.tools.db_tools.db_manager.DBManager", lambda _configs: manager)

    with pytest.raises(RuntimeError, match="unavailable"):
        connectivity_probe.probe_datasource_connection({"type": "postgresql"})

    manager.close.assert_called_once_with()


def test_probe_llm_connection_rejects_unsupported_type(monkeypatch):
    model_config = MagicMock(type="unsupported")
    monkeypatch.setattr(connectivity_probe, "load_model_config", lambda _payload: model_config)

    with pytest.raises(DatusException, match="Unsupported model type"):
        connectivity_probe.probe_llm_connection({"type": "unsupported", "model": "unknown"})


def test_probe_llm_connection_builds_client_and_generates(monkeypatch):
    model_config = MagicMock(type="fake")
    model_class = MagicMock()
    model_client = model_class.return_value
    monkeypatch.setattr(connectivity_probe, "load_model_config", lambda _payload: model_config)
    monkeypatch.setitem(connectivity_probe.LLMBaseModel.MODEL_TYPE_MAP, "fake", "FakeModel")
    monkeypatch.setitem(sys.modules, "datus.models.fake_model", SimpleNamespace(FakeModel=model_class))

    connectivity_probe.probe_llm_connection({"type": "fake", "model": "test"})

    model_class.assert_called_once_with(model_config=model_config)
    model_client.generate.assert_called_once_with("Hello")
