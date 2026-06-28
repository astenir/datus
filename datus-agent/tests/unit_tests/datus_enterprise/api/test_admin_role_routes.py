import argparse
import asyncio
from types import SimpleNamespace

import pytest
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
from datus.api.service import create_app
from datus.utils.exceptions import DatusException, ErrorCode
from datus_enterprise.api import admin_role_routes


class CollectingAuditSink:
    def __init__(self):
        self.events = []

    async def write(self, event):
        self.events.append(event)


class FailingAuditSink:
    async def write(self, event):
        raise RuntimeError("audit down")


def _install_extensions(monkeypatch, role_store, audit_sink=None, user_store=None, *, enabled=False):
    monkeypatch.setattr(
        admin_role_routes.deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=enabled,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=audit_sink or NoopAuditSink(),
            user_store=user_store or InMemoryEnterpriseUserStore(),
            role_store=role_store,
        ),
    )


def _client(ctx: AppContext):
    app = FastAPI()
    app.include_router(admin_role_routes.router)

    async def override_service(request: Request):
        request.state.app_context = ctx
        return SimpleNamespace()

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = override_service
    app.dependency_overrides[deps.get_request_app_context] = override_context
    return TestClient(app)


def test_admin_roles_rejects_without_permission(monkeypatch):
    _install_extensions(monkeypatch, InMemoryEnterpriseRoleStore())
    ctx = AppContext(user_id="operator", permissions={"module.admin.users"})

    with _client(ctx) as client:
        response = client.get("/api/v1/admin/roles")

    assert response.status_code == 403
    assert "module.admin.roles" in response.json()["detail"]


def test_admin_role_upsert_rbac_denial_precedes_readonly_status(monkeypatch):
    role_store = InMemoryEnterpriseRoleStore()
    audit_sink = CollectingAuditSink()
    monkeypatch.setenv("DATUS_PLATFORM_STATUS", "readonly")
    _install_extensions(monkeypatch, role_store, audit_sink, enabled=True)
    ctx = AppContext(user_id="operator", permissions={"module.admin.users"})

    with _client(ctx) as client:
        response = client.put(
            "/api/v1/admin/roles/analyst",
            json={"name": "Analyst", "permissions": ["module.chat"]},
        )

    assert response.status_code == 403
    assert "module.admin.roles" in response.json()["detail"]
    assert asyncio.run(role_store.list_roles()) == []
    assert [event.action for event in audit_sink.events] == ["module.admin.roles"]


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


@pytest.mark.asyncio
async def test_admin_role_upsert_returns_success_when_post_write_audit_fails(monkeypatch):
    role_store = InMemoryEnterpriseRoleStore()
    _install_extensions(monkeypatch, role_store, FailingAuditSink())
    ctx = AppContext(user_id="operator", permissions={"module.admin.roles"})

    result = await admin_role_routes.upsert_admin_role(
        "analyst",
        admin_role_routes.UpsertAdminRoleRequest(name="Analyst", permissions=["module.chat"]),
        ctx,
    )

    assert result.success is True
    assert result.data.role_id == "analyst"
    assert (await role_store.get_role("analyst"))["permissions"] == ["module.chat"]


@pytest.mark.asyncio
async def test_admin_role_permissions_return_success_when_post_write_audit_fails(monkeypatch):
    role_store = InMemoryEnterpriseRoleStore()
    await role_store.upsert_role(role_id="analyst", name="Analyst", permissions=["module.chat"])
    _install_extensions(monkeypatch, role_store, FailingAuditSink())
    ctx = AppContext(user_id="operator", permissions={"module.admin.roles"})

    result = await admin_role_routes.set_admin_role_permissions(
        "analyst",
        admin_role_routes.SetRolePermissionsRequest(permissions=["module.sql_executor"]),
        ctx,
    )

    assert result.success is True
    assert result.data.permissions == ["module.sql_executor"]
    assert (await role_store.get_role("analyst"))["permissions"] == ["module.sql_executor"]


