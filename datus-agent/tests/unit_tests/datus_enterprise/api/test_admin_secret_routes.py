from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.enterprise.defaults import (
    InMemoryEnterpriseSecretStore,
    InMemorySessionOwnerStore,
    LocalAuthorizationProvider,
    NoopAuditSink,
    PassthroughConfigProjector,
)
from datus.api.enterprise.loader import EnterpriseExtensions
from datus_enterprise.api import admin_secret_routes


class CollectingAuditSink:
    def __init__(self):
        self.events = []

    async def write(self, event):
        self.events.append(event)


def _install_extensions(monkeypatch, *, secret_store=None, audit_sink=None):
    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=True,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=audit_sink or NoopAuditSink(),
            secret_store=secret_store,
        ),
    )


def _client(ctx: AppContext):
    app = FastAPI()
    app.include_router(admin_secret_routes.router)

    async def override_service(request: Request):
        request.state.app_context = ctx
        return object()

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = override_service
    app.dependency_overrides[deps.get_request_app_context] = override_context
    return TestClient(app)


def test_admin_secrets_rejects_without_permission(monkeypatch):
    _install_extensions(monkeypatch, secret_store=InMemoryEnterpriseSecretStore())
    ctx = AppContext(user_id="u1", permissions={"module.admin.users"})

    with _client(ctx) as client:
        response = client.get("/api/v1/admin/secrets")

    assert response.status_code == 403
    assert "module.admin.secrets" in response.json()["detail"]


def test_admin_secrets_returns_unavailable_without_store(monkeypatch):
    audit_sink = CollectingAuditSink()
    _install_extensions(monkeypatch, audit_sink=audit_sink)
    ctx = AppContext(user_id="admin", permissions={"module.admin.secrets"})

    with _client(ctx) as client:
        response = client.get("/api/v1/admin/secrets")

    body = response.json()
    assert body["success"] is False
    assert body["errorCode"] == "SECRET_STORE_UNAVAILABLE"
    assert audit_sink.events[-1].decision == "deny"
    assert audit_sink.events[-1].reason == "secret store unavailable"


def test_admin_secret_upsert_get_list_delete_and_audit_redaction(monkeypatch):
    secret_store = InMemoryEnterpriseSecretStore()
    audit_sink = CollectingAuditSink()
    _install_extensions(monkeypatch, secret_store=secret_store, audit_sink=audit_sink)
    ctx = AppContext(user_id="admin", permissions={"module.admin.secrets"})

    with _client(ctx) as client:
        put_response = client.put(
            "/api/v1/admin/secrets/datasource/warehouse/password",
            json={
                "provider": "env",
                "reference": "WAREHOUSE_PASSWORD",
                "description": "Warehouse password",
                "enabled": True,
            },
        )
        get_response = client.get("/api/v1/admin/secrets/datasource/warehouse/password")
        list_response = client.get("/api/v1/admin/secrets", params={"prefix": "datasource/"})
        delete_response = client.delete("/api/v1/admin/secrets/datasource/warehouse/password")

    for response in (put_response, get_response, list_response, delete_response):
        assert response.status_code == 200

    put_body = put_response.json()
    assert put_body["success"] is True
    assert put_body["data"]["name"] == "datasource/warehouse/password"
    assert put_body["data"]["provider"] == "env"
    assert put_body["data"]["ref_hint"] == "***WORD"
    assert "WAREHOUSE_PASSWORD" not in put_response.text

    assert get_response.json()["data"]["ref_hint"] == "***WORD"
    assert [secret["name"] for secret in list_response.json()["data"]] == ["datasource/warehouse/password"]
    assert "WAREHOUSE_PASSWORD" not in list_response.text
    assert delete_response.json()["data"] == {"deleted": True}

    allow_events = [event for event in audit_sink.events if event.decision == "allow"]
    assert [event.metadata["operation"] for event in allow_events] == [
        "upsert_admin_secret",
        "get_admin_secret",
        "list_admin_secrets",
        "delete_admin_secret",
    ]
    assert allow_events[0].metadata["new_summary"] == {
        "name": "datasource/warehouse/password",
        "provider": "env",
        "ref_hint": "***WORD",
        "enabled": True,
    }
    assert "WAREHOUSE_PASSWORD" not in str(allow_events[0].metadata)


def test_admin_secret_validates_input(monkeypatch):
    secret_store = InMemoryEnterpriseSecretStore()
    audit_sink = CollectingAuditSink()
    _install_extensions(monkeypatch, secret_store=secret_store, audit_sink=audit_sink)
    ctx = AppContext(user_id="admin", permissions={"module.admin.secrets"})

    with _client(ctx) as client:
        response = client.put(
            "/api/v1/admin/secrets/bad name",
            json={"provider": "env", "reference": "SECRET_REF"},
        )
        provider_response = client.put(
            "/api/v1/admin/secrets/model/openai/key",
            json={"provider": "bad provider", "reference": "SECRET_REF"},
        )

    assert response.json()["success"] is False
    assert response.json()["errorCode"] == "SECRET_NAME_INVALID"
    assert provider_response.json()["success"] is False
    assert provider_response.json()["errorCode"] == "SECRET_PROVIDER_INVALID"


def test_enterprise_admin_secret_routes_are_registered():
    paths = {route.path for route in admin_secret_routes.router.routes}

    assert "/api/v1/admin/secrets" in paths
    assert "/api/v1/admin/secrets/{name:path}" in paths
