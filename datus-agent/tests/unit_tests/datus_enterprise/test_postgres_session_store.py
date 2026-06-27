"""Tests for the enterprise PostgreSQL session body store."""

from __future__ import annotations

from types import SimpleNamespace

from datus.api.enterprise.loader import load_enterprise_extensions
from datus_enterprise.postgres_session_store import _SCHEMA_SQL, PgSessionBodyStore


def test_session_body_store_loader_wires_optional_provider(monkeypatch):
    created = {}

    class DummySessionBodyStore:
        def __init__(self, dsn: str):
            created["dsn"] = dsn

        def open_session(self, *, project_id, scope, session_id):  # pragma: no cover - protocol shape only
            return SimpleNamespace(project_id=project_id, scope=scope, session_id=session_id)

        async def session_exists(self, **kwargs):
            return False

        async def list_session_ids(self, **kwargs):
            return []

        async def get_session_info(self, **kwargs):
            return {"exists": False}

        async def delete_session(self, **kwargs):
            return None

        async def copy_session(self, **kwargs):
            return None

        async def get_session_messages(self, **kwargs):
            return []

        async def get_detailed_usage(self, **kwargs):
            return {}

        async def upsert_running_turn_usage(self, **kwargs):
            return None

        async def get_running_turn_usage(self, **kwargs):
            return None

        async def clear_running_turn_usage(self, **kwargs):
            return None

        async def save_system_prompt_snapshot(self, **kwargs):
            return None

        async def load_system_prompt_snapshot(self, **kwargs):
            return None

        async def delete_system_prompt_snapshot(self, **kwargs):
            return None

    import datus_enterprise.postgres_session_store as module

    monkeypatch.setattr(module, "DummySessionBodyStore", DummySessionBodyStore, raising=False)
    extensions = load_enterprise_extensions(
        {
            "enabled": True,
            "authorization_provider": {"class": "datus.api.enterprise.defaults:LocalAuthorizationProvider"},
            "audit_sink": {"class": "datus.api.enterprise.defaults:NoopAuditSink"},
            "datasource_grant_store": {"class": "datus.api.enterprise.defaults:InMemoryEnterpriseDatasourceGrantStore"},
            "session_body_store": {
                "class": "datus_enterprise.postgres_session_store:DummySessionBodyStore",
                "kwargs": {"dsn": "postgresql://session-body"},
            },
        }
    )

    assert isinstance(extensions.session_body_store, DummySessionBodyStore)
    assert created["dsn"] == "postgresql://session-body"


def test_pg_session_body_schema_is_additive_and_has_no_tenant_id():
    normalized = " ".join(_SCHEMA_SQL.lower().split())
    assert "create table if not exists enterprise_session_bodies" in normalized
    assert "create table if not exists enterprise_session_messages" in normalized
    assert "create table if not exists enterprise_session_turn_usage" in normalized
    assert "create table if not exists enterprise_session_running_usage" in normalized
    assert "create table if not exists enterprise_session_system_prompts" in normalized
    assert "tenant_id" not in normalized
    assert "drop table" not in normalized
    assert "alter table" not in normalized


def test_pg_session_body_store_rejects_empty_dsn():
    try:
        PgSessionBodyStore(dsn="")
    except Exception as exc:
        assert "PostgreSQL DSN is required" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("empty DSN should fail")
