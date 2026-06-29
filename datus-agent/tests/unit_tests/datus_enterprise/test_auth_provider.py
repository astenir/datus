"""Tests for enterprise production auth providers."""

from __future__ import annotations

import time
from base64 import b64encode
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import HTTPException

from datus.api.constants import HEADER_PRINCIPAL, HEADER_USER_ID
from datus_enterprise import auth_provider
from datus_enterprise.auth_provider import SignedHeaderAuthProvider, UserInfoBearerAuthProvider


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


def _bearer_request(token: str | None = "token-1") -> MagicMock:
    request = MagicMock()
    request.headers = {}
    if token is not None:
        request.headers["Authorization"] = f"Bearer {token}"
    return request


def _basic_request(username: str = "admin", password: str = "admin") -> MagicMock:
    request = MagicMock()
    encoded = b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    request.headers = {"Authorization": f"Basic {encoded}"}
    return request


def _patch_async_client(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    transport = httpx.MockTransport(handler)
    original_async_client = httpx.AsyncClient

    def _factory(*args, **kwargs):
        kwargs["transport"] = transport
        return original_async_client(*args, **kwargs)

    monkeypatch.setattr(auth_provider.httpx, "AsyncClient", _factory)


@pytest.mark.asyncio
async def test_userinfo_bearer_auth_provider_builds_app_context(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert str(request.url) == "https://sso.example.internal/api/userinfo"
        assert request.headers["Authorization"] == "Bearer token-1"
        assert request.headers["Content-Type"] == "application/x-www-form-urlencoded"
        return httpx.Response(
            200,
            json={
                "userId": 698,
                "username": "x_liuyanping",
                "realname": "刘延平",
                "email": "x_liuyanping@phfund.com.cn",
                "mobilePhone": "",
                "fixedPhone": "",
                "company": "",
                "department": "fund",
                "title": "analyst",
                "userStatus": "正常",
                "sortNumber": "0",
                "permissionList": [None],
            },
        )

    _patch_async_client(monkeypatch, handler)
    provider = UserInfoBearerAuthProvider(userinfo_url="https://sso.example.internal/api/userinfo")

    ctx = await provider.authenticate(_bearer_request())

    assert ctx.user_id == "x_liuyanping"
    assert ctx.project_id is None
    assert ctx.roles == []
    assert ctx.permissions == set()
    assert ctx.is_admin is False
    assert ctx.principal["user_id"] == "x_liuyanping"
    assert ctx.principal["external_user_id"] == "698"
    assert ctx.principal["display_name"] == "刘延平"
    assert ctx.principal["email"] == "x_liuyanping@phfund.com.cn"
    assert ctx.principal["department"] == "fund"
    assert "permissionList" not in ctx.principal


@pytest.mark.asyncio
async def test_userinfo_bearer_auth_provider_requires_bearer_header() -> None:
    provider = UserInfoBearerAuthProvider(userinfo_url="https://sso.example.internal/api/userinfo")

    with pytest.raises(HTTPException) as exc_info:
        await provider.authenticate(_bearer_request(token=None))

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "AUTH_REQUIRED"


@pytest.mark.asyncio
async def test_userinfo_bearer_auth_provider_dev_admin_defaults_without_header() -> None:
    provider = UserInfoBearerAuthProvider(
        userinfo_url="https://sso.example.internal/api/userinfo",
        dev_admin_enabled=True,
    )

    ctx = await provider.authenticate(_bearer_request(token=None))

    assert ctx.user_id == "admin"
    assert ctx.project_id is None
    assert ctx.is_admin is True
    assert "enterprise_admin" in ctx.roles
    assert "module.*" in ctx.permissions
    assert ctx.datasource_grants == {"*": {"effect": "allow", "allow_catalog": True, "allow_sql": True}}
    assert ctx.principal["auth_mode"] == "dev_admin"
    assert ctx.principal["_datus_dev_admin"] is True


@pytest.mark.asyncio
async def test_userinfo_bearer_auth_provider_dev_admin_accepts_basic_admin() -> None:
    provider = UserInfoBearerAuthProvider(
        userinfo_url="https://sso.example.internal/api/userinfo",
        default_project_id="enterprise",
        dev_admin_enabled="true",
        dev_admin_require_basic_auth="true",
    )

    ctx = await provider.authenticate(_basic_request())

    assert ctx.user_id == "admin"
    assert ctx.project_id == "enterprise"
    assert ctx.is_admin is True


@pytest.mark.asyncio
async def test_userinfo_bearer_auth_provider_dev_admin_rejects_missing_or_wrong_basic() -> None:
    provider = UserInfoBearerAuthProvider(
        userinfo_url="https://sso.example.internal/api/userinfo",
        dev_admin_enabled=True,
        dev_admin_require_basic_auth=True,
    )

    with pytest.raises(HTTPException) as missing:
        await provider.authenticate(_bearer_request(token=None))
    assert missing.value.status_code == 401
    assert missing.value.detail == "AUTH_REQUIRED"

    with pytest.raises(HTTPException) as wrong:
        await provider.authenticate(_basic_request(password="wrong"))
    assert wrong.value.status_code == 401
    assert wrong.value.detail == "AUTH_TOKEN_INVALID"


@pytest.mark.asyncio
async def test_userinfo_bearer_auth_provider_rejects_bad_bearer_format() -> None:
    provider = UserInfoBearerAuthProvider(userinfo_url="https://sso.example.internal/api/userinfo")
    request = MagicMock()
    request.headers = {"Authorization": "token-1"}

    with pytest.raises(HTTPException) as exc_info:
        await provider.authenticate(request)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "AUTH_TOKEN_INVALID"


@pytest.mark.asyncio
async def test_userinfo_bearer_auth_provider_rejects_userinfo_401(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_async_client(monkeypatch, lambda _request: httpx.Response(401, json={"error": "unauthorized"}))
    provider = UserInfoBearerAuthProvider(userinfo_url="https://sso.example.internal/api/userinfo")

    with pytest.raises(HTTPException) as exc_info:
        await provider.authenticate(_bearer_request())

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "AUTH_TOKEN_INVALID"


@pytest.mark.asyncio
async def test_userinfo_bearer_auth_provider_rejects_missing_user_id(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_async_client(monkeypatch, lambda _request: httpx.Response(200, json={"realname": "刘延平"}))
    provider = UserInfoBearerAuthProvider(userinfo_url="https://sso.example.internal/api/userinfo")

    with pytest.raises(HTTPException) as exc_info:
        await provider.authenticate(_bearer_request())

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "AUTH_REQUIRED"


@pytest.mark.asyncio
async def test_userinfo_bearer_auth_provider_rejects_invalid_user_id(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_async_client(monkeypatch, lambda _request: httpx.Response(200, json={"username": "bad user"}))
    provider = UserInfoBearerAuthProvider(userinfo_url="https://sso.example.internal/api/userinfo")

    with pytest.raises(HTTPException) as exc_info:
        await provider.authenticate(_bearer_request())

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "AUTH_USER_INVALID"


@pytest.mark.asyncio
async def test_userinfo_bearer_auth_provider_rejects_disallowed_status(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_async_client(
        monkeypatch,
        lambda _request: httpx.Response(200, json={"username": "x_liuyanping", "userStatus": "停用"}),
    )
    provider = UserInfoBearerAuthProvider(userinfo_url="https://sso.example.internal/api/userinfo")

    with pytest.raises(HTTPException) as exc_info:
        await provider.authenticate(_bearer_request())

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "AUTH_USER_DISABLED"


@pytest.mark.asyncio
async def test_userinfo_bearer_auth_provider_rejects_missing_status(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_async_client(monkeypatch, lambda _request: httpx.Response(200, json={"username": "x_liuyanping"}))
    provider = UserInfoBearerAuthProvider(userinfo_url="https://sso.example.internal/api/userinfo")

    with pytest.raises(HTTPException) as exc_info:
        await provider.authenticate(_bearer_request())

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "AUTH_USER_DISABLED"


@pytest.mark.asyncio
async def test_userinfo_bearer_auth_provider_maps_configured_user_id_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_async_client(monkeypatch, lambda _request: httpx.Response(200, json={"userId": 698, "userStatus": "正常"}))
    provider = UserInfoBearerAuthProvider(
        userinfo_url="https://sso.example.internal/api/userinfo",
        user_id_field="userId",
    )

    ctx = await provider.authenticate(_bearer_request())

    assert ctx.user_id == "698"
    assert ctx.principal["external_user_id"] == "698"


@pytest.mark.asyncio
async def test_userinfo_bearer_auth_provider_fails_closed_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("slow", request=request)

    _patch_async_client(monkeypatch, handler)
    provider = UserInfoBearerAuthProvider(userinfo_url="https://sso.example.internal/api/userinfo")

    with pytest.raises(HTTPException) as exc_info:
        await provider.authenticate(_bearer_request())

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "AUTH_USERINFO_TIMEOUT"
