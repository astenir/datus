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
from datus.api.models.database_models import DatabasesData, ListDatabasesData
from datus.api.routes import chat_routes, cli_routes, database_routes
from datus.api.services.cli_service import CLIService, _SQLTaskRecord


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
