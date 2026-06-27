from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Sequence

import asyncpg
import pytest

from datus.api.enterprise.models import AuditEvent
from datus_enterprise.postgres_stores import (
    PgArtifactAclStore,
    PgAuditSink,
    PgEnterpriseDatasourceGrantStore,
    PgEnterpriseQuotaStore,
    PgEnterpriseRoleStore,
    PgEnterpriseSecretStore,
    PgEnterpriseUserStore,
    PgSessionOwnerStore,
)

PG_DSN = os.getenv("DATUS_ENTERPRISE_PG_DSN")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.nightly,
    pytest.mark.skipif(not PG_DSN, reason="DATUS_ENTERPRISE_PG_DSN is not set"),
]


@pytest.mark.asyncio
async def test_enterprise_postgres_metadata_stores_smoke() -> None:
    dsn = os.environ["DATUS_ENTERPRISE_PG_DSN"]
    prefix = f"it_{uuid.uuid4().hex}"
    user_id = f"{prefix}_alice"
    role_id = f"{prefix}_analyst"
    datasource_key = f"{prefix}_finance"
    project_id = f"{prefix}_project"
    session_id = f"{prefix}_session"
    second_session_id = f"{prefix}_session_2"
    artifact_slug = f"{prefix}_dashboard"
    audit_action = f"{prefix}.sql.execute"
    quota_resource = f"{prefix}.sql.execute"
    secret_name = f"{prefix}/datasource/password"

    stores = [
        PgEnterpriseUserStore(dsn=dsn),
        PgEnterpriseRoleStore(dsn=dsn),
        PgEnterpriseDatasourceGrantStore(dsn=dsn),
        PgSessionOwnerStore(dsn=dsn),
        PgArtifactAclStore(dsn=dsn),
        PgAuditSink(dsn=dsn),
        PgEnterpriseQuotaStore(dsn=dsn, max_size=4),
        PgEnterpriseSecretStore(dsn=dsn),
    ]
    (
        user_store,
        role_store,
        grant_store,
        session_store,
        acl_store,
        audit_sink,
        quota_store,
        secret_store,
    ) = stores

    try:
        created_user = await user_store.upsert_user(
            user_id=user_id,
            display_name="Integration Alice",
            email=f"{prefix}@example.com",
        )
        assert created_user["enabled"] is True
        await _assert_schema_created(dsn)

        assert await user_store.get_user(user_id) == created_user
        assert _ids(await user_store.list_users(enabled=True), "user_id", prefix) == [user_id]
        disabled_user = await user_store.set_user_enabled(user_id, False)
        assert disabled_user is not None
        assert disabled_user["enabled"] is False
        assert (await user_store.get_user(user_id))["enabled"] is False

        role = await role_store.upsert_role(
            role_id=role_id,
            name=f"{prefix} analyst",
            description="Integration test role",
            permissions=["module.sql_executor", "module.chat"],
        )
        assert role["permissions"] == ["module.chat", "module.sql_executor"]
        updated_role = await role_store.set_role_permissions(role_id, ["module.datasource_catalog"])
        assert updated_role is not None
        assert updated_role["permissions"] == ["module.datasource_catalog"]
        assert await role_store.set_user_roles(user_id, [role_id]) == [role_id]
        assert await role_store.list_user_roles(user_id) == [role_id]
        assert await role_store.list_role_users(role_id) == [user_id]

        grant = await grant_store.put_grant(
            subject_type="user",
            subject_id=user_id,
            datasource_key=datasource_key,
            effect="allow",
            scope={"allow_catalog": True, "allow_sql": True, "schemas": ["public"], "tables": ["public.accounts"]},
        )
        assert grant["scope"] == {
            "allow_catalog": True,
            "allow_sql": True,
            "schemas": ["public"],
            "tables": ["public.accounts"],
        }
        assert await grant_store.get_grant(
            subject_type="user",
            subject_id=user_id,
            datasource_key=datasource_key,
        ) == grant
        assert await grant_store.list_grants(subject_type="user", subject_id=user_id) == [grant]
        assert await grant_store.delete_grant(
            subject_type="user",
            subject_id=user_id,
            datasource_key=datasource_key,
        ) is True
        assert await grant_store.list_grants(subject_type="user", subject_id=user_id) == []

        await session_store.set_owner(project_id, session_id, user_id)
        await session_store.set_owner(project_id, second_session_id, user_id)
        assert await session_store.get_owner(project_id, session_id) == user_id
        assert set(await session_store.list_session_ids(project_id, user_id)) == {session_id, second_session_id}
        assert {
            record["session_id"] for record in await session_store.list_sessions(project_id, user_id)
        } == {session_id, second_session_id}
        await session_store.delete_owner(project_id, session_id)
        assert await session_store.get_owner(project_id, session_id) is None

        acl = {
            "owner_user_id": user_id,
            "visibility": "role",
            "allowed_roles": [role_id],
            "datasources": [datasource_key],
            "nested": {
                "constraints": [{"kind": "schema", "values": ["public"]}],
                "flags": {"query": True, "export": False},
            },
        }
        assert await acl_store.put_acl(artifact_type="dashboard", slug=artifact_slug, acl=acl) == acl
        assert await acl_store.get_acl(artifact_type="dashboard", slug=artifact_slug) == acl

        await audit_sink.write(
            AuditEvent(
                user_id=user_id,
                action=audit_action,
                resource_type="datasource",
                resource_id=datasource_key,
                decision="allow",
                reason=None,
                request_id=f"{prefix}_request",
                metadata={"rows": 1, "scope": {"tables": ["public.accounts"]}},
            )
        )
        events = await audit_sink.query_events(limit=5, user_id=user_id, action=audit_action, decision="allow")
        assert len(events) == 1
        assert events[0].resource_id == datasource_key
        assert events[0].metadata == {"rows": 1, "scope": {"tables": ["public.accounts"]}}

        await quota_store.put_quota(
            subject_type="user",
            subject_id=user_id,
            resource=quota_resource,
            limit=1,
            window_seconds=60,
        )
        concurrent_results = await asyncio.gather(
            quota_store.consume_quota(
                subjects=[{"subject_type": "user", "subject_id": user_id}],
                resource=quota_resource,
                amount=1,
            ),
            quota_store.consume_quota(
                subjects=[{"subject_type": "user", "subject_id": user_id}],
                resource=quota_resource,
                amount=1,
            ),
        )
        assert sum(result["allowed"] is True for result in concurrent_results) == 1
        assert sum(result["allowed"] is False for result in concurrent_results) == 1
        exceeded = await quota_store.consume_quota(
            subjects=[{"subject_type": "user", "subject_id": user_id}],
            resource=quota_resource,
            amount=1,
        )
        assert exceeded["allowed"] is False
        assert exceeded["reason"] == "quota exceeded"
        usage = await quota_store.list_usage(subject_type="user", subject_id=user_id, resource=quota_resource)
        assert sum(record["used"] for record in usage) == 1

        secret = await secret_store.put_secret(
            name=secret_name,
            provider="env",
            reference=f"{prefix.upper()}_PASSWORD",
            description="Integration secret reference",
        )
        assert secret["enabled"] is True
        assert await secret_store.get_secret(secret_name) == secret
        assert _ids(await secret_store.list_secrets(prefix=f"{prefix}/"), "name", prefix) == [secret_name]
        assert await secret_store.delete_secret(secret_name) is True
        assert await secret_store.get_secret(secret_name) is None
    finally:
        for store in stores:
            await store.close()
        await _cleanup_pg_metadata(dsn, prefix)


