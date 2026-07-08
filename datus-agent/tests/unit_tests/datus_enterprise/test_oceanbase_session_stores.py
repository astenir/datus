"""Tests for OceanBase MySQL enterprise session stores."""

from __future__ import annotations

import asyncio
import queue
import threading
from types import SimpleNamespace

import pytest

from datus.api.enterprise.loader import load_enterprise_extensions
from datus_enterprise.oceanbase_common import OceanBaseMySQLConfig, OceanBaseMySQLPool
from datus_enterprise.oceanbase_session_store import _SCHEMA_SQL as BODY_SCHEMA_SQL
from datus_enterprise.oceanbase_session_store import ObSessionBodyStore
from datus_enterprise.oceanbase_stores import _SCHEMA_SQL as METADATA_SCHEMA_SQL
from datus_enterprise.oceanbase_stores import (
    ObArtifactAclStore,
    ObAuditSink,
    ObEnterpriseAgentStore,
    ObEnterpriseDatasourceGrantStore,
    ObEnterpriseQuotaStore,
    ObEnterpriseRoleStore,
    ObEnterpriseSecretStore,
    ObEnterpriseUserStore,
    ObSessionOwnerStore,
    ObUserDatasourceStore,
    ObUserModelCredentialStore,
)


class FakeObCursor:
    def __init__(self, *, existing_base_url: bool) -> None:
        self.existing_base_url = existing_base_url
        self.statements: list[tuple[str, tuple[object, ...]]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query: str, params: tuple[object, ...] = ()) -> None:
        self.statements.append((query, params))

    def fetchone(self) -> dict[str, str] | None:
        return {"Field": "base_url"} if self.existing_base_url else None


class FakeObConnection:
    def __init__(self, cursor: FakeObCursor) -> None:
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self) -> FakeObCursor:
        return self._cursor


class FakeObPool:
    def __init__(self, cursor: FakeObCursor) -> None:
        self._cursor = cursor

    def connection(self, *, database: str | None = None) -> FakeObConnection:
        return FakeObConnection(self._cursor)


class FakeTrackedConnection:
    def __init__(self) -> None:
        self.close_count = 0
        self.open = True

    def close(self) -> None:
        self.close_count += 1
        self.open = False


class FakePymysqlConnection(FakeTrackedConnection):
    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass


def test_ob_session_store_schemas_are_additive_and_have_no_tenant_id():
    normalized = " ".join(f"{METADATA_SCHEMA_SQL}\n{BODY_SCHEMA_SQL}".lower().split())
    assert "create table if not exists enterprise_users" in normalized
    assert "create table if not exists enterprise_roles" in normalized
    assert "create table if not exists enterprise_datasource_grants" in normalized
    assert "create table if not exists enterprise_agents" in normalized
    assert "create table if not exists session_owners" in normalized
    assert "create table if not exists enterprise_artifact_acls" in normalized
    assert "create table if not exists enterprise_audit_logs" in normalized
    assert "create table if not exists enterprise_quotas" in normalized
    assert "create table if not exists enterprise_secrets" in normalized
    assert "create table if not exists user_model_credentials" in normalized
    assert "create table if not exists user_model_preferences" in normalized
    assert "create table if not exists user_datasources" in normalized
    assert "create table if not exists enterprise_session_bodies" in normalized
    assert "create table if not exists enterprise_session_messages" in normalized
    assert "create table if not exists enterprise_session_turn_usage" in normalized
    assert "create table if not exists enterprise_session_running_usage" in normalized
    assert "create table if not exists enterprise_session_system_prompts" in normalized
    assert "tenant_id" not in normalized
    assert "drop table" not in normalized
    assert "alter table" not in normalized


def test_ob_user_model_credential_store_adds_base_url_column_for_existing_table():
    cursor = FakeObCursor(existing_base_url=False)
    store = ObUserModelCredentialStore.__new__(ObUserModelCredentialStore)
    store._config = SimpleNamespace(database="datus_enterprise")
    store._pool = FakeObPool(cursor)
    store._schema_lock = threading.Lock()
    store._user_model_credential_schema_ready = False
    ensured = []
    store._ensure_database_and_schema_sync = lambda schema_sql: ensured.append(schema_sql)

    store._ensure_user_model_credential_columns_sync()
    first_statement_count = len(cursor.statements)
    store._ensure_user_model_credential_columns_sync()

    normalized = [" ".join(query.lower().split()) for query, _ in cursor.statements]
    assert ensured
    assert normalized[0] == "show columns from user_model_credentials like %s"
    assert normalized[1] == "alter table user_model_credentials add column base_url varchar(512)"
    assert len(cursor.statements) == first_statement_count


def test_ob_session_stores_reject_invalid_config():
    with pytest.raises(Exception) as owner_exc:
        ObSessionOwnerStore(host="", user="root@test", password="testpass", database="datus_enterprise")
    assert "OceanBase host is required" in str(owner_exc.value)

    with pytest.raises(Exception) as body_exc:
        ObSessionBodyStore(host="127.0.0.1", user="root@test", password="testpass", database="bad-name")
    assert "Invalid OceanBase identifier" in str(body_exc.value)


