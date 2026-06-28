"""Enterprise-mode disable strategy for legacy API route surfaces."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.enterprise.defaults import (
    InMemorySessionOwnerStore,
    LocalAuthorizationProvider,
    PassthroughConfigProjector,
)
from datus.api.enterprise.loader import EnterpriseExtensions
from datus.api.routes import agent_routes, explorer_routes, success_story_routes, tool_routes, visualization_routes


class CollectingAuditSink:
    def __init__(self):
        self.events = []

    async def write(self, event):
        self.events.append(event)


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


def _client(router, ctx: AppContext, svc):
    app = FastAPI()
    app.include_router(router)

    async def override_service(request: Request):
        request.state.app_context = ctx
        return svc

    app.dependency_overrides[deps.get_datus_service] = override_service
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
    svc = MagicMock()
    svc.agent_config = SimpleNamespace()
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.admin.*"})

    with _client(router, ctx, svc) as client:
        response = getattr(client, method)(path, json=json_body) if json_body is not None else getattr(client, method)(path)

    assert response.status_code == 403
    assert response.json()["detail"] == "ENTERPRISE_ROUTE_DISABLED"
    assert svc.mock_calls == []
    event = audit_sink.events[-1]
    assert event.user_id == "u1"
    assert event.action == "system.route_disabled"
    assert event.resource_type == "legacy_api"
    assert event.decision == "deny"
    assert event.metadata == {"operation": operation}
