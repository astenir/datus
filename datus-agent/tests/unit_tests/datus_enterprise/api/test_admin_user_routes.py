import asyncio
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
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
from datus_enterprise.api import admin_user_routes


class CollectingAuditSink:
    def __init__(self):
        self.events = []

    async def write(self, event):
        self.events.append(event)


class FailingAuditSink:
    async def write(self, event):
        raise RuntimeError("audit down")


def _install_extensions(monkeypatch, user_store, audit_sink=None, *, role_store=None, grant_store=None, enabled=False):
    monkeypatch.setattr(
        admin_user_routes.deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=enabled,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=audit_sink or NoopAuditSink(),
            user_store=user_store,
            role_store=role_store or InMemoryEnterpriseRoleStore(),
            datasource_grant_store=grant_store or InMemoryEnterpriseDatasourceGrantStore(),
        ),
    )


def _client(ctx: AppContext):
    app = FastAPI()
    app.include_router(admin_user_routes.router)

    async def override_service(request: Request):
        request.state.app_context = ctx
        return SimpleNamespace()

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = override_service
    app.dependency_overrides[deps.get_request_app_context] = override_context
    return TestClient(app)


def test_admin_users_rejects_without_permission(monkeypatch):
    _install_extensions(monkeypatch, InMemoryEnterpriseUserStore())
    ctx = AppContext(user_id="operator", permissions={"module.admin.sessions"})

    with _client(ctx) as client:
        response = client.get("/api/v1/admin/users")

    assert response.status_code == 403
    assert "module.admin.users" in response.json()["detail"]


def test_admin_user_upsert_get_and_list_audit_sanitized(monkeypatch):
    user_store = InMemoryEnterpriseUserStore()
    role_store = InMemoryEnterpriseRoleStore()
    grant_store = InMemoryEnterpriseDatasourceGrantStore()
    audit_sink = CollectingAuditSink()
    _install_extensions(monkeypatch, user_store, audit_sink, role_store=role_store, grant_store=grant_store)
    ctx = AppContext(user_id="operator", permissions={"module.admin.users"})
    asyncio.run(role_store.upsert_role(role_id="analyst", name="Analyst", permissions=["module.chat"]))
    asyncio.run(role_store.upsert_role(role_id="viewer", name="Viewer", permissions=["module.report.view"]))
    asyncio.run(role_store.set_user_roles("alice", ["viewer", "analyst"]))
    asyncio.run(
        grant_store.put_grant(
            subject_type="user",
            subject_id="alice",
            datasource_key="db_a",
            effect="allow",
            scope={"tables": ["orders"]},
        )
    )
    asyncio.run(
        grant_store.put_grant(
            subject_type="role",
            subject_id="analyst",
            datasource_key="db_b",
            effect="allow",
            scope={},
        )
    )

    with _client(ctx) as client:
        upsert_response = client.put(
            "/api/v1/admin/users/alice",
            json={
                "display_name": "Alice",
                "email": "alice@example.com",
                "enabled": True,
                "external_user_id": "698",
                "department": "fund",
                "title": "analyst",
                "last_seen_at": "2026-01-01T00:00:00+00:00",
            },
        )
        get_response = client.get("/api/v1/admin/users/alice")
        list_response = client.get("/api/v1/admin/users")

    assert upsert_response.status_code == 200
    assert upsert_response.json()["success"] is True
    upsert_data = upsert_response.json()["data"]
    assert {key: upsert_data[key] for key in ("user_id", "display_name", "email", "enabled")} == {
        "user_id": "alice",
        "display_name": "Alice",
        "email": "alice@example.com",
        "enabled": True,
    }
    assert {key: upsert_data[key] for key in ("external_user_id", "department", "title", "last_seen_at")} == {
        "external_user_id": "698",
        "department": "fund",
        "title": "analyst",
        "last_seen_at": "2026-01-01T00:00:00+00:00",
    }
    assert isinstance(upsert_data["created_at"], str)
    assert isinstance(upsert_data["updated_at"], str)
    detail = get_response.json()["data"]
    assert detail["user_id"] == "alice"
    assert detail["role_ids"] == ["analyst", "viewer"]
    assert detail["role_count"] == 2
    assert detail["roles"] == [
        {"role_id": "analyst", "name": "Analyst", "permissions": ["module.chat"], "built_in": False},
        {"role_id": "viewer", "name": "Viewer", "permissions": ["module.report.view"], "built_in": False},
    ]
    assert detail["effective_permissions"] == ["module.chat", "module.report.view"]
    assert detail["direct_datasource_grant_count"] == 1
    assert detail["direct_datasource_grants"][0]["subject_type"] == "user"
    assert detail["direct_datasource_grants"][0]["subject_id"] == "alice"
    assert detail["direct_datasource_grants"][0]["datasource_key"] == "db_a"
    assert detail["direct_datasource_grants"][0]["scope"] == {"tables": ["orders"]}
    assert detail["role_datasource_grant_count"] == 1
    assert detail["role_datasource_grants"][0]["subject_type"] == "role"
    assert detail["role_datasource_grants"][0]["subject_id"] == "analyst"
    assert detail["role_datasource_grants"][0]["datasource_key"] == "db_b"
    assert detail["effective_datasource_grant_count"] == 2

    list_user = list_response.json()["data"][0]
    assert list_user["user_id"] == "alice"
    assert list_user["role_ids"] == ["analyst", "viewer"]
    assert list_user["role_count"] == 2
    assert list_user["direct_datasource_grant_count"] == 1
    assert "roles" not in list_user
    assert "direct_datasource_grants" not in list_user
    assert "password" not in list_response.text

    assert audit_sink.events[-3].action == "module.admin.users"
    assert audit_sink.events[-3].resource_type == "user"
    assert audit_sink.events[-3].resource_id == "alice"
    assert audit_sink.events[-3].decision == "allow"
    assert audit_sink.events[-3].metadata["operation"] == "upsert_admin_user"
    assert audit_sink.events[-3].metadata["new"] == {
        "user_id": "alice",
        "display_name": "Alice",
        "email": "alice@example.com",
        "enabled": True,
        "external_user_id": "698",
        "department": "fund",
        "title": "analyst",
    }


