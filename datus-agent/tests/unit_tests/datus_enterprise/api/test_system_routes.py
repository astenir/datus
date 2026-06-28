from types import SimpleNamespace

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
from datus.api.service import create_app
from datus_enterprise.api import system_routes


def _install_extensions(monkeypatch, *, enabled=True):
    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=enabled,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=NoopAuditSink(),
        ),
    )


def _svc():
    return SimpleNamespace(
        agent_config=SimpleNamespace(current_datasource="finance"),
        task_manager=SimpleNamespace(
            list_task_snapshots=lambda: [
                {"session_id": "s1", "is_running": True},
                {"session_id": "s2", "is_running": False},
            ]
        ),
    )


def _client(ctx: AppContext, svc=None):
    app = FastAPI()
    app.include_router(system_routes.router)

    async def override_service(request: Request):
        request.state.app_context = ctx
        return svc or _svc()

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = override_service
    app.dependency_overrides[deps.get_request_app_context] = override_context
    return TestClient(app)


def test_system_status_requires_permission(monkeypatch):
    _install_extensions(monkeypatch)
    ctx = AppContext(user_id="u1", permissions={"module.admin.audit"})

    with _client(ctx) as client:
        response = client.get("/api/v1/system/status")

    assert response.status_code == 403
    assert "module.system.status" in response.json()["detail"]


def test_system_status_rbac_denial_does_not_resolve_datus_service(monkeypatch):
    _install_extensions(monkeypatch)
    ctx = AppContext(user_id="u1", permissions={"module.admin.audit"})
    app = FastAPI()
    app.include_router(system_routes.router)

    async def reject_service(request: Request):
        raise AssertionError("RBAC denial resolved DatusService")

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = reject_service
    app.dependency_overrides[deps.get_request_app_context] = override_context

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/system/status")

    assert response.status_code == 403


def test_system_status_returns_sanitized_summary(monkeypatch):
    _install_extensions(monkeypatch, enabled=True)
    monkeypatch.setenv("DATUS_PLATFORM_STATUS", "readonly")
    ctx = AppContext(user_id="operator", project_id="proj_a", permissions={"module.system.status"})

    with _client(ctx) as client:
        response = client.get("/api/v1/system/status")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"] == {
        "platform_status": "readonly",
        "enterprise_enabled": True,
        "project_id": "proj_a",
        "current_datasource": "finance",
        "active_tasks": 1,
        "known_tasks": 2,
    }


def test_system_status_handles_missing_task_manager(monkeypatch):
    _install_extensions(monkeypatch, enabled=False)
    monkeypatch.setenv("DATUS_PLATFORM_STATUS", "invalid")
    ctx = AppContext(user_id="operator", project_id="proj_a", permissions={"module.system.status"})
    svc = SimpleNamespace(agent_config=SimpleNamespace(current_datasource=None))

    with _client(ctx, svc=svc) as client:
        response = client.get("/api/v1/system/status")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["platform_status"] == "unknown"
    assert body["data"]["enterprise_enabled"] is False
    assert body["data"]["active_tasks"] == 0
    assert body["data"]["known_tasks"] == 0


def test_enterprise_system_routes_are_registered():
    args = SimpleNamespace(config="", datasource="default", output_dir="./output", log_level="INFO")
    app = create_app(args)
    route_paths = {route.path for route in app.routes if hasattr(route, "path")}

    assert "/api/v1/system/status" in route_paths
