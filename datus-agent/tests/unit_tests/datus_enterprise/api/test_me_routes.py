import asyncio
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.enterprise.defaults import (
    InMemoryEnterpriseQuotaStore,
    InMemorySessionOwnerStore,
    LocalAuthorizationProvider,
    NoopAuditSink,
    PassthroughConfigProjector,
)
from datus.api.enterprise.loader import EnterpriseExtensions
from datus.api.models.base_models import Result
from datus.api.models.cli_models import ChatSessionData
from datus.api.service import create_app
from datus_enterprise.api import me_routes


def _install_extensions(monkeypatch, *, quota_store=None):
    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=True,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=NoopAuditSink(),
            quota_store=quota_store,
        ),
    )


def _svc():
    return SimpleNamespace(
        agent_config=SimpleNamespace(),
        chat=SimpleNamespace(
            list_sessions=lambda user_id=None, subagent_id=None: Result[ChatSessionData](
                success=True,
                data=ChatSessionData(sessions=[]),
            )
        ),
    )


def _client(ctx: AppContext, svc=None):
    app = FastAPI()
    app.include_router(me_routes.router)

    async def override_service(request: Request):
        request.state.app_context = ctx
        return svc or _svc()

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = override_service
    app.dependency_overrides[deps.get_request_app_context] = override_context
    return TestClient(app)


def test_me_returns_current_context_summary(monkeypatch):
    _install_extensions(monkeypatch)
    ctx = AppContext(
        user_id="u1",
        project_id="proj_a",
        roles=["analyst"],
        permissions={"module.chat", "module.dashboard.*"},
        datasource_grants={"finance": {"effect": "allow", "allow_sql": True}},
        is_admin=False,
    )

    with _client(ctx) as client:
        response = client.get("/api/v1/me")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["user_id"] == "u1"
    assert body["data"]["project_id"] == "proj_a"
    assert body["data"]["roles"] == ["analyst"]
    assert body["data"]["permissions"] == ["module.chat", "module.dashboard.*"]
    assert body["data"]["datasource_grants"] == {"finance": {"effect": "allow", "allow_sql": True}}
    assert body["data"]["features"]["chat"] is True
    assert body["data"]["features"]["dashboard_query"] is True
    assert body["data"]["features"]["sql_executor"] is False


def test_me_permissions_merges_principal_compatibility(monkeypatch):
    _install_extensions(monkeypatch)
    ctx = AppContext(
        user_id="u1",
        permissions={"module.chat"},
        principal={"permissions": ["module.report.view"], "roles": ["principal-role"]},
        roles=["ctx-role"],
    )

    with _client(ctx) as client:
        permissions_response = client.get("/api/v1/me/permissions")
        summary_response = client.get("/api/v1/me")

    assert permissions_response.json()["data"] == ["module.chat", "module.report.view"]
    assert summary_response.json()["data"]["roles"] == ["ctx-role", "principal-role"]


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/me",
        "/api/v1/me/permissions",
        "/api/v1/me/datasource-grants",
        "/api/v1/me/features",
        "/api/v1/me/usage",
    ],
)
def test_current_user_metadata_routes_do_not_resolve_datus_service(monkeypatch, path):
    _install_extensions(monkeypatch)
    ctx = AppContext(user_id="u1", project_id="proj_a", permissions={"module.chat"})
    app = FastAPI()
    app.include_router(me_routes.router)

    async def reject_service(request: Request):
        raise AssertionError("Current-user metadata route resolved DatusService")

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = reject_service
    app.dependency_overrides[deps.get_request_app_context] = override_context

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(path)

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_me_sessions_uses_current_user_scope(monkeypatch):
    _install_extensions(monkeypatch)
    calls = []
    svc = SimpleNamespace(
        agent_config=SimpleNamespace(),
        chat=SimpleNamespace(
            list_sessions=lambda user_id=None, subagent_id=None: (
                calls.append((user_id, subagent_id))
                or Result[ChatSessionData](success=True, data=ChatSessionData(sessions=[]))
            )
        ),
    )
    ctx = AppContext(user_id="u1")

    with _client(ctx, svc=svc) as client:
        response = client.get("/api/v1/me/sessions")

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert calls == [("u1", None)]


def test_me_usage_returns_current_user_quota_usage(monkeypatch):
    quota_store = InMemoryEnterpriseQuotaStore()
    asyncio.run(
        quota_store.put_quota(
            subject_type="user",
            subject_id="u1",
            resource="chat.stream",
            limit=2,
            window_seconds=3600,
        )
    )
    asyncio.run(
        quota_store.consume_quota(
            subjects=[{"subject_type": "user", "subject_id": "u1"}],
            resource="chat.stream",
        )
    )
    _install_extensions(monkeypatch, quota_store=quota_store)
    ctx = AppContext(user_id="u1")

    with _client(ctx) as client:
        response = client.get("/api/v1/me/usage")

    assert response.status_code == 200
    usage = response.json()["data"]
    assert len(usage) == 1
    assert usage[0]["resource"] == "chat.stream"
    assert usage[0]["used"] == 1


def test_enterprise_me_routes_are_registered():
    args = SimpleNamespace(config="", datasource="default", output_dir="./output", log_level="INFO")
    app = create_app(args)
    route_paths = {route.path for route in app.routes if hasattr(route, "path")}

    assert "/api/v1/me" in route_paths
    assert "/api/v1/me/permissions" in route_paths
    assert "/api/v1/me/datasource-grants" in route_paths
    assert "/api/v1/me/features" in route_paths
    assert "/api/v1/me/sessions" in route_paths
    assert "/api/v1/me/usage" in route_paths
