"""Downstream coverage for the enterprise datasource catalog wrapper."""

import argparse
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from datus.api.auth.context import AppContext
from datus.api.models.base_models import Result
from datus.api.models.database_models import DatabaseInfo, DatabasesData
from datus.api.models.downstream import (
    DatasourceConnectionStatus,
    DatasourcePrewarmData,
    DatasourceStatusData,
)
from datus.api.service import create_app
from datus_enterprise.api import database_routes


def _make_svc(current_datasource: str = "default_ds") -> MagicMock:
    svc = MagicMock()
    svc.agent_config = SimpleNamespace(
        services=SimpleNamespace(
            datasources={
                current_datasource: SimpleNamespace(type="sqlite"),
                "explicit_ds": SimpleNamespace(type="sqlite"),
            },
            default_datasource=current_datasource,
        ),
        current_datasource=current_datasource,
        principal={},
    )
    svc.datasource.current_datasource = current_datasource
    svc.datasource.datasource_statuses.return_value = [
        DatasourceConnectionStatus(datasource_id=current_datasource, status="unknown", cached=False)
    ]
    svc.datasource.start_prewarm.return_value = True
    return svc


def _projection(svc: MagicMock, *, datasource_grants=None):
    return SimpleNamespace(
        config=svc.agent_config,
        datasource_grants=datasource_grants or {},
    )


def test_create_app_registers_authoritative_database_routes_once():
    args = argparse.Namespace(config="", datasource="default", output_dir="./output", log_level="INFO")
    app = create_app(args)
    list_routes = [
        route
        for route in app.routes
        if getattr(route, "path", None) == "/api/v1/catalog/list"
        and "GET" in getattr(route, "methods", set())
    ]

    assert len(list_routes) == 1
    assert list_routes[0].endpoint.__module__ == "datus_enterprise.api.database_routes"


@pytest.mark.asyncio
async def test_list_catalogs_delegates_to_upstream_and_prunes_grant_scope(monkeypatch):
    svc = _make_svc(current_datasource="finance")
    databases = [
        DatabaseInfo(
            name="finance",
            uri="postgresql://finance",
            type="postgresql",
            current=True,
            schema_name="public",
            connection_status="connected",
            tables=["allowed", "hidden"],
        )
    ]
    monkeypatch.setattr(
        database_routes,
        "project_request_config",
        AsyncMock(
            return_value=_projection(
                svc,
                datasource_grants={"finance": {"effect": "allow", "tables": ["public.allowed"]}},
            )
        ),
    )
    upstream = AsyncMock(return_value=Result(success=True, data=DatabasesData(databases=databases)))
    monkeypatch.setattr(database_routes.upstream_database_routes, "list_catalogs", upstream)

    result = await database_routes.list_catalogs(
        svc,
        AppContext(permissions={"module.datasource_catalog"}),
        datasource_id="finance",
        catalog_name="",
        database_name="",
        schema_name="",
        include_sys_schemas=False,
    )

    assert result.success is True
    assert result.data.databases[0].tables == ["allowed"]
    upstream.assert_awaited_once_with(
        svc,
        datasource_id="finance",
        catalog_name="",
        database_name="",
        schema_name="",
        include_sys_schemas=False,
    )


@pytest.mark.asyncio
async def test_list_catalogs_records_upstream_timeout(monkeypatch):
    svc = _make_svc()
    monkeypatch.setattr(
        database_routes,
        "project_request_config",
        AsyncMock(return_value=_projection(svc)),
    )
    monkeypatch.setattr(
        database_routes.upstream_database_routes,
        "list_catalogs",
        AsyncMock(
            return_value=Result(
                success=False,
                errorCode="REQUEST_TIMEOUT",
                errorMessage="Datasource query timed out",
            )
        ),
    )

    result = await database_routes.list_catalogs(
        svc,
        AppContext(permissions={"module.datasource_catalog"}),
        datasource_id="",
        catalog_name="",
        database_name="",
        schema_name="",
        include_sys_schemas=False,
    )

    assert result.errorCode == "REQUEST_TIMEOUT"
    svc.datasource.record_datasource_timeout.assert_called_once_with("default_ds")


