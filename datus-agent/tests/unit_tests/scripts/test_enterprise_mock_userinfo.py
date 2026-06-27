from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from fastapi.testclient import TestClient


def _load_mock():
    path = Path(__file__).resolve().parents[3] / "scripts" / "enterprise_mock_userinfo.py"
    spec = importlib.util.spec_from_file_location("enterprise_mock_userinfo", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_userinfo_returns_alice_profile_for_dev_token():
    mock = _load_mock()

    with TestClient(mock.app) as client:
        response = client.get("/userinfo", headers={"Authorization": "Bearer dev-alice-token"})

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "alice"
    assert body["userId"] == "10001"
    assert body["email"] == "alice@example.com"
    assert body["realname"] == "Alice"
    assert body["userStatus"] == "正常"
    assert body["department"] == "fund"
    assert "roles" not in body
    assert "permissions" not in body


def test_userinfo_rejects_missing_or_invalid_token():
    mock = _load_mock()

    with TestClient(mock.app) as client:
        missing = client.get("/userinfo")
        invalid = client.get("/userinfo", headers={"Authorization": "Bearer wrong-token"})

    assert missing.status_code == 401
    assert missing.json()["detail"] == "missing bearer token"
    assert invalid.status_code == 401
    assert invalid.json()["detail"] == "invalid token"


def test_userinfo_can_return_disabled_profile_for_provider_status_check():
    mock = _load_mock()

    with TestClient(mock.app) as client:
        response = client.get("/userinfo", headers={"Authorization": "Bearer disabled-token"})

    assert response.status_code == 200
    assert response.json()["username"] == "disabled_user"
    assert response.json()["userStatus"] == "停用"


def test_tokens_lists_available_local_dev_tokens_without_extra_profile_fields():
    mock = _load_mock()

    with TestClient(mock.app) as client:
        response = client.get("/tokens")

    assert response.status_code == 200
    tokens = response.json()
    assert {"token": "dev-alice-token", "username": "alice", "userStatus": "正常"} in tokens
    assert {"token": "disabled-token", "username": "disabled_user", "userStatus": "停用"} in tokens
    assert all(set(item) == {"token", "username", "userStatus"} for item in tokens)
