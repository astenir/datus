"""Enterprise-mode disable strategy for legacy API route surfaces."""

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.enterprise.defaults import (
    InMemorySessionOwnerStore,
    LocalAuthorizationProvider,
    NoopAuditSink,
    PassthroughConfigProjector,
)
from datus.api.enterprise.loader import EnterpriseExtensions
from datus.api.routes import agent_routes, explorer_routes, success_story_routes, tool_routes, visualization_routes


class CollectingAuditSink:
    def __init__(self):
        self.events = []

    async def write(self, event):
        self.events.append(event)


class StaticAuthProvider:
    def __init__(self, ctx: AppContext):
        self.ctx = ctx

    async def authenticate(self, request: Request) -> AppContext:
        request.state.app_context = self.ctx
        return self.ctx


def _install_extensions(monkeypatch, audit_sink):
    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=True,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=audit_sink,
        ),
    )


def _client(monkeypatch, router, ctx: AppContext):
    monkeypatch.setattr(deps, "_auth_provider", StaticAuthProvider(ctx))
    app = FastAPI()
    app.include_router(router)

    async def reject_service(request: Request):
        raise AssertionError("legacy disabled route resolved DatusService")

    app.dependency_overrides[deps.get_datus_service] = reject_service
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize(
    ("router", "method", "path", "json_body", "operation"),
    [
        (explorer_routes.router, "get", "/api/v1/subject/list", None, "explorer.legacy"),
        (agent_routes.router, "get", "/api/v1/agent/list", None, "agent.config_legacy"),
        (
            visualization_routes.router,
            "post",
            "/api/v1/data_visualization",
            {"csv_data": "id,value\n1,2\n", "chart_type": None, "sql": None, "user_question": None},
            "visualization.legacy",
        ),
        (tool_routes.router, "post", "/api/v1/tools/db_tools.read_query", {}, "tools.direct_dispatch"),
        (
            success_story_routes.router,
            "post",
            "/api/v1/success-stories",
            {"messages": [], "metadata": {}},
            "success_stories.write_legacy",
        ),
    ],
)
def test_legacy_routes_are_disabled_in_enterprise_mode(monkeypatch, router, method, path, json_body, operation):
    audit_sink = CollectingAuditSink()
    _install_extensions(monkeypatch, audit_sink)
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.admin.*"})

    with _client(monkeypatch, router, ctx) as client:
        response = getattr(client, method)(path, json=json_body) if json_body is not None else getattr(client, method)(path)

    assert response.status_code == 403
    assert response.json()["detail"] == "ENTERPRISE_ROUTE_DISABLED"
    event = audit_sink.events[-1]
    assert event.user_id == "u1"
    assert event.action == "system.route_disabled"
    assert event.resource_type == "legacy_api"
    assert event.decision == "deny"
    assert event.metadata == {"operation": operation}


def test_local_agent_static_helper_does_not_require_service_initialization(monkeypatch):
    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=False,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=NoopAuditSink(),
        ),
    )
    monkeypatch.setattr(deps, "_auth_provider", None)
    monkeypatch.setattr(deps, "_service_cache", None)
    app = FastAPI()
    app.include_router(agent_routes.router)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/agent/use_tools", params={"agent_type": "gen_sql"})

    assert response.status_code == 200
    assert response.json()["success"] is True
