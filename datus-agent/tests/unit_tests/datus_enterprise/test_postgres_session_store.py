"""Tests for the enterprise PostgreSQL session body store."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from datus.api.enterprise.loader import load_enterprise_extensions
from datus_enterprise.postgres_session_store import _SCHEMA_SQL, PgSessionBodyStore


class Row(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class FakeAcquire:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakePool:
    def __init__(self, conn):
        self.conn = conn
        self.closed = False
        self.terminated = False

    def acquire(self):
        return FakeAcquire(self.conn)

    async def close(self):
        self.closed = True

    def terminate(self):
        self.terminated = True


class FakeSessionConnection:
    def __init__(self, session_ids):
        self.session_ids = session_ids
        self.queries = []

    async def execute(self, query, *args):
        self.queries.append(("execute", query, args))
        return "CREATE"

    async def fetch(self, query, *args):
        self.queries.append(("fetch", query, args))
        return [Row(session_id=session_id) for session_id in self.session_ids]


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


@pytest.mark.asyncio
async def test_pg_session_body_store_keeps_schema_lock_and_pool_per_event_loop(monkeypatch):
    loop_a = object()
    loop_b = object()
    active_loop = {"value": loop_a}

    conn_a = FakeSessionConnection(["s1"])
    conn_b = FakeSessionConnection(["s2"])
    pool_a = FakePool(conn_a)
    pool_b = FakePool(conn_b)
    pools = [pool_a, pool_b]

    async def create_pool(**kwargs):
        return pools.pop(0)

    monkeypatch.setattr(
        "datus_enterprise.postgres_session_store.asyncio.get_running_loop",
        lambda: active_loop["value"],
    )
    monkeypatch.setitem(sys.modules, "asyncpg", SimpleNamespace(create_pool=create_pool))

    store = PgSessionBodyStore(dsn="postgresql://session-body")

    assert await store.list_session_ids(project_id="project", scope="alice") == ["s1"]
    lock_a = store._schema_locks_by_loop[id(loop_a)][1]

    active_loop["value"] = loop_b
    store._schema_ready = False

    assert await store.list_session_ids(project_id="project", scope="alice") == ["s2"]
    lock_b = store._schema_locks_by_loop[id(loop_b)][1]

    assert lock_a is not lock_b
    assert pool_a.closed is False
    assert pool_a.terminated is False
    assert store._pool is pool_b
    assert store._pools_by_loop == {
        id(loop_a): (loop_a, pool_a),
        id(loop_b): (loop_b, pool_b),
    }
