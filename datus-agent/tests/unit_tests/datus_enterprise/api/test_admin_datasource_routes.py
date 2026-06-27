import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, Request
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.enterprise.defaults import (
    InMemoryEnterpriseDatasourceGrantStore,
    InMemoryEnterpriseRoleStore,
    InMemoryEnterpriseUserStore,
    InMemorySessionOwnerStore,
    LocalAuthorizationProvider,
    NoopAuditSink,
    PassthroughConfigProjector,
)
from datus.api.enterprise.loader import EnterpriseExtensions
from datus.configuration.project_config import ProjectOverride
from datus.utils.exceptions import DatusException
from datus_enterprise.api import admin_datasource_routes
from datus_enterprise.api.admin_datasource_routes import SetDefaultDatasourceRequest


def _svc():
    agent_config = SimpleNamespace(
        current_datasource="db_b",
        services=SimpleNamespace(
            default_datasource="db_a",
            datasources={
                "db_a": SimpleNamespace(type="sqlite", password="secret-a"),
                "db_b": {"type": "duckdb", "password": "secret-b"},
            },
        ),
    )
    return SimpleNamespace(agent_config=agent_config)


class CollectingAuditSink:
    def __init__(self):
        self.events = []

    async def write(self, event):
        self.events.append(event)


def _install_extensions(
    monkeypatch,
    *,
    audit_sink=None,
    user_store=None,
    role_store=None,
    datasource_grant_store=None,
    enabled=False,
):
    monkeypatch.setattr(
        admin_datasource_routes.deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=enabled,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=audit_sink or NoopAuditSink(),
            user_store=user_store or InMemoryEnterpriseUserStore(),
            role_store=role_store or InMemoryEnterpriseRoleStore(),
            datasource_grant_store=datasource_grant_store or InMemoryEnterpriseDatasourceGrantStore(),
        ),
    )


def test_list_admin_datasources_returns_sanitized_summaries_and_audits(monkeypatch):
    audit_sink = CollectingAuditSink()
    ctx = AppContext(user_id="u1", project_id="proj_a", permissions={"module.admin.datasources"})
    app = FastAPI()
    app.include_router(admin_datasource_routes.router)

    async def override_service(request: Request):
        request.state.app_context = ctx
        return _svc()

    app.dependency_overrides[deps.get_datus_service] = override_service
    _install_extensions(monkeypatch, audit_sink=audit_sink)

    with TestClient(app) as client:
        response = client.get("/api/v1/admin/datasources")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"] == [
        {"name": "db_a", "type": "sqlite", "is_default": False},
        {"name": "db_b", "type": "duckdb", "is_default": True},
    ]
    assert "secret" not in response.text
    event = audit_sink.events[-1]
    assert event.user_id == "u1"
    assert event.action == "module.admin.datasources"
    assert event.resource_type == "datasource"
    assert event.resource_id is None
    assert event.decision == "allow"
    assert event.metadata == {"operation": "list_admin_datasources", "count": 2}


def test_list_admin_datasources_rejects_without_admin_datasources(monkeypatch):
    ctx = AppContext(project_id="proj_a", permissions={"module.config.view"})
    app = FastAPI()
    app.include_router(admin_datasource_routes.router)

    async def override_service(request: Request):
        request.state.app_context = ctx
        return _svc()

    app.dependency_overrides[deps.get_datus_service] = override_service
    monkeypatch.setattr(
        admin_datasource_routes.deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=False,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=NoopAuditSink(),
        ),
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/admin/datasources")

    assert response.status_code == 403
    assert "module.admin.datasources" in response.json()["detail"]


