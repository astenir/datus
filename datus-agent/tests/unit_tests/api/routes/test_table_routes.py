"""Enterprise authorization coverage for table and semantic model routes."""

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
)
from datus.api.enterprise.loader import EnterpriseExtensions
from datus.api.models.base_models import Result
from datus.api.models.table_models import ColumnInfo, GetTableDetailData, TableDetailData
from datus.api.routes import table_routes
from datus.tools.db_tools import connector_registry
from datus_enterprise.config_projection import DatasourceGrantConfigProjector

_CONNECTOR_REGISTRY_SNAPSHOT_ATTRS = ("_capabilities", "_uri_builders", "_context_resolvers")


@pytest.fixture(autouse=True)
def _register_catalog_dialect_capabilities():
    snapshots = {
        attr: {
            key: (set(value) if isinstance(value, set) else value)
            for key, value in getattr(connector_registry, attr).items()
        }
        for attr in _CONNECTOR_REGISTRY_SNAPSHOT_ATTRS
    }
    connector_registry.register_handlers("starrocks", capabilities={"catalog", "database"})
    try:
        yield
    finally:
        for attr, saved in snapshots.items():
            live = getattr(connector_registry, attr)
            live.clear()
            live.update(saved)


class CollectingAuditSink:
    def __init__(self):
        self.events = []

    async def write(self, event):
        self.events.append(event)


class FailingAuditSink:
    async def write(self, event):
        raise RuntimeError("audit unavailable")


def _enterprise_extensions(audit_sink=None):
    return EnterpriseExtensions(
        enabled=True,
        authorization_provider=LocalAuthorizationProvider(),
        config_projector=DatasourceGrantConfigProjector(),
        session_owner_store=InMemorySessionOwnerStore(),
        audit_sink=audit_sink or NoopAuditSink(),
        quota_store=InMemoryEnterpriseQuotaStore(),
    )


def _svc():
    svc = MagicMock()
    svc.agent_config = SimpleNamespace(
        services=SimpleNamespace(
            datasources={"finance": SimpleNamespace(type="sqlite"), "hr": SimpleNamespace(type="sqlite")},
            default_datasource=None,
        ),
        current_datasource="finance",
        principal={},
    )
    svc.datasource.current_datasource = "finance"
    svc.datasource.get_table_schema.return_value = Result[GetTableDetailData](
        success=True,
        data=GetTableDetailData(
            table=TableDetailData(
                name="accounts",
                columns=[ColumnInfo(name="id", type="INTEGER", nullable=False, pk=True)],
                indexes=[],
            )
        ),
    )
    svc.datasource.get_semantic_model.return_value = Result(success=True, data={"yaml": "semantic_model:\n"})
    svc.datasource.save_semantic_model = AsyncMock(return_value=Result(success=True, data={"saved": True}))
    svc.datasource.validate_semantic_model = AsyncMock(return_value=Result(success=True, data={"valid": True}))
    return svc


def _client(ctx: AppContext, svc):
    app = FastAPI()
    app.include_router(table_routes.router)

    async def override_service(request: Request):
        request.state.app_context = ctx
        return svc

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = override_service
    app.dependency_overrides[deps.get_request_app_context] = override_context
    return TestClient(app, raise_server_exceptions=False)


def _ctx(*, permissions: set[str], grants=None):
    return AppContext(
        user_id="alice",
        project_id="enterprise",
        permissions=permissions,
        datasource_grants=grants
        if grants is not None
        else {"finance": {"effect": "allow", "allow_catalog": True, "tables": ["public.accounts"]}},
    )


def test_table_detail_requires_datasource_catalog_permission(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = _svc()
    ctx = _ctx(permissions={"module.chat"})

    with _client(ctx, svc) as client:
        response = client.get("/api/v1/table/detail?table=public.accounts")

    assert response.status_code == 403
    svc.datasource.get_table_schema.assert_not_called()


def test_table_detail_rejects_table_outside_datasource_grant(monkeypatch):
    audit_sink = CollectingAuditSink()
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions(audit_sink=audit_sink))
    svc = _svc()
    ctx = _ctx(permissions={"module.datasource_catalog"})

    with _client(ctx, svc) as client:
        response = client.get("/api/v1/table/detail?table=public.payroll")

    assert response.status_code == 403
    assert "not authorized" in response.json()["detail"]
    svc.datasource.get_table_schema.assert_not_called()
    event = audit_sink.events[-1]
    assert event.action == "table.detail"
    assert event.resource_type == "table"
    assert event.resource_id == "public.payroll"
    assert event.decision == "deny"
    assert event.metadata["datasource"] == "finance"


def test_table_detail_denial_survives_audit_failure(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions(audit_sink=FailingAuditSink()))
    svc = _svc()
    ctx = _ctx(permissions={"module.datasource_catalog"})

    with _client(ctx, svc) as client:
        response = client.get("/api/v1/table/detail?table=public.payroll")

    assert response.status_code == 403
    assert "not authorized" in response.json()["detail"]
    svc.datasource.get_table_schema.assert_not_called()


