# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Unit tests for datus/api/routes/database_routes.py — list_catalogs endpoint."""

from types import SimpleNamespace
from typing import Optional
from unittest.mock import ANY, MagicMock, patch

import pytest

from datus.api.auth.context import AppContext
from datus.api.models.base_models import Result
from datus.api.models.database_models import (
    DatabaseInfo,
    DatabasesData,
    DatasourceConnectionStatus,
    DatasourcePrewarmData,
    DatasourceStatusData,
    ListDatabasesData,
    ListDatabasesInput,
)
from datus.api.routes.database_routes import (
    _DB_IO_TIMEOUT,
    _prune_databases_for_datasource_grant,
    datasource_status,
    list_catalogs,
    prewarm_datasource,
)


def _make_db_info(name: str = "main") -> DatabaseInfo:
    return DatabaseInfo(
        name=name,
        uri=f"sqlite:///{name}.db",
        type="sqlite",
        current=True,
        connection_status="connected",
    )


def _make_svc(
    list_databases_return: Optional[Result[ListDatabasesData]] = None,
    current_datasource: str = "default_ds",
) -> MagicMock:
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
    if list_databases_return is not None:
        svc.datasource.list_databases.return_value = list_databases_return
    svc.datasource.datasource_statuses.return_value = [
        DatasourceConnectionStatus(datasource_id=current_datasource, status="unknown", cached=False)
    ]
    svc.datasource.start_prewarm.return_value = True
    return svc


async def _timeout_wait_for(awaitable, timeout):
    """Async stub for asyncio.wait_for that closes the awaitable before raising TimeoutError."""
    if hasattr(awaitable, "close"):
        awaitable.close()
    raise TimeoutError


async def _call(
    svc: MagicMock,
    datasource_id: str = "",
    catalog_name: Optional[str] = None,
    database_name: str = "",
    schema_name: str = "",
    include_sys_schemas: bool = False,
) -> Result[DatabasesData]:
    """Call list_catalogs with explicit defaults to bypass FastAPI Query() object resolution."""
    return await list_catalogs(
        svc,
        AppContext(permissions={"module.datasource_catalog"}),
        datasource_id=datasource_id,
        catalog_name=catalog_name,
        database_name=database_name,
        schema_name=schema_name,
        include_sys_schemas=include_sys_schemas,
    )


class TestListCatalogs:
    """list_catalogs wraps list_databases in a thread, maps to DatabasesData, and handles timeout."""

    @pytest.mark.asyncio
    async def test_success_returns_databases_data(self):
        db = _make_db_info("main")
        list_result = Result[ListDatabasesData](
            success=True,
            data=ListDatabasesData(databases=[db], total_count=1, current_database="main"),
        )
        svc = _make_svc(list_databases_return=list_result)

        result = await _call(svc)

        assert result.success is True
        assert isinstance(result.data, DatabasesData)
        assert len(result.data.databases) == 1
        assert result.data.databases[0].name == "main"

    @pytest.mark.asyncio
    async def test_success_empty_list(self):
        list_result = Result[ListDatabasesData](
            success=True,
            data=ListDatabasesData(databases=[], total_count=0, current_database=None),
        )
        svc = _make_svc(list_databases_return=list_result)

        result = await _call(svc)

        assert result.success is True
        assert isinstance(result.data, DatabasesData)
        assert result.data.databases == []

    @pytest.mark.asyncio
    async def test_timeout_returns_request_timeout_error(self):
        svc = _make_svc()

        with patch("datus.api.routes.database_routes.asyncio.wait_for", side_effect=_timeout_wait_for) as mock_wf:
            result = await _call(svc)

        assert result.success is False
        assert result.errorCode == "REQUEST_TIMEOUT"
        assert result.errorMessage == "Datasource query timed out"
        svc.datasource.record_datasource_timeout.assert_called_once_with("default_ds")
        mock_wf.assert_called_once_with(ANY, timeout=_DB_IO_TIMEOUT)

    @pytest.mark.asyncio
    async def test_timeout_result_type_is_result(self):
        svc = _make_svc()

        with patch("datus.api.routes.database_routes.asyncio.wait_for", side_effect=_timeout_wait_for) as mock_wf:
            result = await _call(svc)

        assert isinstance(result, Result)
        assert result.data is None
        mock_wf.assert_called_once_with(ANY, timeout=_DB_IO_TIMEOUT)

    @pytest.mark.asyncio
    async def test_service_error_propagates_error_code(self):
        list_result = Result[ListDatabasesData](
            success=False,
            errorCode="DATASOURCE_NOT_FOUND",
            errorMessage="Datasource not found",
        )
        svc = _make_svc(list_databases_return=list_result)

        result = await _call(svc)

        assert result.success is False
        assert result.errorCode == "DATASOURCE_NOT_FOUND"
        assert result.errorMessage == "Datasource not found"

    @pytest.mark.asyncio
    async def test_success_true_but_data_none_returns_error(self):
        list_result = Result[ListDatabasesData](success=True, data=None)
        svc = _make_svc(list_databases_return=list_result)

        result = await _call(svc)

        assert result.success is False

    @pytest.mark.asyncio
    async def test_uses_current_datasource_when_datasource_id_empty(self):
        list_result = Result[ListDatabasesData](
            success=True,
            data=ListDatabasesData(databases=[], total_count=0, current_database=None),
        )
        svc = _make_svc(list_databases_return=list_result, current_datasource="my_ds")

        await _call(svc, datasource_id="")

        call_arg = svc.datasource.list_databases.call_args[0][0]
        assert isinstance(call_arg, ListDatabasesInput)
        assert call_arg.datasource_id == "my_ds"

    @pytest.mark.asyncio
    async def test_uses_explicit_datasource_id_when_provided(self):
        list_result = Result[ListDatabasesData](
            success=True,
            data=ListDatabasesData(databases=[], total_count=0, current_database=None),
        )
        svc = _make_svc(list_databases_return=list_result, current_datasource="other_ds")

        await _call(svc, datasource_id="explicit_ds")

        call_arg = svc.datasource.list_databases.call_args[0][0]
        assert isinstance(call_arg, ListDatabasesInput)
        assert call_arg.datasource_id == "explicit_ds"

    @pytest.mark.asyncio
    async def test_multiple_databases_all_returned(self):
        dbs = [_make_db_info(f"db_{i}") for i in range(3)]
        list_result = Result[ListDatabasesData](
            success=True,
            data=ListDatabasesData(databases=dbs, total_count=3, current_database="db_0"),
        )
        svc = _make_svc(list_databases_return=list_result)

        result = await _call(svc)

        assert result.success is True
        assert len(result.data.databases) == 3
        assert result.data.databases[0].name == "db_0"
        assert result.data.databases[2].name == "db_2"


