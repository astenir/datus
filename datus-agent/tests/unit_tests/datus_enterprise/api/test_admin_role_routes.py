import asyncio
from types import SimpleNamespace

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.enterprise.defaults import (
    InMemoryEnterpriseRoleStore,
    InMemoryEnterpriseUserStore,
    InMemorySessionOwnerStore,
    LocalAuthorizationProvider,
    NoopAuditSink,
    PassthroughConfigProjector,
)
from datus.api.enterprise.loader import EnterpriseExtensions
from datus_enterprise.api import admin_role_routes


class CollectingAuditSink:
    def __init__(self):
        self.events = []

    async def write(self, event):
        self.events.append(event)


def _install_extensions(monkeypatch, role_store, audit_sink=None):
    monkeypatch.setattr(
        admin_role_routes.deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=False,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=audit_sink or NoopAuditSink(),
            user_store=InMemoryEnterpriseUserStore(),
            role_store=role_store,
        ),
    )


def _client(ctx: AppContext):
    app = FastAPI()
    app.include_router(admin_role_routes.router)

    async def override_service(request: Request):
        request.state.app_context = ctx
        return SimpleNamespace()

    app.dependency_overrides[deps.get_datus_service] = override_service
    return TestClient(app)


def test_admin_roles_rejects_without_permission(monkeypatch):
    _install_extensions(monkeypatch, InMemoryEnterpriseRoleStore())
    ctx = AppContext(user_id="operator", permissions={"module.admin.users"})

    with _client(ctx) as client:
        response = client.get("/api/v1/admin/roles")

    assert response.status_code == 403
    assert "module.admin.roles" in response.json()["detail"]


def test_admin_role_upsert_get_and_list_audit_sanitized(monkeypatch):
    role_store = InMemoryEnterpriseRoleStore()
    audit_sink = CollectingAuditSink()
    _install_extensions(monkeypatch, role_store, audit_sink)
    ctx = AppContext(user_id="operator", permissions={"module.admin.roles"})

    with _client(ctx) as client:
        upsert_response = client.put(
            "/api/v1/admin/roles/analyst",
            json={
                "name": "Analyst",
                "description": "Can analyze data",
                "permissions": ["module.sql_executor", "module.chat", "module.chat"],
            },
        )
        get_response = client.get("/api/v1/admin/roles/analyst")
        list_response = client.get("/api/v1/admin/roles")

    assert upsert_response.status_code == 200
    assert upsert_response.json()["success"] is True
    upsert_data = upsert_response.json()["data"]
    assert {key: upsert_data[key] for key in ("role_id", "name", "description", "permissions", "built_in")} == {
        "role_id": "analyst",
        "name": "Analyst",
        "description": "Can analyze data",
        "permissions": ["module.chat", "module.sql_executor"],
        "built_in": False,
    }
    assert isinstance(upsert_data["created_at"], str)
    assert isinstance(upsert_data["updated_at"], str)
    assert get_response.json()["data"]["role_id"] == "analyst"
    assert list_response.json()["data"][0]["role_id"] == "analyst"
    assert "secret" not in list_response.text

    assert audit_sink.events[-3].action == "module.admin.roles"
    assert audit_sink.events[-3].resource_type == "role"
    assert audit_sink.events[-3].resource_id == "analyst"
    assert audit_sink.events[-3].decision == "allow"
    assert audit_sink.events[-3].metadata["operation"] == "upsert_admin_role"
    assert audit_sink.events[-3].metadata["new"] == {
        "role_id": "analyst",
        "name": "Analyst",
        "description": "Can analyze data",
        "permissions": ["module.chat", "module.sql_executor"],
        "built_in": False,
    }


