"""Downstream DatusService coverage kept out of the upstream test file."""

from datus.api.services.datus_service import DatusService


def test_session_body_store_does_not_mutate_shared_config(real_agent_config):
    body_store = object()

    svc = DatusService(agent_config=real_agent_config, project_id="p1", session_body_store=body_store)

    assert getattr(real_agent_config, "_session_body_store", None) is None
    assert getattr(real_agent_config, "_session_project_id", None) is None
    assert svc.task_manager._session_body_store is body_store
    assert svc.chat._session_body_store is body_store
