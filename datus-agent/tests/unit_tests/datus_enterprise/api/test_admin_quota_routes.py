import asyncio

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
from datus_enterprise.api import admin_quota_routes


class CollectingAuditSink:
    def __init__(self):
        self.events = []

    async def write(self, event):
        self.events.append(event)


class FailingAuditSink:
    async def write(self, event):
        raise RuntimeError("audit down")


def _install_extensions(monkeypatch, *, quota_store=None, audit_sink=None):
    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=True,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=audit_sink or NoopAuditSink(),
            quota_store=quota_store,
        ),
    )


def _client(ctx: AppContext):
    app = FastAPI()
    app.include_router(admin_quota_routes.router)

    async def override_service(request: Request):
        request.state.app_context = ctx
        return object()

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = override_service
    app.dependency_overrides[deps.get_request_app_context] = override_context
    return TestClient(app)


def test_admin_quotas_rejects_without_permission(monkeypatch):
    _install_extensions(monkeypatch, quota_store=InMemoryEnterpriseQuotaStore())
    ctx = AppContext(user_id="u1", permissions={"module.admin.users"})

    with _client(ctx) as client:
        response = client.get("/api/v1/admin/quotas")

    assert response.status_code == 403
    assert "module.admin.quotas" in response.json()["detail"]


def test_admin_quota_upsert_rbac_denial_precedes_readonly_status(monkeypatch):
    quota_store = InMemoryEnterpriseQuotaStore()
    audit_sink = CollectingAuditSink()
    monkeypatch.setenv("DATUS_PLATFORM_STATUS", "readonly")
    _install_extensions(monkeypatch, quota_store=quota_store, audit_sink=audit_sink)
    ctx = AppContext(user_id="u1", permissions={"module.admin.users"})

    with _client(ctx) as client:
        response = client.put(
            "/api/v1/admin/quotas",
            json={
                "subject_type": "user",
                "subject_id": "alice",
                "resource": "llm.tokens",
                "limit": 1000,
            },
        )

    assert response.status_code == 403
    assert "module.admin.quotas" in response.json()["detail"]
    assert asyncio.run(quota_store.list_quotas()) == []
    assert [event.action for event in audit_sink.events] == ["module.admin.quotas"]


def test_admin_quotas_returns_unavailable_without_store(monkeypatch):
    audit_sink = CollectingAuditSink()
    _install_extensions(monkeypatch, audit_sink=audit_sink)
    ctx = AppContext(user_id="admin", permissions={"module.admin.quotas"})

    with _client(ctx) as client:
        response = client.get("/api/v1/admin/quotas")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["errorCode"] == "QUOTA_STORE_UNAVAILABLE"
    assert audit_sink.events[-1].decision == "deny"
    assert audit_sink.events[-1].reason == "quota store unavailable"


def test_admin_quota_upsert_list_usage_and_audit(monkeypatch):
    quota_store = InMemoryEnterpriseQuotaStore()
    audit_sink = CollectingAuditSink()
    _install_extensions(monkeypatch, quota_store=quota_store, audit_sink=audit_sink)
    ctx = AppContext(user_id="admin", permissions={"module.admin.quotas"})

    with _client(ctx) as client:
        put_response = client.put(
            "/api/v1/admin/quotas",
            json={
                "subject_type": "user",
                "subject_id": "alice",
                "resource": "llm.tokens",
                "limit": 1000,
                "window_seconds": 3600,
                "enabled": True,
            },
        )
        list_response = client.get("/api/v1/admin/quotas", params={"subject_type": "user", "subject_id": "alice"})
        usage_response = client.get("/api/v1/admin/usage", params={"resource": "llm.tokens"})

    put_body = put_response.json()
    assert put_body["success"] is True
    assert put_body["data"]["subject_type"] == "user"
    assert put_body["data"]["subject_id"] == "alice"
    assert put_body["data"]["resource"] == "llm.tokens"
    assert put_body["data"]["limit"] == 1000
    assert put_body["data"]["window_seconds"] == 3600
    assert put_body["data"]["enabled"] is True

    list_body = list_response.json()
    assert list_body["success"] is True
    assert [quota["resource"] for quota in list_body["data"]] == ["llm.tokens"]

    usage_body = usage_response.json()
    assert usage_body["success"] is True
    assert usage_body["data"] == []

    allow_events = [event for event in audit_sink.events if event.decision == "allow"]
    assert [event.metadata["operation"] for event in allow_events] == [
        "upsert_admin_quota",
        "list_admin_quotas",
        "list_admin_usage",
    ]
    assert allow_events[0].metadata["new_summary"] == {
        "subject_type": "user",
        "subject_id": "alice",
        "resource": "llm.tokens",
        "limit": 1000,
        "window_seconds": 3600,
        "enabled": True,
    }


@pytest.mark.asyncio
async def test_admin_quota_upsert_returns_success_when_post_write_audit_fails(monkeypatch):
    quota_store = InMemoryEnterpriseQuotaStore()
    _install_extensions(monkeypatch, quota_store=quota_store, audit_sink=FailingAuditSink())
    ctx = AppContext(user_id="admin", permissions={"module.admin.quotas"})

    result = await admin_quota_routes.upsert_admin_quota(
        admin_quota_routes.UpsertQuotaRequest(
            subject_type="user",
            subject_id="alice",
            resource="llm.tokens",
            limit=1000,
            window_seconds=3600,
            enabled=True,
        ),
        ctx,
    )

    assert result.success is True
    assert result.data.subject_type == "user"
    assert result.data.subject_id == "alice"
    assert result.data.resource == "llm.tokens"
    stored = await quota_store.list_quotas(subject_type="user", subject_id="alice", resource="llm.tokens")
    assert stored[0]["limit"] == 1000
    assert stored[0]["window_seconds"] == 3600


def test_admin_quota_validates_input(monkeypatch):
    quota_store = InMemoryEnterpriseQuotaStore()
    audit_sink = CollectingAuditSink()
    _install_extensions(monkeypatch, quota_store=quota_store, audit_sink=audit_sink)
    ctx = AppContext(user_id="admin", permissions={"module.admin.quotas"})

    with _client(ctx) as client:
        response = client.put(
            "/api/v1/admin/quotas",
            json={
                "subject_type": "user",
                "subject_id": "bad user",
                "resource": "llm.tokens",
                "limit": 1000,
            },
        )
        filter_response = client.get("/api/v1/admin/usage", params={"subject_id": "alice"})

    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["errorCode"] == "QUOTA_SUBJECT_INVALID"
    assert filter_response.json()["success"] is False
    assert filter_response.json()["errorCode"] == "QUOTA_FILTER_INVALID"
    assert audit_sink.events[-1].reason == "Quota subject_type is required when subject_id is provided."


def test_enterprise_admin_quota_routes_are_registered():
    paths = {route.path for route in admin_quota_routes.router.routes}

    assert "/api/v1/admin/quotas" in paths
    assert "/api/v1/admin/usage" in paths
