"""Tests for OceanBase MySQL enterprise session stores."""

from __future__ import annotations

import asyncio

import pytest

from datus.api.enterprise.loader import load_enterprise_extensions
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
)


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
    assert isinstance(extensions.session_body_store, ObSessionBodyStore)