def test_oceanbase_pool_close_closes_idle_and_borrowed_connections():
    pool = OceanBaseMySQLPool(
        OceanBaseMySQLConfig(
            host="127.0.0.1",
            port=2881,
            user="root@test",
            password="testpass",
            database="datus_enterprise",
        )
    )
    idle = FakeTrackedConnection()
    borrowed = FakeTrackedConnection()
    pool._available = queue.LifoQueue()
    pool._available.put(idle)
    pool._connections.update({idle, borrowed})

    pool.close()

    assert pool._closed is True
    assert pool._available.empty()
    assert idle.close_count == 1
    assert borrowed.close_count == 1


def test_oceanbase_pool_first_shared_connection_does_not_deadlock(monkeypatch):
    import pymysql

    created_connections: list[FakePymysqlConnection] = []

    def fake_connect(**_kwargs):
        conn = FakePymysqlConnection()
        created_connections.append(conn)
        return conn

    monkeypatch.setattr(pymysql, "connect", fake_connect)
    pool = OceanBaseMySQLPool(
        OceanBaseMySQLConfig(
            host="127.0.0.1",
            port=2881,
            user="root@test",
            password="testpass",
            database="datus_enterprise",
            pool_max_size=1,
        )
    )
    acquired: list[FakePymysqlConnection] = []
    errors: list[BaseException] = []

    def acquire_once() -> None:
        try:
            with pool.connection(database="datus_enterprise") as conn:
                acquired.append(conn)
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=acquire_once, daemon=True)
    thread.start()
    thread.join(timeout=1.0)

    assert thread.is_alive() is False
    assert errors == []
    assert acquired == created_connections
    assert len(created_connections) == 1


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
    kwargs = {
        "host": "127.0.0.1",
        "port": 2881,
        "user": "root@test",
        "password": "testpass",
        "database": "datus_enterprise",
    }
    extensions = load_enterprise_extensions(
        {
            "enabled": True,
            "authorization_provider": {"class": "datus.api.enterprise.defaults:LocalAuthorizationProvider"},
            "user_store": {
                "class": "datus_enterprise.oceanbase_stores:ObEnterpriseUserStore",
                "kwargs": kwargs,
            },
            "role_store": {
                "class": "datus_enterprise.oceanbase_stores:ObEnterpriseRoleStore",
                "kwargs": kwargs,
            },
            "datasource_grant_store": {
                "class": "datus_enterprise.oceanbase_stores:ObEnterpriseDatasourceGrantStore",
                "kwargs": kwargs,
            },
            "agent_store": {
                "class": "datus_enterprise.oceanbase_stores:ObEnterpriseAgentStore",
                "kwargs": kwargs,
            },
            "session_owner_store": {
                "class": "datus_enterprise.oceanbase_stores:ObSessionOwnerStore",
                "kwargs": kwargs,
            },
            "artifact_acl_store": {
                "class": "datus_enterprise.oceanbase_stores:ObArtifactAclStore",
                "kwargs": kwargs,
            },
            "audit_sink": {
                "class": "datus_enterprise.oceanbase_stores:ObAuditSink",
                "kwargs": kwargs,
            },
            "quota_store": {
                "class": "datus_enterprise.oceanbase_stores:ObEnterpriseQuotaStore",
                "kwargs": kwargs,
            },
            "secret_store": {
                "class": "datus_enterprise.oceanbase_stores:ObEnterpriseSecretStore",
                "kwargs": kwargs,
            },
            "user_model_credential_store": {
                "class": "datus_enterprise.oceanbase_stores:ObUserModelCredentialStore",
                "kwargs": {
                    **kwargs,
                    "encryption_secret": "test-user-model-credential-secret-32",
                },
            },
            "user_datasource_store": {
                "class": "datus_enterprise.oceanbase_stores:ObUserDatasourceStore",
                "kwargs": {
                    **kwargs,
                    "encryption_secret": "test-user-datasource-secret-32xxxx",
                },
            },
            "session_body_store": {
                "class": "datus_enterprise.oceanbase_session_store:ObSessionBodyStore",
                "kwargs": kwargs,
            },
        }
    )

    assert isinstance(extensions.user_store, ObEnterpriseUserStore)
    assert isinstance(extensions.role_store, ObEnterpriseRoleStore)
    assert isinstance(extensions.datasource_grant_store, ObEnterpriseDatasourceGrantStore)
    assert isinstance(extensions.agent_store, ObEnterpriseAgentStore)
    assert isinstance(extensions.session_owner_store, ObSessionOwnerStore)
    assert isinstance(extensions.artifact_acl_store, ObArtifactAclStore)
    assert isinstance(extensions.audit_sink, ObAuditSink)
    assert isinstance(extensions.quota_store, ObEnterpriseQuotaStore)
    assert isinstance(extensions.secret_store, ObEnterpriseSecretStore)
    assert isinstance(extensions.user_model_credential_store, ObUserModelCredentialStore)
    assert isinstance(extensions.user_datasource_store, ObUserDatasourceStore)
    assert isinstance(extensions.session_body_store, ObSessionBodyStore)