def test_admin_datasource_grants_upsert_get_list_delete_and_audit(monkeypatch):
    user_store = InMemoryEnterpriseUserStore()
    role_store = InMemoryEnterpriseRoleStore()
    grant_store = InMemoryEnterpriseDatasourceGrantStore()
    audit_sink = CollectingAuditSink()
    asyncio.run(user_store.upsert_user(user_id="alice", display_name="Alice"))
    asyncio.run(role_store.upsert_role(role_id="analyst", name="Analyst"))

    ctx = AppContext(user_id="operator", project_id="proj_a", permissions={"module.admin.datasources"})
    app = FastAPI()
    app.include_router(admin_datasource_routes.router)

    async def override_service(request: Request):
        request.state.app_context = ctx
        return _svc()

    app.dependency_overrides[deps.get_datus_service] = override_service
    _install_extensions(
        monkeypatch,
        audit_sink=audit_sink,
        user_store=user_store,
        role_store=role_store,
        datasource_grant_store=grant_store,
    )

    with TestClient(app) as client:
        put_response = client.put(
            "/api/v1/admin/datasource-grants/role/analyst/db_a",
            json={"effect": "allow", "scope": {"schemas": ["public"], "tables": ["orders", "orders"]}},
        )
        replace_response = client.put(
            "/api/v1/admin/datasource-grants/role/analyst/db_a",
            json={"effect": "deny", "scope": {"allow_sql": False}},
        )
        get_response = client.get("/api/v1/admin/datasource-grants/role/analyst/db_a")
        list_response = client.get("/api/v1/admin/datasource-grants?subject_type=role")
        delete_response = client.delete("/api/v1/admin/datasource-grants/role/analyst/db_a")

    assert put_response.status_code == 200
    assert put_response.json()["data"]["scope"] == {"schemas": ["public"], "tables": ["orders"]}
    assert replace_response.json()["data"]["effect"] == "deny"
    assert replace_response.json()["data"]["scope"] == {"allow_sql": False}
    assert get_response.json()["data"]["effect"] == "deny"
    assert [item["datasource_key"] for item in list_response.json()["data"]] == ["db_a"]
    assert delete_response.json()["data"] == {"deleted": True}
    assert awaitable_list_grants(grant_store) == []

    operations = [event.metadata["operation"] for event in audit_sink.events]
    assert operations[-5:] == [
        "upsert_admin_datasource_grant",
        "upsert_admin_datasource_grant",
        "get_admin_datasource_grant",
        "list_admin_datasource_grants",
        "delete_admin_datasource_grant",
    ]
    assert audit_sink.events[-5].metadata["new"]["scope"] == {"schemas": ["public"], "tables": ["orders"]}
    assert audit_sink.events[-4].metadata["old"]["effect"] == "allow"
    assert audit_sink.events[-4].metadata["new"]["effect"] == "deny"


def test_admin_datasource_grants_validate_subject_datasource_and_scope(monkeypatch):
    user_store = InMemoryEnterpriseUserStore()
    role_store = InMemoryEnterpriseRoleStore()
    grant_store = InMemoryEnterpriseDatasourceGrantStore()
    audit_sink = CollectingAuditSink()
    asyncio.run(user_store.upsert_user(user_id="alice"))
    asyncio.run(role_store.upsert_role(role_id="analyst", name="Analyst"))

    ctx = AppContext(user_id="operator", project_id="proj_a", permissions={"module.admin.datasources"})
    app = FastAPI()
    app.include_router(admin_datasource_routes.router)

    async def override_service(request: Request):
        request.state.app_context = ctx
        return _svc()

    app.dependency_overrides[deps.get_datus_service] = override_service
    _install_extensions(
        monkeypatch,
        audit_sink=audit_sink,
        user_store=user_store,
        role_store=role_store,
        datasource_grant_store=grant_store,
    )

    with TestClient(app) as client:
        invalid_subject_response = client.put(
            "/api/v1/admin/datasource-grants/team/alice/db_a",
            json={"effect": "allow", "scope": {}},
        )
        missing_user_response = client.put(
            "/api/v1/admin/datasource-grants/user/missing/db_a",
            json={"effect": "allow", "scope": {}},
        )
        missing_role_response = client.put(
            "/api/v1/admin/datasource-grants/role/missing/db_a",
            json={"effect": "allow", "scope": {}},
        )
        missing_datasource_response = client.put(
            "/api/v1/admin/datasource-grants/user/alice/missing",
            json={"effect": "allow", "scope": {}},
        )
        invalid_scope_response = client.put(
            "/api/v1/admin/datasource-grants/user/alice/db_a",
            json={"effect": "allow", "scope": {"tables": "orders"}},
        )
        non_mapping_scope_response = client.put(
            "/api/v1/admin/datasource-grants/user/alice/db_a",
            json={"effect": "allow", "scope": []},
        )
        invalid_effect_response = client.put(
            "/api/v1/admin/datasource-grants/user/alice/db_a",
            json={"effect": "maybe", "scope": {}},
        )

    assert invalid_subject_response.json()["errorCode"] == "DATASOURCE_GRANT_SUBJECT_INVALID"
    assert missing_user_response.json()["errorCode"] == "RESOURCE_NOT_FOUND"
    assert missing_role_response.json()["errorCode"] == "RESOURCE_NOT_FOUND"
    assert missing_datasource_response.json()["errorCode"] == "DATASOURCE_NOT_FOUND"
    assert invalid_scope_response.json()["errorCode"] == "DATASOURCE_GRANT_SCOPE_INVALID"
    assert non_mapping_scope_response.status_code == 200
    assert non_mapping_scope_response.json()["errorCode"] == "DATASOURCE_GRANT_SCOPE_INVALID"
    assert invalid_effect_response.status_code == 200
    assert invalid_effect_response.json()["errorCode"] == "DATASOURCE_GRANT_EFFECT_INVALID"
    assert awaitable_list_grants(grant_store) == []
    assert [event.decision for event in audit_sink.events[-7:]] == [
        "deny",
        "deny",
        "deny",
        "deny",
        "deny",
        "deny",
        "deny",
    ]


