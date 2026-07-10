import sqlite3
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.enterprise.defaults import (
    InMemorySessionOwnerStore,
    InMemoryUserModelCredentialStore,
    LocalAuthorizationProvider,
    NoopAuditSink,
    PassthroughConfigProjector,
    SqliteUserModelCredentialStore,
)
from datus.api.enterprise.loader import EnterpriseExtensions
from datus_enterprise.api import model_credential_routes
from datus_enterprise.model_credentials import apply_user_model_credential


def _agent_config(*, custom_models_enabled: bool = False):
    return SimpleNamespace(
        provider_catalog={
            "providers": {
                "openai": {
                    "auth_type": "api_key",
                    "label": "OpenAI",
                    "default_model": "gpt-4.1",
                    "models": ["gpt-4.1", "gpt-4.1-mini"],
                },
                "codex": {
                    "auth_type": "oauth",
                    "label": "Codex",
                    "models": ["gpt-5.1-codex"],
                },
            }
        },
        enterprise_config={
            "user_model_credentials": {
                "custom_openai_compatible": {
                    "enabled": custom_models_enabled,
                    "allowed_base_urls": ["https://models.corp/*", "http://localhost:8000/v1"],
                }
            }
        },
        providers={},
        set_active_provider_model=lambda provider, model, persist=False: None,
    )


def _install_extensions(monkeypatch, *, store=None):
    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        EnterpriseExtensions(
            enabled=True,
            authorization_provider=LocalAuthorizationProvider(),
            config_projector=PassthroughConfigProjector(),
            session_owner_store=InMemorySessionOwnerStore(),
            audit_sink=NoopAuditSink(),
            user_model_credential_store=store or InMemoryUserModelCredentialStore(),
        ),
    )


def _client(ctx: AppContext, svc=None):
    app = FastAPI()
    app.include_router(model_credential_routes.router)

    async def override_service(request: Request):
        request.state.app_context = ctx
        return svc or SimpleNamespace(agent_config=_agent_config())

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = override_service
    app.dependency_overrides[deps.get_request_app_context] = override_context
    return TestClient(app)


def test_model_credentials_crud_redacts_api_key(monkeypatch):
    store = InMemoryUserModelCredentialStore()
    _install_extensions(monkeypatch, store=store)
    ctx = AppContext(user_id="alice", permissions={"module.chat"})

    with _client(ctx) as client:
        providers_response = client.get("/api/v1/me/model-providers")
        create_response = client.post(
            "/api/v1/me/model-credentials",
            json={
                "provider": "openai",
                "model": "gpt-4.1",
                "api_key": "sk-alice-secret",
                "display_name": "Alice OpenAI",
                "enabled": True,
            },
        )
        credential_id = create_response.json()["data"]["id"]
        list_response = client.get("/api/v1/me/model-credentials")
        preference_response = client.get("/api/v1/me/model-preferences")
        delete_response = client.delete(f"/api/v1/me/model-credentials/{credential_id}")

    assert providers_response.status_code == 200
    assert [item["provider"] for item in providers_response.json()["data"]] == ["openai"]
    assert create_response.status_code == 200
    assert create_response.json()["data"]["ref_hint"] == "***cret"
    assert "sk-alice-secret" not in create_response.text
    assert "sk-alice-secret" not in list_response.text
    assert list_response.json()["data"][0]["id"] == credential_id
    assert preference_response.json()["data"]["default_credential_id"] == credential_id
    assert preference_response.json()["data"]["default_model"] == "gpt-4.1"
    assert delete_response.json()["data"] == {"deleted": True}


def test_model_credentials_are_isolated_by_current_user(monkeypatch):
    store = InMemoryUserModelCredentialStore()
    _install_extensions(monkeypatch, store=store)

    with _client(AppContext(user_id="alice", permissions={"module.chat"})) as client:
        client.post(
            "/api/v1/me/model-credentials",
            json={"provider": "openai", "model": "gpt-4.1", "api_key": "sk-alice-secret"},
        )

    with _client(AppContext(user_id="bob", permissions={"module.chat"})) as client:
        response = client.get("/api/v1/me/model-credentials")

    assert response.status_code == 200
    assert response.json()["data"] == []


