"""Tests for enterprise production auth providers."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from datus.api.constants import HEADER_PRINCIPAL, HEADER_USER_ID
from datus_enterprise.auth_provider import SignedHeaderAuthProvider


def _request(provider: SignedHeaderAuthProvider, headers: dict[str, str], *, path: str = "/api/v1/me") -> MagicMock:
    timestamp = headers.setdefault("X-Datus-Timestamp", str(int(time.time())))
    signature = provider.sign_request(method="GET", path=path, timestamp=timestamp, headers=headers)
    headers.setdefault("X-Datus-Signature", signature)
    request = MagicMock()
    request.method = "GET"
    request.url.path = path
    request.headers = headers
    return request


@pytest.mark.asyncio
async def test_signed_header_auth_provider_builds_app_context() -> None:
    provider = SignedHeaderAuthProvider(secret="test-secret")
    request = _request(
        provider,
        {
            HEADER_USER_ID: "alice",
            "X-Datus-Project-Id": "finance",
            "X-Datus-Roles": '["analyst", "developer"]',
            "X-Datus-Permissions": "module.chat,module.sql_executor",
            HEADER_PRINCIPAL: '{"department": "fund", "model_policy": {"allowed_models": ["openai/gpt-4.1"]}}',
            "X-Datus-Email": "alice@example.com",
            "X-Datus-Display-Name": "Alice",
        },
    )

    ctx = await provider.authenticate(request)

    assert ctx.user_id == "alice"
    assert ctx.project_id == "finance"
    assert ctx.roles == ["analyst", "developer"]
    assert ctx.permissions == {"module.chat", "module.sql_executor"}
    assert ctx.principal["user_id"] == "alice"
    assert ctx.principal["roles"] == ["analyst", "developer"]
    assert ctx.principal["permissions"] == ["module.chat", "module.sql_executor"]
    assert ctx.principal["department"] == "fund"
    assert ctx.principal["model_policy"] == {"allowed_models": ["openai/gpt-4.1"]}
    assert ctx.principal["email"] == "alice@example.com"
    assert ctx.principal["display_name"] == "Alice"
    assert ctx.is_admin is False


@pytest.mark.asyncio
async def test_signed_header_auth_provider_requires_signature() -> None:
    provider = SignedHeaderAuthProvider(secret="test-secret")
    request = _request(provider, {HEADER_USER_ID: "alice"})
    request.headers = {key: value for key, value in request.headers.items() if key != "X-Datus-Signature"}

    with pytest.raises(HTTPException) as exc_info:
        await provider.authenticate(request)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "AUTH_SIGNATURE_REQUIRED"


@pytest.mark.asyncio
async def test_signed_header_auth_provider_rejects_invalid_signature() -> None:
    provider = SignedHeaderAuthProvider(secret="test-secret")
    request = _request(provider, {HEADER_USER_ID: "alice", "X-Datus-Signature": "bad"})

    with pytest.raises(HTTPException) as exc_info:
        await provider.authenticate(request)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "AUTH_SIGNATURE_INVALID"


@pytest.mark.asyncio
async def test_signed_header_auth_provider_rejects_expired_timestamp() -> None:
    provider = SignedHeaderAuthProvider(secret="test-secret", max_skew_seconds=1)
    request = _request(provider, {HEADER_USER_ID: "alice", "X-Datus-Timestamp": str(int(time.time()) - 60)})

    with pytest.raises(HTTPException) as exc_info:
        await provider.authenticate(request)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "AUTH_TIMESTAMP_EXPIRED"


@pytest.mark.asyncio
async def test_signed_header_auth_provider_rejects_reserved_principal_fields() -> None:
    provider = SignedHeaderAuthProvider(secret="test-secret")
    request = _request(provider, {HEADER_USER_ID: "alice", HEADER_PRINCIPAL: '{"user_id": "mallory"}'})

    with pytest.raises(HTTPException) as exc_info:
        await provider.authenticate(request)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "AUTH_PRINCIPAL_INVALID"


@pytest.mark.asyncio
async def test_signed_header_auth_provider_loads_secret_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATUS_PROXY_AUTH_SECRET", "test-secret")
    provider = SignedHeaderAuthProvider(secret_env="DATUS_PROXY_AUTH_SECRET")
    request = _request(provider, {HEADER_USER_ID: "alice"})

    ctx = await provider.authenticate(request)

    assert ctx.user_id == "alice"