def test_catalog_pruning_unions_independently_selected_grant_nodes():
    """A selected leaf must retain its ancestors without hiding disjoint selected branches."""
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
            tables=["test_table"],
        ),
        DatabaseInfo(
            name="ccks_fund",
            uri="postgresql://ccks_fund",
            type="postgresql",
            current=True,
            schema_name="private",
            connection_status="connected",
            tables=["secret_table"],
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
        DatabaseInfo(
            name="other_db",
            uri="postgresql://other_db",
            type="postgresql",
            current=False,
            schema_name="public",
            connection_status="connected",
            tables=["other_table"],
        ),
    ]

    visible = _prune_databases_for_datasource_grant(
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
        (
            "ccks_fund",
            "public",
            ["mf_benchmarkgrowthrate", "mf_bondportifoliodetail"],
        ),
        ("ccks_fund", "test", ["test_table"]),
        ("postgres", "public", ["server_table"]),
    ]


class TestDatasourceStatus:
    """datasource_status returns cached status without catalog loading."""

    @pytest.mark.asyncio
    async def test_status_uses_visible_datasources(self):
        svc = _make_svc(current_datasource="my_ds")

        result = await datasource_status(
            svc,
            AppContext(permissions={"module.datasource_catalog"}),
            datasource_id="",
        )

        assert result.success is True
        assert isinstance(result.data, DatasourceStatusData)
        svc.datasource.datasource_statuses.assert_called_once_with(["my_ds", "explicit_ds"])

    @pytest.mark.asyncio
    async def test_status_uses_explicit_datasource(self):
        svc = _make_svc()

        result = await datasource_status(
            svc,
            AppContext(permissions={"module.datasource_catalog"}),
            datasource_id="explicit_ds",
        )

        assert result.success is True
        svc.datasource.datasource_statuses.assert_called_once_with(["explicit_ds"])


class TestPrewarmDatasource:
    """prewarm_datasource schedules a background prewarm instead of blocking the request."""

    @pytest.mark.asyncio
    async def test_prewarm_schedules_background_task(self):
        svc = _make_svc()
        fake_task = MagicMock()

        def _fake_create_task(awaitable):
            awaitable.close()
            return fake_task

        with (
            patch("datus.api.routes.database_routes.asyncio.create_task") as mock_create_task,
            patch("datus.api.routes.database_routes.track_background_task") as mock_track,
        ):
            mock_create_task.side_effect = _fake_create_task
            result = await prewarm_datasource(
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
    async def test_prewarm_reports_already_running_without_scheduling(self):
        svc = _make_svc()
        svc.datasource.start_prewarm.return_value = False

        with patch("datus.api.routes.database_routes.asyncio.create_task") as mock_create_task:
            result = await prewarm_datasource(
                svc,
                AppContext(permissions={"module.datasource_catalog"}),
                datasource_id="explicit_ds",
            )

        assert result.success is True
        assert result.data.status == "already_running"
        mock_create_task.assert_not_called()
