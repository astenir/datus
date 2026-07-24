"""Unit tests for datus/api/routes/models_routes.py."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, Request
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
from datus.api.routes import models_routes
from datus.api.routes.models_routes import list_models
from datus.configuration.agent_config import ModelConfig


def _make_svc(
    *,
    catalog: Dict[str, Any],
    available: Optional[Iterable[str]] = None,
    custom_models: Optional[Dict[str, Any]] = None,
    target_provider: Optional[str] = None,
    target_model: Optional[str] = None,
    target: str = "",
) -> MagicMock:
    """Build a MagicMock svc with provider_catalog + provider_available wired up.

    ``available`` is the whitelist of providers for which
    ``provider_available()`` returns True. None means all providers in the
    catalog are available.
    """
    allowed = set(available) if available is not None else set((catalog.get("providers") or {}).keys())
    svc = MagicMock()
    svc.agent_config.provider_catalog = catalog
    svc.agent_config.provider_available.side_effect = lambda p: p in allowed
    svc.agent_config.models = custom_models if custom_models is not None else {}
    svc.agent_config._target_provider = target_provider
    svc.agent_config._target_model = target_model
    svc.agent_config.target = target
    svc.agent_config.embedding_model_targets = set()
    return svc


def _basic_catalog() -> Dict[str, Any]:
    return {
        "providers": {
            "openai": {
                "type": "openai",
                "base_url": "https://api.openai.com/v1",
                "api_key_env": "OPENAI_API_KEY",
                "models": ["gpt-4o", "gpt-4.1"],
                "default_model": "gpt-4.1",
            },
            "claude": {
                "type": "claude",
                "base_url": "https://api.anthropic.com",
                "api_key_env": "ANTHROPIC_API_KEY",
                "models": ["claude-sonnet-4-5"],
                "default_model": "claude-sonnet-4-5",
            },
            "deepseek": {
                "type": "deepseek",
                "base_url": "https://api.deepseek.com",
                "api_key_env": "DEEPSEEK_API_KEY",
                "models": ["deepseek-chat"],
                "default_model": "deepseek-chat",
            },
        },
        "model_specs": {
            "gpt-4.1": {"context_length": 400000, "max_tokens": 128000},
            "gpt-4o": {"context_length": 128000, "max_tokens": 16384},
            "claude-sonnet-4-5": {"context_length": 1048576, "max_tokens": 65536},
            "deepseek-chat": {"context_length": 65535, "max_tokens": 8192},
        },
    }


def _install_extensions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=True,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=NoopAuditSink(),
        ),
    )


def _client(ctx: AppContext, svc: MagicMock) -> TestClient:
    app = FastAPI()
    app.include_router(models_routes.router)

    async def override_service(request: Request):
        request.state.app_context = ctx
        return svc

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = override_service
    app.dependency_overrides[deps.get_request_app_context] = override_context
    return TestClient(app)


def test_models_route_rejects_users_without_chat_or_config_view(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_extensions(monkeypatch)
    svc = _make_svc(catalog=_basic_catalog(), available={"openai"})
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.datasource_catalog"})
    with _client(ctx, svc) as client:
        response = client.get("/api/v1/models")
    assert response.status_code == 403
    assert "module.config.view" in response.json()["detail"]


def test_models_route_allows_chat_view(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_extensions(monkeypatch)
    monkeypatch.setattr(models_routes, "load_cached_model_details", lambda: None)
    monkeypatch.setattr(models_routes, "load_cache_fetched_at", lambda: None)
    svc = _make_svc(catalog=_basic_catalog(), available={"openai"})
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.chat"})
    with _client(ctx, svc) as client:
        response = client.get("/api/v1/models")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["providers"] == ["openai"]


def test_models_route_allows_config_view(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_extensions(monkeypatch)
    monkeypatch.setattr(models_routes, "load_cached_model_details", lambda: None)
    monkeypatch.setattr(models_routes, "load_cache_fetched_at", lambda: None)
    svc = _make_svc(catalog=_basic_catalog(), available={"openai"})
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.config.view"})
    with _client(ctx, svc) as client:
        response = client.get("/api/v1/models")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["providers"] == ["openai"]


def test_models_route_filters_with_enterprise_model_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_extensions(monkeypatch)
    monkeypatch.setattr(models_routes, "load_cached_model_details", lambda: None)
    monkeypatch.setattr(models_routes, "load_cache_fetched_at", lambda: None)
    svc = _make_svc(
        catalog=_basic_catalog(),
        available={"openai", "claude"},
        custom_models={"local-safe": _custom_model("local-safe-model")},
        target_provider="openai",
        target_model="gpt-4o",
    )
    ctx = AppContext(
        user_id="u1",
        project_id="proj",
        permissions={"module.config.view"},
        principal={"model_policy": {"allowed_models": ["openai/gpt-4.1", "custom/local-safe"]}},
    )
    with _client(ctx, svc) as client:
        response = client.get("/api/v1/models")
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["current_model"] is None
    assert body["data"]["providers"] == ["openai", "custom"]
    assert [(item["provider"], item["id"]) for item in body["data"]["models"]] == [
        ("openai", "gpt-4.1"),
        ("custom", "local-safe"),
    ]


def _custom_model(model: str, type_: str = "openai") -> ModelConfig:
    return ModelConfig(type=type_, api_key="sk-test", model=model)


class TestCustomModelsDownstream:
    @pytest.mark.asyncio
    async def test_custom_embedding_model_is_marked_and_not_selected_as_current(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(models_routes, "load_cached_model_details", lambda: None)
        monkeypatch.setattr(models_routes, "load_cache_fetched_at", lambda: None)
        svc = _make_svc(
            catalog=_basic_catalog(),
            available=set(),
            custom_models={"qwen-ebd": _custom_model("Qwen/Qwen3-Embedding-0.6B")},
            target="qwen-ebd",
        )
        svc.agent_config.embedding_model_targets = {"qwen-ebd"}
        result = await list_models(svc)
        assert result.data.models[0].capabilities == ["embedding"]
        assert result.data.current_model is None
