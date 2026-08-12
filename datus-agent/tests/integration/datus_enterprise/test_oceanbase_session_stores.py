"""Opt-in OceanBase MySQL integration tests for enterprise session storage."""

from __future__ import annotations

import os
import uuid

import pytest

from datus.api.enterprise.models import AuditEvent
from datus_enterprise.oceanbase_session_store import ObSessionBodyStore
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
)

OB_HOST = os.getenv("DATUS_ENTERPRISE_OB_HOST")
OB_PORT = os.getenv("DATUS_ENTERPRISE_OB_PORT", "2881")
OB_USER = os.getenv("DATUS_ENTERPRISE_OB_USER")
OB_PASSWORD = os.getenv("DATUS_ENTERPRISE_OB_PASSWORD")
OB_DATABASE = os.getenv("DATUS_ENTERPRISE_OB_DATABASE", "datus_enterprise_it")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.nightly,
    pytest.mark.skipif(
        not (OB_HOST and OB_USER and OB_PASSWORD),
        reason="DATUS_ENTERPRISE_OB_HOST/USER/PASSWORD are required for OceanBase session integration tests.",
    ),
]


@pytest.mark.asyncio
async def test_oceanbase_enterprise_metadata_and_session_round_trip():
    prefix = f"it_{uuid.uuid4().hex[:12]}"
    project_id = f"{prefix}_project"
    user_id = f"{prefix}_alice"
    role_id = f"{prefix}_analyst"
    datasource_key = f"{prefix}_finance"
    scope = user_id
    session_id = f"chat_session_{prefix}"
    copied_session_id = f"feedback_session_{prefix}"
    stores = _stores()
    (
        user_store,
        role_store,
        grant_store,
        agent_store,
        owner_store,
        acl_store,
        audit_sink,
        quota_store,
        secret_store,
        body_store,
    ) = stores

    try:
        user = await user_store.upsert_user(
            user_id=user_id,
            display_name="OceanBase Alice",
            email=f"{prefix}@example.com",
            external_user_id=f"{prefix}_external",
            department="Data",
            title="Analyst",
        )
        assert user["enabled"] is True
        assert await user_store.get_user(user_id) == user
        assert [row["user_id"] for row in await user_store.list_users(enabled=True) if row["user_id"] == user_id] == [
            user_id
        ]
        assert (await user_store.set_user_enabled(user_id, False))["enabled"] is False

        role = await role_store.upsert_role(
            role_id=role_id,
            name="Analyst",
            permissions=["module.chat", "module.datasource_catalog"],
        )
        assert role["permissions"] == ["module.chat", "module.datasource_catalog"]
        assert await role_store.set_user_roles(user_id, [role_id]) == [role_id]
        assert await role_store.list_user_roles(user_id) == [role_id]
        assert await role_store.list_role_users(role_id) == [user_id]

        grant = await grant_store.put_grant(
            subject_type="user",
            subject_id=user_id,
            datasource_key=datasource_key,
            effect="allow",
            scope={"allow_sql": True, "tables": ["public.accounts"]},
        )
        assert grant["scope"] == {"allow_sql": True, "tables": ["public.accounts"]}
        assert (
            await grant_store.get_grant(subject_type="user", subject_id=user_id, datasource_key=datasource_key) == grant
        )

        agent = await agent_store.put_agent(
            agent_id=f"{prefix}_agent",
            payload={
                "name": "Finance agent",
                "status": "published",
                "owner_user_id": user_id,
                "datasource_id": datasource_key,
                "tools": ["sql"],
                "scoped_context": {"datasource": datasource_key},
                "acl": {"visibility": "role", "allowed_roles": [role_id]},
            },
        )
        assert agent["status"] == "published"
        assert agent["tools"] == ["sql"]
        assert (await agent_store.set_agent_status(agent["agent_id"], "disabled"))["status"] == "disabled"
        assert (await agent_store.put_agent_acl(agent["agent_id"], {"visibility": "enterprise"}))["acl"] == {
            "visibility": "enterprise",
            "allowed_roles": [],
            "allowed_user_ids": [],
        }

        await owner_store.set_owner(project_id, session_id, user_id)
        assert await owner_store.get_owner(project_id, session_id) == user_id
        assert await owner_store.list_session_ids(project_id, user_id) == [session_id]

        acl = {"owner_user_id": user_id, "visibility": "private", "allowed_roles": [], "allowed_user_ids": []}
        assert await acl_store.put_acl(artifact_type="dashboard", slug=f"{prefix}_dashboard", acl=acl) == acl
        assert await acl_store.get_acl(artifact_type="dashboard", slug=f"{prefix}_dashboard") == acl
        await acl_store.delete_acl(artifact_type="dashboard", slug=f"{prefix}_dashboard")
        with pytest.raises(KeyError):
            await acl_store.get_acl(artifact_type="dashboard", slug=f"{prefix}_dashboard")

        await audit_sink.write(
            AuditEvent(
                user_id=user_id,
                action=f"{prefix}.query",
                resource_type="datasource",
                resource_id=datasource_key,
                decision="allow",
                reason="integration",
                request_id=f"{prefix}_request",
                metadata={"k": "v"},
            )
        )
        events = await audit_sink.query_events(limit=10, request_id=f"{prefix}_request")
        assert len(events) == 1
        assert events[0].metadata == {"k": "v"}

        quota = await quota_store.put_quota(
            subject_type="user",
            subject_id=user_id,
            resource=f"{prefix}.tokens",
            limit=5,
            window_seconds=3600,
        )
        assert quota["limit"] == 5
        assert (
            await quota_store.consume_quota(
                subjects=[{"subject_type": "user", "subject_id": user_id}],
                resource=f"{prefix}.tokens",
                amount=3,
            )
        )["allowed"] is True
        denied = await quota_store.consume_quota(
            subjects=[{"subject_type": "user", "subject_id": user_id}],
            resource=f"{prefix}.tokens",
            amount=3,
        )
        assert denied["allowed"] is False

        secret = await secret_store.put_secret(
            name=f"{prefix}/datasource/password",
            provider="env",
            reference=f"{prefix.upper()}_PASSWORD",
            description="integration",
        )
        assert secret["reference"] == f"{prefix.upper()}_PASSWORD"
        assert await secret_store.get_secret(secret["name"]) == secret
        assert [row["name"] for row in await secret_store.list_secrets(prefix=f"{prefix}/")] == [secret["name"]]

        session = body_store.open_session(project_id=project_id, scope=scope, session_id=session_id)
        await session.add_items(
            [
                {"role": "user", "content": "hello oceanbase"},
                {"role": "assistant", "content": [{"type": "output_text", "text": "hello user"}]},
            ]
        )
        assert await session.get_items() == [
            {"role": "user", "content": "hello oceanbase"},
            {"role": "assistant", "content": [{"type": "output_text", "text": "hello user"}]},
        ]
        assert await body_store.session_exists(project_id=project_id, scope=scope, session_id=session_id) is True
        assert await body_store.list_session_ids(project_id=project_id, scope=scope) == [session_id]

        info = await body_store.get_session_info(project_id=project_id, scope=scope, session_id=session_id)
        assert info["exists"] is True
        assert info["message_count"] == 2
        assert info["latest_user_message"] == "hello oceanbase"

        await body_store.upsert_running_turn_usage(
            project_id=project_id,
            scope=scope,
            session_id=session_id,
            user_turn_number=1,
            cumulative={"total_tokens": 123},
            context_length=4096,
        )
        running = await body_store.get_running_turn_usage(project_id=project_id, scope=scope, session_id=session_id)
        assert running["cumulative"]["total_tokens"] == 123

        await body_store.save_system_prompt_snapshot(
            project_id=project_id,
            scope=scope,
            session_id=session_id,
            payload={"schema_version": 1, "prompt": "system", "node_name": "chat"},
        )
        snapshot = await body_store.load_system_prompt_snapshot(
            project_id=project_id, scope=scope, session_id=session_id
        )
        assert snapshot["prompt"] == "system"

        await body_store.copy_session(
            project_id=project_id,
            scope=scope,
            source_session_id=session_id,
            target_session_id=copied_session_id,
        )
        assert sorted(await body_store.list_session_ids(project_id=project_id, scope=scope)) == [
            session_id,
            copied_session_id,
        ]
        assert (
            await body_store.load_system_prompt_snapshot(
                project_id=project_id,
                scope=scope,
                session_id=copied_session_id,
            )
            == snapshot
        )
    finally:
        await grant_store.delete_grant(subject_type="user", subject_id=user_id, datasource_key=datasource_key)
        await agent_store.delete_agent(f"{prefix}_agent")
        await owner_store.delete_owner(project_id, session_id)
        await secret_store.delete_secret(f"{prefix}/datasource/password")
        await body_store.delete_session(project_id=project_id, scope=scope, session_id=session_id)
        await body_store.delete_session(project_id=project_id, scope=scope, session_id=copied_session_id)
        for store in stores:
            await store.close()


def _kwargs() -> dict[str, str]:
    return {
        "host": OB_HOST or "",
        "port": OB_PORT,
        "user": OB_USER or "",
        "password": OB_PASSWORD or "",
        "database": OB_DATABASE,
        "pool_max_size": 1,
    }


def _stores():
    kwargs = _kwargs()
    return [
        ObEnterpriseUserStore(**kwargs),
        ObEnterpriseRoleStore(**kwargs),
        ObEnterpriseDatasourceGrantStore(**kwargs),
        ObEnterpriseAgentStore(**kwargs),
        ObSessionOwnerStore(**kwargs),
        ObArtifactAclStore(**kwargs),
        ObAuditSink(**kwargs),
        ObEnterpriseQuotaStore(**kwargs),
        ObEnterpriseSecretStore(**kwargs),
        ObSessionBodyStore(**kwargs),
    ]