@pytest.mark.asyncio
async def test_admin_user_roles_return_success_when_post_write_audit_fails(monkeypatch):
    role_store = InMemoryEnterpriseRoleStore()
    user_store = InMemoryEnterpriseUserStore()
    await user_store.upsert_user(user_id="alice", display_name="Alice")
    await role_store.upsert_role(role_id="analyst", name="Analyst")
    _install_extensions(monkeypatch, role_store, FailingAuditSink(), user_store)
    ctx = AppContext(user_id="operator", permissions={"module.admin.roles"})

    result = await admin_role_routes.set_admin_user_roles(
        "alice",
        admin_role_routes.SetUserRolesRequest(role_ids=["analyst"]),
        ctx,
    )

    assert result.success is True
    assert result.data.role_ids == ["analyst"]
    assert await role_store.list_user_roles("alice") == ["analyst"]


@pytest.mark.asyncio
async def test_admin_role_delete_returns_success_when_post_delete_audit_fails(monkeypatch):
    role_store = InMemoryEnterpriseRoleStore()
    await role_store.upsert_role(role_id="analyst", name="Analyst")
    _install_extensions(monkeypatch, role_store, FailingAuditSink())
    ctx = AppContext(user_id="operator", permissions={"module.admin.roles"})

    result = await admin_role_routes.delete_admin_role("analyst", ctx)

    assert result.success is True
    assert result.data == {"role_id": "analyst", "deleted": True}
    assert await role_store.get_role("analyst") is None


def test_admin_user_roles_get_put_and_audit_sanitized(monkeypatch):
    role_store = InMemoryEnterpriseRoleStore()
    user_store = InMemoryEnterpriseUserStore()
    audit_sink = CollectingAuditSink()
    _install_extensions(monkeypatch, role_store, audit_sink, user_store)
    ctx = AppContext(user_id="operator", permissions={"module.admin.roles"})
    asyncio.run(user_store.upsert_user(user_id="alice", display_name="Alice"))
    asyncio.run(role_store.upsert_role(role_id="analyst", name="Analyst"))
    asyncio.run(role_store.upsert_role(role_id="viewer", name="Viewer"))

    with _client(ctx) as client:
        put_response = client.put(
            "/api/v1/admin/users/alice/roles",
            json={"role_ids": ["viewer", "analyst", "viewer"]},
        )
        get_response = client.get("/api/v1/admin/users/alice/roles")

    assert put_response.status_code == 200
    assert put_response.json()["success"] is True
    assert put_response.json()["data"] == {"user_id": "alice", "role_ids": ["analyst", "viewer"]}
    assert get_response.json()["data"] == {"user_id": "alice", "role_ids": ["analyst", "viewer"]}
    assert audit_sink.events[-2].action == "module.admin.roles"
    assert audit_sink.events[-2].resource_type == "user_roles"
    assert audit_sink.events[-2].resource_id == "alice"
    assert audit_sink.events[-2].decision == "allow"
    assert audit_sink.events[-2].metadata["operation"] == "set_admin_user_roles"
    assert audit_sink.events[-2].metadata["old"] == {"user_id": "alice", "role_ids": []}
    assert audit_sink.events[-2].metadata["new"] == {"user_id": "alice", "role_ids": ["analyst", "viewer"]}


def test_admin_user_roles_rejects_missing_user_or_role(monkeypatch):
    role_store = InMemoryEnterpriseRoleStore()
    user_store = InMemoryEnterpriseUserStore()
    audit_sink = CollectingAuditSink()
    _install_extensions(monkeypatch, role_store, audit_sink, user_store)
    ctx = AppContext(user_id="operator", permissions={"module.admin.roles"})
    asyncio.run(user_store.upsert_user(user_id="alice", display_name="Alice"))

    with _client(ctx) as client:
        missing_user_response = client.get("/api/v1/admin/users/missing/roles")
        missing_role_response = client.put("/api/v1/admin/users/alice/roles", json={"role_ids": ["missing"]})
        invalid_user_response = client.put("/api/v1/admin/users/bad.id/roles", json={"role_ids": []})
        invalid_role_response = client.put("/api/v1/admin/users/alice/roles", json={"role_ids": ["bad.id"]})

    assert missing_user_response.json()["success"] is False
    assert missing_user_response.json()["errorCode"] == "RESOURCE_NOT_FOUND"
    assert missing_role_response.json()["success"] is False
    assert missing_role_response.json()["errorCode"] == "RESOURCE_NOT_FOUND"
    assert invalid_user_response.json()["errorCode"] == "USER_ID_INVALID"
    assert invalid_role_response.json()["errorCode"] == "ROLE_ID_INVALID"
    assert audit_sink.events[-1].decision == "deny"


