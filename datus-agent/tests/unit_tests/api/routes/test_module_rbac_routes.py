# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.

"""HTTP-level module RBAC coverage for enterprise route dependencies."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.enterprise.defaults import (
    InMemorySessionOwnerStore,
    LocalAuthorizationProvider,
    NoopAuditSink,
    PassthroughConfigProjector,
)
from datus.api.enterprise.loader import EnterpriseExtensions
from datus.api.models.base_models import Result
from datus.api.models.cli_models import ChatSessionData, ExecuteSQLData, StopExecuteSQLData
from datus.api.models.dashboard_models import DashboardDetail, SqlQueryResultEnvelope
from datus.api.models.database_models import DatabaseInfo, DatabasesData, ListDatabasesData
from datus.api.models.report_models import ReportDetail
from datus.api.routes import chat_routes, cli_routes, dashboard_routes, database_routes, report_routes
from datus.api.services.cli_service import CLIService, _SQLTaskRecord
from datus.schemas.artifact_manifest import ArtifactManifest
from datus_enterprise.config_projection import DatasourceGrantConfigProjector


def _enterprise_extensions(config_projector=None) -> EnterpriseExtensions:
    return EnterpriseExtensions(
        enabled=True,
        authorization_provider=LocalAuthorizationProvider(),
        config_projector=config_projector or PassthroughConfigProjector(),
        session_owner_store=InMemorySessionOwnerStore(),
        audit_sink=NoopAuditSink(),
    )


def _client(router, ctx: AppContext, svc: MagicMock):
    app = FastAPI()
    app.include_router(router)

    async def override_service(request: Request):
        request.state.app_context = ctx
        return svc

    app.dependency_overrides[deps.get_datus_service] = override_service
    return TestClient(app, raise_server_exceptions=False)


def _artifact_manifest(kind: str) -> ArtifactManifest:
    return ArtifactManifest(
        slug="sales_overview",
        name="Sales Overview",
        description="Sales overview artifact",
        kind=kind,
        created_at="2026-06-27T00:00:00Z",
    )


def _report_detail() -> ReportDetail:
    return ReportDetail(
        slug="sales_overview",
        name="Sales Overview",
        description="Sales overview artifact",
        manifest=_artifact_manifest("report"),
        created_at="2026-06-27T00:00:00Z",
        files=[],
    )


def _dashboard_detail() -> DashboardDetail:
    return DashboardDetail(
        slug="sales_overview",
        name="Sales Overview",
        description="Sales overview artifact",
        manifest=_artifact_manifest("dashboard"),
        created_at="2026-06-27T00:00:00Z",
        files=[],
        templates=[],
    )


def _dashboard_query_result() -> SqlQueryResultEnvelope:
    return SqlQueryResultEnvelope(
        executed_at="2026-06-27T00:00:00Z",
        datasource="warehouse",
        row_count=0,
        columns=[],
        rows=[],
        sql="SELECT 1",
    )


def _datasource_agent_config(*, current_datasource: str = "default"):
    datasources = {
        "default": SimpleNamespace(type="sqlite"),
        "finance": SimpleNamespace(type="sqlite"),
        "hr": SimpleNamespace(type="sqlite"),
    }
    return SimpleNamespace(
        services=SimpleNamespace(datasources=datasources, default_datasource=None),
        current_datasource=current_datasource,
        principal={},
    )


def test_chat_routes_require_module_chat(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = MagicMock()
    svc.chat.list_sessions.return_value = Result[ChatSessionData](success=True, data=ChatSessionData())
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.datasource_catalog"})

    with _client(chat_routes.router, ctx, svc) as client:
        response = client.get("/api/v1/chat/sessions")

    assert response.status_code == 403
    svc.chat.list_sessions.assert_not_called()


def test_chat_routes_allow_module_chat(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = MagicMock()
    svc.chat.list_sessions.return_value = Result[ChatSessionData](success=True, data=ChatSessionData())
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.chat"})

    with _client(chat_routes.router, ctx, svc) as client:
        response = client.get("/api/v1/chat/sessions")

    assert response.status_code == 200
    assert response.json()["success"] is True
    svc.chat.list_sessions.assert_called_once_with(user_id="u1", subagent_id=None)


def test_chat_stream_denies_unauthorized_datasource_before_task_start(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions(DatasourceGrantConfigProjector()))
    svc = MagicMock()
    svc.agent_config = SimpleNamespace(
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
    ctx = AppContext(
        user_id="u1",
        project_id="proj",
        permissions={"module.chat"},
        datasource_grants={"finance": {"effect": "allow", "allow_sql": True}},
    )

    with _client(chat_routes.router, ctx, svc) as client:
        response = client.post(
            "/api/v1/chat/stream",
            json={"message": "query hr", "datasource": "hr"},
        )

    assert response.status_code == 200
    assert "event: error" in response.text
    assert "DATASOURCE_ACCESS_DENIED" in response.text
    assert "Datasource 'hr' is not authorized for this request." in response.text
    svc.chat.stream_chat.assert_not_called()


@pytest.mark.parametrize(
    "subagent_id",
    ["gen_sql", "gen_report", "gen_visual_report", "gen_dashboard", "gen_visual_dashboard"],
)
def test_chat_stream_denies_privileged_subagents_with_module_chat_only(monkeypatch, subagent_id):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = MagicMock()
    svc.agent_config.agentic_nodes = {}
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.chat"})

    with _client(chat_routes.router, ctx, svc) as client:
        response = client.post("/api/v1/chat/stream", json={"message": "run it", "subagent_id": subagent_id})

    assert response.status_code == 403
    svc.chat.stream_chat.assert_not_called()


def test_chat_stream_denies_custom_privileged_subagent_with_module_chat_only(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = MagicMock()
    svc.agent_config.agentic_nodes = {"sales_dashboard": {"id": "custom-dashboard-id", "node_class": "gen_dashboard"}}
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.chat"})

    with _client(chat_routes.router, ctx, svc) as client:
        response = client.post(
            "/api/v1/chat/stream",
            json={"message": "build dashboard", "subagent_id": "custom-dashboard-id"},
        )

    assert response.status_code == 403
    svc.chat.stream_chat.assert_not_called()


@pytest.mark.parametrize(
    ("agent_type", "subagent_id"),
    [("ask_report", "custom-ask-report-id"), ("ask_dashboard", "custom-ask-dashboard-id")],
)
def test_chat_stream_denies_custom_ask_artifact_subagent_with_module_chat_only(monkeypatch, agent_type, subagent_id):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = MagicMock()
    svc.agent_config.agentic_nodes = {"ask_artifact": {"id": subagent_id, "type": agent_type}}
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.chat"})

    with _client(chat_routes.router, ctx, svc) as client:
        response = client.post(
            "/api/v1/chat/stream",
            json={"message": "inspect artifact", "subagent_id": subagent_id},
        )

    assert response.status_code == 403
    svc.chat.stream_chat.assert_not_called()


@pytest.mark.parametrize(
    ("agent_type", "permission", "artifact_type", "subagent_id"),
    [
        ("ask_report", "module.report.query", "report", "custom-ask-report-id"),
        ("ask_dashboard", "module.dashboard.query", "dashboard", "custom-ask-dashboard-id"),
    ],
)
def test_chat_stream_denies_custom_ask_artifact_subagent_for_acl_miss(
    monkeypatch, agent_type, permission, artifact_type, subagent_id
):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = MagicMock()
    svc.agent_config.agentic_nodes = {
        "ask_artifact": {"id": subagent_id, "type": agent_type, "artifact_slug": "sales_overview"}
    }
    ctx = AppContext(
        user_id="u1",
        project_id="proj",
        permissions={"module.chat", permission},
        principal={"artifact_acl": {artifact_type: ["other_artifact"]}},
    )

    with _client(chat_routes.router, ctx, svc) as client:
        response = client.post(
            "/api/v1/chat/stream",
            json={"message": "inspect artifact", "subagent_id": subagent_id},
        )

    assert response.status_code == 404
    svc.chat.stream_chat.assert_not_called()


@pytest.mark.parametrize(
    ("agent_type", "permission", "artifact_type"),
    [
        ("ask_report", "module.report.query", "report"),
        ("ask_dashboard", "module.dashboard.query", "dashboard"),
    ],
)
def test_chat_stream_denies_builtin_name_ask_artifact_subagent_for_acl_miss(
    monkeypatch, agent_type, permission, artifact_type
):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = MagicMock()
    svc.agent_config.agentic_nodes = {agent_type: {"artifact_slug": "sales_overview"}}
    ctx = AppContext(
        user_id="u1",
        project_id="proj",
        permissions={"module.chat", permission},
        principal={"artifact_acl": {artifact_type: ["other_artifact"]}},
    )

    with _client(chat_routes.router, ctx, svc) as client:
        response = client.post(
            "/api/v1/chat/stream",
            json={"message": "inspect artifact", "subagent_id": agent_type},
        )

    assert response.status_code == 404
    svc.chat.stream_chat.assert_not_called()


def test_datasource_catalog_routes_require_module_datasource_catalog(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = MagicMock()
    svc.datasource.current_datasource = "default"
    svc.datasource.list_databases.return_value = Result[ListDatabasesData](
        success=True,
        data=ListDatabasesData(databases=[], total_count=0, current_database=None),
    )
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.chat"})

    with _client(database_routes.router, ctx, svc) as client:
        response = client.get("/api/v1/catalog/list")

    assert response.status_code == 403
    svc.datasource.list_databases.assert_not_called()


def test_datasource_catalog_routes_allow_module_datasource_catalog(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = MagicMock()
    svc.agent_config = _datasource_agent_config()
    svc.datasource.current_datasource = "default"
    svc.datasource.list_databases.return_value = Result[ListDatabasesData](
        success=True,
        data=ListDatabasesData(databases=[], total_count=0, current_database=None),
    )
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.datasource_catalog"})

    with _client(database_routes.router, ctx, svc) as client:
        response = client.get("/api/v1/catalog/list")

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["data"] == DatabasesData(databases=[]).model_dump()
    svc.datasource.list_databases.assert_called_once()


def test_datasource_catalog_rejects_unauthorized_requested_datasource(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions(DatasourceGrantConfigProjector()))
    svc = MagicMock()
    svc.agent_config = _datasource_agent_config(current_datasource="finance")
    svc.datasource.current_datasource = "finance"
    ctx = AppContext(
        user_id="u1",
        project_id="proj",
        permissions={"module.datasource_catalog"},
        datasource_grants={"finance": {"effect": "allow", "allow_catalog": True}},
    )

    with _client(database_routes.router, ctx, svc) as client:
        response = client.get("/api/v1/catalog/list?datasource_id=hr")

    assert response.status_code == 403
    assert response.json()["detail"] == "Datasource 'hr' is not authorized for this request."
    svc.datasource.list_databases.assert_not_called()


def test_datasource_catalog_uses_projected_default_datasource(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions(DatasourceGrantConfigProjector()))
    svc = MagicMock()
    svc.agent_config = _datasource_agent_config(current_datasource="hr")
    svc.datasource.current_datasource = "hr"
    svc.datasource.list_databases.return_value = Result[ListDatabasesData](
        success=True,
        data=ListDatabasesData(databases=[], total_count=0, current_database=None),
    )
    ctx = AppContext(
        user_id="u1",
        project_id="proj",
        permissions={"module.datasource_catalog"},
        datasource_grants={"finance": {"effect": "allow", "allow_catalog": True}},
    )

    with _client(database_routes.router, ctx, svc) as client:
        response = client.get("/api/v1/catalog/list")

    assert response.status_code == 200
    request = svc.datasource.list_databases.call_args.args[0]
    assert request.datasource_id == "finance"


def test_datasource_catalog_rejects_unauthorized_requested_schema_before_query(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions(DatasourceGrantConfigProjector()))
    svc = MagicMock()
    svc.agent_config = _datasource_agent_config(current_datasource="finance")
    svc.datasource.current_datasource = "finance"
    ctx = AppContext(
        user_id="u1",
        project_id="proj",
        permissions={"module.datasource_catalog"},
        datasource_grants={
            "finance": {
                "effect": "allow",
                "allow_catalog": True,
                "schemas": ["mart"],
            }
        },
    )

    with _client(database_routes.router, ctx, svc) as client:
        response = client.get("/api/v1/catalog/list?schema_name=private")

    assert response.status_code == 403
    assert response.json()["detail"] == "Requested schema 'private' is not authorized for datasource 'finance'."
    svc.datasource.list_databases.assert_not_called()


def test_datasource_catalog_false_grant_returns_empty_catalog(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = MagicMock()
    svc.agent_config = _datasource_agent_config(current_datasource="default")
    svc.datasource.current_datasource = "default"
    svc.datasource.list_databases.return_value = Result[ListDatabasesData](
        success=True,
        data=ListDatabasesData(
            databases=[
                DatabaseInfo(
                    name="main",
                    uri="sqlite:///main.db",
                    type="sqlite",
                    current=True,
                    connection_status="connected",
                    tables=["public_table"],
                )
            ],
            total_count=1,
            current_database="main",
        ),
    )
    ctx = AppContext(
        user_id="u1",
        project_id="proj",
        permissions={"module.datasource_catalog"},
        datasource_grants={"default": False},
    )

    with _client(database_routes.router, ctx, svc) as client:
        response = client.get("/api/v1/catalog/list")

    assert response.status_code == 200
    assert response.json()["data"]["databases"] == []


def test_datasource_catalog_allow_catalog_false_returns_empty_catalog(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = MagicMock()
    svc.agent_config = _datasource_agent_config(current_datasource="default")
    svc.datasource.current_datasource = "default"
    svc.datasource.list_databases.return_value = Result[ListDatabasesData](
        success=True,
        data=ListDatabasesData(
            databases=[
                DatabaseInfo(
                    name="main",
                    uri="sqlite:///main.db",
                    type="sqlite",
                    current=True,
                    connection_status="connected",
                    tables=["public_table"],
                )
            ],
            total_count=1,
            current_database="main",
        ),
    )
    ctx = AppContext(
        user_id="u1",
        project_id="proj",
        permissions={"module.datasource_catalog"},
        datasource_grants={"default": {"effect": "allow", "allow_catalog": False}},
    )

    with _client(database_routes.router, ctx, svc) as client:
        response = client.get("/api/v1/catalog/list")

    assert response.status_code == 200
    assert response.json()["data"]["databases"] == []


def test_datasource_catalog_preserves_unknown_table_count_without_table_scope(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = MagicMock()
    svc.agent_config = _datasource_agent_config(current_datasource="default")
    svc.datasource.current_datasource = "default"
    svc.datasource.list_databases.return_value = Result[ListDatabasesData](
        success=True,
        data=ListDatabasesData(
            databases=[
                DatabaseInfo(
                    name="main",
                    uri="sqlite:///main.db",
                    type="sqlite",
                    current=True,
                    connection_status="disconnected",
                    tables_count=None,
                    tables=None,
                )
            ],
            total_count=1,
            current_database="main",
        ),
    )
    ctx = AppContext(
        user_id="u1",
        project_id="proj",
        permissions={"module.datasource_catalog"},
        datasource_grants={"default": {"effect": "allow"}},
    )

    with _client(database_routes.router, ctx, svc) as client:
        response = client.get("/api/v1/catalog/list")

    assert response.status_code == 200
    databases = response.json()["data"]["databases"]
    assert len(databases) == 1
    assert databases[0]["tables_count"] is None


def test_datasource_catalog_prunes_tables_by_grant_scope(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions(DatasourceGrantConfigProjector()))
    svc = MagicMock()
    svc.agent_config = _datasource_agent_config(current_datasource="finance")
    svc.datasource.current_datasource = "finance"
    svc.datasource.list_databases.return_value = Result[ListDatabasesData](
        success=True,
        data=ListDatabasesData(
            databases=[
                DatabaseInfo(
                    name="finance",
                    uri="sqlite:///finance.db",
                    type="sqlite",
                    current=True,
                    catalog_name="prod",
                    schema_name="mart",
                    connection_status="connected",
                    tables_count=3,
                    tables=["fnd_balance", "dim_date", "hr_employee"],
                ),
                DatabaseInfo(
                    name="finance",
                    uri="sqlite:///finance.db",
                    type="sqlite",
                    current=True,
                    catalog_name="prod",
                    schema_name="private",
                    connection_status="connected",
                    tables_count=1,
                    tables=["fnd_secret"],
                ),
            ],
            total_count=2,
            current_database="finance",
        ),
    )
    ctx = AppContext(
        user_id="u1",
        project_id="proj",
        permissions={"module.datasource_catalog"},
        datasource_grants={
            "finance": {
                "effect": "allow",
                "allow_catalog": True,
                "catalogs": ["prod"],
                "databases": ["finance"],
                "schemas": ["mart"],
                "tables": ["fnd_*", "dim_date"],
            }
        },
    )

    with _client(database_routes.router, ctx, svc) as client:
        response = client.get("/api/v1/catalog/list")

    assert response.status_code == 200
    assert response.json()["success"] is True
    databases = response.json()["data"]["databases"]
    assert len(databases) == 1
    assert databases[0]["schema_name"] == "mart"
    assert databases[0]["tables"] == ["fnd_balance", "dim_date"]
    assert databases[0]["tables_count"] == 2


def test_report_detail_requires_module_report_view(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = MagicMock()
    svc.report.get_detail = AsyncMock(return_value=Result[ReportDetail](success=True, data=_report_detail()))
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.chat"})

    with _client(report_routes.router, ctx, svc) as client:
        response = client.get("/api/v1/report/detail", params={"slug": "sales_overview"})

    assert response.status_code == 403
    svc.report.get_detail.assert_not_awaited()


def test_report_detail_allows_module_report_view(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = MagicMock()
    svc.agent_config.project_root = "/tmp/project"
    svc.report.get_detail = AsyncMock(return_value=Result[ReportDetail](success=True, data=_report_detail()))
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.report.view"})

    with _client(report_routes.router, ctx, svc) as client:
        response = client.get("/api/v1/report/detail", params={"slug": "sales_overview"})

    assert response.status_code == 200
    assert response.json()["success"] is True
    svc.report.get_detail.assert_awaited_once()
    assert svc.report.get_detail.await_args.kwargs["report_slug"] == "sales_overview"


def test_report_detail_rejects_artifact_acl_denial(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = MagicMock()
    svc.agent_config.project_root = "/tmp/project"
    svc.report.get_detail = AsyncMock(return_value=Result[ReportDetail](success=True, data=_report_detail()))
    ctx = AppContext(
        user_id="u1",
        project_id="proj",
        permissions={"module.report.view"},
        principal={"artifact_acl": {"report": ["other_report"]}},
    )

    with _client(report_routes.router, ctx, svc) as client:
        response = client.get("/api/v1/report/detail", params={"slug": "sales_overview"})

    assert response.status_code == 404
    svc.report.get_detail.assert_not_awaited()


def test_dashboard_detail_requires_module_dashboard_view(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = MagicMock()
    svc.dashboard.get_detail = AsyncMock(return_value=Result[DashboardDetail](success=True, data=_dashboard_detail()))
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.chat"})

    with _client(dashboard_routes.router, ctx, svc) as client:
        response = client.get("/api/v1/dashboard/detail", params={"slug": "sales_overview"})

    assert response.status_code == 403
    svc.dashboard.get_detail.assert_not_awaited()


def test_dashboard_detail_allows_module_dashboard_view(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = MagicMock()
    svc.agent_config.project_root = "/tmp/project"
    svc.dashboard.get_detail = AsyncMock(return_value=Result[DashboardDetail](success=True, data=_dashboard_detail()))
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.dashboard.view"})

    with _client(dashboard_routes.router, ctx, svc) as client:
        response = client.get("/api/v1/dashboard/detail", params={"slug": "sales_overview"})

    assert response.status_code == 200
    assert response.json()["success"] is True
    svc.dashboard.get_detail.assert_awaited_once()
    assert svc.dashboard.get_detail.await_args.kwargs["dashboard_slug"] == "sales_overview"


def test_dashboard_detail_rejects_artifact_acl_denial(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = MagicMock()
    svc.agent_config.project_root = "/tmp/project"
    svc.dashboard.get_detail = AsyncMock(return_value=Result[DashboardDetail](success=True, data=_dashboard_detail()))
    ctx = AppContext(
        user_id="u1",
        project_id="proj",
        permissions={"module.dashboard.view"},
        principal={"artifact_acl": {"dashboard": ["other_dashboard"]}},
    )

    with _client(dashboard_routes.router, ctx, svc) as client:
        response = client.get("/api/v1/dashboard/detail", params={"slug": "sales_overview"})

    assert response.status_code == 404
    svc.dashboard.get_detail.assert_not_awaited()


def test_dashboard_query_requires_module_dashboard_query(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = MagicMock()
    svc.dashboard.run_query = AsyncMock(
        return_value=Result[SqlQueryResultEnvelope](success=True, data=_dashboard_query_result())
    )
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.dashboard.view"})

    with _client(dashboard_routes.router, ctx, svc) as client:
        response = client.post(
            "/api/v1/dashboard/query",
            json={"dashboard_slug": "sales_overview", "query_slug": "summary", "params": {}},
        )

    assert response.status_code == 403
    svc.dashboard.run_query.assert_not_awaited()


def test_dashboard_query_allows_module_dashboard_query(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = MagicMock()
    svc.agent_config.project_root = "/tmp/project"
    svc.dashboard.run_query = AsyncMock(
        return_value=Result[SqlQueryResultEnvelope](success=True, data=_dashboard_query_result())
    )
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.dashboard.query"})

    with _client(dashboard_routes.router, ctx, svc) as client:
        response = client.post(
            "/api/v1/dashboard/query",
            json={"dashboard_slug": "sales_overview", "query_slug": "summary", "params": {"region": "east"}},
        )

    assert response.status_code == 200
    assert response.json()["success"] is True
    svc.dashboard.run_query.assert_awaited_once()
    assert svc.dashboard.run_query.await_args.kwargs["dashboard_slug"] == "sales_overview"
    assert svc.dashboard.run_query.await_args.kwargs["query_slug"] == "summary"
    assert svc.dashboard.run_query.await_args.kwargs["params"] == {"region": "east"}


def test_dashboard_query_rejects_artifact_acl_denial(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = MagicMock()
    svc.agent_config.project_root = "/tmp/project"
    svc.dashboard.run_query = AsyncMock(
        return_value=Result[SqlQueryResultEnvelope](success=True, data=_dashboard_query_result())
    )
    ctx = AppContext(
        user_id="u1",
        project_id="proj",
        permissions={"module.dashboard.query"},
        principal={"artifact_acl": {"dashboard": ["other_dashboard"]}},
    )

    with _client(dashboard_routes.router, ctx, svc) as client:
        response = client.post(
            "/api/v1/dashboard/query",
            json={"dashboard_slug": "sales_overview", "query_slug": "summary", "params": {}},
        )

    assert response.status_code == 404
    svc.dashboard.run_query.assert_not_awaited()


def test_sql_execute_routes_require_module_sql_executor(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = MagicMock()
    svc.cli.execute_sql = AsyncMock(
        return_value=Result[ExecuteSQLData](
            success=True,
            data=ExecuteSQLData(
                execute_task_id="task-1",
                sql_query="SELECT 1",
                result_format="json",
                execution_time=0.01,
                executed_at="2026-06-27T00:00:00Z",
            ),
        )
    )
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.chat"})

    with _client(cli_routes.router, ctx, svc) as client:
        response = client.post("/api/v1/sql/execute", json={"sql_query": "SELECT 1", "result_format": "json"})

    assert response.status_code == 403
    svc.cli.execute_sql.assert_not_awaited()


def test_sql_execute_routes_allow_module_sql_executor(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = MagicMock()
    svc.cli.execute_sql = AsyncMock(
        return_value=Result[ExecuteSQLData](
            success=True,
            data=ExecuteSQLData(
                execute_task_id="task-1",
                sql_query="SELECT 1",
                result_format="json",
                execution_time=0.01,
                executed_at="2026-06-27T00:00:00Z",
            ),
        )
    )
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.sql_executor"})

    with _client(cli_routes.router, ctx, svc) as client:
        response = client.post("/api/v1/sql/execute", json={"sql_query": "SELECT 1", "result_format": "json"})

    assert response.status_code == 200
    assert response.json()["success"] is True
    svc.cli.execute_sql.assert_awaited_once()
    assert svc.cli.execute_sql.await_args.kwargs == {"user_id": "u1"}


def test_sql_stop_execute_routes_require_module_sql_executor(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = MagicMock()
    svc.cli.stop_execute_sql = AsyncMock(
        return_value=Result[StopExecuteSQLData](
            success=True,
            data=StopExecuteSQLData(execute_task_id="task-1", stopped=True),
        )
    )
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.chat"})

    with _client(cli_routes.router, ctx, svc) as client:
        response = client.post("/api/v1/sql/stop_execute", json={"execute_task_id": "task-1"})

    assert response.status_code == 403
    svc.cli.stop_execute_sql.assert_not_awaited()


def test_sql_stop_execute_routes_pass_user_owner_and_hide_other_user_task(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = MagicMock()
    cli = CLIService(agent_config=None, chat_service=None)
    svc.cli = cli

    task = MagicMock()
    cli._sql_tasks["alice-task"] = _SQLTaskRecord(task=task, owner_user_id="alice")
    ctx = AppContext(user_id="bob", project_id="proj", permissions={"module.sql_executor"})

    with _client(cli_routes.router, ctx, svc) as client:
        response = client.post("/api/v1/sql/stop_execute", json={"execute_task_id": "alice-task"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is False
    assert payload["data"]["stopped"] is False
    assert "No running SQL execution" in payload["errorMessage"]
    task.cancel.assert_not_called()


@pytest.mark.parametrize("context_type", ["tables", "catalogs"])
def test_cli_context_metadata_requires_datasource_catalog(monkeypatch, context_type):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = MagicMock()
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.chat"})

    with _client(cli_routes.router, ctx, svc) as client:
        response = client.post(f"/api/v1/context/{context_type}", json={"context_type": context_type})

    assert response.status_code == 403
    svc.cli.execute_context.assert_not_called()


@pytest.mark.parametrize("command", ["databases", "tables"])
def test_cli_internal_metadata_requires_datasource_catalog(monkeypatch, command):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = MagicMock()
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.chat"})

    with _client(cli_routes.router, ctx, svc) as client:
        response = client.post(f"/api/v1/internal/{command}", json={"command": command, "args": ""})

    assert response.status_code == 403
    svc.cli.execute_internal_command.assert_not_called()
