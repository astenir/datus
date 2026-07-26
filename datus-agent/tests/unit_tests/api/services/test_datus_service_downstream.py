"""Downstream DatusService coverage kept out of the upstream test file."""

import pytest

from datus.api.services.datus_service import DatusService
from datus_enterprise.services.dashboard_service import EnterpriseDashboardService
from datus_enterprise.services.database_service import EnterpriseDatasourceService
from datus_enterprise.services.mcp_service import EnterpriseMCPService
from datus_enterprise.services.report_service import EnterpriseReportService
from datus_enterprise.services.success_story_service import EnterpriseSuccessStoryService


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


def test_downstream_service_factories_use_enterprise_extensions(real_agent_config):
    svc = DatusService(agent_config=real_agent_config, project_id="p1")

    assert isinstance(svc.datasource, EnterpriseDatasourceService)
    assert isinstance(svc.mcp, EnterpriseMCPService)
    assert isinstance(svc.dashboard, EnterpriseDashboardService)
    assert isinstance(svc.report, EnterpriseReportService)
    assert isinstance(svc.success_story, EnterpriseSuccessStoryService)