def test_admin_user_roles_translates_store_role_not_found_race(monkeypatch):
    class RaceRoleStore(InMemoryEnterpriseRoleStore):
        async def set_user_roles(self, user_id, role_ids):
            raise DatusException(ErrorCode.COMMON_FIELD_INVALID, message="Role not found: analyst.")

    role_store = RaceRoleStore()
    user_store = InMemoryEnterpriseUserStore()
    audit_sink = CollectingAuditSink()
    _install_extensions(monkeypatch, role_store, audit_sink, user_store)
    ctx = AppContext(user_id="operator", permissions={"module.admin.roles"})
    asyncio.run(user_store.upsert_user(user_id="alice", display_name="Alice"))
    asyncio.run(role_store.upsert_role(role_id="analyst", name="Analyst"))

    with _client(ctx) as client:
        response = client.put("/api/v1/admin/users/alice/roles", json={"role_ids": ["analyst"]})

    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["errorCode"] == "RESOURCE_NOT_FOUND"
    assert audit_sink.events[-1].decision == "deny"
    assert audit_sink.events[-1].reason == "role not found"


def test_admin_role_delete_rejects_assigned_role(monkeypatch):
    role_store = InMemoryEnterpriseRoleStore()
    user_store = InMemoryEnterpriseUserStore()
    audit_sink = CollectingAuditSink()
    _install_extensions(monkeypatch, role_store, audit_sink, user_store)
    ctx = AppContext(user_id="operator", permissions={"module.admin.roles"})
    asyncio.run(user_store.upsert_user(user_id="alice", display_name="Alice"))
    asyncio.run(role_store.upsert_role(role_id="analyst", name="Analyst"))
    asyncio.run(role_store.set_user_roles("alice", ["analyst"]))

    with _client(ctx) as client:
        response = client.delete("/api/v1/admin/roles/analyst")

    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["errorCode"] == "ROLE_DELETE_FORBIDDEN"
    assert audit_sink.events[-1].decision == "deny"
    assert audit_sink.events[-1].reason == "role has assigned users"
    assert audit_sink.events[-1].metadata["assigned_user_count"] == 1


def test_admin_role_delete_rechecks_bindings_when_store_returns_false(monkeypatch):
    class RaceRoleStore(InMemoryEnterpriseRoleStore):
        def __init__(self):
            super().__init__()
            self._list_calls = 0

        async def list_role_users(self, role_id):
            self._list_calls += 1
            if self._list_calls == 1:
                return []
            return ["alice"]

        async def delete_role(self, role_id):
            return False

    role_store = RaceRoleStore()
    audit_sink = CollectingAuditSink()
    _install_extensions(monkeypatch, role_store, audit_sink)
    ctx = AppContext(user_id="operator", permissions={"module.admin.roles"})
    asyncio.run(role_store.upsert_role(role_id="analyst", name="Analyst"))

    with _client(ctx) as client:
        response = client.delete("/api/v1/admin/roles/analyst")

    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["errorCode"] == "ROLE_DELETE_FORBIDDEN"
    assert audit_sink.events[-1].decision == "deny"
    assert audit_sink.events[-1].reason == "role has assigned users"


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
    assert "/api/v1/admin/users/{user_id}/roles" in paths


def test_create_app_registers_admin_role_routes():
    args = argparse.Namespace(config="", datasource="default", output_dir="./output", log_level="INFO")
    app = create_app(args)
    paths = {route.path for route in app.routes if hasattr(route, "path")}

    assert "/api/v1/admin/roles" in paths
    assert "/api/v1/admin/roles/{role_id}" in paths
    assert "/api/v1/admin/roles/{role_id}/permissions" in paths
    assert "/api/v1/admin/users/{user_id}/roles" in paths