def test_admin_datasource_grants_can_delete_stale_subject_or_datasource(monkeypatch):
    grant_store = InMemoryEnterpriseDatasourceGrantStore()
    asyncio.run(
        grant_store.put_grant(
            subject_type="user",
            subject_id="deleted_user",
            datasource_key="removed_db",
            effect="allow",
            scope={},
        )
    )

    ctx = AppContext(user_id="operator", project_id="proj_a", permissions={"module.admin.datasources"})
    app = FastAPI()
    app.include_router(admin_datasource_routes.router)

    async def override_service(request: Request):
        request.state.app_context = ctx
        return _svc()

    app.dependency_overrides[deps.get_datus_service] = override_service
    _install_extensions(monkeypatch, datasource_grant_store=grant_store)

    with TestClient(app) as client:
        response = client.delete("/api/v1/admin/datasource-grants/user/deleted_user/removed_db")

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert awaitable_list_grants(grant_store) == []


@pytest.mark.asyncio
async def test_set_project_default_datasource_persists_override_and_evicts(monkeypatch):
    saved = {}
    cache = MagicMock()
    cache.evict = AsyncMock()
    monkeypatch.setattr(admin_datasource_routes.deps, "_service_cache", cache)
    monkeypatch.setattr(admin_datasource_routes, "load_project_override", lambda: ProjectOverride(project_name="p"))

    def fake_save(override):
        saved["override"] = override

    monkeypatch.setattr(admin_datasource_routes, "save_project_override", fake_save)

    result = await admin_datasource_routes.set_project_default_datasource_endpoint(
        SetDefaultDatasourceRequest(name="db_b"),
        _svc(),
        AppContext(project_id="proj_a"),
    )

    assert result.success is True
    assert result.data == {"default_datasource": "db_b", "scope": "project"}
    assert saved["override"].default_datasource == "db_b"
    assert saved["override"].project_name == "p"
    cache.evict.assert_awaited_once_with("proj_a")


@pytest.mark.asyncio
async def test_set_project_default_datasource_evicts_enterprise_cache_key(monkeypatch):
    saved = {}
    cache = MagicMock()
    cache.evict = AsyncMock()
    monkeypatch.setattr(admin_datasource_routes.deps, "_service_cache", cache)
    monkeypatch.setattr(
        admin_datasource_routes.deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=True,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=NoopAuditSink(),
        ),
    )
    monkeypatch.setattr(admin_datasource_routes, "load_project_override", lambda: ProjectOverride(project_name="p"))
    monkeypatch.setattr(
        admin_datasource_routes, "save_project_override", lambda override: saved.setdefault("o", override)
    )

    result = await admin_datasource_routes.set_project_default_datasource_endpoint(
        SetDefaultDatasourceRequest(name="db_b"),
        _svc(),
        AppContext(project_id="proj_a"),
    )

    assert result.success is True
    cache.evict.assert_awaited_once_with("enterprise:proj_a")


