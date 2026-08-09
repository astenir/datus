import sqlite3
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.enterprise.defaults import (
    InMemorySessionOwnerStore,
    InMemoryUserDatasourceStore,
    LocalAuthorizationProvider,
    NoopAuditSink,
    PassthroughConfigProjector,
    SqliteUserDatasourceStore,
)
from datus.api.enterprise.loader import EnterpriseExtensions
from datus.api.enterprise.models import ProjectionInput
from datus_enterprise.api import personal_datasource_routes
from datus_enterprise.config_projection import DatasourceGrantConfigProjector
from datus_enterprise.personal_datasources import personal_datasource_key


class CollectingAuditSink:
    def __init__(self):
        self.events = []

    async def write(self, event):
        self.events.append(event)


class FailingAuditSink:
    async def write(self, event):
        raise RuntimeError("audit down")


def _agent_config(*, user_datasources=None):
    if user_datasources is None:
        user_datasources = {
            "enabled": True,
            "allowed_types": ["postgresql", "mysql"],
            "allowed_hosts": ["localhost", "127.0.0.1", "*.corp"],
            "default_ports": {"postgresql": "5432", "mysql": "3306"},
        }
    return SimpleNamespace(
        enterprise_config={"user_datasources": user_datasources},
        services=SimpleNamespace(datasources={}),
        current_datasource="",
        principal={},
    )


def _install_extensions(monkeypatch, *, store=None, projector=None, audit_sink=None):
    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=True,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=projector or PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=audit_sink or NoopAuditSink(),
            user_datasource_store=store or InMemoryUserDatasourceStore(),
        ),
    )


def _client(ctx: AppContext, svc=None):
    app = FastAPI()
    app.include_router(personal_datasource_routes.router)

    async def override_service(request: Request):
        request.state.app_context = ctx
        return svc or SimpleNamespace(agent_config=_agent_config())

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = override_service
    app.dependency_overrides[deps.get_request_app_context] = override_context
    return TestClient(app)


def test_personal_datasources_crud_redacts_password(monkeypatch):
    store = InMemoryUserDatasourceStore()
    _install_extensions(monkeypatch, store=store)
    ctx = AppContext(user_id="alice", permissions={"module.datasource_catalog"})

    with _client(ctx) as client:
        providers_response = client.get("/api/v1/me/datasource-providers")
        create_response = client.post(
            "/api/v1/me/datasources",
            json={
                "type": "postgresql",
                "host": "localhost",
                "port": "5432",
                "username": "alice",
                "password": "alice-db-secret",
                "database": "finance",
                "schema_name": "public",
                "display_name": "个人分析库",
            },
        )
        datasource_id = create_response.json()["data"]["id"]
        list_response = client.get("/api/v1/me/datasources")
        delete_response = client.delete(f"/api/v1/me/datasources/{datasource_id}")

    assert providers_response.status_code == 200
    assert providers_response.json()["data"]["allowed_types"] == ["mysql", "postgresql"]
    assert create_response.status_code == 200
    assert create_response.json()["data"]["datasource_key"] == personal_datasource_key(datasource_id)
    assert create_response.json()["data"]["display_name"] == "个人分析库"
    assert create_response.json()["data"]["password_hint"] == "***cret"
    assert "alice-db-secret" not in create_response.text
    assert "alice-db-secret" not in list_response.text
    assert list_response.json()["data"][0]["id"] == datasource_id
    assert delete_response.json()["data"] == {"deleted": True}


def test_personal_datasources_are_isolated_by_current_user(monkeypatch):
    store = InMemoryUserDatasourceStore()
    _install_extensions(monkeypatch, store=store)

    with _client(AppContext(user_id="alice", permissions={"module.datasource_catalog"})) as client:
        client.post(
            "/api/v1/me/datasources",
            json={
                "type": "postgresql",
                "host": "localhost",
                "port": "5432",
                "username": "alice",
                "password": "alice-db-secret",
                "database": "finance",
            },
        )

    with _client(AppContext(user_id="bob", permissions={"module.datasource_catalog"})) as client:
        response = client.get("/api/v1/me/datasources")

    assert response.status_code == 200
    assert response.json()["data"] == []


