# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.

"""Unit tests for datus/api/routes/config_routes.py."""

import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, HTTPException, Request
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
from datus.api.routes import config_routes
from datus.api.routes.config_routes import (
    ProbeDatasourceRequest,
    ProbeModelRequest,
    UpdateDatasourcesRequest,
    UpdateModelsRequest,
    get_agent_config_endpoint,
    probe_datasource_connectivity_endpoint,
    probe_model_connectivity_endpoint,
    update_datasources_endpoint,
    update_models_endpoint,
)
from datus.configuration.agent_config import DbConfig


def _mock_svc(datasources, *, target="deepseek", current_datasource="starrocks", models=None, home="~/.datus"):
    svc = MagicMock()
    svc.agent_config.target = target
    svc.agent_config.models = models if models is not None else {}
    svc.agent_config.current_datasource = current_datasource
    svc.agent_config.datasource_configs = datasources
    svc.agent_config.home = home
    return svc


@pytest.mark.asyncio
async def test_get_agent_config_returns_datasources_flat():
    """datasource_configs is a single-layer {ds: cfg} map, returned as-is."""
    starrocks_cfg = {"type": "starrocks", "host": "h1"}
    starrocks22_cfg = {"type": "starrocks", "host": "h2"}
    svc = _mock_svc(
        datasources={
            "starrocks": starrocks_cfg,
            "starrocks22": starrocks22_cfg,
        },
    )

    result = await get_agent_config_endpoint(svc=svc, _ctx=_ctx())

    assert result.success is True
    assert result.data["datasources"] == {
        "starrocks": starrocks_cfg,
        "starrocks22": starrocks22_cfg,
    }
    assert result.data["target"] == "deepseek"
    assert result.data["current_datasource"] == "starrocks"
    assert result.data["home"] == "~/.datus"


@pytest.mark.asyncio
async def test_get_agent_config_skips_none_config():
    """Datasources whose config is None are dropped from the response."""
    real_cfg = {"type": "duckdb"}
    svc = _mock_svc(datasources={"empty": None, "real": real_cfg})

    result = await get_agent_config_endpoint(svc=svc, _ctx=_ctx())

    assert result.data["datasources"] == {"real": real_cfg}


@pytest.mark.asyncio
async def test_get_agent_config_handles_empty_datasources():
    svc = _mock_svc(datasources={})

    result = await get_agent_config_endpoint(svc=svc, _ctx=_ctx())

    assert result.data["datasources"] == {}


class _FakeConfigManager:
    """Minimal stand-in for ConfigurationManager — captures save() calls."""

    def __init__(self, initial=None, *, save_error: Exception | None = None):
        self.data = copy.deepcopy(initial) if initial else {}
        self.save_count = 0
        self.save_error = save_error

    def save(self):
        self.save_count += 1
        if self.save_error is not None:
            raise self.save_error


@pytest.fixture
def patched_cm(monkeypatch):
    """Replace the module-level configuration_manager() with a fake instance."""
    cm = _FakeConfigManager()
    monkeypatch.setattr(config_routes, "configuration_manager", lambda: cm)
    return cm


@pytest.fixture
def patched_cache(monkeypatch):
    """Replace deps._service_cache with an AsyncMock so evict() is awaitable."""
    cache = MagicMock()
    cache.evict = AsyncMock()
    monkeypatch.setattr(config_routes.deps, "_service_cache", cache)
    return cache


def _ctx(project_id="proj_a"):
    return SimpleNamespace(project_id=project_id)


class CollectingAuditSink:
    def __init__(self):
        self.events = []

    async def write(self, event):
        self.events.append(event)


def _enterprise_extensions(enabled=True, audit_sink=None):
    return EnterpriseExtensions(
        enabled=enabled,
        authorization_provider=LocalAuthorizationProvider(),
        config_projector=PassthroughConfigProjector(),
        session_owner_store=InMemorySessionOwnerStore(),
        audit_sink=audit_sink or NoopAuditSink(),
    )