def test_admin_user_upsert_is_blocked_in_readonly_status_and_audited(monkeypatch):
    user_store = InMemoryEnterpriseUserStore()
    audit_sink = CollectingAuditSink()
    monkeypatch.setenv("DATUS_PLATFORM_STATUS", "readonly")
    _install_extensions(monkeypatch, user_store, audit_sink, enabled=True)
    ctx = AppContext(user_id="operator", permissions={"module.admin.users"})

    with _client(ctx) as client:
        response = client.put(
            "/api/v1/admin/users/alice",
            json={"display_name": "Alice", "email": "alice@example.com", "enabled": True},
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "PLATFORM_STATUS_FORBIDDEN"
    assert asyncio.run(user_store.list_users()) == []
    event = audit_sink.events[-1]
    assert event.action == "system.platform_status"
    assert event.resource_type == "user"
    assert event.decision == "deny"
    assert event.metadata == {"operation": "admin.users.upsert", "platform_status": "readonly"}


def test_admin_user_upsert_rbac_denial_precedes_readonly_status(monkeypatch):
    user_store = InMemoryEnterpriseUserStore()
    audit_sink = CollectingAuditSink()
    monkeypatch.setenv("DATUS_PLATFORM_STATUS", "readonly")
    _install_extensions(monkeypatch, user_store, audit_sink, enabled=True)
    ctx = AppContext(user_id="operator", permissions={"module.admin.sessions"})

    with _client(ctx) as client:
        response = client.put(
            "/api/v1/admin/users/alice",
            json={"display_name": "Alice", "email": "alice@example.com", "enabled": True},
        )

    assert response.status_code == 403
    assert "module.admin.users" in response.json()["detail"]
    assert asyncio.run(user_store.list_users()) == []
    assert [event.action for event in audit_sink.events] == ["module.admin.users"]


def test_admin_users_enabled_filter_and_toggle(monkeypatch):
    user_store = InMemoryEnterpriseUserStore()
    audit_sink = CollectingAuditSink()
    _install_extensions(monkeypatch, user_store, audit_sink)
    ctx = AppContext(user_id="operator", permissions={"module.admin.users"})

    with _client(ctx) as client:
        client.put("/api/v1/admin/users/alice", json={"display_name": "Alice", "enabled": True})
        client.put("/api/v1/admin/users/bob", json={"display_name": "Bob", "enabled": False})
        disabled_response = client.get("/api/v1/admin/users", params={"enabled": False})
        disable_response = client.post("/api/v1/admin/users/alice/disable")
        enable_response = client.post("/api/v1/admin/users/bob/enable")

    assert [item["user_id"] for item in disabled_response.json()["data"]] == ["bob"]
    assert disable_response.json()["data"]["enabled"] is False
    assert enable_response.json()["data"]["enabled"] is True
    assert audit_sink.events[-2].metadata["operation"] == "disable_admin_user"
    assert audit_sink.events[-1].metadata["operation"] == "enable_admin_user"


@pytest.mark.asyncio
async def test_admin_user_upsert_returns_success_when_post_write_audit_fails(monkeypatch):
    user_store = InMemoryEnterpriseUserStore()
    _install_extensions(monkeypatch, user_store, FailingAuditSink())
    ctx = AppContext(user_id="operator", permissions={"module.admin.users"})

    result = await admin_user_routes.upsert_admin_user(
        "alice",
        admin_user_routes.UpsertAdminUserRequest(display_name="Alice", email="alice@example.com", enabled=True),
        ctx,
    )

    assert result.success is True
    assert result.data.user_id == "alice"
    assert result.data.display_name == "Alice"
    stored = await user_store.get_user("alice")
    assert stored["display_name"] == "Alice"
    assert stored["email"] == "alice@example.com"


@pytest.mark.asyncio
async def test_admin_user_disable_returns_success_when_post_write_audit_fails(monkeypatch):
    user_store = InMemoryEnterpriseUserStore()
    await user_store.upsert_user(user_id="alice", display_name="Alice", email=None, enabled=True)
    _install_extensions(monkeypatch, user_store, FailingAuditSink())
    ctx = AppContext(user_id="operator", permissions={"module.admin.users"})

    result = await admin_user_routes.disable_admin_user("alice", ctx)

    assert result.success is True
    assert result.data.user_id == "alice"
    assert result.data.enabled is False
    assert (await user_store.get_user("alice"))["enabled"] is False


def test_admin_user_missing_and_invalid_id_return_result_errors(monkeypatch):
    audit_sink = CollectingAuditSink()
    _install_extensions(monkeypatch, InMemoryEnterpriseUserStore(), audit_sink)
    ctx = AppContext(user_id="operator", permissions={"module.admin.users"})

    with _client(ctx) as client:
        missing_response = client.get("/api/v1/admin/users/missing")
        invalid_response = client.put("/api/v1/admin/users/bad.id", json={})
        whitespace_response = client.put("/api/v1/admin/users/%20alice%20", json={})

    assert missing_response.status_code == 200
    assert missing_response.json()["success"] is False
    assert missing_response.json()["errorCode"] == "RESOURCE_NOT_FOUND"
    assert invalid_response.status_code == 200
    assert invalid_response.json()["success"] is False
    assert invalid_response.json()["errorCode"] == "USER_ID_INVALID"
    assert whitespace_response.status_code == 200
    assert whitespace_response.json()["success"] is False
    assert whitespace_response.json()["errorCode"] == "USER_ID_INVALID"
    assert audit_sink.events[-1].decision == "deny"


def test_admin_user_store_failure_returns_stable_error_and_audits(monkeypatch):
    class FailingUserStore(InMemoryEnterpriseUserStore):
        async def get_user(self, user_id):
            raise RuntimeError("store down")

    audit_sink = CollectingAuditSink()
    _install_extensions(monkeypatch, FailingUserStore(), audit_sink)
    ctx = AppContext(user_id="operator", permissions={"module.admin.users"})

    with _client(ctx) as client:
        response = client.get("/api/v1/admin/users/alice")

    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["errorCode"] == "USER_READ_FAILED"
    assert audit_sink.events[-1].decision == "deny"
    assert audit_sink.events[-1].reason == "user read failed"


def test_admin_user_routes_register_expected_paths():
    app = FastAPI()
    app.include_router(admin_user_routes.router)
    paths = {route.path for route in app.routes}

    assert "/api/v1/admin/users" in paths
    assert "/api/v1/admin/users/{user_id}" in paths
    assert "/api/v1/admin/users/{user_id}/disable" in paths
    assert "/api/v1/admin/users/{user_id}/enable" in paths
