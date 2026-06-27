"""Enterprise production auth providers."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from collections.abc import Iterable
from typing import Any

import httpx
from fastapi import HTTPException, Request

from datus.api.auth.context import AppContext
from datus.api.auth.provider import EvictCallback
from datus.api.constants import HEADER_PRINCIPAL, HEADER_USER_ID, USER_ID_PATTERN


class UserInfoBearerAuthProvider:
    """Authenticate enterprise access tokens through a user-info endpoint.

    This provider is for enterprise environments where the gateway cannot be
    changed. Datus receives ``Authorization: Bearer <access_token>``, calls the
    enterprise user-info endpoint with the same bearer token, and maps the
    response to ``AppContext``. Authorization still comes from Datus RBAC stores.
    """

    def __init__(
        self,
        *,
        userinfo_url: str,
        timeout_seconds: float = 3.0,
        authorization_header: str = "Authorization",
        content_type: str = "application/x-www-form-urlencoded",
        user_id_field: str = "username",
        external_user_id_field: str = "userId",
        email_field: str = "email",
        display_name_field: str = "realname",
        status_field: str = "userStatus",
        allowed_statuses: list[str] | None = None,
        default_project_id: str | None = None,
        principal_fields: list[str] | None = None,
    ) -> None:
        normalized_url = userinfo_url.strip()
        if not normalized_url:
            raise ValueError("UserInfoBearerAuthProvider requires userinfo_url.")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive.")
        if default_project_id and not USER_ID_PATTERN.match(default_project_id):
            raise ValueError("default_project_id contains invalid characters.")

        self._userinfo_url = normalized_url
        self._timeout_seconds = float(timeout_seconds)
        self._authorization_header = authorization_header
        self._content_type = content_type
        self._user_id_field = user_id_field
        self._external_user_id_field = external_user_id_field
        self._email_field = email_field
        self._display_name_field = display_name_field
        self._status_field = status_field
        self._allowed_statuses = {value.strip() for value in (allowed_statuses or ["正常"]) if value.strip()}
        self._default_project_id = default_project_id
        self._principal_fields = principal_fields or [
            external_user_id_field,
            user_id_field,
            display_name_field,
            email_field,
            "mobilePhone",
            "fixedPhone",
            "company",
            "department",
            "title",
            status_field,
            "sortNumber",
        ]
        self._evict_callbacks: list[EvictCallback] = []

    async def authenticate(self, request: Request) -> AppContext:
        token = self._read_bearer_token(request)
        profile = await self._fetch_userinfo(token)
        user_id = _require_safe_user_id(_profile_str(profile, self._user_id_field))
        self._validate_status(profile)

        principal = self._principal_from_profile(profile)
        principal["user_id"] = user_id

        return AppContext(
            user_id=user_id,
            project_id=self._default_project_id,
            config=None,
            principal=principal,
            roles=[],
            permissions=set(),
            is_admin=False,
        )

    def on_evict(self, callback: EvictCallback) -> None:
        self._evict_callbacks.append(callback)

    def _read_bearer_token(self, request: Request) -> str:
        raw = request.headers.get(self._authorization_header)
        if raw is None:
            raise HTTPException(status_code=401, detail="AUTH_REQUIRED")
        value = raw.strip()
        scheme, _, token = value.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise HTTPException(status_code=401, detail="AUTH_TOKEN_INVALID")
        return token.strip()

    async def _fetch_userinfo(self, token: str) -> dict[str, Any]:
        headers = {
            self._authorization_header: f"Bearer {token}",
            "Content-Type": self._content_type,
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.get(self._userinfo_url, headers=headers)
        except httpx.TimeoutException as e:
            raise HTTPException(status_code=503, detail="AUTH_USERINFO_TIMEOUT") from e
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail="AUTH_USERINFO_UNAVAILABLE") from e

        if response.status_code == 401:
            raise HTTPException(status_code=401, detail="AUTH_TOKEN_INVALID")
        if response.status_code >= 400:
            raise HTTPException(status_code=503, detail="AUTH_USERINFO_UNAVAILABLE")
        try:
            data = response.json()
        except ValueError as e:
            raise HTTPException(status_code=503, detail="AUTH_USERINFO_INVALID") from e
        if not isinstance(data, dict):
            raise HTTPException(status_code=503, detail="AUTH_USERINFO_INVALID")
        return data

    def _validate_status(self, profile: dict[str, Any]) -> None:
        if not self._allowed_statuses or not self._status_field:
            return
        status = _profile_str(profile, self._status_field)
        if status and status not in self._allowed_statuses:
            raise HTTPException(status_code=403, detail="AUTH_USER_DISABLED")

    def _principal_from_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        principal: dict[str, Any] = {}
        for field in self._principal_fields:
            if not field or field in {"user_id", "roles", "permissions"}:
                continue
            value = profile.get(field)
            if value is None:
                continue
            if isinstance(value, (str, int, float, bool)):
                principal[field] = value

        email = _profile_str(profile, self._email_field)
        display_name = _profile_str(profile, self._display_name_field)
        external_user_id = _profile_str(profile, self._external_user_id_field)
        if email:
            principal["email"] = email
        if display_name:
            principal["display_name"] = display_name
        if external_user_id:
            principal["external_user_id"] = external_user_id
        return principal


class SignedHeaderAuthProvider:
    """Authenticate identities asserted by a trusted reverse proxy.

    The proxy must sign the configured identity headers with HMAC-SHA256. This
    lets enterprise deployments use SSO at the gateway while preventing direct
    clients from spoofing ``X-Datus-User-Id`` or RBAC metadata headers.
    """

    def __init__(
        self,
        *,
        secret: str | None = None,
        secret_env: str | None = None,
        signature_header: str = "X-Datus-Signature",
        timestamp_header: str = "X-Datus-Timestamp",
        user_header: str = HEADER_USER_ID,
        project_header: str = "X-Datus-Project-Id",
        roles_header: str = "X-Datus-Roles",
        permissions_header: str = "X-Datus-Permissions",
        principal_header: str = HEADER_PRINCIPAL,
        email_header: str = "X-Datus-Email",
        display_name_header: str = "X-Datus-Display-Name",
        max_skew_seconds: int = 300,
        default_project_id: str | None = None,
    ) -> None:
        resolved_secret = secret or (os.getenv(secret_env) if secret_env else None)
        if not resolved_secret:
            raise ValueError("SignedHeaderAuthProvider requires secret or secret_env.")
        if max_skew_seconds <= 0:
            raise ValueError("max_skew_seconds must be positive.")
        if default_project_id and not USER_ID_PATTERN.match(default_project_id):
            raise ValueError("default_project_id contains invalid characters.")

        self._secret = resolved_secret.encode("utf-8")
        self._signature_header = signature_header
        self._timestamp_header = timestamp_header
        self._user_header = user_header
        self._project_header = project_header
        self._roles_header = roles_header
        self._permissions_header = permissions_header
        self._principal_header = principal_header
        self._email_header = email_header
        self._display_name_header = display_name_header
        self._max_skew_seconds = int(max_skew_seconds)
        self._default_project_id = default_project_id
        self._evict_callbacks: list[EvictCallback] = []
        self._signed_headers = [
            self._user_header,
            self._project_header,
            self._roles_header,
            self._permissions_header,
            self._principal_header,
            self._email_header,
            self._display_name_header,
        ]

    async def authenticate(self, request: Request) -> AppContext:
        timestamp = self._read_timestamp(request)
        self._verify_signature(request, timestamp)

        user_id = _require_safe_user_id(_header_value(request, self._user_header))
        project_id = _optional_safe_id(_header_value(request, self._project_header)) or self._default_project_id
        roles = _string_list_header(_header_value(request, self._roles_header))
        permissions = set(_string_list_header(_header_value(request, self._permissions_header)))
        principal = _principal_header(_header_value(request, self._principal_header))
        principal.update(
            {
                "user_id": user_id,
                "roles": roles,
                "permissions": sorted(permissions),
            }
        )

        email = _header_value(request, self._email_header)
        display_name = _header_value(request, self._display_name_header)
        if email:
            principal["email"] = email
        if display_name:
            principal["display_name"] = display_name

        return AppContext(
            user_id=user_id,
            project_id=project_id,
            config=None,
            principal=principal,
            roles=roles,
            permissions=permissions,
            is_admin=_matches_admin(roles, permissions),
        )

    def on_evict(self, callback: EvictCallback) -> None:
        self._evict_callbacks.append(callback)

    def _read_timestamp(self, request: Request) -> str:
        raw = _header_value(request, self._timestamp_header)
        if not raw:
            raise HTTPException(status_code=401, detail="AUTH_REQUIRED")
        try:
            timestamp = int(raw)
        except ValueError as e:
            raise HTTPException(status_code=401, detail="AUTH_TIMESTAMP_INVALID") from e
        if abs(int(time.time()) - timestamp) > self._max_skew_seconds:
            raise HTTPException(status_code=401, detail="AUTH_TIMESTAMP_EXPIRED")
        return raw

    def _verify_signature(self, request: Request, timestamp: str) -> None:
        provided = _header_value(request, self._signature_header)
        if not provided:
            raise HTTPException(status_code=401, detail="AUTH_SIGNATURE_REQUIRED")
        expected = self.sign_request(
            method=request.method,
            path=request.url.path,
            timestamp=timestamp,
            headers={name: _header_value(request, name) for name in self._signed_headers},
        )
        normalized = provided.removeprefix("sha256=").strip()
        if not hmac.compare_digest(normalized, expected):
            raise HTTPException(status_code=401, detail="AUTH_SIGNATURE_INVALID")

    def sign_request(self, *, method: str, path: str, timestamp: str, headers: dict[str, str]) -> str:
        """Return the hex HMAC signature for one request.

        Exposed to tests and gateway adapters so the canonical string is not
        reimplemented in multiple places.
        """

        canonical = _canonical_message(
            method=method,
            path=path,
            timestamp=timestamp,
            headers={name: _header_map_value(headers, name) for name in self._signed_headers},
            signed_headers=self._signed_headers,
        )
        return hmac.new(self._secret, canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def _canonical_message(
    *,
    method: str,
    path: str,
    timestamp: str,
    headers: dict[str, str],
    signed_headers: Iterable[str],
) -> str:
    lines = ["v1", method.upper(), path, timestamp]
    for name in signed_headers:
        lines.append(f"{name.lower()}:{headers.get(name, '').strip()}")
    return "\n".join(lines)


def _header_value(request: Request, name: str) -> str:
    raw = request.headers.get(name)
    return raw.strip() if raw is not None else ""


def _header_map_value(headers: dict[str, str], name: str) -> str:
    raw = headers.get(name)
    if raw is None:
        raw = headers.get(name.lower())
    return raw.strip() if raw is not None else ""


def _require_safe_user_id(raw: str) -> str:
    if not raw:
        raise HTTPException(status_code=401, detail="AUTH_REQUIRED")
    if not USER_ID_PATTERN.match(raw):
        raise HTTPException(status_code=401, detail="AUTH_USER_INVALID")
    return raw


def _optional_safe_id(raw: str) -> str | None:
    if not raw:
        return None
    if not USER_ID_PATTERN.match(raw):
        raise HTTPException(status_code=401, detail="AUTH_PROJECT_INVALID")
    return raw


def _string_list_header(raw: str) -> list[str]:
    if not raw:
        return []
    if raw.startswith("["):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=401, detail="AUTH_HEADER_INVALID") from e
        if not isinstance(value, list):
            raise HTTPException(status_code=401, detail="AUTH_HEADER_INVALID")
        return _string_list(value)
    return _string_list(part.strip() for part in raw.split(","))


def _string_list(values: Iterable[Any]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        if not isinstance(value, str):
            raise HTTPException(status_code=401, detail="AUTH_HEADER_INVALID")
        item = value.strip()
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result


def _principal_header(raw: str) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=401, detail="AUTH_PRINCIPAL_INVALID") from e
    if not isinstance(value, dict):
        raise HTTPException(status_code=401, detail="AUTH_PRINCIPAL_INVALID")
    if "user_id" in value or "roles" in value or "permissions" in value:
        raise HTTPException(status_code=401, detail="AUTH_PRINCIPAL_INVALID")
    return value


def _profile_str(profile: dict[str, Any], field: str) -> str:
    if not field:
        return ""
    value = profile.get(field)
    if value is None:
        return ""
    return str(value).strip()


def _matches_admin(roles: list[str], permissions: set[str]) -> bool:
    return "enterprise_admin" in roles or "module.admin.*" in permissions or "module.*" in permissions


__all__ = ["SignedHeaderAuthProvider", "UserInfoBearerAuthProvider"]