def test_catalog_pruning_unions_independently_selected_grant_nodes():
    databases = [
        DatabaseInfo(
            name="ccks_fund",
            uri="postgresql://ccks_fund",
            type="postgresql",
            current=True,
            schema_name="public",
            connection_status="connected",
            tables=["mf_benchmarkgrowthrate", "mf_bondportifoliodetail", "other_table"],
        ),
        DatabaseInfo(
            name="ccks_fund",
            uri="postgresql://ccks_fund",
            type="postgresql",
            current=True,
            schema_name="test",
            connection_status="connected",
            tables=[],
        ),
        DatabaseInfo(
            name="postgres",
            uri="postgresql://postgres",
            type="postgresql",
            current=False,
            schema_name="public",
            connection_status="connected",
            tables=["server_table"],
        ),
    ]

    visible = database_routes._prune_databases_for_datasource_grant(
        databases,
        datasource_id="ccks_fund",
        datasource_grants={
            "ccks_fund": {
                "effect": "allow",
                "databases": ["postgres"],
                "schemas": ["ccks_fund.test"],
                "tables": [
                    "ccks_fund.public.mf_benchmarkgrowthrate",
                    "ccks_fund.public.mf_bondportifoliodetail",
                ],
            }
        },
    )

    assert [(item.name, item.schema_name, item.tables) for item in visible] == [
        ("ccks_fund", "public", ["mf_benchmarkgrowthrate", "mf_bondportifoliodetail"]),
        ("ccks_fund", "test", []),
        ("postgres", "public", ["server_table"]),
    ]


@pytest.mark.asyncio
async def test_datasource_status_uses_visible_datasources(monkeypatch):
    svc = _make_svc(current_datasource="my_ds")
    monkeypatch.setattr(
        database_routes,
        "project_request_config",
        AsyncMock(return_value=_projection(svc)),
    )

    result = await database_routes.datasource_status(
        svc,
        AppContext(permissions={"module.datasource_catalog"}),
        datasource_id="",
    )

    assert result.success is True
    assert isinstance(result.data, DatasourceStatusData)
    svc.datasource.datasource_statuses.assert_called_once_with(["my_ds", "explicit_ds"])


@pytest.mark.asyncio
async def test_prewarm_schedules_background_task(monkeypatch):
    svc = _make_svc()
    monkeypatch.setattr(
        database_routes,
        "project_request_config",
        AsyncMock(return_value=_projection(svc)),
    )
    fake_task = MagicMock()

    def _fake_create_task(awaitable):
        awaitable.close()
        return fake_task

    with (
        patch("datus_enterprise.api.database_routes.asyncio.create_task") as mock_create_task,
        patch("datus_enterprise.api.database_routes.track_background_task") as mock_track,
    ):
        mock_create_task.side_effect = _fake_create_task
        result = await database_routes.prewarm_datasource(
            svc,
            AppContext(permissions={"module.datasource_catalog"}),
            datasource_id="explicit_ds",
        )

    assert result.success is True
    assert isinstance(result.data, DatasourcePrewarmData)
    assert result.data.datasource_id == "explicit_ds"
    assert result.data.status == "queued"
    svc.datasource.start_prewarm.assert_called_once_with("explicit_ds")
    mock_create_task.assert_called_once()
    mock_track.assert_called_once_with(fake_task)


@pytest.mark.asyncio
async def test_prewarm_reports_already_running_without_scheduling(monkeypatch):
    svc = _make_svc()
    svc.datasource.start_prewarm.return_value = False
    monkeypatch.setattr(
        database_routes,
        "project_request_config",
        AsyncMock(return_value=_projection(svc)),
    )

    with patch("datus_enterprise.api.database_routes.asyncio.create_task") as mock_create_task:
        result = await database_routes.prewarm_datasource(
            svc,
            AppContext(permissions={"module.datasource_catalog"}),
            datasource_id="explicit_ds",
        )

    assert result.success is True
    assert result.data.status == "already_running"
    mock_create_task.assert_not_called()