def _override_app_context(app: FastAPI, ctx: AppContext) -> None:
    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_request_app_context] = override_context


@pytest.mark.asyncio
async def test_update_datasources_replaces_services_datasources(patched_cm, patched_cache):
    patched_cm.data = {"services": {"datasources": {"old": {"type": "duckdb"}}, "other": "keep"}}
    body = UpdateDatasourcesRequest(
        datasources={
            "db_a": {"type": "starrocks", "host": "h1"},
            "db_b": {"type": "duckdb", "uri": "/tmp/a.db"},
        }
    )

    result = await update_datasources_endpoint(body, ctx=_ctx("proj_a"))

    assert result.success is True
    assert result.data == {"updated": True}
    assert patched_cm.data["services"]["datasources"] == {
        "db_a": {"type": "starrocks", "host": "h1"},
        "db_b": {"type": "duckdb", "uri": "/tmp/a.db"},
    }
    assert patched_cm.data["services"]["other"] == "keep"
    assert patched_cm.save_count == 1
    patched_cache.evict.assert_awaited_once_with("proj_a")


@pytest.mark.asyncio
async def test_update_datasources_evicts_enterprise_cache_key(monkeypatch, patched_cm, patched_cache):
    monkeypatch.setattr(config_routes.deps, "_enterprise_extensions", _enterprise_extensions(enabled=True))

    await update_datasources_endpoint(
        UpdateDatasourcesRequest(datasources={"db_a": {"type": "duckdb"}}),
        ctx=_ctx("proj_a"),
    )

    patched_cache.evict.assert_awaited_once_with("enterprise:proj_a")


@pytest.mark.asyncio
async def test_update_datasources_empty_dict_clears_block(patched_cm, patched_cache):
    patched_cm.data = {"services": {"datasources": {"old": {"type": "duckdb"}}}}

    result = await update_datasources_endpoint(UpdateDatasourcesRequest(datasources={}), ctx=_ctx())

    assert result.data["updated"] is True
    assert patched_cm.data["services"]["datasources"] == {}


@pytest.mark.asyncio
async def test_update_datasources_rejects_invalid_name(patched_cm, patched_cache):
    body = UpdateDatasourcesRequest(datasources={"bad name!": {"type": "duckdb"}})
    with pytest.raises(HTTPException) as exc_info:
        await update_datasources_endpoint(body, ctx=_ctx())
    assert exc_info.value.status_code == 400
    assert "Invalid datasource name 'bad name!'" in exc_info.value.detail
    assert patched_cm.save_count == 0
    patched_cache.evict.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_datasources_initializes_services_when_missing(patched_cm, patched_cache):
    patched_cm.data = {}

    await update_datasources_endpoint(
        UpdateDatasourcesRequest(datasources={"db_a": {"type": "duckdb"}}),
        ctx=_ctx(),
    )

    assert patched_cm.data["services"]["datasources"] == {"db_a": {"type": "duckdb"}}


@pytest.mark.asyncio
async def test_update_datasources_restores_config_data_when_save_fails(monkeypatch, patched_cache):
    original = {"services": {"datasources": {"old": {"type": "duckdb"}}, "other": "keep"}}
    cm = _FakeConfigManager(initial=original, save_error=OSError("disk full"))
    monkeypatch.setattr(config_routes, "configuration_manager", lambda: cm)

    with pytest.raises(OSError, match="disk full"):
        await update_datasources_endpoint(
            UpdateDatasourcesRequest(datasources={"new": {"type": "sqlite"}}),
            ctx=_ctx(),
        )

    assert cm.data == original
    patched_cache.evict.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_models_replaces_models_and_target(patched_cm, patched_cache):
    patched_cm.data = {"models": {"old": {"type": "openai"}}, "target": "old"}
    body = UpdateModelsRequest(
        models={"new": {"type": "deepseek", "model": "deepseek-chat"}},
        target="new",
    )

    result = await update_models_endpoint(body, ctx=_ctx("proj_b"))

    assert result.data["updated"] is True
    assert patched_cm.data["models"] == {"new": {"type": "deepseek", "model": "deepseek-chat"}}
    assert patched_cm.data["target"] == "new"
    assert patched_cm.save_count == 1
    patched_cache.evict.assert_awaited_once_with("proj_b")