def test_personal_datasource_rejects_disallowed_host(monkeypatch):
    _install_extensions(monkeypatch, store=InMemoryUserDatasourceStore())
    ctx = AppContext(user_id="alice", permissions={"module.datasource_catalog"})

    with _client(ctx) as client:
        response = client.post(
            "/api/v1/me/datasources",
            json={
                "type": "postgresql",
                "host": "10.0.0.1",
                "port": "5432",
                "username": "alice",
                "password": "alice-db-secret",
                "database": "finance",
            },
        )

    assert response.status_code == 400
    assert "Datasource host is not allowed" in response.json()["detail"]


def test_personal_datasource_mutations_are_audited_without_password(monkeypatch):
    store = InMemoryUserDatasourceStore()
    audit_sink = CollectingAuditSink()
    _install_extensions(monkeypatch, store=store, audit_sink=audit_sink)
    ctx = AppContext(user_id="alice", permissions={"module.datasource_catalog"})
    monkeypatch.setattr(personal_datasource_routes, "_probe_datasource_sync", lambda payload: None)

    with _client(ctx) as client:
        create_response = client.post(
            "/api/v1/me/datasources",
            json={
                "type": "postgresql",
                "host": "localhost",
                "port": "5432",
                "username": "alice",
                "password": "alice-db-secret",
                "database": "finance",
            },
        )
        datasource_id = create_response.json()["data"]["id"]
        test_response = client.post(f"/api/v1/me/datasources/{datasource_id}/test")
        update_response = client.put(
            f"/api/v1/me/datasources/{datasource_id}",
            json={
                "type": "postgresql",
                "host": "localhost",
                "port": "5432",
                "username": "alice",
                "password": "new-alice-db-secret",
                "database": "finance",
                "display_name": "Finance dev",
            },
        )
        delete_response = client.delete(f"/api/v1/me/datasources/{datasource_id}")

    assert create_response.status_code == 200
    assert test_response.json()["data"] == {"ok": True}
    assert update_response.status_code == 200
    assert delete_response.json()["data"] == {"deleted": True}
    assert [event.metadata["operation"] for event in audit_sink.events] == ["create", "probe", "update", "delete"]
    assert [event.action for event in audit_sink.events] == ["me.datasource"] * 4
    assert all(event.resource_id == datasource_id for event in audit_sink.events)
    assert "alice-db-secret" not in str([event.metadata for event in audit_sink.events])
    assert "new-alice-db-secret" not in str([event.metadata for event in audit_sink.events])


@pytest.mark.asyncio
async def test_personal_datasource_create_survives_audit_failure(monkeypatch):
    store = InMemoryUserDatasourceStore()
    _install_extensions(monkeypatch, store=store, audit_sink=FailingAuditSink())
    ctx = AppContext(user_id="alice", permissions={"module.datasource_catalog"})

    result = await personal_datasource_routes.create_my_personal_datasource(
        personal_datasource_routes.UpsertPersonalDatasourceRequest(
            type="postgresql",
            host="localhost",
            port="5432",
            username="alice",
            password="alice-db-secret",
            database="finance",
        ),
        SimpleNamespace(agent_config=_agent_config()),
        ctx,
    )

    assert result.success is True
    assert result.data.username == "alice"
    assert [record["database"] for record in await store.list_datasources("alice")] == ["finance"]


