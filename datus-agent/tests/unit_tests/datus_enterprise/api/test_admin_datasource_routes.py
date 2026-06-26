from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, Request
from fastapi.routing import APIRoute
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
from datus.configuration.project_config import ProjectOverride
from datus.utils.exceptions import DatusException
from datus_enterprise.api import admin_datasource_routes
from datus_enterprise.api.admin_datasource_routes import SetDefaultDatasourceRequest


def _svc():
    agent_config = SimpleNamespace(services=SimpleNamespace(datasources={"db_a": object(), "db_b": object()}))
    return SimpleNamespace(agent_config=agent_config)


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
        AppContext(user_id="u1", project_id="proj_a", permissions={"module.config.edit"}),
    )

    assert audit_sink.events[-1].user_id == "u1"
    assert audit_sink.events[-1].action == "module.config.edit"
    assert audit_sink.events[-1].resource_id == "db_b"
    assert audit_sink.events[-1].decision == "allow"


def test_set_project_default_datasource_http_uses_app_context_dependency(monkeypatch):
    """HTTP route should authorize from request.state, not a query parameter named ctx."""

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

    assert route_paths == {"/api/v1/admin/datasource-default"}