@pytest.mark.asyncio
async def test_set_project_default_datasource_audits_through_enterprise_sink(monkeypatch):
    class CollectingAuditSink:
        def __init__(self):
            self.events = []

        async def write(self, event):
            self.events.append(event)

    audit_sink = CollectingAuditSink()
    cache = MagicMock()
    cache.evict = AsyncMock()
    monkeypatch.setattr(admin_datasource_routes.deps, "_service_cache", cache)
    monkeypatch.setattr(
        admin_datasource_routes.deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=True,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=audit_sink,
        ),
    )
    monkeypatch.setattr(admin_datasource_routes, "load_project_override", lambda: ProjectOverride(project_name="p"))
    monkeypatch.setattr(admin_datasource_routes, "save_project_override", lambda override: None)

    await admin_datasource_routes.set_project_default_datasource_endpoint(
        SetDefaultDatasourceRequest(name="db_b"),
        _svc(),
        AppContext(user_id="u1", project_id="proj_a", permissions={"module.admin.datasources"}),
    )

    assert audit_sink.events[-1].user_id == "u1"
    assert audit_sink.events[-1].action == "module.admin.datasources"
    assert audit_sink.events[-1].resource_id == "db_b"
    assert audit_sink.events[-1].decision == "allow"


def test_set_project_default_datasource_http_uses_app_context_dependency(monkeypatch):
    """HTTP route should authorize from request.state, not a query parameter named ctx."""

    saved = {}
    cache = MagicMock()
    cache.evict = AsyncMock()
    ctx = AppContext(project_id="proj_a", permissions={"module.admin.datasources"})
    app = FastAPI()
    app.include_router(admin_datasource_routes.router)

    async def override_service(request: Request):
        request.state.app_context = ctx
        return _svc()

    app.dependency_overrides[deps.get_datus_service] = override_service
    monkeypatch.setattr(admin_datasource_routes.deps, "_service_cache", cache)
    monkeypatch.setattr(
        admin_datasource_routes.deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=False,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=NoopAuditSink(),
        ),
    )
    monkeypatch.setattr(admin_datasource_routes, "load_project_override", lambda: ProjectOverride(project_name="p"))
    monkeypatch.setattr(
        admin_datasource_routes, "save_project_override", lambda override: saved.setdefault("o", override)
    )

    with TestClient(app) as client:
        response = client.put("/api/v1/admin/datasource-default", json={"name": "db_b"})

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert saved["o"].default_datasource == "db_b"
    cache.evict.assert_awaited_once_with("proj_a")


def test_set_project_default_datasource_http_rejects_config_edit_without_admin_datasources(monkeypatch):
    saved = {}
    cache = MagicMock()
    cache.evict = AsyncMock()
    ctx = AppContext(project_id="proj_a", permissions={"module.config.edit"})
    app = FastAPI()
    app.include_router(admin_datasource_routes.router)

    async def override_service(request: Request):
        request.state.app_context = ctx
        return _svc()

    app.dependency_overrides[deps.get_datus_service] = override_service
    monkeypatch.setattr(admin_datasource_routes.deps, "_service_cache", cache)
    monkeypatch.setattr(
        admin_datasource_routes.deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=False,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=NoopAuditSink(),
        ),
    )
    monkeypatch.setattr(
        admin_datasource_routes, "save_project_override", lambda override: saved.setdefault("o", override)
    )

    with TestClient(app) as client:
        response = client.put("/api/v1/admin/datasource-default", json={"name": "db_b"})

    assert response.status_code == 403
    assert "module.admin.datasources" in response.json()["detail"]
    assert saved == {}
    cache.evict.assert_not_awaited()


@pytest.mark.asyncio
async def test_set_project_default_datasource_rejects_unknown(monkeypatch):
    cache = MagicMock()
    cache.evict = AsyncMock()
    monkeypatch.setattr(admin_datasource_routes.deps, "_service_cache", cache)

    with pytest.raises(DatusException):
        await admin_datasource_routes.set_project_default_datasource_endpoint(
            SetDefaultDatasourceRequest(name="missing"),
            _svc(),
            AppContext(project_id="proj_a"),
        )

    cache.evict.assert_not_awaited()


def test_admin_datasource_routes_do_not_register_legacy_switch_path():
    route_paths = {route.path for route in admin_datasource_routes.router.routes if isinstance(route, APIRoute)}

    assert route_paths == {
        "/api/v1/admin/datasource-default",
        "/api/v1/admin/datasource-grants",
        "/api/v1/admin/datasource-grants/{subject_type}/{subject_id}/{datasource_key}",
        "/api/v1/admin/datasources",
    }


def awaitable_list_grants(store):
    return asyncio.run(store.list_grants())
