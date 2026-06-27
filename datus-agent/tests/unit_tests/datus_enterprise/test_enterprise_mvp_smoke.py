"""End-to-end smoke coverage for the single-node enterprise MVP boundary."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.enterprise.defaults import (
    InMemoryEnterpriseDatasourceGrantStore,
    InMemoryEnterpriseQuotaStore,
    InMemoryEnterpriseRoleStore,
    InMemoryEnterpriseUserStore,
    InMemorySessionOwnerStore,
    LocalAuthorizationProvider,
    SqliteAuditSink,
)
from datus.api.enterprise.loader import EnterpriseExtensions, load_enterprise_extensions
from datus.api.models.base_models import Result
from datus.api.models.cli_models import ExecuteSQLData
from datus.api.models.database_models import DatabaseInfo, ListDatabasesData
from datus.api.routes import cli_routes, database_routes
from datus.utils.time_utils import now_utc_iso
from datus_enterprise.api import admin_datasource_routes, me_routes
from datus_enterprise.projection import DatasourceGrantProjector

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def _reset_deps():
    deps._auth_provider = None
    deps._service_cache = None
    deps._enterprise_extensions = None
    deps._datasource = "default"
    deps._default_source = None
    deps._default_interactive = True
    yield
    deps._auth_provider = None
    deps._service_cache = None
    deps._enterprise_extensions = None
    deps._datasource = "default"
    deps._default_source = None
    deps._default_interactive = True


class _BearerUserAuthProvider:
    def __init__(self, users: dict[str, str]) -> None:
        self._users = users

    async def authenticate(self, request: Request) -> AppContext:
        raw = request.headers.get("Authorization", "")
        scheme, _, token = raw.partition(" ")
        if scheme.lower() != "bearer" or token not in self._users:
            raise HTTPException(status_code=401, detail="AUTH_REQUIRED")
        return AppContext(user_id=self._users[token], project_id="enterprise")

    def on_evict(self, callback) -> None:  # noqa: ARG002
        return None


class _StaticServiceCache:
    def __init__(self, service) -> None:
        self.service = service

    async def get_or_create(self, key, factory, expected_fingerprint=None):  # noqa: ARG002
        return self.service

    async def shutdown(self) -> None:
        return None


def _agent_config() -> SimpleNamespace:
    return SimpleNamespace(
        services=SimpleNamespace(
            datasources={
                "finance": SimpleNamespace(type="sqlite"),
                "hr": SimpleNamespace(type="sqlite"),
            },
            default_datasource=None,
        ),
        current_datasource="finance",
        principal={},
    )


def _service() -> SimpleNamespace:
    agent_config = _agent_config()
    datasource = SimpleNamespace()
    datasource.list_databases = MagicMock(
        return_value=Result[ListDatabasesData](
            success=True,
            data=ListDatabasesData(
                databases=[
                    DatabaseInfo(
                        name="main",
                        uri="sqlite:///finance.db",
                        type="sqlite",
                        current=True,
                        schema_name="public",
                        connection_status="connected",
                        tables=["accounts", "payroll"],
                        tables_count=2,
                    )
                ],
                total_count=1,
                current_database="main",
            ),
        )
    )
    cli = SimpleNamespace()
    cli.execute_sql = AsyncMock(
        return_value=Result[ExecuteSQLData](
            success=True,
            data=ExecuteSQLData(
                execute_task_id="task-1",
                sql_query="SELECT * FROM accounts",
                row_count=1,
                sql_return="[]",
                result_format="json",
                execution_time=0.01,
                executed_at=now_utc_iso(),
                columns=["id"],
            ),
        )
    )
    cli.stop_execute_sql = AsyncMock()
    return SimpleNamespace(agent_config=agent_config, datasource=datasource, cli=cli)


def _install_enterprise_runtime(tmp_path, svc):
    user_store = InMemoryEnterpriseUserStore()
    role_store = InMemoryEnterpriseRoleStore()
    datasource_grant_store = InMemoryEnterpriseDatasourceGrantStore()
    quota_store = InMemoryEnterpriseQuotaStore()
    audit_sink = SqliteAuditSink(str(tmp_path / "enterprise.db"))

    async def seed() -> None:
        await user_store.upsert_user(user_id="admin", display_name="Admin")
        await user_store.upsert_user(user_id="alice", display_name="Alice")
        await role_store.upsert_role(
            role_id="enterprise_admin",
            name="Enterprise Admin",
            permissions=["module.admin.datasources", "module.datasource_catalog", "module.sql_executor"],
        )
        await role_store.upsert_role(
            role_id="analyst",
            name="Analyst",
            permissions=["module.datasource_catalog", "module.sql_executor"],
        )
        await role_store.set_user_roles("admin", ["enterprise_admin"])
        await role_store.set_user_roles("alice", ["analyst"])
        await datasource_grant_store.put_grant(
            subject_type="role",
            subject_id="enterprise_admin",
            datasource_key="finance",
            effect="allow",
            scope={"allow_catalog": True, "allow_sql": True},
        )

    asyncio.run(seed())
    extensions = EnterpriseExtensions(
        enabled=True,
        authorization_provider=LocalAuthorizationProvider(),
        config_projector=DatasourceGrantProjector(),
        session_owner_store=InMemorySessionOwnerStore(),
        audit_sink=audit_sink,
        user_store=user_store,
        role_store=role_store,
        datasource_grant_store=datasource_grant_store,
        quota_store=quota_store,
    )
    deps.init_deps(
        _BearerUserAuthProvider({"admin-token": "admin", "alice-token": "alice"}),
        _StaticServiceCache(svc),
        datasource="finance",
        enterprise_extensions=extensions,
    )
    return audit_sink


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(me_routes.router)
    app.include_router(admin_datasource_routes.router)
    app.include_router(database_routes.router)
    app.include_router(cli_routes.router)
    return TestClient(app, raise_server_exceptions=False)


def test_enterprise_mvp_smoke_authorizes_catalog_and_sql_through_server_stores(tmp_path):
    svc = _service()
    audit_sink = _install_enterprise_runtime(tmp_path, svc)

    with _client() as client:
        admin_response = client.put(
            "/api/v1/admin/datasource-grants/user/alice/finance",
            headers={"Authorization": "Bearer admin-token"},
            json={
                "effect": "allow",
                "scope": {
                    "allow_catalog": True,
                    "allow_sql": True,
                    "databases": ["main"],
                    "schemas": ["public"],
                    "tables": ["public.accounts"],
                },
            },
        )
        me_response = client.get("/api/v1/me", headers={"Authorization": "Bearer alice-token"})
        catalog_response = client.get(
            "/api/v1/catalog/list?datasource_id=finance",
            headers={"Authorization": "Bearer alice-token"},
        )
        unauthorized_catalog_response = client.get(
            "/api/v1/catalog/list?datasource_id=hr",
            headers={"Authorization": "Bearer alice-token"},
        )
        sql_response = client.post(
            "/api/v1/sql/execute",
            headers={"Authorization": "Bearer alice-token"},
            json={"database_name": "main", "sql_query": "SELECT * FROM accounts", "result_format": "json"},
        )

    assert admin_response.status_code == 200
    assert admin_response.json()["success"] is True
    assert me_response.json()["data"]["permissions"] == ["module.datasource_catalog", "module.sql_executor"]
    assert me_response.json()["data"]["datasource_grants"]["finance"]["tables"] == ["public.accounts"]

    assert catalog_response.status_code == 200
    visible_databases = catalog_response.json()["data"]["databases"]
    assert visible_databases[0]["tables"] == ["accounts"]
    assert unauthorized_catalog_response.status_code == 403
    assert "not authorized" in unauthorized_catalog_response.json()["detail"]

    assert sql_response.status_code == 200
    assert sql_response.json()["success"] is True
    projected_config = svc.cli.execute_sql.await_args.kwargs["agent_config"]
    assert projected_config.current_datasource == "finance"
    assert list(projected_config.services.datasources) == ["finance"]
    assert projected_config.principal["user_id"] == "alice"
    assert projected_config.principal["datasource_grants"]["finance"]["tables"] == ["public.accounts"]

    audit_events = asyncio.run(audit_sink.query_events(limit=20))
    assert any(event.action == "module.admin.datasources" and event.decision == "allow" for event in audit_events)
    assert any(event.action == "sql.execute" and event.decision == "allow" for event in audit_events)


def test_enterprise_mvp_config_keeps_sqlite_metadata_fallback():
    config = yaml.safe_load((REPO_ROOT / "conf/agent.enterprise.mvp.yml.example").read_text())

    enterprise = config["enterprise"]
    assert enterprise["user_store"]["class"] == "datus.api.enterprise.defaults:SqliteEnterpriseUserStore"
    assert enterprise["role_store"]["class"] == "datus.api.enterprise.defaults:SqliteEnterpriseRoleStore"
    assert (
        enterprise["datasource_grant_store"]["class"]
        == "datus.api.enterprise.defaults:SqliteEnterpriseDatasourceGrantStore"
    )
    assert enterprise["session_owner_store"]["class"] == "datus.api.enterprise.defaults:SqliteSessionOwnerStore"
    assert enterprise["audit_sink"]["class"] == "datus.api.enterprise.defaults:SqliteAuditSink"
    assert enterprise["quota_store"]["class"] == "datus.api.enterprise.defaults:InMemoryEnterpriseQuotaStore"
    assert "artifact_acl_store" not in enterprise


def test_enterprise_pg_config_loads_postgres_metadata_providers():
    config = yaml.safe_load((REPO_ROOT / "conf/agent.enterprise.pg.yml.example").read_text())
    enterprise = config["enterprise"]

    for key in (
        "user_store",
        "role_store",
        "datasource_grant_store",
        "session_owner_store",
        "artifact_acl_store",
        "audit_sink",
        "quota_store",
        "secret_store",
    ):
        enterprise[key]["kwargs"]["dsn"] = "postgresql://metadata"
        assert enterprise[key]["kwargs"]["min_size"] == 1
        assert enterprise[key]["kwargs"]["max_size"] == 2

    extensions = load_enterprise_extensions(enterprise)

    assert extensions.enabled is True
    assert extensions.user_store.__class__.__name__ == "PgEnterpriseUserStore"
    assert extensions.role_store.__class__.__name__ == "PgEnterpriseRoleStore"
    assert extensions.datasource_grant_store.__class__.__name__ == "PgEnterpriseDatasourceGrantStore"
    assert extensions.session_owner_store.__class__.__name__ == "PgSessionOwnerStore"
    assert extensions.artifact_acl_store.__class__.__name__ == "PgArtifactAclStore"
    assert extensions.audit_sink.__class__.__name__ == "PgAuditSink"
    assert extensions.quota_store.__class__.__name__ == "PgEnterpriseQuotaStore"
    assert extensions.secret_store.__class__.__name__ == "PgEnterpriseSecretStore"