@pytest.mark.asyncio
async def test_update_models_evicts_enterprise_cache_key(monkeypatch, patched_cm, patched_cache):
    monkeypatch.setattr(config_routes.deps, "_enterprise_extensions", _enterprise_extensions(enabled=True))
    patched_cm.data = {"models": {"m1": {"type": "openai"}}, "target": "m1"}

    await update_models_endpoint(UpdateModelsRequest(target="m1"), ctx=_ctx("proj_b"))

    patched_cache.evict.assert_awaited_once_with("enterprise:proj_b")


@pytest.mark.asyncio
async def test_update_models_target_only(patched_cm, patched_cache):
    patched_cm.data = {"models": {"m1": {"type": "openai"}, "m2": {"type": "claude"}}, "target": "m1"}

    await update_models_endpoint(UpdateModelsRequest(target="m2"), ctx=_ctx())

    assert patched_cm.data["target"] == "m2"
    assert patched_cm.data["models"] == {"m1": {"type": "openai"}, "m2": {"type": "claude"}}


@pytest.mark.asyncio
async def test_update_models_models_only(patched_cm, patched_cache):
    patched_cm.data = {"models": {"old": {}}, "target": "old"}

    await update_models_endpoint(
        UpdateModelsRequest(models={"old": {"type": "openai"}}),
        ctx=_ctx(),
    )

    assert patched_cm.data["models"] == {"old": {"type": "openai"}}
    assert patched_cm.data["target"] == "old"


@pytest.mark.asyncio
async def test_update_models_restores_config_data_when_save_fails(monkeypatch, patched_cache):
    original = {"models": {"old": {"type": "openai", "model": "gpt-old"}}, "target": "old"}
    cm = _FakeConfigManager(initial=original, save_error=OSError("disk full"))
    monkeypatch.setattr(config_routes, "configuration_manager", lambda: cm)

    with pytest.raises(OSError, match="disk full"):
        await update_models_endpoint(
            UpdateModelsRequest(models={"new": {"type": "openai", "model": "gpt-new"}}, target="new"),
            ctx=_ctx(),
        )

    assert cm.data == original
    patched_cache.evict.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_models_requires_at_least_one_field(patched_cm, patched_cache):
    with pytest.raises(HTTPException) as exc_info:
        await update_models_endpoint(UpdateModelsRequest(), ctx=_ctx())
    assert exc_info.value.status_code == 400
    assert "At least one of 'models' or 'target' must be provided" in exc_info.value.detail
    assert patched_cm.save_count == 0


@pytest.mark.asyncio
async def test_update_models_rejects_target_not_in_models(patched_cm, patched_cache):
    patched_cm.data = {"models": {"m1": {}}, "target": "m1"}

    with pytest.raises(HTTPException) as exc_info:
        await update_models_endpoint(UpdateModelsRequest(target="ghost"), ctx=_ctx())
    assert exc_info.value.status_code == 400
    assert "target 'ghost' does not exist in models" in exc_info.value.detail
    assert patched_cm.save_count == 0


@pytest.mark.asyncio
async def test_update_models_target_validated_against_new_models(patched_cm, patched_cache):
    """When both models and target are provided, target must exist in the NEW models."""
    patched_cm.data = {"models": {"keep_me": {}}, "target": "keep_me"}

    with pytest.raises(HTTPException) as exc_info:
        await update_models_endpoint(
            UpdateModelsRequest(models={"only_new": {"type": "openai"}}, target="keep_me"),
            ctx=_ctx(),
        )
    assert exc_info.value.status_code == 400
    assert "target 'keep_me' does not exist in models" in exc_info.value.detail