def test_admin_role_permissions_and_delete(monkeypatch):
    role_store = InMemoryEnterpriseRoleStore()
    audit_sink = CollectingAuditSink()
    _install_extensions(monkeypatch, role_store, audit_sink)
    ctx = AppContext(user_id="operator", permissions={"module.admin.roles"})

    with _client(ctx) as client:
        client.put("/api/v1/admin/roles/analyst", json={"name": "Analyst", "permissions": ["module.chat"]})
        permissions_response = client.put(
            "/api/v1/admin/roles/analyst/permissions",
            json={"permissions": ["module.dashboard.query", "module.report.query"]},
        )
        delete_response = client.delete("/api/v1/admin/roles/analyst")
        missing_response = client.get("/api/v1/admin/roles/analyst")

    assert permissions_response.json()["data"]["permissions"] == ["module.dashboard.query", "module.report.query"]
    assert delete_response.json()["success"] is True
    assert delete_response.json()["data"] == {"role_id": "analyst", "deleted": True}
    assert missing_response.json()["success"] is False
    assert missing_response.json()["errorCode"] == "RESOURCE_NOT_FOUND"
    assert audit_sink.events[-3].metadata["operation"] == "set_admin_role_permissions"
    assert audit_sink.events[-2].metadata["operation"] == "delete_admin_role"


def test_admin_role_missing_invalid_and_permission_validation(monkeypatch):
    audit_sink = CollectingAuditSink()
    _install_extensions(monkeypatch, InMemoryEnterpriseRoleStore(), audit_sink)
    ctx = AppContext(user_id="operator", permissions={"module.admin.roles"})

    with _client(ctx) as client:
        missing_response = client.get("/api/v1/admin/roles/missing")
        invalid_id_response = client.put("/api/v1/admin/roles/bad.id", json={"name": "Bad"})
        invalid_name_response = client.put("/api/v1/admin/roles/bad", json={"name": "   "})
        invalid_permission_response = client.put(
            "/api/v1/admin/roles/bad",
            json={"name": "Bad", "permissions": ["module.chat "]},
        )

    assert missing_response.status_code == 200
    assert missing_response.json()["success"] is False
    assert missing_response.json()["errorCode"] == "RESOURCE_NOT_FOUND"
    assert invalid_id_response.json()["errorCode"] == "ROLE_ID_INVALID"
    assert invalid_name_response.json()["errorCode"] == "ROLE_NAME_INVALID"
    assert invalid_permission_response.json()["errorCode"] == "ROLE_PERMISSION_INVALID"
    assert audit_sink.events[-1].decision == "deny"


def test_admin_role_store_failure_returns_stable_error_and_audits(monkeypatch):
    class FailingRoleStore(InMemoryEnterpriseRoleStore):
        async def get_role(self, role_id):
            raise RuntimeError("store down")

    audit_sink = CollectingAuditSink()
    _install_extensions(monkeypatch, FailingRoleStore(), audit_sink)
    ctx = AppContext(user_id="operator", permissions={"module.admin.roles"})

    with _client(ctx) as client:
        response = client.get("/api/v1/admin/roles/analyst")

    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["errorCode"] == "ROLE_READ_FAILED"
    assert audit_sink.events[-1].decision == "deny"
    assert audit_sink.events[-1].reason == "role read failed"


def test_admin_role_built_in_role_delete_is_rejected(monkeypatch):
    role_store = InMemoryEnterpriseRoleStore()
    audit_sink = CollectingAuditSink()
    _install_extensions(monkeypatch, role_store, audit_sink)
    ctx = AppContext(user_id="operator", permissions={"module.admin.roles"})
    asyncio.run(role_store.upsert_role(role_id="enterprise_admin", name="Enterprise Admin", built_in=True))

    with _client(ctx) as client:
        response = client.delete("/api/v1/admin/roles/enterprise_admin")

    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["errorCode"] == "ROLE_DELETE_FORBIDDEN"
    assert audit_sink.events[-1].decision == "deny"
    assert audit_sink.events[-1].reason == "built-in role cannot be deleted"


def test_admin_role_routes_register_expected_paths():
    app = FastAPI()
    app.include_router(admin_role_routes.router)
    paths = {route.path for route in app.routes}

    assert "/api/v1/admin/roles" in paths
    assert "/api/v1/admin/roles/{role_id}" in paths
    assert "/api/v1/admin/roles/{role_id}/permissions" in paths
