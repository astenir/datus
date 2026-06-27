from types import SimpleNamespace

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.enterprise.defaults import (
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


def _install_extensions(monkeypatch, user_store, audit_sink=None):
    monkeypatch.setattr(
        admin_user_routes.deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=False,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=audit_sink or NoopAuditSink(),
            user_store=user_store,
        ),
    )


def _client(ctx: AppContext):
    app = FastAPI()
    app.include_router(admin_user_routes.router)

    async def override_service(request: Request):
        request.state.app_context = ctx
        return SimpleNamespace()

    app.dependency_overrides[deps.get_datus_service] = override_service
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
    audit_sink = CollectingAuditSink()
    _install_extensions(monkeypatch, user_store, audit_sink)
    ctx = AppContext(user_id="operator", permissions={"module.admin.users"})

    with _client(ctx) as client:
        upsert_response = client.put(
            "/api/v1/admin/users/alice",
            json={"display_name": "Alice", "email": "alice@example.com", "enabled": True},
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
    assert isinstance(upsert_data["created_at"], str)
    assert isinstance(upsert_data["updated_at"], str)
    assert get_response.json()["data"]["user_id"] == "alice"
    assert list_response.json()["data"][0]["user_id"] == "alice"
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
    }


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
