"""Tests for OceanBase MySQL enterprise session stores."""

from __future__ import annotations

import asyncio

import pytest

from datus.api.enterprise.loader import load_enterprise_extensions
from datus_enterprise.oceanbase_session_store import _SCHEMA_SQL as BODY_SCHEMA_SQL
from datus_enterprise.oceanbase_session_store import ObSessionBodyStore
from datus_enterprise.oceanbase_stores import _SCHEMA_SQL as OWNER_SCHEMA_SQL
from datus_enterprise.oceanbase_stores import ObSessionOwnerStore


def test_ob_session_store_schemas_are_additive_and_have_no_tenant_id():
    normalized = " ".join(f"{OWNER_SCHEMA_SQL}\n{BODY_SCHEMA_SQL}".lower().split())
    assert "create table if not exists session_owners" in normalized
    assert "create table if not exists enterprise_session_bodies" in normalized
    assert "create table if not exists enterprise_session_messages" in normalized
    assert "create table if not exists enterprise_session_turn_usage" in normalized
    assert "create table if not exists enterprise_session_running_usage" in normalized
    assert "create table if not exists enterprise_session_system_prompts" in normalized
    assert "tenant_id" not in normalized
    assert "drop table" not in normalized
    assert "alter table" not in normalized


def test_ob_session_stores_reject_invalid_config():
    with pytest.raises(Exception) as owner_exc:
        ObSessionOwnerStore(host="", user="root@test", password="testpass", database="datus_enterprise")
    assert "OceanBase host is required" in str(owner_exc.value)

    with pytest.raises(Exception) as body_exc:
        ObSessionBodyStore(host="127.0.0.1", user="root@test", password="testpass", database="bad-name")
    assert "Invalid OceanBase identifier" in str(body_exc.value)


def test_ob_session_body_store_run_sync_bridge():
    store = ObSessionBodyStore(
        host="127.0.0.1",
        port=2881,
        user="root@test",
        password="testpass",
        database="datus_enterprise",
    )

    async def operation():
        await asyncio.sleep(0)
        return "ok"

    assert store.run_sync(operation) == "ok"


def test_oceanbase_session_store_loader_wires_optional_providers():
    extensions = load_enterprise_extensions(
        {
            "enabled": True,
            "authorization_provider": {"class": "datus.api.enterprise.defaults:LocalAuthorizationProvider"},
            "audit_sink": {"class": "datus.api.enterprise.defaults:NoopAuditSink"},
            "datasource_grant_store": {"class": "datus.api.enterprise.defaults:InMemoryEnterpriseDatasourceGrantStore"},
            "session_owner_store": {
                "class": "datus_enterprise.oceanbase_stores:ObSessionOwnerStore",
                "kwargs": {
                    "host": "127.0.0.1",
                    "port": 2881,
                    "user": "root@test",
                    "password": "testpass",
                    "database": "datus_enterprise",
                },
            },
            "session_body_store": {
                "class": "datus_enterprise.oceanbase_session_store:ObSessionBodyStore",
                "kwargs": {
                    "host": "127.0.0.1",
                    "port": 2881,
                    "user": "root@test",
                    "password": "testpass",
                    "database": "datus_enterprise",
                },
            },
        }
    )

    assert isinstance(extensions.session_owner_store, ObSessionOwnerStore)
    assert isinstance(extensions.session_body_store, ObSessionBodyStore)