@pytest.mark.asyncio
async def test_update_models_rejects_invalid_model_name(patched_cm, patched_cache):
    with pytest.raises(HTTPException) as exc_info:
        await update_models_endpoint(
            UpdateModelsRequest(models={"bad name!": {"type": "openai"}}),
            ctx=_ctx(),
        )
    assert exc_info.value.status_code == 400
    assert "Invalid model name 'bad name!'" in exc_info.value.detail
    assert patched_cm.save_count == 0


@pytest.mark.asyncio
async def test_update_datasources_survives_missing_service_cache(monkeypatch, patched_cm):
    """No crash when the service cache hasn't been initialized yet."""
    monkeypatch.setattr(config_routes.deps, "_service_cache", None)

    result = await update_datasources_endpoint(
        UpdateDatasourcesRequest(datasources={"db_a": {"type": "duckdb"}}),
        ctx=_ctx(),
    )

    assert result.data["updated"] is True


@pytest.mark.asyncio
async def test_update_datasources_uses_default_project_when_missing(patched_cm, patched_cache):
    await update_datasources_endpoint(
        UpdateDatasourcesRequest(datasources={"db_a": {"type": "duckdb"}}),
        ctx=_ctx(project_id=None),
    )

    patched_cache.evict.assert_awaited_once_with("default")


def test_update_config_http_requires_config_edit_permission(monkeypatch, patched_cm):
    app = FastAPI()
    app.include_router(config_routes.router)
    ctx = AppContext(user_id="u1", project_id="proj_a", permissions={"module.chat"})
    svc = MagicMock()

    async def override_service(request: Request):
        request.state.app_context = ctx
        return svc

    app.dependency_overrides[deps.get_datus_service] = override_service
    _override_app_context(app, ctx)
    monkeypatch.setattr(config_routes.deps, "_enterprise_extensions", _enterprise_extensions(enabled=True))

    with TestClient(app) as client:
        datasources_response = client.put("/api/v1/config/datasources", json={"datasources": {}})
        models_response = client.put(
            "/api/v1/config/models",
            json={"models": {"m1": {"type": "openai", "model": "gpt-test"}}, "target": "m1"},
        )

    assert datasources_response.status_code == 403
    assert models_response.status_code == 403
    assert patched_cm.save_count == 0


def test_update_config_http_returns_bad_request_for_invalid_datasource_name(monkeypatch, patched_cm):
    app = FastAPI()
    app.include_router(config_routes.router)
    ctx = AppContext(user_id="u1", project_id="proj_a", permissions={"module.config.edit"})
    svc = MagicMock()

    async def override_service(request: Request):
        request.state.app_context = ctx
        return svc

    app.dependency_overrides[deps.get_datus_service] = override_service
    _override_app_context(app, ctx)
    monkeypatch.setattr(config_routes.deps, "_enterprise_extensions", _enterprise_extensions(enabled=True))

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.put("/api/v1/config/datasources", json={"datasources": {"bad name!": {"type": "duckdb"}}})

    assert response.status_code == 400
    assert "Invalid datasource name 'bad name!'" in response.json()["detail"]
    assert patched_cm.save_count == 0


def test_update_config_http_returns_bad_request_for_unknown_target(monkeypatch, patched_cm):
    patched_cm.data = {"models": {"m1": {"type": "openai", "model": "gpt-test"}}, "target": "m1"}
    app = FastAPI()
    app.include_router(config_routes.router)
    ctx = AppContext(user_id="u1", project_id="proj_a", permissions={"module.config.edit"})
    svc = MagicMock()

    async def override_service(request: Request):
        request.state.app_context = ctx
        return svc

    app.dependency_overrides[deps.get_datus_service] = override_service
    _override_app_context(app, ctx)
    monkeypatch.setattr(config_routes.deps, "_enterprise_extensions", _enterprise_extensions(enabled=True))

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.put("/api/v1/config/models", json={"target": "ghost"})

    assert response.status_code == 400
    assert "target 'ghost' does not exist in models" in response.json()["detail"]
    assert patched_cm.save_count == 0


