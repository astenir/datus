"""Downstream DatusService coverage kept out of the upstream test file."""

import pytest

from datus.api.services.datus_service import DatusService


def test_session_body_store_does_not_mutate_shared_config(real_agent_config):
    body_store = object()

    svc = DatusService(agent_config=real_agent_config, project_id="p1", session_body_store=body_store)

    assert getattr(real_agent_config, "_session_body_store", None) is None
    assert getattr(real_agent_config, "_session_project_id", None) is None
    assert svc.task_manager._session_body_store is body_store
    assert svc.chat._session_body_store is body_store


def test_web_filesystem_executor_defaults_to_downstream_server(real_agent_config):
    svc = DatusService(agent_config=real_agent_config, project_id="p1")

    assert svc.task_manager._web_filesystem_executor == "server"


def test_web_filesystem_executor_accepts_explicit_upstream_client(real_agent_config):
    real_agent_config.api_config = {"chat": {"web_filesystem_executor": "client"}}

    svc = DatusService(agent_config=real_agent_config, project_id="p1")

    assert svc.task_manager._web_filesystem_executor == "client"


def test_web_filesystem_executor_rejects_unknown_value(real_agent_config):
    real_agent_config.api_config = {"chat": {"web_filesystem_executor": "browser"}}

    with pytest.raises(ValueError, match="agent.api.chat.web_filesystem_executor"):
        DatusService(agent_config=real_agent_config, project_id="p1")