def test_model_credential_rejects_unknown_provider(monkeypatch):
    _install_extensions(monkeypatch, store=InMemoryUserModelCredentialStore())
    ctx = AppContext(user_id="alice", permissions={"module.chat"})

    with _client(ctx) as client:
        response = client.post(
            "/api/v1/me/model-credentials",
            json={"provider": "unknown", "model": "gpt-4.1", "api_key": "sk-alice-secret"},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "MODEL_NOT_ALLOWED_FOR_PROVIDER"


def test_model_credential_allows_custom_openai_compatible_endpoint(monkeypatch):
    store = InMemoryUserModelCredentialStore()
    _install_extensions(monkeypatch, store=store)
    ctx = AppContext(user_id="alice", permissions={"module.chat"})
    svc = SimpleNamespace(agent_config=_agent_config(custom_models_enabled=True))

    with _client(ctx, svc=svc) as client:
        providers_response = client.get("/api/v1/me/model-providers")
        create_response = client.post(
            "/api/v1/me/model-credentials",
            json={
                "provider": "custom_openai_compatible",
                "model": "Qwen3.5-397B",
                "base_url": "https://models.corp/v1",
                "api_key": "sk-local-secret",
                "display_name": "Self-hosted vLLM",
            },
        )

    assert providers_response.status_code == 200
    assert any(item["custom"] is True for item in providers_response.json()["data"])
    assert create_response.status_code == 200
    assert create_response.json()["data"]["provider"] == "openai"
    assert create_response.json()["data"]["model"] == "Qwen3.5-397B"
    assert create_response.json()["data"]["base_url"] == "https://models.corp/v1"
    assert "sk-local-secret" not in create_response.text


def test_model_credential_rejects_custom_endpoint_when_not_allowed(monkeypatch):
    _install_extensions(monkeypatch, store=InMemoryUserModelCredentialStore())
    ctx = AppContext(user_id="alice", permissions={"module.chat"})
    svc = SimpleNamespace(agent_config=_agent_config(custom_models_enabled=True))

    with _client(ctx, svc=svc) as client:
        response = client.post(
            "/api/v1/me/model-credentials",
            json={
                "provider": "openai",
                "model": "Qwen3.5-397B",
                "base_url": "https://evil.example/v1",
                "api_key": "sk-local-secret",
            },
        )

    assert response.status_code == 400
    assert "Model base URL is not allowed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_apply_user_model_credential_uses_request_scoped_config_without_cross_user_leakage():
    store = InMemoryUserModelCredentialStore()
    await store.put_credential(
        user_id="alice",
        credential_id="alice-key",
        provider="openai",
        model="gpt-4.1",
        api_key="sk-alice-secret",
    )
    await store.put_credential(
        user_id="bob",
        credential_id="bob-key",
        provider="openai",
        model="gpt-4.1-mini",
        api_key="sk-bob-secret",
    )

    class Config:
        def __init__(self):
            self.provider_catalog = _agent_config().provider_catalog
            self.providers = {}
            self._target_provider = None
            self._target_model = None

        def set_active_provider_model(self, provider, model, persist=False):
            self._target_provider = provider
            self._target_model = model

    base = Config()
    alice_config = Config()
    bob_config = Config()

    alice = await apply_user_model_credential(
        store=store,
        user_id="alice",
        agent_config=alice_config,
        requested_model=None,
    )
    bob = await apply_user_model_credential(
        store=store,
        user_id="bob",
        agent_config=bob_config,
        requested_model=None,
    )

    assert alice == {
        "credential_id": "alice-key",
        "provider": "openai",
        "model": "gpt-4.1",
        "base_url": None,
        "ref_hint": "***cret",
    }
    assert bob["credential_id"] == "bob-key"
    assert alice_config.providers["openai"].api_key == "sk-alice-secret"
    assert bob_config.providers["openai"].api_key == "sk-bob-secret"
    assert base.providers == {}
    assert base._target_provider is None


@pytest.mark.asyncio
async def test_apply_user_model_credential_selects_the_requested_credential_id():
    store = InMemoryUserModelCredentialStore()
    await store.put_credential(
        user_id="alice",
        credential_id="first-key",
        provider="openai",
        model="gpt-4.1",
        api_key="sk-first-secret",
    )
    await store.put_credential(
        user_id="alice",
        credential_id="second-key",
        provider="openai",
        model="gpt-4.1-mini",
        api_key="sk-second-secret",
    )

    class Config:
        def __init__(self):
            self.provider_catalog = _agent_config().provider_catalog
            self.providers = {}
            self._target_provider = None
            self._target_model = None

        def set_active_provider_model(self, provider, model, persist=False):
            self._target_provider = provider
            self._target_model = model

    config = Config()
    applied = await apply_user_model_credential(
        store=store,
        user_id="alice",
        agent_config=config,
        requested_model=None,
        requested_credential_id="second-key",
    )

    assert applied["credential_id"] == "second-key"
    assert config.providers["openai"].api_key == "sk-second-secret"
    assert config._target_model == "gpt-4.1-mini"


@pytest.mark.asyncio
async def test_apply_user_model_credential_rejects_an_unavailable_requested_id():
    store = InMemoryUserModelCredentialStore()

    with pytest.raises(Exception, match="User model credential is unavailable"):
        await apply_user_model_credential(
            store=store,
            user_id="alice",
            agent_config=_agent_config(),
            requested_model=None,
            requested_credential_id="missing-key",
        )


@pytest.mark.asyncio
async def test_apply_user_model_credential_overlays_custom_endpoint_without_shared_mutation():
    store = InMemoryUserModelCredentialStore()
    await store.put_credential(
        user_id="alice",
        credential_id="local-key",
        provider="openai",
        model="Qwen3.5-397B",
        api_key="sk-local-secret",
        base_url="https://models.corp/v1",
    )

    class Config:
        def __init__(self):
            self.provider_catalog = _agent_config().provider_catalog
            self.enterprise_config = _agent_config(custom_models_enabled=True).enterprise_config
            self.providers = {}
            self._target_provider = None
            self._target_model = None

        def set_active_provider_model(self, provider, model, persist=False):
            self._target_provider = provider
            self._target_model = model

    base = Config()
    projected = Config()

    applied = await apply_user_model_credential(
        store=store,
        user_id="alice",
        agent_config=projected,
        requested_model=None,
    )

    assert applied == {
        "credential_id": "local-key",
        "provider": "openai",
        "model": "Qwen3.5-397B",
        "base_url": "https://models.corp/v1",
        "ref_hint": "***cret",
    }
    assert projected.providers["openai"].api_key == "sk-local-secret"
    assert projected.providers["openai"].base_url == "https://models.corp/v1"
    assert projected._target_model == "Qwen3.5-397B"
    assert base.providers == {}


@pytest.mark.asyncio
async def test_sqlite_user_model_credential_store_encrypts_api_key(tmp_path):
    db_path = tmp_path / "credentials.db"
    store = SqliteUserModelCredentialStore(str(db_path), encryption_secret="x" * 32)

    await store.put_credential(
        user_id="alice",
        credential_id="cred-1",
        provider="openai",
        model="gpt-4.1",
        api_key="sk-alice-secret",
        base_url="https://models.corp/v1",
    )

    record = await store.get_credential("alice", "cred-1")
    with sqlite3.connect(db_path) as conn:
        blob, base_url = conn.execute("SELECT api_key_blob, base_url FROM user_model_credentials").fetchone()

    assert record["api_key"] == "sk-alice-secret"
    assert record["base_url"] == "https://models.corp/v1"
    assert base_url == "https://models.corp/v1"
    assert record["ref_hint"] == "***cret"
    assert "sk-alice-secret" not in blob
