"""Enterprise authorization coverage for table and semantic model routes."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

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
from datus_enterprise.config_projection import DatasourceGrantConfigProjector


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

    app.dependency_overrides[deps.get_datus_service] = override_service
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
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = _svc()
    ctx = _ctx(permissions={"module.datasource_catalog"})

    with _client(ctx, svc) as client:
        response = client.get("/api/v1/table/detail?table=public.payroll")

    assert response.status_code == 403
    assert "not authorized" in response.json()["detail"]
    svc.datasource.get_table_schema.assert_not_called()


def test_table_detail_allows_authorized_table(monkeypatch):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    svc = _svc()
    ctx = _ctx(permissions={"module.datasource_catalog"})

    with _client(ctx, svc) as client:
        response = client.get("/api/v1/table/detail?table=public.accounts")

    assert response.status_code == 200
    assert response.json()["success"] is True
    svc.datasource.get_table_schema.assert_called_once_with("public.accounts")


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
    svc.datasource.save_semantic_model.assert_not_awaited()