async def _assert_schema_created(dsn: str) -> None:
    conn = await asyncpg.connect(dsn)
    try:
        table_names = [
            "enterprise_users",
            "enterprise_roles",
            "enterprise_datasource_grants",
            "session_owners",
            "enterprise_artifact_acls",
            "enterprise_audit_logs",
            "enterprise_quotas",
            "enterprise_quota_usage",
            "enterprise_secrets",
        ]
        rows = await conn.fetch("SELECT to_regclass(name) AS table_name FROM unnest($1::text[]) AS name", table_names)
        assert {str(row["table_name"]) for row in rows} == set(table_names)
    finally:
        await conn.close()


async def _cleanup_pg_metadata(dsn: str, prefix: str) -> None:
    conn = await asyncpg.connect(dsn)
    pattern = f"{prefix}%"
    try:
        await _execute_if_table_exists(
            conn,
            "enterprise_role_permissions",
            "DELETE FROM enterprise_role_permissions WHERE role_id LIKE $1",
            pattern,
        )
        await _execute_if_table_exists(
            conn,
            "enterprise_user_roles",
            "DELETE FROM enterprise_user_roles WHERE user_id LIKE $1 OR role_id LIKE $1",
            pattern,
        )
        await _execute_if_table_exists(
            conn,
            "enterprise_roles",
            "DELETE FROM enterprise_roles WHERE role_id LIKE $1",
            pattern,
        )
        await _execute_if_table_exists(
            conn,
            "enterprise_users",
            "DELETE FROM enterprise_users WHERE user_id LIKE $1",
            pattern,
        )
        await _execute_if_table_exists(
            conn,
            "enterprise_datasource_grants",
            "DELETE FROM enterprise_datasource_grants WHERE subject_id LIKE $1 OR datasource_key LIKE $1",
            pattern,
        )
        await _execute_if_table_exists(
            conn,
            "session_owners",
            "DELETE FROM session_owners WHERE project_id LIKE $1 OR session_id LIKE $1 OR user_id LIKE $1",
            pattern,
        )
        await _execute_if_table_exists(
            conn,
            "enterprise_artifact_acls",
            "DELETE FROM enterprise_artifact_acls WHERE slug LIKE $1",
            pattern,
        )
        await _execute_if_table_exists(
            conn,
            "enterprise_audit_logs",
            """
            DELETE FROM enterprise_audit_logs
            WHERE user_id LIKE $1 OR action LIKE $1 OR resource_id LIKE $1 OR request_id LIKE $1
            """,
            pattern,
        )
        await _execute_if_table_exists(
            conn,
            "enterprise_quota_usage",
            "DELETE FROM enterprise_quota_usage WHERE subject_id LIKE $1 OR resource LIKE $1",
            pattern,
        )
        await _execute_if_table_exists(
            conn,
            "enterprise_quotas",
            "DELETE FROM enterprise_quotas WHERE subject_id LIKE $1 OR resource LIKE $1",
            pattern,
        )
        await _execute_if_table_exists(
            conn,
            "enterprise_secrets",
            "DELETE FROM enterprise_secrets WHERE name LIKE $1",
            pattern,
        )
    finally:
        await conn.close()


async def _execute_if_table_exists(conn: asyncpg.Connection, table_name: str, query: str, *args: str) -> None:
    exists = await conn.fetchval("SELECT to_regclass($1)", table_name)
    if exists is not None:
        await conn.execute(query, *args)


def _ids(records: Sequence[dict[str, object]], key: str, prefix: str) -> list[str]:
    return sorted(str(record[key]) for record in records if str(record[key]).startswith(prefix))