def test_config_rbac_denial_does_not_resolve_datus_service(monkeypatch, patched_cm):
    app = FastAPI()
    app.include_router(config_routes.router)
    ctx = AppContext(user_id="u1", project_id="proj_a", permissions={"module.chat"})

    async def reject_service(request: Request):
        raise AssertionError("RBAC denial resolved DatusService")

    app.dependency_overrides[deps.get_datus_service] = reject_service
    _override_app_context(app, ctx)
    monkeypatch.setattr(config_routes.deps, "_enterprise_extensions", _enterprise_extensions(enabled=True))

    with TestClient(app, raise_server_exceptions=False) as client:
        responses = [
            client.get("/api/v1/config/agent"),
            client.put("/api/v1/config/datasources", json={"datasources": {}}),
            client.put(
                "/api/v1/config/models",
                json={"models": {"m1": {"type": "openai", "model": "gpt-test"}}, "target": "m1"},
            ),
            client.post("/api/v1/config/models/test", json={"type": "openai", "model": "gpt-test"}),
            client.post("/api/v1/config/datasources/test", json={"type": "duckdb"}),
        ]

    assert [response.status_code for response in responses] == [403, 403, 403, 403, 403]
    assert patched_cm.save_count == 0


@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    [
        ("put", "/api/v1/config/datasources", {"datasources": []}),
        ("put", "/api/v1/config/datasources", {"bad": "body"}),
        ("put", "/api/v1/config/models", {"models": []}),
        ("put", "/api/v1/config/models", {"target": 123}),
        ("post", "/api/v1/config/models/test", {"type": 1, "model": []}),
        ("post", "/api/v1/config/datasources/test", {"type": []}),
    ],
)
def test_config_invalid_body_does_not_resolve_datus_service(monkeypatch, patched_cm, method, path, json_body):
    app = FastAPI()
    app.include_router(config_routes.router)
    ctx = AppContext(
        user_id="u1",
        project_id="proj_a",
        permissions={"module.config.edit", "module.config.view"},
    )

    async def reject_service(request: Request):
        raise AssertionError("invalid body resolved DatusService")

    app.dependency_overrides[deps.get_datus_service] = reject_service
    _override_app_context(app, ctx)
    monkeypatch.setattr(config_routes.deps, "_enterprise_extensions", _enterprise_extensions(enabled=True))

    with TestClient(app, raise_server_exceptions=False) as client:
        response = getattr(client, method)(path, json=json_body)

    assert response.status_code == 422
    assert patched_cm.save_count == 0


