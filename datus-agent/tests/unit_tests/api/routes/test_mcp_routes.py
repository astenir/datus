"""HTTP-level module RBAC coverage for datus/api/routes/mcp_routes.py."""

from unittest.mock import AsyncMock, MagicMock

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
from datus.api.models.base_models import Result
from datus.api.routes import mcp_routes


def _enterprise_extensions() -> EnterpriseExtensions:
    return EnterpriseExtensions(
        enabled=True,
        authorization_provider=LocalAuthorizationProvider(),
        config_projector=PassthroughConfigProjector(),
        session_owner_store=InMemorySessionOwnerStore(),
        audit_sink=NoopAuditSink(),
    )


def _svc() -> MagicMock:
    svc = MagicMock()
    svc.mcp.list_servers.return_value = Result[dict](success=True, data={"servers": []})
    svc.mcp.add_server.return_value = Result[dict](success=True, data={"name": "srv"})
    svc.mcp.remove_server.return_value = Result[dict](success=True, data={"removed": True})
    svc.mcp.check_connectivity = AsyncMock(return_value=Result[dict](success=True, data={"connected": True}))
    svc.mcp.list_tools = AsyncMock(return_value=Result[dict](success=True, data={"tools": []}))
    svc.mcp.call_tool = AsyncMock(return_value=Result[dict](success=True, data={"result": "ok"}))
    svc.mcp.get_tool_filter.return_value = Result[dict](success=True, data={"enabled": True})
    svc.mcp.set_tool_filter.return_value = Result[dict](success=True, data={"enabled": True})
    svc.mcp.remove_tool_filter.return_value = Result[dict](success=True, data={"removed": True})
    return svc


def _client(ctx: AppContext, svc: MagicMock) -> TestClient:
    app = FastAPI()
    app.include_router(mcp_routes.router)

    async def override_service(request: Request):
        request.state.app_context = ctx
        return svc

    app.dependency_overrides[deps.get_datus_service] = override_service
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    [
        ("get", "/api/v1/mcp/servers", None),
        ("post", "/api/v1/mcp/servers", {"name": "srv", "type": "stdio", "command": "python"}),
        ("delete", "/api/v1/mcp/servers/srv", None),
        ("get", "/api/v1/mcp/servers/srv/connectivity", None),
        ("get", "/api/v1/mcp/servers/srv/tools", None),
        ("post", "/api/v1/mcp/servers/srv/tools/tool_a/call", {"parameters": {"x": 1}}),
        ("get", "/api/v1/mcp/servers/srv/filters", None),
        ("put", "/api/v1/mcp/servers/srv/filters", {"enabled": True, "allowed_tools": ["tool_a"]}),
        ("delete", "/api/v1/mcp/servers/srv/filters", None),
    ],
)
def test_mcp_routes_require_module_mcp(monkeypatch, method, path, json_body):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = _svc()
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.chat"})

    with _client(ctx, svc) as client:
        response = (
            getattr(client, method)(path, json=json_body) if json_body is not None else getattr(client, method)(path)
        )

    assert response.status_code == 403
    svc.mcp.list_servers.assert_not_called()
    svc.mcp.add_server.assert_not_called()
    svc.mcp.remove_server.assert_not_called()
    svc.mcp.check_connectivity.assert_not_awaited()
    svc.mcp.list_tools.assert_not_awaited()
    svc.mcp.call_tool.assert_not_awaited()
    svc.mcp.get_tool_filter.assert_not_called()
    svc.mcp.set_tool_filter.assert_not_called()
    svc.mcp.remove_tool_filter.assert_not_called()


def test_mcp_routes_allow_module_mcp(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = _svc()
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.mcp"})

    with _client(ctx, svc) as client:
        response = client.get("/api/v1/mcp/servers")

    assert response.status_code == 200
    assert response.json()["success"] is True
    svc.mcp.list_servers.assert_called_once_with(server_type=None)
