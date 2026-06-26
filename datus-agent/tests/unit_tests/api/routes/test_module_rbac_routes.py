# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.

"""HTTP-level module RBAC coverage for enterprise route dependencies."""

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
from datus.api.models.database_models import DatabasesData, ListDatabasesData
from datus.api.models.report_models import ReportDetail
from datus.api.routes import chat_routes, cli_routes, dashboard_routes, database_routes, report_routes
from datus.api.services.cli_service import CLIService, _SQLTaskRecord
from datus.schemas.artifact_manifest import ArtifactManifest


def _enterprise_extensions() -> EnterpriseExtensions:
    return EnterpriseExtensions(
        enabled=True,
        authorization_provider=LocalAuthorizationProvider(),
        config_projector=PassthroughConfigProjector(),
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
