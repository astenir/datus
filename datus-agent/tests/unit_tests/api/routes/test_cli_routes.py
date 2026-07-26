import argparse
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from datus.api.auth.context import AppContext
from datus.api.models.base_models import Result
from datus.api.models.cli_models import ExecuteSQLData
from datus.api.models.downstream import ExecuteSQLInput
from datus.api.service import create_app
from datus_enterprise.api import cli_routes


def test_create_app_registers_authoritative_cli_routes_once():
    args = argparse.Namespace(config="", datasource="default", output_dir="./output", log_level="INFO")
    app = create_app(args)
    routes = [
        route
        for route in app.routes
        if getattr(route, "path", None) == "/api/v1/sql/execute"
        and "POST" in getattr(route, "methods", set())
    ]

    assert len(routes) == 1
    assert routes[0].endpoint.__module__ == "datus_enterprise.api.cli_routes"


@pytest.mark.asyncio
async def test_execute_sql_returns_result_when_post_execute_audit_fails(monkeypatch):
    agent_config = SimpleNamespace(current_datasource="default")
    svc = SimpleNamespace(
        agent_config=agent_config,
        cli=SimpleNamespace(
            execute_sql=AsyncMock(
                return_value=Result[ExecuteSQLData](
                    success=True,
                    data=ExecuteSQLData(
                        execute_task_id="task-1",
                        sql_query="SELECT 1",
                        result_format="json",
                        execution_time=0.01,
                        executed_at="2026-06-28T00:00:00Z",
                        row_count=1,
                    ),
                )
            )
        ),
    )
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.sql_executor"})
    captured_projection_kwargs = {}

    async def project_config(*args, **kwargs):
        captured_projection_kwargs.update(kwargs)
        return SimpleNamespace(config=agent_config, principal={"datasource": "default"})

    async def quota_ok(*args, **kwargs):
        return None

    async def fail_audit(*args, **kwargs):
        raise RuntimeError("audit down")

    monkeypatch.setattr(cli_routes.api_deps, "resolve_datus_service_for_request", AsyncMock(return_value=svc))
    monkeypatch.setattr(cli_routes, "project_request_config", project_config)
    monkeypatch.setattr(cli_routes, "consume_enterprise_quota", quota_ok)
    monkeypatch.setattr(cli_routes, "audit_decision", fail_audit)

    result = await cli_routes.execute_sql(
        ExecuteSQLInput(sql_query="SELECT 1", result_format="json", datasource="fund"),
        ctx,
        SimpleNamespace(),
    )

    assert result.success is True
    assert result.data.execute_task_id == "task-1"
    assert result.data.row_count == 1
    assert captured_projection_kwargs["requested_datasource"] == "fund"
    svc.cli.execute_sql.assert_awaited_once()