def test_config_edit_rbac_denial_precedes_readonly_status(monkeypatch, patched_cm):
    audit_sink = CollectingAuditSink()
    monkeypatch.setenv("DATUS_PLATFORM_STATUS", "readonly")
    app = FastAPI()
    app.include_router(config_routes.router)
    ctx = AppContext(user_id="u1", project_id="proj_a", permissions={"module.config.view"})

    async def reject_service(request: Request):
        raise AssertionError("RBAC denial resolved DatusService")

    app.dependency_overrides[deps.get_datus_service] = reject_service
    _override_app_context(app, ctx)
    monkeypatch.setattr(
        config_routes.deps,
        "_enterprise_extensions",
        _enterprise_extensions(enabled=True, audit_sink=audit_sink),
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.put(
            "/api/v1/config/models",
            json={"models": {"m1": {"type": "openai", "model": "gpt-test"}}, "target": "m1"},
        )

    assert response.status_code == 403
    assert "module.config.edit" in response.json()["detail"]
    assert patched_cm.save_count == 0
    assert [event.action for event in audit_sink.events] == ["module.config.edit"]


def test_get_config_http_requires_config_view_permission(monkeypatch):
    app = FastAPI()
    app.include_router(config_routes.router)
    ctx = AppContext(user_id="u1", project_id="proj_a", permissions={"module.chat"})
    svc = _mock_svc(datasources={})

    async def override_service(request: Request):
        request.state.app_context = ctx
        return svc

    app.dependency_overrides[deps.get_datus_service] = override_service
    _override_app_context(app, ctx)
    monkeypatch.setattr(config_routes.deps, "_enterprise_extensions", _enterprise_extensions(enabled=True))

    with TestClient(app) as client:
        response = client.get("/api/v1/config/agent")

    assert response.status_code == 403


def test_get_config_http_allows_config_view_permission(monkeypatch):
    app = FastAPI()
    app.include_router(config_routes.router)
    ctx = AppContext(user_id="u1", project_id="proj_a", permissions={"module.config.view"})
    svc = _mock_svc(datasources={"db_a": {"type": "duckdb"}}, target="m1", models={"m1": {"type": "openai"}})

    async def override_service(request: Request):
        request.state.app_context = ctx
        return svc

    app.dependency_overrides[deps.get_datus_service] = override_service
    _override_app_context(app, ctx)
    monkeypatch.setattr(config_routes.deps, "_enterprise_extensions", _enterprise_extensions(enabled=True))

    with TestClient(app) as client:
        response = client.get("/api/v1/config/agent")

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["data"]["datasources"] == {"db_a": {"type": "duckdb"}}


def test_config_probe_http_requires_config_edit_permission(monkeypatch):
    app = FastAPI()
    app.include_router(config_routes.router)
    ctx = AppContext(user_id="u1", project_id="proj_a", permissions={"module.config.view"})
    svc = MagicMock()
    model_probe = MagicMock()
    datasource_probe = MagicMock()

    async def override_service(request: Request):
        request.state.app_context = ctx
        return svc

    app.dependency_overrides[deps.get_datus_service] = override_service
    _override_app_context(app, ctx)
    monkeypatch.setattr(config_routes.deps, "_enterprise_extensions", _enterprise_extensions(enabled=True))
    monkeypatch.setattr(config_routes, "_probe_llm_sync", model_probe)
    monkeypatch.setattr(config_routes, "_probe_datasource_sync", datasource_probe)

    with TestClient(app) as client:
        model_response = client.post("/api/v1/config/models/test", json={"type": "openai", "model": "gpt-test"})
        datasource_response = client.post("/api/v1/config/datasources/test", json={"type": "duckdb"})

    assert model_response.status_code == 403
    assert datasource_response.status_code == 403
    model_probe.assert_not_called()
    datasource_probe.assert_not_called()


def test_config_probe_http_allows_config_edit_permission(monkeypatch):
    app = FastAPI()
    app.include_router(config_routes.router)
    ctx = AppContext(user_id="u1", project_id="proj_a", permissions={"module.config.edit"})
    svc = MagicMock()
    model_probe = MagicMock()
    datasource_probe = MagicMock()

    async def override_service(request: Request):
        request.state.app_context = ctx
        return svc

    app.dependency_overrides[deps.get_datus_service] = override_service
    _override_app_context(app, ctx)
    monkeypatch.setattr(config_routes.deps, "_enterprise_extensions", _enterprise_extensions(enabled=True))
    monkeypatch.setattr(config_routes, "_probe_llm_sync", model_probe)
    monkeypatch.setattr(config_routes, "_probe_datasource_sync", datasource_probe)

    with TestClient(app) as client:
        model_response = client.post("/api/v1/config/models/test", json={"type": "openai", "model": "gpt-test"})
        datasource_response = client.post("/api/v1/config/datasources/test", json={"type": "duckdb"})

    assert model_response.status_code == 200
    assert datasource_response.status_code == 200
    assert model_response.json()["data"] == {"ok": True}
    assert datasource_response.json()["data"] == {"ok": True}
    model_probe.assert_called_once()
    datasource_probe.assert_called_once()


@pytest.mark.asyncio
async def test_test_model_connectivity_ok(monkeypatch):
    """Successful LLM probe returns ok=True and forwards the payload unchanged."""
    captured = {}

    def fake_probe(payload):
        captured["payload"] = payload

    monkeypatch.setattr(config_routes, "_probe_llm_sync", fake_probe)

    body = ProbeModelRequest(type="openai", model="gpt-4o", api_key="sk-xxx", base_url="https://api.openai.com/v1")
    result = await probe_model_connectivity_endpoint(body, _ctx=_ctx())

    assert result.success is True
    assert result.data == {"ok": True}
    assert captured["payload"]["type"] == "openai"
    assert captured["payload"]["api_key"] == "sk-xxx"


@pytest.mark.asyncio
async def test_test_model_connectivity_reports_error_message(monkeypatch):
    """Probe exception is surfaced as ok=False with message; HTTP stays 200."""

    def fake_probe(payload):
        raise RuntimeError("401 unauthorized")

    monkeypatch.setattr(config_routes, "_probe_llm_sync", fake_probe)

    body = ProbeModelRequest(type="openai", model="gpt-4o", api_key="bad")
    result = await probe_model_connectivity_endpoint(body, _ctx=_ctx())

    assert result.success is True
    assert result.data["ok"] is False
    assert "401" in result.data["message"]


@pytest.mark.asyncio
async def test_test_model_connectivity_passes_extra_fields(monkeypatch):
    """Unknown fields on the request body are forwarded to the probe (extra=allow)."""
    captured = {}

    def fake_probe(payload):
        captured["payload"] = payload

    monkeypatch.setattr(config_routes, "_probe_llm_sync", fake_probe)

    body = ProbeModelRequest.model_validate({"type": "openai", "model": "gpt-4o", "api_key": "k", "vendor": "openai"})
    await probe_model_connectivity_endpoint(body, _ctx=_ctx())

    assert captured["payload"].get("vendor") == "openai"


@pytest.mark.asyncio
async def test_test_datasource_connectivity_ok(monkeypatch):
    """Successful datasource probe returns ok=True and forwards the payload unchanged."""
    captured = {}

    def fake_probe(payload):
        captured["payload"] = payload

    monkeypatch.setattr(config_routes, "_probe_datasource_sync", fake_probe)

    body = ProbeDatasourceRequest.model_validate({"type": "duckdb", "uri": "/tmp/test.duckdb"})
    result = await probe_datasource_connectivity_endpoint(body, _ctx=_ctx())

    assert result.data == {"ok": True}
    assert captured["payload"]["type"] == "duckdb"
    assert captured["payload"]["uri"] == "/tmp/test.duckdb"


def test_probe_datasource_sync_uses_flat_db_config_map(monkeypatch):
    """DBManager expects {datasource: DbConfig}, not a nested datasource/database map."""
    captured = {}

    class FakeConn:
        def test_connection(self):
            captured["tested"] = True

    class FakeDBManager:
        def __init__(self, db_configs):
            captured["db_configs"] = db_configs

        def get_conn(self, datasource):
            captured["datasource"] = datasource
            return FakeConn()

        def close(self):
            captured["closed"] = True

    monkeypatch.setattr("datus.tools.db_tools.db_manager.DBManager", FakeDBManager)

    config_routes._probe_datasource_sync({"type": "postgresql", "host": "localhost", "database": "postgres"})

    assert captured["datasource"] == "_probe_"
    assert captured["tested"] is True
    assert captured["closed"] is True
    assert set(captured["db_configs"]) == {"_probe_"}
    assert isinstance(captured["db_configs"]["_probe_"], DbConfig)
    assert captured["db_configs"]["_probe_"].type == "postgresql"


@pytest.mark.asyncio
async def test_test_datasource_connectivity_reports_error_message(monkeypatch):
    """Probe exception is surfaced as ok=False with message; HTTP stays 200."""

    def fake_probe(payload):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(config_routes, "_probe_datasource_sync", fake_probe)

    body = ProbeDatasourceRequest.model_validate({"type": "starrocks", "host": "unreachable", "port": "9999"})
    result = await probe_datasource_connectivity_endpoint(body, _ctx=_ctx())

    assert result.data["ok"] is False
    assert "connection refused" in result.data["message"]