@pytest.mark.asyncio
async def test_personal_datasource_projection_is_request_scoped(monkeypatch):
    store = InMemoryUserDatasourceStore()
    _install_extensions(monkeypatch, store=store, projector=DatasourceGrantConfigProjector())
    await store.put_datasource(
        user_id="alice",
        datasource_id="ds1",
        datasource_type="postgresql",
        host="localhost",
        port="5432",
        username="alice",
        password="alice-db-secret",
        database="finance",
    )
    await store.put_datasource(
        user_id="bob",
        datasource_id="ds2",
        datasource_type="postgresql",
        host="localhost",
        port="5432",
        username="bob",
        password="bob-db-secret",
        database="finance",
    )

    base = _agent_config()
    result = await DatasourceGrantConfigProjector().project(
        ProjectionInput(
            ctx=AppContext(user_id="alice", datasource_grants={}),
            base_config=base,
            operation="catalog.list",
            requested_datasource=personal_datasource_key("ds1"),
        )
    )

    assert result.denied_reason is None
    assert personal_datasource_key("ds1") in result.config.services.datasources
    assert personal_datasource_key("ds2") not in result.config.services.datasources
    assert result.config.services.datasources[personal_datasource_key("ds1")].password == "alice-db-secret"
    assert base.services.datasources == {}


@pytest.mark.asyncio
async def test_personal_datasource_projection_rechecks_feature_flag(monkeypatch):
    store = InMemoryUserDatasourceStore()
    _install_extensions(monkeypatch, store=store, projector=DatasourceGrantConfigProjector())
    await store.put_datasource(
        user_id="alice",
        datasource_id="ds1",
        datasource_type="postgresql",
        host="localhost",
        port="5432",
        username="alice",
        password="alice-db-secret",
        database="finance",
    )

    result = await DatasourceGrantConfigProjector().project(
        ProjectionInput(
            ctx=AppContext(user_id="alice", datasource_grants={}),
            base_config=_agent_config(
                user_datasources={
                    "enabled": False,
                    "allowed_types": ["postgresql"],
                    "allowed_hosts": ["localhost"],
                }
            ),
            operation="catalog.list",
            requested_datasource=personal_datasource_key("ds1"),
        )
    )

    assert result.denied_reason == "Personal datasources are not enabled."
    assert personal_datasource_key("ds1") not in result.config.services.datasources


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "user_datasources",
    [
        {
            "enabled": True,
            "allowed_types": ["mysql"],
            "allowed_hosts": ["localhost"],
        },
        {
            "enabled": True,
            "allowed_types": ["postgresql"],
            "allowed_hosts": ["db.corp"],
        },
    ],
)
async def test_personal_datasource_projection_rechecks_current_allowlist(monkeypatch, user_datasources):
    store = InMemoryUserDatasourceStore()
    _install_extensions(monkeypatch, store=store, projector=DatasourceGrantConfigProjector())
    await store.put_datasource(
        user_id="alice",
        datasource_id="ds1",
        datasource_type="postgresql",
        host="localhost",
        port="5432",
        username="alice",
        password="alice-db-secret",
        database="finance",
    )

    result = await DatasourceGrantConfigProjector().project(
        ProjectionInput(
            ctx=AppContext(user_id="alice", datasource_grants={}),
            base_config=_agent_config(user_datasources=user_datasources),
            operation="catalog.list",
            requested_datasource=personal_datasource_key("ds1"),
        )
    )

    assert result.denied_reason == "Datasource 'personal_ds1' is not authorized for this request."
    assert personal_datasource_key("ds1") not in result.config.services.datasources


@pytest.mark.asyncio
async def test_sqlite_user_datasource_store_encrypts_password(tmp_path):
    db_path = tmp_path / "datasources.db"
    store = SqliteUserDatasourceStore(str(db_path), encryption_secret="x" * 32)

    await store.put_datasource(
        user_id="alice",
        datasource_id="ds-1",
        datasource_type="postgresql",
        host="localhost",
        port="5432",
        username="alice",
        password="alice-db-secret",
        database="finance",
    )

    record = await store.get_datasource("alice", "ds-1")
    with sqlite3.connect(db_path) as conn:
        blob = conn.execute("SELECT password_blob FROM user_datasources").fetchone()[0]

    assert record["password"] == "alice-db-secret"
    assert record["password_hint"] == "***cret"
    assert "alice-db-secret" not in blob