def test_table_detail_rejects_when_catalog_access_is_disabled(monkeypatch):
    audit_sink = CollectingAuditSink()
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions(audit_sink=audit_sink))
    svc = _svc()
    ctx = _ctx(
        permissions={"module.datasource_catalog"},
        grants={"finance": {"effect": "allow", "allow_catalog": False, "allow_sql": True}},
    )

    with _client(ctx, svc) as client:
        response = client.get("/api/v1/table/detail?table=public.accounts")

    assert response.status_code == 403
    assert response.json()["detail"] == "No datasource grant available."
    svc.datasource.get_table_schema.assert_not_called()
    event = audit_sink.events[-1]
    assert event.action == "catalog.table.detail"
    assert event.resource_type == "datasource"
    assert event.decision == "deny"
    assert event.reason == "No datasource grant available."


def test_semantic_model_routes_allow_catalog_when_sql_access_is_disabled(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = _svc()
    ctx = _ctx(
        permissions={"module.datasource_catalog", "module.config.edit"},
        grants={
            "finance": {
                "effect": "allow",
                "allow_catalog": True,
                "allow_sql": False,
                "tables": ["public.accounts"],
            }
        },
    )

    with _client(ctx, svc) as client:
        read_response = client.get("/api/v1/semantic_model?table=public.accounts")
        save_response = client.post(
            "/api/v1/semantic_model",
            json={"table": "public.accounts", "yaml": "semantic_model:\n  name: accounts\n"},
        )
        validate_response = client.post(
            "/api/v1/semantic_model/validate",
            json={"table": "public.accounts", "yaml": "semantic_model:\n  name: accounts\n"},
        )

    assert read_response.status_code == 200
    assert save_response.status_code == 200
    assert validate_response.status_code == 200
    svc.datasource.get_semantic_model.assert_called_once_with("public.accounts")
    svc.datasource.save_semantic_model.assert_awaited_once()
    svc.datasource.validate_semantic_model.assert_awaited_once()


def test_table_detail_allows_authorized_table(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = _svc()
    ctx = _ctx(permissions={"module.datasource_catalog"})

    with _client(ctx, svc) as client:
        response = client.get("/api/v1/table/detail?table=public.accounts")

    assert response.status_code == 200
    assert response.json()["success"] is True
    svc.datasource.get_table_schema.assert_called_once_with("public.accounts")


def test_table_detail_allows_starrocks_catalog_database_table_grant(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = _svc()
    svc.agent_config.services.datasources["finance"] = SimpleNamespace(type="starrocks")
    svc.datasource.current_db_connector.get_type.return_value = "starrocks"
    ctx = _ctx(
        permissions={"module.datasource_catalog"},
        grants={
            "finance": {
                "effect": "allow",
                "allow_catalog": True,
                "catalogs": ["default_catalog"],
                "databases": ["finance"],
                "tables": ["default_catalog.finance.orders"],
            }
        },
    )

    with _client(ctx, svc) as client:
        response = client.get("/api/v1/table/detail?table=default_catalog.finance.orders")

    assert response.status_code == 200
    assert response.json()["success"] is True
    svc.datasource.get_table_schema.assert_called_once_with("default_catalog.finance.orders")


def test_save_semantic_model_is_blocked_in_readonly_status(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    monkeypatch.setenv("DATUS_PLATFORM_STATUS", "readonly")
    svc = _svc()
    ctx = _ctx(permissions={"module.config.edit"})

    with _client(ctx, svc) as client:
        response = client.post(
            "/api/v1/semantic_model",
            json={"table": "public.accounts", "yaml": "semantic_model:\n  name: accounts\n"},
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "PLATFORM_STATUS_FORBIDDEN"


def test_save_semantic_model_rbac_denial_precedes_readonly_status(monkeypatch):
    audit_sink = CollectingAuditSink()
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions(audit_sink=audit_sink))
    monkeypatch.setenv("DATUS_PLATFORM_STATUS", "readonly")
    ctx = _ctx(permissions={"module.datasource_catalog"})
    app = FastAPI()
    app.include_router(table_routes.router)

    async def reject_service(request: Request):
        raise AssertionError("RBAC denial resolved DatusService")

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = reject_service
    app.dependency_overrides[deps.get_request_app_context] = override_context

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v1/semantic_model",
            json={"table": "public.accounts", "yaml": "semantic_model:\n  name: accounts\n"},
        )

    assert response.status_code == 403
    assert "module.config.edit" in response.json()["detail"]
    assert [event.action for event in audit_sink.events] == ["module.config.edit"]


def test_save_semantic_model_readonly_status_does_not_resolve_datus_service(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    monkeypatch.setenv("DATUS_PLATFORM_STATUS", "readonly")
    ctx = _ctx(permissions={"module.config.edit"})
    app = FastAPI()
    app.include_router(table_routes.router)

    async def reject_service(request: Request):
        raise AssertionError("resolved DatusService before platform status denial")

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = reject_service
    app.dependency_overrides[deps.get_request_app_context] = override_context

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v1/semantic_model",
            json={"table": "public.accounts", "yaml": "semantic_model:\n  name: accounts\n"},
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "PLATFORM_STATUS_FORBIDDEN"


@pytest.mark.parametrize("path", ["/api/v1/semantic_model", "/api/v1/semantic_model/validate"])
def test_semantic_model_invalid_body_does_not_resolve_datus_service(monkeypatch, path):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    ctx = _ctx(permissions={"module.config.edit"})
    app = FastAPI()
    app.include_router(table_routes.router)

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
