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


class CollectingAuditSink:
    def __init__(self):
        self.events = []

    async def write(self, event):
        self.events.append(event)


def _enterprise_extensions(audit_sink=None) -> EnterpriseExtensions:
    return EnterpriseExtensions(
        enabled=True,
        authorization_provider=LocalAuthorizationProvider(),
        config_projector=PassthroughConfigProjector(),
        session_owner_store=InMemorySessionOwnerStore(),
        audit_sink=audit_sink or NoopAuditSink(),
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

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = override_service
    app.dependency_overrides[deps.get_request_app_context] = override_context
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
def test_mcp_rbac_denial_does_not_resolve_datus_service(monkeypatch, method, path, json_body):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.chat"})
    app = FastAPI()
    app.include_router(mcp_routes.router)

    async def reject_service(request: Request):
        raise AssertionError("RBAC denial resolved DatusService")

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = reject_service
    app.dependency_overrides[deps.get_request_app_context] = override_context

    with TestClient(app, raise_server_exceptions=False) as client:
        response = (
            getattr(client, method)(path, json=json_body) if json_body is not None else getattr(client, method)(path)
        )

    assert response.status_code == 403


def test_mcp_routes_allow_module_mcp(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = _svc()
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.mcp", "mcp.server.list"})

    with _client(ctx, svc) as client:
        response = client.get("/api/v1/mcp/servers")

    assert response.status_code == 200
    assert response.json()["success"] is True
    svc.mcp.list_servers.assert_called_once_with(server_type=None)


@pytest.mark.parametrize(
    ("path", "expected_permission", "service_attr"),
    [
        ("/api/v1/mcp/servers", "mcp.server.list", "list_servers"),
        ("/api/v1/mcp/servers/srv/tools", "mcp.server.tools", "list_tools"),
        ("/api/v1/mcp/servers/srv/filters", "mcp.filter.view", "get_tool_filter"),
    ],
)
def test_mcp_read_routes_require_fine_grained_permission(
    monkeypatch,
    path,
    expected_permission,
    service_attr,
):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = _svc()
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.mcp"})

    with _client(ctx, svc) as client:
        response = client.get(path)

    assert response.status_code == 403
    assert expected_permission in response.json()["detail"]
    service_method = getattr(svc.mcp, service_attr)
    if isinstance(service_method, AsyncMock):
        service_method.assert_not_awaited()
    else:
        service_method.assert_not_called()


@pytest.mark.parametrize(
    ("path", "expected_permission"),
    [
        ("/api/v1/mcp/servers", "mcp.server.list"),
        ("/api/v1/mcp/servers/srv/tools", "mcp.server.tools"),
        ("/api/v1/mcp/servers/srv/filters", "mcp.filter.view"),
    ],
)
def test_mcp_read_permission_denial_does_not_resolve_datus_service(
    monkeypatch,
    path,
    expected_permission,
):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.mcp"})
    app = FastAPI()
    app.include_router(mcp_routes.router)

    async def reject_service(request: Request):
        raise AssertionError("MCP read permission denial resolved DatusService")

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = reject_service
    app.dependency_overrides[deps.get_request_app_context] = override_context

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(path)

    assert response.status_code == 403
    assert expected_permission in response.json()["detail"]


@pytest.mark.parametrize(
    ("path", "permission", "service_attr"),
    [
        ("/api/v1/mcp/servers", "mcp.server.list", "list_servers"),
        ("/api/v1/mcp/servers/srv/tools", "mcp.server.tools", "list_tools"),
        ("/api/v1/mcp/servers/srv/filters", "mcp.filter.view", "get_tool_filter"),
    ],
)
def test_mcp_read_routes_allow_matching_fine_grained_permission(
    monkeypatch,
    path,
    permission,
    service_attr,
):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = _svc()
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.mcp", permission})

    with _client(ctx, svc) as client:
        response = client.get(path)

    assert response.status_code == 200
    assert response.json()["success"] is True
    service_method = getattr(svc.mcp, service_attr)
    if isinstance(service_method, AsyncMock):
        service_method.assert_awaited_once()
    else:
        service_method.assert_called_once()


def test_mcp_list_tools_ignores_client_filter_bypass(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = _svc()
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.mcp", "mcp.server.tools"})

    with _client(ctx, svc) as client:
        response = client.get("/api/v1/mcp/servers/srv/tools?apply_filter=false")

    assert response.status_code == 200
    assert response.json()["success"] is True
    svc.mcp.list_tools.assert_awaited_once_with("srv", True)


def test_mcp_tool_call_requires_fine_grained_tool_permission(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = _svc()
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.mcp"})

    with _client(ctx, svc) as client:
        response = client.post("/api/v1/mcp/servers/srv/tools/tool_a/call", json={"parameters": {"x": 1}})

    assert response.status_code == 403
    assert "mcp.srv.tool_a" in response.json()["detail"]
    svc.mcp.call_tool.assert_not_awaited()


def test_mcp_tool_permission_denial_does_not_resolve_datus_service(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.mcp"})
    app = FastAPI()
    app.include_router(mcp_routes.router)

    async def reject_service(request: Request):
        raise AssertionError("tool permission denial resolved DatusService")

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = reject_service
    app.dependency_overrides[deps.get_request_app_context] = override_context

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/api/v1/mcp/servers/srv/tools/tool_a/call", json={"parameters": {"x": 1}})

    assert response.status_code == 403
    assert "mcp.srv.tool_a" in response.json()["detail"]


def test_mcp_fine_grained_permission_denial_precedes_readonly_status(monkeypatch):
    audit_sink = CollectingAuditSink()
    monkeypatch.setenv("DATUS_PLATFORM_STATUS", "readonly")
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions(audit_sink=audit_sink))
    svc = _svc()
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.mcp"})

    with _client(ctx, svc) as client:
        response = client.post("/api/v1/mcp/servers/srv/tools/tool_a/call", json={"parameters": {"x": 1}})

    assert response.status_code == 403
    assert "mcp.srv.tool_a" in response.json()["detail"]
    assert audit_sink.events[-1].action == "mcp.srv.tool_a"
    svc.mcp.call_tool.assert_not_awaited()


def test_mcp_tool_call_allows_matching_fine_grained_tool_permission(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = _svc()
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.mcp", "mcp.srv.tool_a"})

    with _client(ctx, svc) as client:
        response = client.post("/api/v1/mcp/servers/srv/tools/tool_a/call", json={"parameters": {"x": 1}})

    assert response.status_code == 200
    assert response.json()["success"] is True
    svc.mcp.call_tool.assert_awaited_once()


@pytest.mark.parametrize(
    ("method", "path", "json_body", "expected_permission", "service_attr"),
    [
        (
            "post",
            "/api/v1/mcp/servers",
            {"name": "srv", "type": "stdio", "command": "python"},
            "mcp.server.add",
            "add_server",
        ),
        ("delete", "/api/v1/mcp/servers/srv", None, "mcp.server.remove", "remove_server"),
        ("get", "/api/v1/mcp/servers/srv/connectivity", None, "mcp.server.connectivity", "check_connectivity"),
        (
            "put",
            "/api/v1/mcp/servers/srv/filters",
            {"enabled": True, "allowed_tools": ["tool_a"]},
            "mcp.filter.set",
            "set_tool_filter",
        ),
        ("delete", "/api/v1/mcp/servers/srv/filters", None, "mcp.filter.remove", "remove_tool_filter"),
    ],
)
def test_mcp_management_execution_requires_fine_grained_permission(
    monkeypatch,
    method,
    path,
    json_body,
    expected_permission,
    service_attr,
):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = _svc()
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.mcp"})

    with _client(ctx, svc) as client:
        response = (
            getattr(client, method)(path, json=json_body) if json_body is not None else getattr(client, method)(path)
        )

    assert response.status_code == 403
    assert expected_permission in response.json()["detail"]
    service_method = getattr(svc.mcp, service_attr)
    if isinstance(service_method, AsyncMock):
        service_method.assert_not_awaited()
    else:
        service_method.assert_not_called()


def test_mcp_add_permission_denial_with_invalid_body_does_not_resolve_datus_service(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.mcp"})
    app = FastAPI()
    app.include_router(mcp_routes.router)

    async def reject_service(request: Request):
        raise AssertionError("MCP add permission denial resolved DatusService")

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = reject_service
    app.dependency_overrides[deps.get_request_app_context] = override_context

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/api/v1/mcp/servers", json={"bad": "body"})

    assert response.status_code == 403
    assert "mcp.server.add" in response.json()["detail"]


@pytest.mark.parametrize(
    ("method", "path", "permission"),
    [
        ("post", "/api/v1/mcp/servers", "mcp.server.add"),
        ("post", "/api/v1/mcp/servers/srv/tools/tool_a/call", "mcp.srv.tool_a"),
        ("put", "/api/v1/mcp/servers/srv/filters", "mcp.filter.set"),
    ],
)
def test_mcp_invalid_body_does_not_resolve_datus_service(monkeypatch, method, path, permission):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.mcp", permission})
    app = FastAPI()
    app.include_router(mcp_routes.router)

    async def reject_service(request: Request):
        raise AssertionError("Invalid body resolved DatusService")

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = reject_service
    app.dependency_overrides[deps.get_request_app_context] = override_context

    with TestClient(app, raise_server_exceptions=False) as client:
        response = getattr(client, method)(path, json=[])

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("method", "path", "json_body", "permission", "service_attr"),
    [
        (
            "post",
            "/api/v1/mcp/servers",
            {"name": "srv", "type": "stdio", "command": "python"},
            "mcp.server.add",
            "add_server",
        ),
        ("delete", "/api/v1/mcp/servers/srv", None, "mcp.server.remove", "remove_server"),
        ("get", "/api/v1/mcp/servers/srv/connectivity", None, "mcp.server.connectivity", "check_connectivity"),
        (
            "put",
            "/api/v1/mcp/servers/srv/filters",
            {"enabled": True, "allowed_tools": ["tool_a"]},
            "mcp.filter.set",
            "set_tool_filter",
        ),
        ("delete", "/api/v1/mcp/servers/srv/filters", None, "mcp.filter.remove", "remove_tool_filter"),
    ],
)
def test_mcp_management_execution_allows_matching_fine_grained_permission(
    monkeypatch,
    method,
    path,
    json_body,
    permission,
    service_attr,
):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = _svc()
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.mcp", permission})

    with _client(ctx, svc) as client:
        response = (
            getattr(client, method)(path, json=json_body) if json_body is not None else getattr(client, method)(path)
        )

    assert response.status_code == 200
    assert response.json()["success"] is True
    service_method = getattr(svc.mcp, service_attr)
    if isinstance(service_method, AsyncMock):
        service_method.assert_awaited_once()
    else:
        service_method.assert_called_once()


@pytest.mark.parametrize(
    ("method", "path", "json_body", "operation", "permission"),
    [
        (
            "post",
            "/api/v1/mcp/servers",
            {"name": "srv", "type": "stdio", "command": "python"},
            "mcp.server.add",
            "mcp.server.add",
        ),
        ("delete", "/api/v1/mcp/servers/srv", None, "mcp.server.remove", "mcp.server.remove"),
        ("get", "/api/v1/mcp/servers/srv/connectivity", None, "mcp.server.connectivity", "mcp.server.connectivity"),
        (
            "post",
            "/api/v1/mcp/servers/srv/tools/tool_a/call",
            {"parameters": {"x": 1}},
            "mcp.tool.call",
            "mcp.srv.tool_a",
        ),
        (
            "put",
            "/api/v1/mcp/servers/srv/filters",
            {"enabled": True, "allowed_tools": ["tool_a"]},
            "mcp.filter.set",
            "mcp.filter.set",
        ),
        ("delete", "/api/v1/mcp/servers/srv/filters", None, "mcp.filter.remove", "mcp.filter.remove"),
    ],
)
def test_mcp_execution_and_mutation_routes_block_readonly_before_service(
    monkeypatch, method, path, json_body, operation, permission
):
    audit_sink = CollectingAuditSink()
    monkeypatch.setenv("DATUS_PLATFORM_STATUS", "readonly")
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions(audit_sink=audit_sink))
    svc = _svc()
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.mcp", permission})

    with _client(ctx, svc) as client:
        response = (
            getattr(client, method)(path, json=json_body) if json_body is not None else getattr(client, method)(path)
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "PLATFORM_STATUS_FORBIDDEN"
    assert audit_sink.events[-1].action == "system.platform_status"
    assert audit_sink.events[-1].metadata == {"operation": operation, "platform_status": "readonly"}
    svc.mcp.add_server.assert_not_called()
    svc.mcp.remove_server.assert_not_called()
    svc.mcp.check_connectivity.assert_not_awaited()
    svc.mcp.call_tool.assert_not_awaited()
    svc.mcp.set_tool_filter.assert_not_called()
    svc.mcp.remove_tool_filter.assert_not_called()
