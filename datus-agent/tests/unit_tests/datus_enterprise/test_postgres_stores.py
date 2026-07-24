from __future__ import annotations

import sys
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from datus.api.enterprise.models import AuditEvent
from datus.utils.exceptions import DatusException
from datus_enterprise.postgres_stores import (
    PgArtifactAclStore,
    PgAuditSink,
    PgEnterpriseDatasourceGrantStore,
    PgEnterpriseQuotaStore,
    PgEnterpriseRoleStore,
    PgEnterpriseSecretStore,
    PgEnterpriseUserStore,
    PgSessionOwnerStore,
    PgUserDatasourceStore,
    PgUserModelCredentialStore,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


class Row(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class FakeTransaction:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        self.conn.transaction_count += 1
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


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


class FakeConnection:
    def __init__(self):
        self.users = {}
        self.chat_preferences = {}
        self.roles = {}
        self.role_permissions = {}
        self.user_roles = {}
        self.grants = {}
        self.sessions = {}
        self.artifact_acls = {}
        self.audit_logs = []
        self.quotas = {}
        self.usage = {}
        self.secrets = {}
        self.model_credentials = {}
        self.model_preferences = {}
        self.user_datasources = {}
        self.queries = []
        self.transaction_count = 0

    def transaction(self):
        return FakeTransaction(self)

    async def execute(self, query, *args):
        self.queries.append(("execute", query, args))
        normalized = " ".join(query.split())
        if normalized.startswith("CREATE TABLE"):
            return "CREATE"
        if "DELETE FROM enterprise_role_permissions" in normalized:
            self.role_permissions.pop(args[0], None)
            return "DELETE 1"
        if "INSERT INTO enterprise_roles" in normalized:
            role_id, name, description, built_in = args
            existing = self.roles.get(role_id, {})
            self.roles[role_id] = {
                "role_id": role_id,
                "name": name,
                "description": description,
                "built_in": built_in,
                "created_at": existing.get("created_at", NOW),
                "updated_at": NOW,
            }
            return "INSERT 0 1"
        if "UPDATE enterprise_roles SET updated_at" in normalized:
            if args[0] in self.roles:
                self.roles[args[0]]["updated_at"] = NOW
            return "UPDATE 1"
        if "DELETE FROM enterprise_user_roles WHERE user_id" in normalized:
            self.user_roles.pop(args[0], None)
            return "DELETE 1"
        if "DELETE FROM enterprise_roles WHERE role_id" in normalized:
            deleted = self.roles.pop(args[0], None)
            self.role_permissions.pop(args[0], None)
            return f"DELETE {1 if deleted else 0}"
        if "DELETE FROM enterprise_datasource_grants" in normalized:
            deleted = self.grants.pop(tuple(args), None)
            return f"DELETE {1 if deleted else 0}"
        if "INSERT INTO session_owners" in normalized:
            project_id, session_id, user_id = args
            existing = self.sessions.get((project_id, session_id), {})
            self.sessions[(project_id, session_id)] = {
                "project_id": project_id,
                "session_id": session_id,
                "user_id": user_id,
                "created_at": existing.get("created_at", NOW),
                "updated_at": NOW,
            }
            return "INSERT 0 1"
        if "DELETE FROM session_owners" in normalized:
            deleted = self.sessions.pop((args[0], args[1]), None)
            return f"DELETE {1 if deleted else 0}"
        if "INSERT INTO enterprise_audit_logs" in normalized:
            self.audit_logs.append(
                Row(
                    user_id=args[0],
                    action=args[1],
                    resource_type=args[2],
                    resource_id=args[3],
                    decision=args[4],
                    reason=args[5],
                    request_id=args[6],
                    metadata_json=args[7],
                    id=len(self.audit_logs) + 1,
                    created_at=NOW,
                )
            )
            return "INSERT 0 1"
        if "DELETE FROM enterprise_secrets" in normalized:
            deleted = self.secrets.pop(args[0], None)
            return f"DELETE {1 if deleted else 0}"
        if "DELETE FROM user_model_credentials" in normalized:
            deleted = self.model_credentials.pop((args[0], args[1]), None)
            return f"DELETE {1 if deleted else 0}"
        if "UPDATE user_model_preferences SET default_credential_id = NULL" in normalized:
            preference = self.model_preferences.get(args[0])
            if preference and preference["default_credential_id"] == args[1]:
                preference["default_credential_id"] = None
                preference["default_model"] = None
                preference["updated_at"] = NOW
                return "UPDATE 1"
            return "UPDATE 0"
        if "UPDATE user_model_credentials SET last_used_at" in normalized:
            row = self.model_credentials.get((args[0], args[1]))
            if row is None:
                return "UPDATE 0"
            row["last_used_at"] = NOW
            return "UPDATE 1"
        if "DELETE FROM user_datasources" in normalized:
            deleted = self.user_datasources.pop((args[0], args[1]), None)
            return f"DELETE {1 if deleted else 0}"
        if "UPDATE user_datasources SET last_used_at" in normalized:
            row = self.user_datasources.get((args[0], args[1]))
            if row is None:
                return "UPDATE 0"
            row["last_used_at"] = NOW
            return "UPDATE 1"
        raise AssertionError(f"Unhandled execute: {normalized}")

    async def executemany(self, query, records):
        self.queries.append(("executemany", query, tuple(records)))
        normalized = " ".join(query.split())
        if "INSERT INTO enterprise_role_permissions" in normalized:
            for role_id, permission in records:
                self.role_permissions.setdefault(role_id, set()).add(permission)
            return "INSERT 0"
        if "INSERT INTO enterprise_user_roles" in normalized:
            for user_id, role_id in records:
                self.user_roles.setdefault(user_id, set()).add(role_id)
            return "INSERT 0"
        raise AssertionError(f"Unhandled executemany: {normalized}")

    async def fetchrow(self, query, *args):
        self.queries.append(("fetchrow", query, args))
        normalized = " ".join(query.split())
        if "INSERT INTO enterprise_users" in normalized:
            user_id, display_name, email, enabled = args[:4]
            external_user_id, department, title, last_seen_at = (
                args[4:8] if len(args) >= 8 else (None, None, None, None)
            )
            existing = self.users.get(user_id, {})
            self.users[user_id] = Row(
                user_id=user_id,
                display_name=display_name,
                email=email,
                enabled=enabled,
                external_user_id=external_user_id,
                department=department,
                title=title,
                last_seen_at=last_seen_at,
                created_at=existing.get("created_at", NOW),
                updated_at=NOW,
            )
            return self.users[user_id]
        if "FROM enterprise_users WHERE user_id" in normalized and normalized.startswith("SELECT"):
            return self.users.get(args[0])
        if "UPDATE enterprise_users" in normalized:
            user = self.users.get(args[0])
            if user is None:
                return None
            user["enabled"] = args[1]
            user["updated_at"] = NOW
            return user
        if "INSERT INTO enterprise_user_chat_preferences" in normalized:
            user_id, default_agent_id = args
            existing = self.chat_preferences.get(user_id, {})
            row = Row(
                user_id=user_id,
                default_agent_id=default_agent_id,
                created_at=existing.get("created_at", NOW),
                updated_at=NOW,
            )
            self.chat_preferences[user_id] = row
            return row
        if "FROM enterprise_user_chat_preferences" in normalized:
            return self.chat_preferences.get(args[0])
        if "FROM enterprise_roles WHERE role_id" in normalized and normalized.startswith("SELECT 1"):
            return Row({"?column?": 1}) if args[0] in self.roles else None
        if "FROM enterprise_roles WHERE role_id" in normalized and "FOR UPDATE" in normalized:
            return Row(role_id=args[0]) if args[0] in self.roles else None
        if "FROM enterprise_roles LEFT JOIN" in normalized and "WHERE role_id" in normalized:
            return self._role_row(args[0])
        if "FROM enterprise_user_roles WHERE role_id" in normalized and "LIMIT 1" in normalized:
            return Row({"?column?": 1}) if any(args[0] in roles for roles in self.user_roles.values()) else None
        if "INSERT INTO enterprise_datasource_grants" in normalized:
            subject_type, subject_id, datasource_key, effect, scope_json = args
            existing = self.grants.get((subject_type, subject_id, datasource_key), {})
            row = Row(
                subject_type=subject_type,
                subject_id=subject_id,
                datasource_key=datasource_key,
                effect=effect,
                scope_json=scope_json,
                created_at=existing.get("created_at", NOW),
                updated_at=NOW,
            )
            self.grants[(subject_type, subject_id, datasource_key)] = row
            return row
        if "FROM enterprise_datasource_grants" in normalized and "WHERE subject_type" in normalized:
            return self.grants.get((args[0], args[1], args[2]))
        if "FROM session_owners" in normalized and "SELECT project_id" in normalized:
            return self.sessions.get((args[0], args[1]))
        if "FROM session_owners" in normalized and "SELECT user_id" in normalized:
            return self.sessions.get((args[0], args[1]))
        if "INSERT INTO enterprise_artifact_acls" in normalized:
            artifact_type, slug, acl_json = args
            existing = self.artifact_acls.get((artifact_type, slug), {})
            row = Row(
                artifact_type=artifact_type,
                slug=slug,
                acl_json=acl_json,
                created_at=existing.get("created_at", NOW),
                updated_at=NOW,
            )
            self.artifact_acls[(artifact_type, slug)] = row
            return Row(acl_json=acl_json)
        if "FROM enterprise_artifact_acls" in normalized and "WHERE artifact_type" in normalized:
            row = self.artifact_acls.get((args[0], args[1]))
            return Row(acl_json=row["acl_json"]) if row else None
        if "INSERT INTO enterprise_quotas" in normalized:
            subject_type, subject_id, resource, limit_value, window_seconds, enabled = args
            existing = self.quotas.get((subject_type, subject_id, resource), {})
            row = Row(
                subject_type=subject_type,
                subject_id=subject_id,
                resource=resource,
                limit_value=limit_value,
                window_seconds=window_seconds,
                enabled=enabled,
                created_at=existing.get("created_at", NOW),
                updated_at=NOW,
            )
            self.quotas[(subject_type, subject_id, resource)] = row
            return row
        if "FROM enterprise_quota_usage" in normalized and "FOR UPDATE" in normalized:
            subject_type, subject_id, resource = args[:3]
            candidates = [row for key, row in self.usage.items() if key[:3] == (subject_type, subject_id, resource)]
            return sorted(candidates, key=lambda row: row["window_start"], reverse=True)[0] if candidates else None
        if "INSERT INTO enterprise_quota_usage" in normalized:
            subject_type, subject_id, resource, window_start, amount = args
            key = (subject_type, subject_id, resource, window_start)
            existing = self.usage.get(key)
            used = int(existing["used"]) + amount if existing else amount
            row = Row(
                subject_type=subject_type,
                subject_id=subject_id,
                resource=resource,
                window_start=window_start,
                used=used,
                updated_at=NOW,
            )
            self.usage[key] = row
            return row
        if "INSERT INTO enterprise_secrets" in normalized:
            name, provider, reference, description, enabled = args
            existing = self.secrets.get(name, {})
            row = Row(
                name=name,
                provider=provider,
                reference=reference,
                description=description,
                enabled=enabled,
                created_at=existing.get("created_at", NOW),
                updated_at=NOW,
            )
            self.secrets[name] = row
            return row
        if "FROM enterprise_secrets" in normalized and "WHERE name" in normalized:
            return self.secrets.get(args[0])
        if "INSERT INTO user_model_credentials" in normalized:
            user_id, credential_id, provider, model, api_key_blob, api_key_hint, base_url, display_name, enabled = args
            existing = self.model_credentials.get((user_id, credential_id), {})
            row = Row(
                user_id=user_id,
                credential_id=credential_id,
                provider=provider,
                model=model,
                api_key_blob=api_key_blob,
                api_key_hint=api_key_hint,
                base_url=base_url,
                display_name=display_name,
                enabled=enabled,
                last_used_at=existing.get("last_used_at"),
                created_at=existing.get("created_at", NOW),
                updated_at=NOW,
            )
            self.model_credentials[(user_id, credential_id)] = row
            return row
        if "FROM user_model_credentials" in normalized and "WHERE user_id" in normalized:
            return self.model_credentials.get((args[0], args[1]))
        if "UPDATE user_model_credentials" in normalized and "RETURNING" in normalized:
            row = self.model_credentials.get((args[0], args[1]))
            if row is None:
                return None
            row["enabled"] = args[2]
            row["updated_at"] = NOW
            return row
        if "INSERT INTO user_model_preferences" in normalized:
            user_id, default_credential_id, default_model = args
            existing = self.model_preferences.get(user_id, {})
            row = Row(
                user_id=user_id,
                default_credential_id=default_credential_id,
                default_model=default_model,
                created_at=existing.get("created_at", NOW),
                updated_at=NOW,
            )
            self.model_preferences[user_id] = row
            return row
        if "FROM user_model_preferences" in normalized and "WHERE user_id" in normalized:
            return self.model_preferences.get(args[0])
        if "INSERT INTO user_datasources" in normalized:
            (
                user_id,
                datasource_id,
                datasource_type,
                host,
                port,
                username,
                password_blob,
                password_hint,
                database_name,
                schema_name,
                catalog_name,
                display_name,
                enabled,
            ) = args
            existing = self.user_datasources.get((user_id, datasource_id), {})
            row = Row(
                user_id=user_id,
                datasource_id=datasource_id,
                datasource_type=datasource_type,
                host=host,
                port=port,
                username=username,
                password_blob=password_blob,
                password_hint=password_hint,
                database_name=database_name,
                schema_name=schema_name,
                catalog_name=catalog_name,
                display_name=display_name,
                enabled=enabled,
                last_used_at=existing.get("last_used_at"),
                created_at=existing.get("created_at", NOW),
                updated_at=NOW,
            )
            self.user_datasources[(user_id, datasource_id)] = row
            return row
        if "FROM user_datasources" in normalized and "WHERE user_id" in normalized:
            return self.user_datasources.get((args[0], args[1]))
        if "UPDATE user_datasources" in normalized and "RETURNING" in normalized:
            row = self.user_datasources.get((args[0], args[1]))
            if row is None:
                return None
            row["enabled"] = args[2]
            row["updated_at"] = NOW
            return row
        raise AssertionError(f"Unhandled fetchrow: {normalized}")

    async def fetch(self, query, *args):
        self.queries.append(("fetch", query, args))
        normalized = " ".join(query.split())
        if "FROM enterprise_users" in normalized:
            rows = list(self.users.values())
            if "WHERE enabled" in normalized:
                rows = [row for row in rows if row["enabled"] is args[0]]
            return sorted(rows, key=lambda row: row["user_id"])
        if "FROM enterprise_roles LEFT JOIN" in normalized:
            return [self._role_row(role_id) for role_id in sorted(self.roles)]
        if "FROM enterprise_roles WHERE role_id = ANY" in normalized:
            return [Row(role_id=role_id) for role_id in args[0] if role_id in self.roles]
        if "FROM enterprise_user_roles" in normalized and "WHERE user_id" in normalized:
            return [Row(role_id=role_id) for role_id in sorted(self.user_roles.get(args[0], set()))]
        if "FROM enterprise_user_roles" in normalized and "WHERE role_id" in normalized:
            return [Row(user_id=user_id) for user_id, roles in sorted(self.user_roles.items()) if args[0] in roles]
        if "FROM enterprise_datasource_grants" in normalized:
            return self._filtered(
                self.grants.values(), ("subject_type", "subject_id", "datasource_key"), normalized, args
            )
        if "SELECT session_id FROM session_owners" in normalized:
            return [
                Row(session_id=row["session_id"])
                for row in self.sessions.values()
                if row["project_id"] == args[0] and row["user_id"] == args[1]
            ]
        if "FROM session_owners" in normalized:
            rows = [row for row in self.sessions.values() if row["project_id"] == args[0]]
            if "AND user_id" in normalized:
                rows = [row for row in rows if row["user_id"] == args[1]]
            return sorted(rows, key=lambda row: row["session_id"])
        if "FROM enterprise_audit_logs" in normalized:
            rows = list(self.audit_logs)
            filter_columns = ("user_id", "action", "resource_type", "resource_id", "decision", "request_id")
            rows = self._filtered(rows, filter_columns, normalized, args[:-1])
            value_index = sum(1 for column in filter_columns if f"{column} = $" in normalized)
            if "id < $" in normalized:
                rows = [row for row in rows if row["id"] < args[value_index]]
                value_index += 1
            if "created_at >= $" in normalized:
                created_after = _parse_iso(args[value_index])
                rows = [row for row in rows if row["created_at"] >= created_after]
                value_index += 1
            if "created_at < $" in normalized:
                created_before = _parse_iso(args[value_index])
                rows = [row for row in rows if row["created_at"] < created_before]
            return sorted(rows, key=lambda row: row["id"], reverse=True)[: args[-1]]
        if "FROM enterprise_quotas" in normalized and "FOR UPDATE" in normalized:
            resource, subject_types, subject_ids = args
            subjects = set(zip(subject_types, subject_ids, strict=True))
            return [
                row
                for key, row in self.quotas.items()
                if row["resource"] == resource and row["enabled"] and key[:2] in subjects
            ]
        if "FROM enterprise_quotas" in normalized:
            return self._filtered(self.quotas.values(), ("subject_type", "subject_id", "resource"), normalized, args)
        if "FROM enterprise_quota_usage" in normalized:
            return self._filtered(self.usage.values(), ("subject_type", "subject_id", "resource"), normalized, args)
        if "FROM enterprise_secrets" in normalized:
            rows = list(self.secrets.values())
            if "WHERE name LIKE" in normalized:
                prefix = _unescape_like_prefix(args[0])
                rows = [row for row in rows if row["name"].startswith(prefix)]
            return sorted(rows, key=lambda row: row["name"])
        if "FROM user_model_credentials" in normalized:
            rows = [row for (user_id, _), row in self.model_credentials.items() if user_id == args[0]]
            return sorted(rows, key=lambda row: (row["created_at"], row["credential_id"]))
        if "FROM user_datasources" in normalized:
            rows = [row for (user_id, _), row in self.user_datasources.items() if user_id == args[0]]
            return sorted(rows, key=lambda row: (row["created_at"], row["datasource_id"]))
        raise AssertionError(f"Unhandled fetch: {normalized}")

    def _role_row(self, role_id):
        role = self.roles.get(role_id)
        if role is None:
            return None
        return Row(**role, permissions=sorted(self.role_permissions.get(role_id, set())))

    def _filtered(self, rows, columns, query, args):
        result = list(rows)
        index = 0
        for column in columns:
            if f"{column} = $" not in query:
                continue
            value = args[index]
            result = [row for row in result if row[column] == value]
            index += 1
        return list(result)


@pytest.fixture
def fake_pg(monkeypatch):
    conn = FakeConnection()
    pool = FakePool(conn)

    async def create_pool(**kwargs):
        conn.pool_kwargs = kwargs
        return pool

    monkeypatch.setitem(sys.modules, "asyncpg", SimpleNamespace(create_pool=create_pool))
    return conn


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


@pytest.mark.asyncio
async def test_pg_store_recovers_once_when_connection_closes_during_query(monkeypatch):
    class ConnectionDoesNotExistError(Exception):
        pass

    class ClosingFetchConnection(FakeConnection):
        async def fetch(self, query, *args):
            raise ConnectionDoesNotExistError("connection was closed in the middle of operation")

    stale_pool = FakePool(ClosingFetchConnection())
    healthy_conn = FakeConnection()
    healthy_pool = FakePool(healthy_conn)
    pools = [stale_pool, healthy_pool]

    async def create_pool(**kwargs):
        pool = pools.pop(0)
        pool.conn.pool_kwargs = kwargs
        return pool

    monkeypatch.setitem(sys.modules, "asyncpg", SimpleNamespace(create_pool=create_pool))

    store = PgEnterpriseUserStore(dsn="postgresql://metadata")
    await healthy_conn.fetchrow(
        """
        INSERT INTO enterprise_users (user_id, display_name, email, enabled, created_at, updated_at)
        VALUES ($1, $2, $3, $4, now(), now())
        ON CONFLICT(user_id) DO UPDATE SET
            display_name = excluded.display_name,
            email = excluded.email,
            enabled = excluded.enabled,
            updated_at = now()
        RETURNING user_id, display_name, email, enabled, created_at, updated_at
        """,
        "alice",
        "Alice",
        "a@example.com",
        True,
    )

    assert [user["user_id"] for user in await store.list_users(enabled=True)] == ["alice"]
    assert stale_pool.closed is True
    assert store._pool is healthy_pool


@pytest.mark.asyncio
async def test_pg_store_keeps_pool_per_event_loop(monkeypatch):
    loop_a = object()
    loop_b = object()
    active_loop = {"value": loop_a}

    stale_conn = FakeConnection()
    stale_pool = FakePool(stale_conn)
    healthy_conn = FakeConnection()
    healthy_pool = FakePool(healthy_conn)
    pools = [stale_pool, healthy_pool]

    async def create_pool(**kwargs):
        pool = pools.pop(0)
        pool.conn.pool_kwargs = kwargs
        return pool

    monkeypatch.setattr("datus_enterprise.postgres_stores.asyncio.get_running_loop", lambda: active_loop["value"])
    monkeypatch.setitem(sys.modules, "asyncpg", SimpleNamespace(create_pool=create_pool))

    store = PgEnterpriseUserStore(dsn="postgresql://metadata")
    await stale_conn.fetchrow(
        """
        INSERT INTO enterprise_users (user_id, display_name, email, enabled, created_at, updated_at)
        VALUES ($1, $2, $3, $4, now(), now())
        ON CONFLICT(user_id) DO UPDATE SET
            display_name = excluded.display_name,
            email = excluded.email,
            enabled = excluded.enabled,
            updated_at = now()
        RETURNING user_id, display_name, email, enabled, created_at, updated_at
        """,
        "alice",
        "Alice",
        "a@example.com",
        True,
    )
    await healthy_conn.fetchrow(
        """
        INSERT INTO enterprise_users (user_id, display_name, email, enabled, created_at, updated_at)
        VALUES ($1, $2, $3, $4, now(), now())
        ON CONFLICT(user_id) DO UPDATE SET
            display_name = excluded.display_name,
            email = excluded.email,
            enabled = excluded.enabled,
            updated_at = now()
        RETURNING user_id, display_name, email, enabled, created_at, updated_at
        """,
        "alice",
        "Alice",
        "a@example.com",
        True,
    )

    assert [user["user_id"] for user in await store.list_users(enabled=True)] == ["alice"]
    active_loop["value"] = loop_b

    assert [user["user_id"] for user in await store.list_users(enabled=True)] == ["alice"]
    assert stale_pool.terminated is False
    assert stale_pool.closed is False
    assert store._pool is healthy_pool
    assert store._pools_by_loop == {
        id(loop_a): (loop_a, stale_pool),
        id(loop_b): (loop_b, healthy_pool),
    }


@pytest.mark.asyncio
async def test_pg_user_store_upsert_list_get_and_disable(fake_pg):
    store = PgEnterpriseUserStore(dsn="postgresql://metadata")

    created = await store.upsert_user(user_id="alice", display_name="Alice", email="a@example.com")
    assert created["enabled"] is True
    assert fake_pg.pool_kwargs["dsn"] == "postgresql://metadata"
    assert fake_pg.pool_kwargs["min_size"] == 1
    assert fake_pg.pool_kwargs["max_size"] == 2

    assert await store.get_user("alice") == created
    assert [user["user_id"] for user in await store.list_users(enabled=True)] == ["alice"]

    disabled = await store.set_user_enabled("alice", False)
    assert disabled["enabled"] is False
    assert await store.list_users(enabled=True) == []

    assert (await store.get_chat_preference("alice"))["default_agent_id"] is None
    preference = await store.put_chat_preference(user_id="alice", default_agent_id="sales_sql")
    assert preference["default_agent_id"] == "sales_sql"
    cleared = await store.put_chat_preference(user_id="alice", default_agent_id=None)
    assert cleared["default_agent_id"] is None


@pytest.mark.asyncio
async def test_pg_role_store_permissions_bindings_and_delete_semantics(fake_pg):
    store = PgEnterpriseRoleStore(dsn="postgresql://metadata")

    role = await store.upsert_role(
        role_id="analyst",
        name="Analyst",
        permissions=["module.sql_executor", "module.chat"],
    )
    assert role["permissions"] == ["module.chat", "module.sql_executor"]
    assert await store.set_role_permissions("missing", ["module.chat"]) is None

    updated = await store.set_role_permissions("analyst", ["module.datasource_catalog"])
    assert updated["permissions"] == ["module.datasource_catalog"]

    assert await store.set_user_roles("alice", ["analyst"]) == ["analyst"]
    assert await store.list_user_roles("alice") == ["analyst"]
    assert await store.list_role_users("analyst") == ["alice"]
    assert await store.delete_role("analyst") is False

    assert await store.set_user_roles("alice", []) == []
    assert await store.delete_role("analyst") is True

    with pytest.raises(DatusException, match="Role not found"):
        await store.set_user_roles("alice", ["missing"])


@pytest.mark.asyncio
async def test_pg_datasource_grant_store_round_trips_scope_and_filters(fake_pg):
    store = PgEnterpriseDatasourceGrantStore(dsn="postgresql://metadata")

    grant = await store.put_grant(
        subject_type="user",
        subject_id="alice",
        datasource_key="finance",
        effect="allow",
        scope={"allow_sql": True, "tables": ["public.accounts"]},
    )
    assert grant["scope"] == {"allow_sql": True, "tables": ["public.accounts"]}
    assert await store.get_grant(subject_type="user", subject_id="alice", datasource_key="finance") == grant
    assert await store.list_grants(subject_type="user", subject_id="alice") == [grant]
    assert await store.delete_grant(subject_type="user", subject_id="alice", datasource_key="finance") is True


@pytest.mark.asyncio
async def test_pg_session_owner_store_set_get_list_and_delete(fake_pg):
    store = PgSessionOwnerStore(dsn="postgresql://metadata")

    await store.set_owner("enterprise", "s1", "alice")
    await store.set_owner("enterprise", "s2", "alice")

    assert await store.get_owner("enterprise", "s1") == "alice"
    session = await store.get_session("enterprise", "s1")
    assert session is not None
    assert session["user_id"] == "alice"
    assert await store.get_session("enterprise", "missing") is None
    assert await store.list_session_ids("enterprise", "alice") == ["s1", "s2"]
    assert [record["session_id"] for record in await store.list_sessions("enterprise", "alice")] == ["s1", "s2"]

    await store.delete_owner("enterprise", "s1")
    assert await store.get_owner("enterprise", "s1") is None


@pytest.mark.asyncio
async def test_pg_artifact_acl_store_round_trips_nested_acl_and_missing_semantics(fake_pg):
    store = PgArtifactAclStore(dsn="postgresql://metadata")
    acl = {
        "owner_user_id": "alice",
        "visibility": "role",
        "allowed_roles": ["analyst"],
        "datasources": ["finance"],
        "public": False,
        "effect": "allow",
        "scope": {
            "users": ["alice", "bob"],
            "roles": ["analyst"],
            "resources": {"dashboards": ["ops"]},
        },
    }

    stored = await store.put_acl(artifact_type="dashboard", slug="ops", acl=acl)

    assert stored == acl
    assert await store.get_acl(artifact_type="dashboard", slug="ops") == acl
    with pytest.raises(KeyError):
        await store.get_acl(artifact_type="dashboard", slug="missing")


@pytest.mark.asyncio
async def test_pg_artifact_acl_store_upsert_preserves_created_at_and_parameterizes_values(fake_pg):
    store = PgArtifactAclStore(dsn="postgresql://metadata")
    created_at = datetime(2025, 12, 31, tzinfo=timezone.utc)
    fake_pg.artifact_acls[("report", "sales")] = Row(
        artifact_type="report",
        slug="sales",
        acl_json={"owner_user_id": "old", "visibility": "private"},
        created_at=created_at,
        updated_at=created_at,
    )

    updated = await store.put_acl(
        artifact_type="report",
        slug="sales",
        acl={"owner_user_id": "alice", "visibility": "enterprise"},
    )

    row = fake_pg.artifact_acls[("report", "sales")]
    assert updated == {"owner_user_id": "alice", "visibility": "enterprise"}
    assert row["created_at"] == created_at
    assert row["updated_at"] == NOW

    fetchrow_queries = [entry for entry in fake_pg.queries if entry[0] == "fetchrow"]
    upsert_query, upsert_args = fetchrow_queries[-1][1], fetchrow_queries[-1][2]
    assert "$1" in upsert_query and "$2" in upsert_query and "$3::jsonb" in upsert_query
    assert "report" not in upsert_query
    assert "sales" not in upsert_query
    assert "alice" not in upsert_query
    assert upsert_args[:2] == ("report", "sales")


@pytest.mark.asyncio
async def test_pg_audit_sink_writes_and_queries_filtered_events(fake_pg):
    sink = PgAuditSink(dsn="postgresql://metadata")

    await sink.write(
        AuditEvent(
            user_id="alice",
            action="sql.execute",
            resource_type="datasource",
            resource_id="finance",
            decision="allow",
            reason=None,
            request_id="r1",
            metadata={"row_count": 1},
        )
    )
    await sink.write(
        AuditEvent(
            user_id="bob",
            action="chat.stream",
            resource_type="session",
            resource_id="s1",
            decision="deny",
            reason="SESSION_FORBIDDEN",
            request_id="r2",
            metadata={},
        )
    )
    fake_pg.audit_logs[1]["created_at"] = datetime(2026, 1, 2, tzinfo=timezone.utc)

    events = await sink.query_events(limit=10, user_id="alice", action="sql.execute", decision="allow")
    cursor_events = await sink.query_events(limit=10, before_id=2)
    request_events = await sink.query_events(limit=10, request_id="r1")
    time_events = await sink.query_events(
        limit=10,
        created_after="2026-01-01T12:00:00+00:00",
        created_before="2026-01-03T00:00:00+00:00",
    )
    assert len(events) == 1
    assert events[0].id == 1
    assert events[0].created_at == "2026-01-01T00:00:00+00:00"
    assert events[0].metadata == {"row_count": 1}
    assert [event.id for event in cursor_events] == [1]
    assert [event.id for event in request_events] == [1]
    assert [event.id for event in time_events] == [2]


@pytest.mark.asyncio
async def test_pg_quota_store_consumes_inside_transaction_and_fails_closed_on_excess(fake_pg):
    store = PgEnterpriseQuotaStore(dsn="postgresql://metadata")
    await store.put_quota(
        subject_type="user",
        subject_id="alice",
        resource="sql.execute",
        limit=2,
        window_seconds=60,
    )

    first = await store.consume_quota(
        subjects=[{"subject_type": "user", "subject_id": "alice"}],
        resource="sql.execute",
        amount=1,
    )
    assert first["allowed"] is True
    assert first["usage"][0]["used"] == 1

    second = await store.consume_quota(
        subjects=[{"subject_type": "user", "subject_id": "alice"}],
        resource="sql.execute",
        amount=2,
    )
    assert second == {
        "allowed": False,
        "reason": "quota exceeded",
        "subject_type": "user",
        "subject_id": "alice",
        "resource": "sql.execute",
        "limit": 2,
        "used": 1,
        "remaining": 1,
        "window_start": first["usage"][0]["window_start"],
        "window_seconds": 60,
    }
    assert fake_pg.transaction_count >= 2
    assert any("FOR UPDATE" in query for _, query, _ in fake_pg.queries)
    assert [usage["used"] for usage in await store.list_usage(subject_type="user", subject_id="alice")] == [1]


@pytest.mark.asyncio
async def test_pg_secret_store_crud_and_prefix_listing(fake_pg):
    store = PgEnterpriseSecretStore(dsn="postgresql://metadata")

    secret = await store.put_secret(
        name="datasource/warehouse/password",
        provider="env",
        reference="WAREHOUSE_PASSWORD",
        description="Warehouse password",
    )
    await store.put_secret(name="model/openai/key", provider="env", reference="OPENAI_API_KEY")

    assert secret["enabled"] is True
    assert await store.get_secret("datasource/warehouse/password") == secret
    assert [item["name"] for item in await store.list_secrets(prefix="datasource/")] == [
        "datasource/warehouse/password"
    ]
    assert await store.delete_secret("datasource/warehouse/password") is True


@pytest.mark.asyncio
async def test_pg_secret_store_prefix_escapes_sql_like_wildcards(fake_pg):
    store = PgEnterpriseSecretStore(dsn="postgresql://metadata")

    await store.put_secret(name="datasource_prod/password", provider="env", reference="PROD_PASSWORD")
    await store.put_secret(name="datasourceXprod/password", provider="env", reference="WRONG_PASSWORD")

    names = [secret["name"] for secret in await store.list_secrets(prefix="datasource_")]

    assert names == ["datasource_prod/password"]
    fetch_queries = [entry for entry in fake_pg.queries if entry[0] == "fetch"]
    query, args = fetch_queries[-1][1], fetch_queries[-1][2]
    assert "ESCAPE" in query
    assert args == ("datasource\\_%",)


@pytest.mark.asyncio
async def test_pg_user_model_credential_store_encrypts_and_clears_default(fake_pg):
    store = PgUserModelCredentialStore(
        dsn="postgresql://metadata",
        encryption_secret="test-user-model-credential-secret-32",
    )

    credential = await store.put_credential(
        user_id="alice",
        credential_id="cred-openai",
        provider="openai",
        model="gpt-4.1-mini",
        api_key="sk-test-secret",
        base_url="https://models.corp/v1",
        display_name="OpenAI",
    )
    preference = await store.put_preference(
        user_id="alice",
        default_credential_id="cred-openai",
        default_model="gpt-4.1-mini",
    )

    stored_blob = fake_pg.model_credentials[("alice", "cred-openai")]["api_key_blob"]
    assert stored_blob != "sk-test-secret"
    assert credential["api_key"] == "sk-test-secret"
    assert credential["base_url"] == "https://models.corp/v1"
    assert credential["ref_hint"] == "***cret"
    assert preference["default_credential_id"] == "cred-openai"
    assert await store.get_credential("bob", "cred-openai") is None

    disabled = await store.set_credential_enabled("alice", "cred-openai", False)
    assert disabled["enabled"] is False

    await store.touch_credential_used("alice", "cred-openai")
    assert (await store.get_credential("alice", "cred-openai"))["last_used_at"] == "2026-01-01T00:00:00+00:00"
    assert [item["id"] for item in await store.list_credentials("alice")] == ["cred-openai"]

    assert await store.delete_credential("alice", "cred-openai") is True
    assert (await store.get_preference("alice"))["default_credential_id"] is None


@pytest.mark.asyncio
async def test_pg_user_datasource_store_encrypts_and_isolates_password(fake_pg):
    store = PgUserDatasourceStore(
        dsn="postgresql://metadata",
        encryption_secret="test-user-datasource-secret-32xxxx",
    )

    datasource = await store.put_datasource(
        user_id="alice",
        datasource_id="ds-finance",
        datasource_type="postgresql",
        host="localhost",
        port="5432",
        username="alice",
        password="alice-db-secret",
        database="finance",
        schema="public",
        display_name="Finance",
    )

    stored_blob = fake_pg.user_datasources[("alice", "ds-finance")]["password_blob"]
    assert stored_blob != "alice-db-secret"
    assert datasource["password"] == "alice-db-secret"
    assert datasource["password_hint"] == "***cret"
    assert await store.get_datasource("bob", "ds-finance") is None

    disabled = await store.set_datasource_enabled("alice", "ds-finance", False)
    assert disabled["enabled"] is False

    await store.touch_datasource_used("alice", "ds-finance")
    assert (await store.get_datasource("alice", "ds-finance"))["last_used_at"] == "2026-01-01T00:00:00+00:00"
    assert [item["id"] for item in await store.list_datasources("alice")] == ["ds-finance"]
    assert await store.delete_datasource("alice", "ds-finance") is True


def _unescape_like_prefix(pattern: str) -> str:
    raw_prefix = pattern.removesuffix("%")
    chars = []
    escaped = False
    for char in raw_prefix:
        if escaped:
            chars.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        else:
            chars.append(char)
    if escaped:
        chars.append("\\")
    return "".join(chars)
