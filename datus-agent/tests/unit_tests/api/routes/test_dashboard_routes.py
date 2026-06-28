from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.enterprise.defaults import InMemorySessionOwnerStore, LocalAuthorizationProvider, NoopAuditSink
from datus.api.enterprise.loader import EnterpriseExtensions
from datus.api.models.base_models import Result
from datus.api.models.dashboard_models import DashboardQueryRequest, SqlQueryResultEnvelope
from datus.api.routes import dashboard_routes
from datus_enterprise.config_projection import DatasourceGrantConfigProjector


def test_dashboard_query_invalid_body_does_not_resolve_datus_service(monkeypatch):
    ctx = AppContext(
        user_id="alice",
        project_id="enterprise",
        permissions={"module.dashboard.query"},
        datasource_grants={"finance": {"effect": "allow", "allow_sql": True}},
    )
    app = FastAPI()
    app.include_router(dashboard_routes.router)

    async def reject_service(request: Request):
        raise AssertionError("Invalid body resolved DatusService")

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = reject_service
    app.dependency_overrides[deps.get_request_app_context] = override_context
    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=True,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=DatasourceGrantConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=NoopAuditSink(),
        ),
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/api/v1/dashboard/query", json=[])

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_dashboard_query_returns_result_when_post_execute_audit_fails(monkeypatch):
    agent_config = SimpleNamespace(current_datasource="default", project_root="/tmp/project")
    svc = SimpleNamespace(
        agent_config=agent_config,
        dashboard=SimpleNamespace(
            run_query=AsyncMock(
                return_value=Result[SqlQueryResultEnvelope](
                    success=True,
                    data=SqlQueryResultEnvelope(
                        executed_at="2026-06-28T00:00:00Z",
                        datasource="default",
                        row_count=1,
                        columns=[],
                        rows=[{"answer": 1}],
                        sql="SELECT 1",
                    ),
                )
            )
        ),
    )
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.dashboard.query"})

    async def project_config(*args, **kwargs):
        return SimpleNamespace(config=agent_config, principal={"datasource": "default"})

    async def quota_ok(*args, **kwargs):
        return None

    async def fail_audit(*args, **kwargs):
        raise RuntimeError("audit down")

    monkeypatch.setattr(dashboard_routes, "_resolve_request_service", AsyncMock(return_value=svc))
    monkeypatch.setattr(dashboard_routes, "require_artifact_access", AsyncMock())
    monkeypatch.setattr(dashboard_routes, "project_request_config", project_config)
    monkeypatch.setattr(dashboard_routes, "consume_enterprise_quota", quota_ok)
    monkeypatch.setattr(dashboard_routes, "audit_decision", fail_audit)

    result = await dashboard_routes.run_dashboard_query(
        DashboardQueryRequest(dashboard_slug="sales", query_slug="summary", params={}),
        ctx,
        SimpleNamespace(),
    )

    assert result.success is True
    assert result.data.datasource == "default"
    assert result.data.row_count == 1
    svc.dashboard.run_query.assert_awaited_once()
