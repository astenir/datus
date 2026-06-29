# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.

"""HTTP-level module RBAC coverage for enterprise route dependencies."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.enterprise.defaults import (
    InMemoryEnterpriseQuotaStore,
    InMemorySessionOwnerStore,
    LocalAuthorizationProvider,
    NoopAuditSink,
    PassthroughConfigProjector,
)
from datus.api.enterprise.loader import EnterpriseExtensions
from datus.api.models.base_models import Result
from datus.api.models.cli_models import ChatSessionData, ExecuteContextData, ExecuteSQLData, StopExecuteSQLData
from datus.api.models.dashboard_models import DashboardDetail, SqlQueryResultEnvelope
from datus.api.models.database_models import DatabaseInfo, DatabasesData, ListDatabasesData
from datus.api.models.report_models import ReportDetail
from datus.api.routes import (
    chat_routes,
    cli_routes,
    dashboard_routes,
    database_routes,
    report_routes,
    subject_routes,
    table_routes,
)
from datus.api.services.cli_service import CLIService, _SQLTaskRecord
from datus.api.services.dashboard_service import DashboardService
from datus.schemas.artifact_manifest import ArtifactManifest
from datus_enterprise.api import agent_routes as enterprise_agent_routes
from datus_enterprise.config_projection import DatasourceGrantConfigProjector

_UNSET = object()


class CollectingAuditSink:
    def __init__(self):
        self.events = []

    async def write(self, event):
        self.events.append(event)


def _enterprise_extensions(config_projector=None, audit_sink=None, quota_store=_UNSET) -> EnterpriseExtensions:
    if quota_store is _UNSET:
        quota_store = InMemoryEnterpriseQuotaStore()
    return EnterpriseExtensions(
        enabled=True,
        authorization_provider=LocalAuthorizationProvider(),
        config_projector=config_projector or PassthroughConfigProjector(),
        session_owner_store=InMemorySessionOwnerStore(),
        audit_sink=audit_sink or NoopAuditSink(),
        quota_store=quota_store,
    )


def _client(router, ctx: AppContext, svc: MagicMock):
    app = FastAPI()
    app.include_router(router)

    async def override_service(request: Request):
        request.state.app_context = ctx
        return svc

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = override_service
    app.dependency_overrides[deps.get_request_app_context] = override_context
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


def _write_dashboard_query_fixture(project_files_root: Path, *, datasource: str) -> None:
    queries_dir = project_files_root / "dashboards" / "sales_overview" / "queries"
    queries_dir.mkdir(parents=True)
    (queries_dir / "summary.sql.j2").write_text("SELECT 1 AS value;\n", encoding="utf-8")
    (queries_dir / "summary.params.json").write_text(
        json.dumps(
            {
                "slug": "summary",
                "description": "Summary",
                "datasource": datasource,
                "params": [],
                "columns": [{"name": "value", "type": "number"}],
                "sample_params": {},
                "sample_row_count": 1,
                "saved_at": "2026-06-27T00:00:00Z",
            }
        ),
        encoding="utf-8",
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


def test_chat_rbac_denial_does_not_resolve_datus_service(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.datasource_catalog"})
    app = FastAPI()
    app.include_router(chat_routes.router)

    async def reject_service(request: Request):
        raise AssertionError("RBAC denial resolved DatusService")

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = reject_service
    app.dependency_overrides[deps.get_request_app_context] = override_context

    with TestClient(app, raise_server_exceptions=False) as client:
        responses = [
            client.post("/api/v1/chat/stream", json={"message": "hello"}),
            client.post(
                "/api/v1/chat/feedback",
                json={"source_session_id": "s1", "reaction_emoji": "thumbsup", "reference_msg": "ok"},
            ),
            client.post("/api/v1/chat/resume", json={"session_id": "s1"}),
            client.post("/api/v1/chat/stop", json={"session_id": "s1"}),
            client.post("/api/v1/chat/sessions/s1/compact"),
            client.get("/api/v1/chat/sessions"),
            client.delete("/api/v1/chat/sessions/s1"),
            client.get("/api/v1/chat/history", params={"session_id": "s1"}),
            client.post(
                "/api/v1/chat/user_interaction",
                json={"session_id": "s1", "interaction_key": "k1", "input": [["1"]]},
            ),
            client.post("/api/v1/chat/insert", json={"session_id": "s1", "message": "hello"}),
            client.post(
                "/api/v1/chat/tool_result",
                json={"session_id": "s1", "call_tool_id": "tc_1", "tool_result": {"success": 1, "result": {}}},
            ),
        ]

    assert [response.status_code for response in responses] == [403] * len(responses)


@pytest.mark.parametrize(
    ("path", "permissions"),
    [
        ("/api/v1/agents/sales_sql/tools", {"module.datasource_catalog"}),
        ("/api/v1/admin/agents/tools", {"module.chat"}),
        ("/api/v1/admin/agents/tool-reference", {"module.chat"}),
    ],
)
def test_enterprise_agent_tools_rbac_denial_does_not_resolve_datus_service(monkeypatch, path, permissions):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    ctx = AppContext(user_id="u1", project_id="proj", permissions=permissions)
    app = FastAPI()
    app.include_router(enterprise_agent_routes.router)

    async def reject_service(request: Request):
        raise AssertionError("RBAC denial resolved DatusService")

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = reject_service
    app.dependency_overrides[deps.get_request_app_context] = override_context

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(path)

    assert response.status_code == 403


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/chat/stream",
        "/api/v1/chat/feedback",
        "/api/v1/chat/resume",
        "/api/v1/chat/stop",
        "/api/v1/chat/user_interaction",
        "/api/v1/chat/insert",
        "/api/v1/chat/tool_result",
    ],
)
def test_chat_invalid_body_does_not_resolve_datus_service(monkeypatch, path):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.chat"})
    app = FastAPI()
    app.include_router(chat_routes.router)

    async def reject_service(request: Request):
        raise AssertionError("Invalid body resolved DatusService")

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = reject_service
    app.dependency_overrides[deps.get_request_app_context] = override_context

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(path, json=[])

    assert response.status_code == 422


def test_chat_routes_allow_module_chat(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = MagicMock()
    svc.chat.list_sessions_async = AsyncMock(return_value=Result[ChatSessionData](success=True, data=ChatSessionData()))
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.chat"})

    with _client(chat_routes.router, ctx, svc) as client:
        response = client.get("/api/v1/chat/sessions")

    assert response.status_code == 200
    assert response.json()["success"] is True
    svc.chat.list_sessions_async.assert_awaited_once_with(user_id="u1", subagent_id=None)


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


def test_chat_stream_returns_unavailable_without_quota_store(monkeypatch):
    audit_sink = CollectingAuditSink()
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions(audit_sink=audit_sink, quota_store=None))
    svc = MagicMock()
    svc.agent_config = _datasource_agent_config()
    svc.chat.stream_chat = MagicMock(side_effect=AssertionError("upstream invoked"))
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.chat"})

    with _client(chat_routes.router, ctx, svc) as client:
        response = client.post("/api/v1/chat/stream", json={"message": "hello"})

    assert response.status_code == 200
    assert "event: error" in response.text
    assert "QUOTA_STORE_UNAVAILABLE" in response.text
    svc.chat.stream_chat.assert_not_called()
    event = next(event for event in audit_sink.events if event.action == "quota.consume")
    assert event.resource_type == "chat"
    assert event.resource_id is None
    assert event.decision == "deny"
    assert event.reason == "quota store unavailable"
    assert event.metadata["quota_resource"] == "chat.stream"


def test_chat_stream_rejects_quota_exceeded_before_task_start(monkeypatch):
    quota_store = InMemoryEnterpriseQuotaStore()
    asyncio.run(
        quota_store.put_quota(
            subject_type="user",
            subject_id="u1",
            resource="chat.stream",
            limit=1,
            window_seconds=3600,
        )
    )
    asyncio.run(
        quota_store.consume_quota(
            subjects=[{"subject_type": "user", "subject_id": "u1"}],
            resource="chat.stream",
        )
    )
    audit_sink = CollectingAuditSink()
    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        _enterprise_extensions(audit_sink=audit_sink, quota_store=quota_store),
    )
    svc = MagicMock()
    svc.agent_config = _datasource_agent_config()
    svc.chat.stream_chat = MagicMock(side_effect=AssertionError("upstream invoked"))
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.chat"})

    with _client(chat_routes.router, ctx, svc) as client:
        response = client.post("/api/v1/chat/stream", json={"message": "hello"})

    assert response.status_code == 200
    assert "event: error" in response.text
    assert "QUOTA_EXCEEDED" in response.text
    svc.chat.stream_chat.assert_not_called()
    event = next(event for event in audit_sink.events if event.action == "quota.consume")
    assert event.resource_type == "chat"
    assert event.resource_id is None
    assert event.decision == "deny"
    assert event.reason == "quota exceeded"
    assert event.metadata["resource"] == "chat.stream"
    assert event.metadata["used"] == 1


def test_chat_stream_consumes_quota_before_task_start(monkeypatch):
    async def empty_stream(*_args, **_kwargs):
        if False:
            yield

    quota_store = InMemoryEnterpriseQuotaStore()
    asyncio.run(
        quota_store.put_quota(
            subject_type="user",
            subject_id="u1",
            resource="chat.stream",
            limit=2,
            window_seconds=3600,
        )
    )
    audit_sink = CollectingAuditSink()
    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        _enterprise_extensions(audit_sink=audit_sink, quota_store=quota_store),
    )
    svc = MagicMock()
    svc.agent_config = _datasource_agent_config()
    svc.chat.stream_chat = MagicMock(return_value=empty_stream())
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.chat"})

    with _client(chat_routes.router, ctx, svc) as client:
        response = client.post("/api/v1/chat/stream", json={"message": "hello"})

    usage = asyncio.run(quota_store.list_usage(subject_type="user", subject_id="u1", resource="chat.stream"))

    assert response.status_code == 200
    assert usage[0]["used"] == 1
    event = next(event for event in audit_sink.events if event.action == "quota.consume")
    assert event.decision == "allow"
    assert event.metadata["quota_resource"] == "chat.stream"
    svc.chat.stream_chat.assert_called_once()


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


def test_catalog_and_table_rbac_denial_does_not_resolve_datus_service(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.chat"})

    async def reject_service(request: Request):
        raise AssertionError("RBAC denial resolved DatusService")

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    catalog_app = FastAPI()
    catalog_app.include_router(database_routes.router)
    catalog_app.dependency_overrides[deps.get_datus_service] = reject_service
    catalog_app.dependency_overrides[deps.get_request_app_context] = override_context

    table_app = FastAPI()
    table_app.include_router(table_routes.router)
    table_app.dependency_overrides[deps.get_datus_service] = reject_service
    table_app.dependency_overrides[deps.get_request_app_context] = override_context

    with TestClient(catalog_app, raise_server_exceptions=False) as client:
        catalog_response = client.get("/api/v1/catalog/list")
    with TestClient(table_app, raise_server_exceptions=False) as client:
        table_response = client.get("/api/v1/table/detail", params={"table": "public.accounts"})
        semantic_read_response = client.get("/api/v1/semantic_model", params={"table": "public.accounts"})
        semantic_save_response = client.post(
            "/api/v1/semantic_model",
            json={"table": "public.accounts", "yaml": "semantic_model:\n  name: accounts\n"},
        )
        semantic_validate_response = client.post(
            "/api/v1/semantic_model/validate",
            json={"table": "public.accounts", "yaml": "semantic_model:\n  name: accounts\n"},
        )

    assert catalog_response.status_code == 403
    assert table_response.status_code == 403
    assert semantic_read_response.status_code == 403
    assert semantic_save_response.status_code == 403
    assert semantic_validate_response.status_code == 403


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


def test_datasource_catalog_returns_bad_request_for_unknown_datasource(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = MagicMock()
    svc.agent_config = _datasource_agent_config(current_datasource="finance")
    svc.datasource.current_datasource = "finance"
    svc.datasource.list_databases = MagicMock()
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.datasource_catalog"})

    with _client(database_routes.router, ctx, svc) as client:
        response = client.get("/api/v1/catalog/list", params={"datasource_id": "missing"})

    assert response.status_code == 400
    assert "Datasource 'missing' not found" in response.json()["detail"]
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


def test_datasource_catalog_table_scope_accepts_catalog_database_table_grant(monkeypatch):
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
                    uri="starrocks://warehouse",
                    type="starrocks",
                    current=True,
                    catalog_name="prod",
                    connection_status="connected",
                    tables_count=2,
                    tables=["orders", "payroll"],
                ),
            ],
            total_count=1,
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
                "tables": ["prod.finance.orders"],
            }
        },
    )

    with _client(database_routes.router, ctx, svc) as client:
        response = client.get("/api/v1/catalog/list")

    assert response.status_code == 200
    databases = response.json()["data"]["databases"]
    assert len(databases) == 1
    assert databases[0]["tables"] == ["orders"]
    assert databases[0]["tables_count"] == 1


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


def test_artifact_rbac_denial_does_not_resolve_datus_service(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.chat"})

    async def reject_service(request: Request):
        raise AssertionError("RBAC denial resolved DatusService")

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    report_app = FastAPI()
    report_app.include_router(report_routes.router)
    report_app.dependency_overrides[deps.get_datus_service] = reject_service
    report_app.dependency_overrides[deps.get_request_app_context] = override_context

    dashboard_app = FastAPI()
    dashboard_app.include_router(dashboard_routes.router)
    dashboard_app.dependency_overrides[deps.get_datus_service] = reject_service
    dashboard_app.dependency_overrides[deps.get_request_app_context] = override_context

    with TestClient(report_app, raise_server_exceptions=False) as client:
        report_response = client.get("/api/v1/report/detail", params={"slug": "sales_overview"})
    with TestClient(dashboard_app, raise_server_exceptions=False) as client:
        dashboard_detail_response = client.get("/api/v1/dashboard/detail", params={"slug": "sales_overview"})
        dashboard_query_response = client.post(
            "/api/v1/dashboard/query",
            json={"dashboard_slug": "sales_overview", "query_slug": "summary", "params": {}},
        )

    assert report_response.status_code == 403
    assert dashboard_detail_response.status_code == 403
    assert dashboard_query_response.status_code == 403


def test_dashboard_query_allows_module_dashboard_query(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = MagicMock()
    svc.agent_config = _datasource_agent_config()
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
    assert svc.dashboard.run_query.await_args.kwargs["agent_config"].current_datasource == "default"
    assert callable(svc.dashboard.run_query.await_args.kwargs["agent_config_projector"])


def test_dashboard_query_returns_unavailable_without_quota_store(monkeypatch, tmp_path: Path):
    audit_sink = CollectingAuditSink()
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions(audit_sink=audit_sink, quota_store=None))
    _write_dashboard_query_fixture(tmp_path, datasource="default")
    agent_config = _datasource_agent_config()
    agent_config.project_root = str(tmp_path)
    svc = SimpleNamespace(agent_config=agent_config, dashboard=DashboardService(agent_config=agent_config))
    db_calls = []

    class _UnexpectedDBFuncTool:
        def __init__(self, *, agent_config, sub_agent_name):
            db_calls.append((agent_config, sub_agent_name))

    import datus.tools.func_tool as func_tool_mod

    monkeypatch.setattr(func_tool_mod, "DBFuncTool", _UnexpectedDBFuncTool)
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.dashboard.query"})

    with _client(dashboard_routes.router, ctx, svc) as client:
        response = client.post(
            "/api/v1/dashboard/query",
            json={"dashboard_slug": "sales_overview", "query_slug": "summary", "params": {}},
        )

    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["errorCode"] == "QUOTA_STORE_UNAVAILABLE"
    assert db_calls == []
    event = next(event for event in audit_sink.events if event.action == "quota.consume")
    assert event.action == "quota.consume"
    assert event.resource_type == "dashboard"
    assert event.resource_id == "sales_overview"
    assert event.decision == "deny"
    assert event.reason == "quota store unavailable"
    assert audit_sink.events[-1].action == "dashboard.query"


def test_dashboard_query_rejects_quota_exceeded_before_execution(monkeypatch, tmp_path: Path):
    quota_store = InMemoryEnterpriseQuotaStore()
    asyncio.run(
        quota_store.put_quota(
            subject_type="user",
            subject_id="u1",
            resource="dashboard.query",
            limit=1,
            window_seconds=3600,
        )
    )
    asyncio.run(
        quota_store.consume_quota(
            subjects=[{"subject_type": "user", "subject_id": "u1"}],
            resource="dashboard.query",
        )
    )
    audit_sink = CollectingAuditSink()
    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        _enterprise_extensions(audit_sink=audit_sink, quota_store=quota_store),
    )
    _write_dashboard_query_fixture(tmp_path, datasource="default")
    agent_config = _datasource_agent_config()
    agent_config.project_root = str(tmp_path)
    svc = SimpleNamespace(agent_config=agent_config, dashboard=DashboardService(agent_config=agent_config))
    db_calls = []

    class _UnexpectedDBFuncTool:
        def __init__(self, *, agent_config, sub_agent_name):
            db_calls.append((agent_config, sub_agent_name))

    import datus.tools.func_tool as func_tool_mod

    monkeypatch.setattr(func_tool_mod, "DBFuncTool", _UnexpectedDBFuncTool)
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.dashboard.query"})

    with _client(dashboard_routes.router, ctx, svc) as client:
        response = client.post(
            "/api/v1/dashboard/query",
            json={"dashboard_slug": "sales_overview", "query_slug": "summary", "params": {}},
        )

    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["errorCode"] == "QUOTA_EXCEEDED"
    assert db_calls == []
    event = next(event for event in audit_sink.events if event.action == "quota.consume")
    assert event.action == "quota.consume"
    assert event.decision == "deny"
    assert event.reason == "quota exceeded"
    assert event.metadata["resource"] == "dashboard.query"
    assert event.metadata["used"] == 1
    assert audit_sink.events[-1].action == "dashboard.query"


def test_dashboard_query_consumes_quota_before_successful_execution(monkeypatch, tmp_path: Path):
    quota_store = InMemoryEnterpriseQuotaStore()
    asyncio.run(
        quota_store.put_quota(
            subject_type="user",
            subject_id="u1",
            resource="dashboard.query",
            limit=2,
            window_seconds=3600,
        )
    )
    audit_sink = CollectingAuditSink()
    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        _enterprise_extensions(audit_sink=audit_sink, quota_store=quota_store),
    )
    _write_dashboard_query_fixture(tmp_path, datasource="default")
    agent_config = _datasource_agent_config()
    agent_config.project_root = str(tmp_path)
    svc = SimpleNamespace(agent_config=agent_config, dashboard=DashboardService(agent_config=agent_config))
    executed_sql = []

    class _Connector:
        def execute_query(self, sql, result_format):
            executed_sql.append((sql, result_format))
            return SimpleNamespace(success=True, sql_return=[{"value": 1}])

    class _DBFuncTool:
        def __init__(self, *, agent_config, sub_agent_name):
            self.agent_config = agent_config
            self.sub_agent_name = sub_agent_name

        def _get_connector(self, datasource):
            return _Connector()

    import datus.tools.func_tool as func_tool_mod

    monkeypatch.setattr(func_tool_mod, "DBFuncTool", _DBFuncTool)
    monkeypatch.setattr(CLIService, "_authorize_read_sql", staticmethod(lambda sql, connector, agent_config: sql))
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.dashboard.query"})

    with _client(dashboard_routes.router, ctx, svc) as client:
        response = client.post(
            "/api/v1/dashboard/query",
            json={"dashboard_slug": "sales_overview", "query_slug": "summary", "params": {}},
        )

    usage = asyncio.run(quota_store.list_usage(subject_type="user", subject_id="u1", resource="dashboard.query"))

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert usage[0]["used"] == 1
    assert [event.action for event in audit_sink.events[-2:]] == ["quota.consume", "dashboard.query"]
    assert audit_sink.events[-2].decision == "allow"
    assert [(sql.strip(), result_format) for sql, result_format in executed_sql] == [("SELECT 1 AS value;", "list")]


def test_dashboard_query_invalid_params_do_not_consume_quota(monkeypatch, tmp_path: Path):
    quota_store = InMemoryEnterpriseQuotaStore()
    asyncio.run(
        quota_store.put_quota(
            subject_type="user",
            subject_id="u1",
            resource="dashboard.query",
            limit=2,
            window_seconds=3600,
        )
    )
    audit_sink = CollectingAuditSink()
    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        _enterprise_extensions(audit_sink=audit_sink, quota_store=quota_store),
    )
    _write_dashboard_query_fixture(tmp_path, datasource="default")
    agent_config = _datasource_agent_config()
    agent_config.project_root = str(tmp_path)
    svc = SimpleNamespace(agent_config=agent_config, dashboard=DashboardService(agent_config=agent_config))
    db_calls = []

    class _UnexpectedDBFuncTool:
        def __init__(self, *, agent_config, sub_agent_name):
            db_calls.append((agent_config, sub_agent_name))

    import datus.tools.func_tool as func_tool_mod

    monkeypatch.setattr(func_tool_mod, "DBFuncTool", _UnexpectedDBFuncTool)
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.dashboard.query"})

    with _client(dashboard_routes.router, ctx, svc) as client:
        response = client.post(
            "/api/v1/dashboard/query",
            json={"dashboard_slug": "sales_overview", "query_slug": "summary", "params": {"unknown": "x"}},
        )

    usage = asyncio.run(quota_store.list_usage(subject_type="user", subject_id="u1", resource="dashboard.query"))

    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["errorCode"] == "INVALID_PARAMS"
    assert usage == []
    assert db_calls == []
    assert "quota.consume" not in [event.action for event in audit_sink.events]
    assert audit_sink.events[-1].action == "dashboard.query"


def test_dashboard_query_audits_sanitized_failure(monkeypatch):
    audit_sink = CollectingAuditSink()
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions(audit_sink=audit_sink))
    svc = MagicMock()
    svc.agent_config = _datasource_agent_config()
    svc.agent_config.project_root = "/tmp/project"
    svc.dashboard.run_query = AsyncMock(
        return_value=Result[SqlQueryResultEnvelope](
            success=False,
            errorCode="QUERY_EXECUTION_FAILED",
            errorMessage="policy backend down at postgres://secret-host",
        )
    )
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.dashboard.query"})

    with _client(dashboard_routes.router, ctx, svc) as client:
        response = client.post(
            "/api/v1/dashboard/query",
            json={"dashboard_slug": "sales_overview", "query_slug": "summary", "params": {"region": "east"}},
        )

    assert response.status_code == 200
    event = audit_sink.events[-1]
    assert event.user_id == "u1"
    assert event.action == "dashboard.query"
    assert event.resource_type == "dashboard"
    assert event.resource_id == "sales_overview"
    assert event.decision == "deny"
    assert event.reason == "QUERY_EXECUTION_FAILED"
    assert event.metadata == {
        "query_slug": "summary",
        "datasource": "default",
        "error_code": "QUERY_EXECUTION_FAILED",
    }


def test_dashboard_query_audits_template_datasource_on_failure(monkeypatch, tmp_path: Path):
    audit_sink = CollectingAuditSink()
    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        _enterprise_extensions(DatasourceGrantConfigProjector(), audit_sink=audit_sink),
    )
    _write_dashboard_query_fixture(tmp_path, datasource="hr")
    agent_config = _datasource_agent_config(current_datasource="finance")
    agent_config.project_root = str(tmp_path)
    svc = SimpleNamespace(
        agent_config=agent_config,
        dashboard=DashboardService(agent_config=agent_config),
    )

    class _FailingDBFuncTool:
        def __init__(self, *, agent_config, sub_agent_name):
            self.agent_config = agent_config
            self.sub_agent_name = sub_agent_name

        def _get_connector(self, datasource):
            raise RuntimeError(f"connector unavailable for {datasource}")

    import datus.tools.func_tool as func_tool_mod

    monkeypatch.setattr(func_tool_mod, "DBFuncTool", _FailingDBFuncTool)
    ctx = AppContext(
        user_id="u1",
        project_id="proj",
        permissions={"module.dashboard.query"},
        datasource_grants={
            "finance": {"effect": "allow", "allow_sql": True},
            "hr": {"effect": "allow", "allow_sql": True},
        },
    )

    with _client(dashboard_routes.router, ctx, svc) as client:
        response = client.post(
            "/api/v1/dashboard/query",
            json={"dashboard_slug": "sales_overview", "query_slug": "summary", "params": {}},
        )

    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["errorCode"] == "DATASOURCE_UNAVAILABLE"
    event = audit_sink.events[-1]
    assert event.action == "dashboard.query"
    assert event.resource_id == "sales_overview"
    assert event.decision == "deny"
    assert event.reason == "DATASOURCE_UNAVAILABLE"
    assert event.metadata == {
        "query_slug": "summary",
        "datasource": "hr",
        "error_code": "DATASOURCE_UNAVAILABLE",
    }


def test_dashboard_query_uses_projected_datasource_config(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions(DatasourceGrantConfigProjector()))
    svc = MagicMock()
    svc.agent_config = _datasource_agent_config(current_datasource="hr")
    svc.agent_config.project_root = "/tmp/project"
    svc.dashboard.run_query = AsyncMock(
        return_value=Result[SqlQueryResultEnvelope](success=True, data=_dashboard_query_result())
    )
    ctx = AppContext(
        user_id="u1",
        project_id="proj",
        permissions={"module.dashboard.query"},
        datasource_grants={"finance": {"effect": "allow", "allow_sql": True}},
    )

    with _client(dashboard_routes.router, ctx, svc) as client:
        response = client.post(
            "/api/v1/dashboard/query",
            json={"dashboard_slug": "sales_overview", "query_slug": "summary", "params": {}},
        )

    assert response.status_code == 200
    projected_config = svc.dashboard.run_query.await_args.kwargs["agent_config"]
    assert projected_config.current_datasource == "finance"
    assert set(projected_config.services.datasources) == {"finance"}
    assert projected_config.principal["datasource"] == "finance"
    assert callable(svc.dashboard.run_query.await_args.kwargs["agent_config_projector"])


def test_dashboard_query_rejects_missing_datasource_grant(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions(DatasourceGrantConfigProjector()))
    svc = MagicMock()
    svc.agent_config = _datasource_agent_config(current_datasource="finance")
    svc.agent_config.project_root = "/tmp/project"
    svc.dashboard.run_query = AsyncMock(
        return_value=Result[SqlQueryResultEnvelope](success=True, data=_dashboard_query_result())
    )
    ctx = AppContext(
        user_id="u1",
        project_id="proj",
        permissions={"module.dashboard.query"},
        datasource_grants={},
    )

    with _client(dashboard_routes.router, ctx, svc) as client:
        response = client.post(
            "/api/v1/dashboard/query",
            json={"dashboard_slug": "sales_overview", "query_slug": "summary", "params": {}},
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "No datasource grant available."
    svc.dashboard.run_query.assert_not_awaited()


def test_dashboard_query_rejects_template_datasource_without_grant(monkeypatch, tmp_path: Path):
    quota_store = InMemoryEnterpriseQuotaStore()
    asyncio.run(
        quota_store.put_quota(
            subject_type="user",
            subject_id="u1",
            resource="dashboard.query",
            limit=2,
            window_seconds=3600,
        )
    )
    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        _enterprise_extensions(DatasourceGrantConfigProjector(), quota_store=quota_store),
    )
    _write_dashboard_query_fixture(tmp_path, datasource="hr")
    agent_config = _datasource_agent_config(current_datasource="finance")
    agent_config.project_root = str(tmp_path)
    svc = SimpleNamespace(
        agent_config=agent_config,
        dashboard=DashboardService(agent_config=agent_config),
    )
    db_calls = []

    class _UnexpectedDBFuncTool:
        def __init__(self, *, agent_config, sub_agent_name):
            db_calls.append((agent_config, sub_agent_name))

    import datus.tools.func_tool as func_tool_mod

    monkeypatch.setattr(func_tool_mod, "DBFuncTool", _UnexpectedDBFuncTool)
    ctx = AppContext(
        user_id="u1",
        project_id="proj",
        permissions={"module.dashboard.query"},
        datasource_grants={"finance": {"effect": "allow", "allow_sql": True}},
    )

    with _client(dashboard_routes.router, ctx, svc) as client:
        response = client.post(
            "/api/v1/dashboard/query",
            json={"dashboard_slug": "sales_overview", "query_slug": "summary", "params": {}},
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "Datasource 'hr' is not authorized for this request."
    usage = asyncio.run(quota_store.list_usage(subject_type="user", subject_id="u1", resource="dashboard.query"))
    assert usage == []
    assert db_calls == []


def test_dashboard_query_returns_result_when_template_datasource_is_missing(monkeypatch, tmp_path: Path):
    quota_store = InMemoryEnterpriseQuotaStore()
    asyncio.run(
        quota_store.put_quota(
            subject_type="user",
            subject_id="u1",
            resource="dashboard.query",
            limit=2,
            window_seconds=3600,
        )
    )
    audit_sink = CollectingAuditSink()
    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        _enterprise_extensions(
            DatasourceGrantConfigProjector(),
            audit_sink=audit_sink,
            quota_store=quota_store,
        ),
    )
    _write_dashboard_query_fixture(tmp_path, datasource="missing")
    agent_config = _datasource_agent_config(current_datasource="finance")
    agent_config.project_root = str(tmp_path)
    svc = SimpleNamespace(
        agent_config=agent_config,
        dashboard=DashboardService(agent_config=agent_config),
    )
    db_calls = []

    class _UnexpectedDBFuncTool:
        def __init__(self, *, agent_config, sub_agent_name):
            db_calls.append((agent_config, sub_agent_name))

    import datus.tools.func_tool as func_tool_mod

    monkeypatch.setattr(func_tool_mod, "DBFuncTool", _UnexpectedDBFuncTool)
    ctx = AppContext(
        user_id="u1",
        project_id="proj",
        permissions={"module.dashboard.query"},
        datasource_grants={"finance": {"effect": "allow", "allow_sql": True}},
    )

    with _client(dashboard_routes.router, ctx, svc) as client:
        response = client.post(
            "/api/v1/dashboard/query",
            json={"dashboard_slug": "sales_overview", "query_slug": "summary", "params": {}},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["errorCode"] == "COMMON_FIELD_INVALID"
    assert "Datasource 'missing' not found" in body["errorMessage"]
    usage = asyncio.run(quota_store.list_usage(subject_type="user", subject_id="u1", resource="dashboard.query"))
    assert usage == []
    assert db_calls == []

    event = audit_sink.events[-1]
    assert event.action == "dashboard.query"
    assert event.resource_type == "dashboard"
    assert event.resource_id == "sales_overview"
    assert event.decision == "deny"
    assert event.reason == "COMMON_FIELD_INVALID"
    assert event.metadata == {
        "query_slug": "summary",
        "datasource": "missing",
        "error_code": "COMMON_FIELD_INVALID",
    }


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


def test_sql_executor_rbac_denial_does_not_resolve_datus_service(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.chat"})
    app = FastAPI()
    app.include_router(cli_routes.router)

    async def reject_service(request: Request):
        raise AssertionError("RBAC denial resolved DatusService")

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = reject_service
    app.dependency_overrides[deps.get_request_app_context] = override_context

    with TestClient(app, raise_server_exceptions=False) as client:
        execute_response = client.post(
            "/api/v1/sql/execute",
            json={"sql_query": "SELECT 1", "result_format": "json"},
        )
        stop_response = client.post("/api/v1/sql/stop_execute", json={"execute_task_id": "task-1"})

    assert execute_response.status_code == 403
    assert stop_response.status_code == 403


@pytest.mark.parametrize(
    ("path", "permissions"),
    [
        ("/api/v1/sql/execute", {"module.sql_executor"}),
        ("/api/v1/sql/stop_execute", {"module.sql_executor"}),
        ("/api/v1/context/tables", {"module.datasource_catalog"}),
        ("/api/v1/internal/tables", {"module.datasource_catalog"}),
    ],
)
def test_cli_invalid_body_does_not_resolve_datus_service(monkeypatch, path, permissions):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    ctx = AppContext(user_id="u1", project_id="proj", permissions=permissions)
    app = FastAPI()
    app.include_router(cli_routes.router)

    async def reject_service(request: Request):
        raise AssertionError("Invalid body resolved DatusService")

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = reject_service
    app.dependency_overrides[deps.get_request_app_context] = override_context

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(path, json=[])

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("router", "path", "json_body", "permissions", "expected_action"),
    [
        (
            cli_routes.router,
            "/api/v1/sql/execute",
            {"sql_query": "SELECT 1", "result_format": "json"},
            {"module.chat"},
            "module.sql_executor",
        ),
        (
            dashboard_routes.router,
            "/api/v1/dashboard/query",
            {"dashboard_slug": "sales_overview", "query_slug": "summary", "params": {}},
            {"module.chat"},
            "module.dashboard.query",
        ),
        (
            chat_routes.router,
            "/api/v1/chat/stream",
            {"message": "hello"},
            {"module.sql_executor"},
            "module.chat",
        ),
    ],
)
def test_runtime_rbac_denial_precedes_readonly_status(
    monkeypatch, router, path, json_body, permissions, expected_action
):
    audit_sink = CollectingAuditSink()
    monkeypatch.setenv("DATUS_PLATFORM_STATUS", "readonly")
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions(audit_sink=audit_sink))
    svc = MagicMock()
    svc.agent_config = _datasource_agent_config()
    ctx = AppContext(user_id="u1", project_id="proj", permissions=permissions)

    with _client(router, ctx, svc) as client:
        response = client.post(path, json=json_body)

    assert response.status_code == 403
    assert expected_action in response.json()["detail"]
    assert [event.action for event in audit_sink.events] == [expected_action]


def test_sql_execute_is_blocked_in_readonly_status_and_audited(monkeypatch):
    audit_sink = CollectingAuditSink()
    monkeypatch.setenv("DATUS_PLATFORM_STATUS", "readonly")
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions(audit_sink=audit_sink))
    svc = MagicMock()
    svc.agent_config = _datasource_agent_config()
    svc.cli.execute_sql = AsyncMock(side_effect=AssertionError("upstream invoked"))
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.sql_executor"})

    with _client(cli_routes.router, ctx, svc) as client:
        response = client.post("/api/v1/sql/execute", json={"sql_query": "SELECT 1", "result_format": "json"})

    assert response.status_code == 403
    assert response.json()["detail"] == "PLATFORM_STATUS_FORBIDDEN"
    svc.cli.execute_sql.assert_not_awaited()
    event = audit_sink.events[-1]
    assert event.action == "system.platform_status"
    assert event.resource_type == "datasource"
    assert event.decision == "deny"
    assert event.metadata == {"operation": "sql.execute", "platform_status": "readonly"}


def test_sql_execute_readonly_status_does_not_resolve_datus_service(monkeypatch):
    audit_sink = CollectingAuditSink()
    monkeypatch.setenv("DATUS_PLATFORM_STATUS", "readonly")
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions(audit_sink=audit_sink))
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.sql_executor"})
    app = FastAPI()
    app.include_router(cli_routes.router)

    async def reject_service(request: Request):
        raise AssertionError("platform status gate resolved DatusService")

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = reject_service
    app.dependency_overrides[deps.get_request_app_context] = override_context

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/api/v1/sql/execute", json={"sql_query": "SELECT 1", "result_format": "json"})

    assert response.status_code == 403
    assert response.json()["detail"] == "PLATFORM_STATUS_FORBIDDEN"
    assert audit_sink.events[-1].action == "system.platform_status"


def test_sql_execute_routes_allow_module_sql_executor(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = MagicMock()
    svc.agent_config = _datasource_agent_config()
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
    assert svc.cli.execute_sql.await_args.kwargs["user_id"] == "u1"
    assert svc.cli.execute_sql.await_args.kwargs["agent_config"].current_datasource == "default"


def test_sql_execute_returns_unavailable_without_quota_store(monkeypatch):
    audit_sink = CollectingAuditSink()
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions(audit_sink=audit_sink, quota_store=None))
    svc = MagicMock()
    svc.agent_config = _datasource_agent_config()
    svc.cli.execute_sql = AsyncMock()
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.sql_executor"})

    with _client(cli_routes.router, ctx, svc) as client:
        response = client.post("/api/v1/sql/execute", json={"sql_query": "SELECT 1", "result_format": "json"})

    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["errorCode"] == "QUOTA_STORE_UNAVAILABLE"
    svc.cli.execute_sql.assert_not_awaited()
    event = audit_sink.events[-1]
    assert event.action == "quota.consume"
    assert event.decision == "deny"
    assert event.reason == "quota store unavailable"


def test_sql_execute_rejects_quota_exceeded_before_execution(monkeypatch):
    quota_store = InMemoryEnterpriseQuotaStore()
    asyncio.run(
        quota_store.put_quota(
            subject_type="user",
            subject_id="u1",
            resource="sql.execute",
            limit=1,
            window_seconds=3600,
        )
    )
    asyncio.run(
        quota_store.consume_quota(
            subjects=[{"subject_type": "user", "subject_id": "u1"}],
            resource="sql.execute",
        )
    )
    audit_sink = CollectingAuditSink()
    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        _enterprise_extensions(audit_sink=audit_sink, quota_store=quota_store),
    )
    svc = MagicMock()
    svc.agent_config = _datasource_agent_config()
    svc.cli.execute_sql = AsyncMock()
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.sql_executor"})

    with _client(cli_routes.router, ctx, svc) as client:
        response = client.post("/api/v1/sql/execute", json={"sql_query": "SELECT 1", "result_format": "json"})

    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["errorCode"] == "QUOTA_EXCEEDED"
    svc.cli.execute_sql.assert_not_awaited()
    event = audit_sink.events[-1]
    assert event.action == "quota.consume"
    assert event.decision == "deny"
    assert event.reason == "quota exceeded"
    assert event.metadata["resource"] == "sql.execute"
    assert event.metadata["used"] == 1


def test_sql_execute_consumes_quota_before_successful_execution(monkeypatch):
    quota_store = InMemoryEnterpriseQuotaStore()
    asyncio.run(
        quota_store.put_quota(
            subject_type="user",
            subject_id="u1",
            resource="sql.execute",
            limit=2,
            window_seconds=3600,
        )
    )
    audit_sink = CollectingAuditSink()
    monkeypatch.setattr(
        deps,
        "_enterprise_extensions",
        _enterprise_extensions(audit_sink=audit_sink, quota_store=quota_store),
    )
    svc = MagicMock()
    svc.agent_config = _datasource_agent_config()
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

    usage = asyncio.run(quota_store.list_usage(subject_type="user", subject_id="u1", resource="sql.execute"))

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert usage[0]["used"] == 1
    assert [event.action for event in audit_sink.events[-2:]] == ["quota.consume", "sql.execute"]
    assert audit_sink.events[-2].decision == "allow"
    svc.cli.execute_sql.assert_awaited_once()


def test_sql_execute_audits_sanitized_result(monkeypatch):
    audit_sink = CollectingAuditSink()
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions(audit_sink=audit_sink))
    svc = MagicMock()
    svc.agent_config = _datasource_agent_config()
    svc.cli.execute_sql = AsyncMock(
        return_value=Result[ExecuteSQLData](
            success=True,
            data=ExecuteSQLData(
                execute_task_id="task-1",
                sql_query="SELECT secret FROM finance.payroll",
                result_format="json",
                row_count=3,
                sql_return='[{"secret": "value"}]',
                execution_time=0.01,
                executed_at="2026-06-27T00:00:00Z",
            ),
        )
    )
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.sql_executor"})

    with _client(cli_routes.router, ctx, svc) as client:
        response = client.post("/api/v1/sql/execute", json={"sql_query": "SELECT secret", "result_format": "json"})

    assert response.status_code == 200
    event = audit_sink.events[-1]
    assert event.user_id == "u1"
    assert event.action == "sql.execute"
    assert event.resource_type == "datasource"
    assert event.resource_id == "default"
    assert event.decision == "allow"
    assert event.reason is None
    assert event.metadata == {"result_format": "json", "execute_task_id": "task-1", "row_count": 3}


def test_sql_execute_audits_sanitized_failure(monkeypatch):
    audit_sink = CollectingAuditSink()
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions(audit_sink=audit_sink))
    svc = MagicMock()
    svc.agent_config = _datasource_agent_config()
    svc.cli.execute_sql = AsyncMock(
        return_value=Result[ExecuteSQLData](
            success=False,
            errorCode="SQL_EXECUTION_ERROR",
            errorMessage="policy backend down at postgres://secret-host",
        )
    )
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.sql_executor"})

    with _client(cli_routes.router, ctx, svc) as client:
        response = client.post("/api/v1/sql/execute", json={"sql_query": "SELECT secret", "result_format": "json"})

    assert response.status_code == 200
    event = audit_sink.events[-1]
    assert event.user_id == "u1"
    assert event.action == "sql.execute"
    assert event.resource_type == "datasource"
    assert event.resource_id == "default"
    assert event.decision == "deny"
    assert event.reason == "SQL_EXECUTION_ERROR"
    assert event.metadata == {"result_format": "json", "error_code": "SQL_EXECUTION_ERROR"}


def test_sql_execute_uses_projected_default_datasource(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions(DatasourceGrantConfigProjector()))
    svc = MagicMock()
    svc.agent_config = _datasource_agent_config(current_datasource="hr")
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
    ctx = AppContext(
        user_id="u1",
        project_id="proj",
        permissions={"module.sql_executor"},
        datasource_grants={"finance": {"effect": "allow", "allow_sql": True}},
    )

    with _client(cli_routes.router, ctx, svc) as client:
        response = client.post("/api/v1/sql/execute", json={"sql_query": "SELECT 1", "result_format": "json"})

    assert response.status_code == 200
    projected_config = svc.cli.execute_sql.await_args.kwargs["agent_config"]
    assert projected_config.current_datasource == "finance"
    assert set(projected_config.services.datasources) == {"finance"}
    assert projected_config.principal["datasource"] == "finance"


def test_sql_execute_rejects_unauthorized_database_before_execution(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions(DatasourceGrantConfigProjector()))
    svc = MagicMock()
    svc.agent_config = _datasource_agent_config(current_datasource="finance")
    svc.cli.execute_sql = AsyncMock()
    ctx = AppContext(
        user_id="u1",
        project_id="proj",
        permissions={"module.sql_executor"},
        datasource_grants={
            "finance": {
                "effect": "allow",
                "allow_sql": True,
                "databases": ["finance"],
            }
        },
    )

    with _client(cli_routes.router, ctx, svc) as client:
        response = client.post(
            "/api/v1/sql/execute",
            json={"sql_query": "SELECT 1", "database_name": "hr", "result_format": "json"},
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "Requested database 'hr' is not authorized for datasource 'finance'."
    svc.cli.execute_sql.assert_not_awaited()


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


@pytest.mark.parametrize("context_type", ["tables", "catalogs", "catalog", "context", "subject", "sql"])
def test_cli_context_metadata_requires_datasource_catalog(monkeypatch, context_type):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = MagicMock()
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.chat"})

    with _client(cli_routes.router, ctx, svc) as client:
        response = client.post(f"/api/v1/context/{context_type}", json={"context_type": context_type})

    assert response.status_code == 403
    svc.cli.execute_context.assert_not_called()


def test_cli_context_tables_rejects_missing_datasource_grant_before_execution(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions(DatasourceGrantConfigProjector()))
    svc = MagicMock()
    svc.agent_config = _datasource_agent_config(current_datasource="finance")
    svc.cli.execute_context.return_value = Result(
        success=True,
        data=ExecuteContextData(context_type="tables", database_name="finance", result={}),
    )
    ctx = AppContext(
        user_id="u1",
        project_id="proj",
        permissions={"module.datasource_catalog"},
        datasource_grants={},
    )

    with _client(cli_routes.router, ctx, svc) as client:
        response = client.post("/api/v1/context/tables", json={"context_type": "tables"})

    assert response.status_code == 403
    assert response.json()["detail"] == "No datasource grant available."
    svc.cli.execute_context.assert_not_called()


def test_cli_context_tables_passes_projected_config(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions(DatasourceGrantConfigProjector()))
    svc = MagicMock()
    svc.agent_config = _datasource_agent_config(current_datasource="hr")
    svc.cli.execute_context.return_value = Result(
        success=True,
        data=ExecuteContextData(context_type="tables", database_name="finance", result={}),
    )
    ctx = AppContext(
        user_id="u1",
        project_id="proj",
        permissions={"module.datasource_catalog"},
        datasource_grants={"finance": {"effect": "allow", "allow_catalog": True}},
    )

    with _client(cli_routes.router, ctx, svc) as client:
        response = client.post("/api/v1/context/tables", json={"context_type": "tables"})

    assert response.status_code == 200
    projected_config = svc.cli.execute_context.call_args.kwargs["agent_config"]
    assert projected_config.current_datasource == "finance"
    assert set(projected_config.services.datasources) == {"finance"}


def test_subject_tree_requires_datasource_catalog(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = MagicMock()
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.chat"})

    with _client(subject_routes.router, ctx, svc) as client:
        response = client.get("/api/v1/subject-tree")

    assert response.status_code == 403


@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    [
        ("GET", "/api/v1/subject-tree", None),
        ("POST", "/api/v1/subject-tree/metric", {"subject_path": ["finance", "revenue"]}),
        ("POST", "/api/v1/subject-tree/metric/dimensions", {"subject_path": ["finance", "revenue"]}),
        ("POST", "/api/v1/subject-tree/metric/preview", {"subject_path": ["finance", "revenue"]}),
        ("POST", "/api/v1/subject-tree/reference_sql", {"subject_path": ["finance", "daily_revenue"]}),
    ],
)
def test_subject_tree_read_rbac_denial_does_not_resolve_datus_service(monkeypatch, method, path, json_body):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.chat"})
    app = FastAPI()
    app.include_router(subject_routes.router)

    async def reject_service(request: Request):
        raise AssertionError("RBAC denial resolved DatusService")

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = reject_service
    app.dependency_overrides[deps.get_request_app_context] = override_context

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.request(method, path, json=json_body)

    assert response.status_code == 403


@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    [
        ("POST", "/api/v1/subject-tree/create", {"subject_path": ["finance"]}),
        (
            "POST",
            "/api/v1/subject-tree/rename",
            {"type": "directory", "subject_path": ["finance"], "new_subject_path": ["finance_v2"]},
        ),
        ("DELETE", "/api/v1/subject-tree/delete", {"type": "directory", "subject_path": ["finance"]}),
        (
            "POST",
            "/api/v1/subject-tree/metric/create",
            {"subject_path": ["finance", "revenue"], "yaml": "metrics:\\n  - name: revenue\\n"},
        ),
        (
            "POST",
            "/api/v1/subject-tree/metric/edit",
            {"subject_path": ["finance", "revenue"], "yaml": "metrics:\\n  - name: revenue\\n"},
        ),
        (
            "POST",
            "/api/v1/subject-tree/reference_sql/create",
            {
                "subject_path": ["finance"],
                "name": "daily_revenue",
                "sql": "SELECT 1",
                "summary": "daily revenue",
                "search_text": "daily revenue",
            },
        ),
        (
            "POST",
            "/api/v1/subject-tree/reference_sql/edit",
            {
                "subject_path": ["finance"],
                "name": "daily_revenue",
                "sql": "SELECT 1",
                "summary": "daily revenue",
                "search_text": "daily revenue",
            },
        ),
        (
            "POST",
            "/api/v1/subject-tree/semantic_model/edit",
            {"entry_id": "table:orders", "update_values": {"description": "Orders"}},
        ),
    ],
)
def test_subject_tree_mutation_requires_config_edit_before_service(monkeypatch, method, path, json_body):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.datasource_catalog"})
    app = FastAPI()
    app.include_router(subject_routes.router)

    async def reject_service(request: Request):
        raise AssertionError("RBAC denial resolved DatusService")

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = reject_service
    app.dependency_overrides[deps.get_request_app_context] = override_context

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.request(method, path, json=json_body)

    assert response.status_code == 403


def test_cli_internal_tables_rejects_missing_datasource_grant_before_execution(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions(DatasourceGrantConfigProjector()))
    svc = MagicMock()
    svc.agent_config = _datasource_agent_config(current_datasource="finance")
    ctx = AppContext(
        user_id="u1",
        project_id="proj",
        permissions={"module.datasource_catalog"},
        datasource_grants={},
    )

    with _client(cli_routes.router, ctx, svc) as client:
        response = client.post("/api/v1/internal/tables", json={"command": "tables", "args": ""})

    assert response.status_code == 403
    assert response.json()["detail"] == "No datasource grant available."
    svc.cli.execute_internal_command.assert_not_called()


@pytest.mark.parametrize("context_type", ["tables", "catalogs", "catalog", "context", "subject", "sql"])
def test_cli_context_metadata_rbac_denial_does_not_resolve_datus_service(monkeypatch, context_type):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.chat"})
    app = FastAPI()
    app.include_router(cli_routes.router)

    async def reject_service(request: Request):
        raise AssertionError("RBAC denial resolved DatusService")

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = reject_service
    app.dependency_overrides[deps.get_request_app_context] = override_context

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(f"/api/v1/context/{context_type}", json={"context_type": context_type})

    assert response.status_code == 403


@pytest.mark.parametrize("command", ["databases", "tables"])
def test_cli_internal_metadata_requires_datasource_catalog(monkeypatch, command):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = MagicMock()
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.chat"})

    with _client(cli_routes.router, ctx, svc) as client:
        response = client.post(f"/api/v1/internal/{command}", json={"command": command, "args": ""})

    assert response.status_code == 403
    svc.cli.execute_internal_command.assert_not_called()


@pytest.mark.parametrize("command", ["databases", "tables"])
def test_cli_internal_metadata_rbac_denial_does_not_resolve_datus_service(monkeypatch, command):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.chat"})
    app = FastAPI()
    app.include_router(cli_routes.router)

    async def reject_service(request: Request):
        raise AssertionError("RBAC denial resolved DatusService")

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = reject_service
    app.dependency_overrides[deps.get_request_app_context] = override_context

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(f"/api/v1/internal/{command}", json={"command": command, "args": ""})

    assert response.status_code == 403


def test_cli_internal_clear_requires_chat_module(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    chat_service = MagicMock()
    chat_service.delete_session.return_value = Result(success=True, data={"deleted": True})
    svc = MagicMock()
    svc.cli = CLIService(agent_config=None, chat_service=chat_service)
    ctx = AppContext(user_id="bob", project_id="proj", permissions={"module.datasource_catalog"})

    with _client(cli_routes.router, ctx, svc) as client:
        response = client.post("/api/v1/internal/clear", json={"command": "clear", "args": "alice-session"})

    assert response.status_code == 403
    assert "module.chat" in response.json()["detail"]
    chat_service.delete_session.assert_not_called()


def test_cli_internal_clear_uses_current_user_scope(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    chat_service = MagicMock()
    chat_service.delete_session.return_value = Result(success=True, data={"deleted": True})
    svc = MagicMock()
    svc.cli = CLIService(agent_config=None, chat_service=chat_service)
    ctx = AppContext(user_id="bob", project_id="proj", permissions={"module.chat"})

    with _client(cli_routes.router, ctx, svc) as client:
        response = client.post("/api/v1/internal/clear", json={"command": "clear", "args": "alice-session"})

    assert response.status_code == 200
    assert response.json()["success"] is True
    chat_service.delete_session.assert_called_once_with("alice-session", user_id="bob")
