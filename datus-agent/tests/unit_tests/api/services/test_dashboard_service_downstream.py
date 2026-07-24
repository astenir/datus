"""Unit tests for ``datus.api.services.dashboard_service`` — CI level, zero external deps.

Covers the on-disk artifact bundle walk, the on-disk template-pair loader,
and the agent-only branches of ``DashboardService.run_query``:

* ``published_version is None`` (IDE live-edit preview) feeds the render
  from ``dashboards/<slug>/queries/<slug>.{sql.j2,params.json}``.
* ``published_version`` set with no ``published_template_loader`` is
  rejected with ``INVALID_PUBLISHED_VERSION`` — the agent-only deployment
  has no Postgres snapshot table, so the loader injection seam is the
  only way to enable that branch.

The Datus-backend-side wrapper covers the published-snapshot path
through its own ``tests/unit/test_dashboard_service_run_query.py``.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from datus.api.services.dashboard_service import (
    DashboardService,
)
from datus.schemas.gen_visual_dashboard_models import TemplateParamDecl
from datus.tools.sql_policy import EnforcementResult, SqlPolicyConfig

_SAMPLE_SQL_J2 = "SELECT * FROM sales WHERE region = :region;\n"
_SAMPLE_META = {
    "slug": "by_region",
    "description": "Sales by region",
    "datasource": "warehouse",
    "params": [{"name": "region", "type": "string", "required": True}],
    "columns": [{"name": "region", "type": "string"}, {"name": "amount", "type": "number"}],
    "sample_params": {"region": "APAC"},
    "sample_row_count": 1,
    "saved_at": "2026-05-20T00:00:00Z",
}
_SAMPLE_MANIFEST = {
    "slug": "demo",
    "name": "Demo Dashboard",
    "description": "Just a demo",
    "kind": "dashboard",
    "created_at": "2026-05-20T00:00:00Z",
}
_SAMPLE_APP_JSX = "import React from 'react';\nexport default function App() { return null; }\n"


class RewriteDashboardSqlPolicyEnforcer:
    def __init__(self, config: SqlPolicyConfig) -> None:
        self.config = config

    def enforce_read(self, sql: str, *, datasource: str, dialect: str, principal: dict | None) -> EnforcementResult:
        return EnforcementResult(allowed=True, sql="SELECT 2 AS rewritten", applied_policies=["rewrite"])


class RaisingDashboardSqlPolicyEnforcer:
    def __init__(self, config: SqlPolicyConfig) -> None:
        self.config = config

    def enforce_read(self, sql: str, *, datasource: str, dialect: str, principal: dict | None) -> EnforcementResult:
        raise RuntimeError("policy backend down")


def _write_dashboard(
    project_files_root: Path,
    *,
    dashboard_slug: str = "demo",
    query_slug: str = "by_region",
    with_template: bool = True,
    sql_template: str = _SAMPLE_SQL_J2,
    meta: dict | None = None,
) -> Path:
    """Lay out a minimal on-disk dashboard fixture under
    ``<project_files_root>/dashboards/<slug>/``.

    Returns the dashboard directory.
    """
    dashboard_dir = project_files_root / "dashboards" / dashboard_slug
    (dashboard_dir / "render").mkdir(parents=True, exist_ok=True)
    (dashboard_dir / "render" / "app.jsx").write_text(_SAMPLE_APP_JSX, encoding="utf-8")
    (dashboard_dir / "manifest.json").write_text(json.dumps(_SAMPLE_MANIFEST), encoding="utf-8")
    if with_template:
        queries_dir = dashboard_dir / "queries"
        queries_dir.mkdir(parents=True, exist_ok=True)
        (queries_dir / f"{query_slug}.sql.j2").write_text(sql_template, encoding="utf-8")
        (queries_dir / f"{query_slug}.params.json").write_text(json.dumps(meta or _SAMPLE_META), encoding="utf-8")
    return dashboard_dir


def _seed_dist(dist_dir: Path) -> None:
    dist_dir.mkdir(parents=True, exist_ok=True)
    (dist_dir / "index.css").write_text("/* offline css */", encoding="utf-8")
    (dist_dir / "index.umd.js").write_text("/* offline js */", encoding="utf-8")


def _patch_executor(monkeypatch, *, captured: dict) -> None:
    """Replace the DB-execution suffix of ``run_query`` so tests focus on
    the template-source switch / render output, not the live connector path.

    The agent service late-imports ``datus.tools.func_tool`` at call time so
    monkeypatching ``DBFuncTool`` on the module attribute is safe.
    """

    class _FakeExecResult:
        success = True
        sql_return = [{"region": "APAC", "amount": 100}]

    class _FakeConnector:
        dialect = "sqlite"

        def execute_query(self, sql, result_format="list"):
            captured["sql"] = sql
            captured["result_format"] = result_format
            return _FakeExecResult()

    class _FakeDBFuncTool:
        def __init__(self, *, agent_config, sub_agent_name):
            captured["agent_config"] = agent_config
            captured["sub_agent_name"] = sub_agent_name

        def _get_connector(self, datasource):
            captured["datasource"] = datasource
            return _FakeConnector()

    import datus.tools.func_tool as func_tool_mod

    monkeypatch.setattr(func_tool_mod, "DBFuncTool", _FakeDBFuncTool)


@pytest.mark.asyncio
async def test_list_dashboards_empty_when_no_dashboards_dir(tmp_path: Path):
    """No ``dashboards/`` directory → empty list, not an error."""
    result = await DashboardService(agent_config=None).list_dashboards(project_files_root=tmp_path)
    assert result.success is True
    assert result.data == []


@pytest.mark.asyncio
async def test_list_dashboards_returns_single_dashboard(tmp_path: Path):
    _write_dashboard(tmp_path)
    result = await DashboardService(agent_config=None).list_dashboards(project_files_root=tmp_path)
    assert result.success is True
    assert len(result.data) == 1
    assert result.data[0].slug == "demo"
    assert result.data[0].name == "Demo Dashboard"
    assert result.data[0].description == "Just a demo"
    assert result.data[0].kind == "dashboard"


@pytest.mark.asyncio
async def test_list_dashboards_returns_multiple_sorted_by_recency(tmp_path: Path):
    """Dashboards are sorted by ``updated_at ?? created_at`` descending."""
    old_manifest = {
        "slug": "old",
        "name": "Old Dashboard",
        "description": "An older dashboard",
        "kind": "dashboard",
        "created_at": "2026-01-01T00:00:00Z",
    }
    old_dir = tmp_path / "dashboards" / "old"
    old_dir.mkdir(parents=True, exist_ok=True)
    (old_dir / "render").mkdir(exist_ok=True)
    (old_dir / "render" / "app.jsx").write_text(_SAMPLE_APP_JSX, encoding="utf-8")
    (old_dir / "manifest.json").write_text(json.dumps(old_manifest), encoding="utf-8")
    newer_manifest = {
        "slug": "newer",
        "name": "Newer Dashboard",
        "description": "More recent",
        "kind": "dashboard",
        "created_at": "2026-06-01T00:00:00Z",
        "updated_at": "2026-06-01T12:00:00Z",
    }
    newer_dir = tmp_path / "dashboards" / "newer"
    newer_dir.mkdir(parents=True, exist_ok=True)
    (newer_dir / "render").mkdir(exist_ok=True)
    (newer_dir / "render" / "app.jsx").write_text(_SAMPLE_APP_JSX, encoding="utf-8")
    (newer_dir / "manifest.json").write_text(json.dumps(newer_manifest), encoding="utf-8")
    result = await DashboardService(agent_config=None).list_dashboards(project_files_root=tmp_path)
    assert result.success is True
    assert len(result.data) == 2
    assert result.data[0].slug == "newer"
    assert result.data[1].slug == "old"


@pytest.mark.asyncio
async def test_list_dashboards_skips_corrupt_manifest(tmp_path: Path):
    """A dashboard with a corrupt manifest.json is silently skipped."""
    good_manifest = {
        "slug": "good",
        "name": "Good Dashboard",
        "description": "Valid manifest",
        "kind": "dashboard",
        "created_at": "2026-05-20T00:00:00Z",
    }
    good_dir = tmp_path / "dashboards" / "good"
    good_dir.mkdir(parents=True, exist_ok=True)
    (good_dir / "manifest.json").write_text(json.dumps(good_manifest), encoding="utf-8")
    bad_dir = tmp_path / "dashboards" / "bad"
    bad_dir.mkdir(parents=True, exist_ok=True)
    (bad_dir / "manifest.json").write_text("{not-json", encoding="utf-8")
    result = await DashboardService(agent_config=None).list_dashboards(project_files_root=tmp_path)
    assert result.success is True
    assert len(result.data) == 1
    assert result.data[0].slug == "good"


@pytest.mark.asyncio
async def test_list_dashboards_skips_dir_without_manifest(tmp_path: Path):
    """A subdirectory without manifest.json is silently skipped."""
    good_manifest = {
        "slug": "good",
        "name": "Good Dashboard",
        "description": "Valid manifest",
        "kind": "dashboard",
        "created_at": "2026-05-20T00:00:00Z",
    }
    good_dir = tmp_path / "dashboards" / "good"
    good_dir.mkdir(parents=True, exist_ok=True)
    (good_dir / "manifest.json").write_text(json.dumps(good_manifest), encoding="utf-8")
    orphan = tmp_path / "dashboards" / "orphan"
    orphan.mkdir(parents=True, exist_ok=True)
    (orphan / "render").mkdir(exist_ok=True)
    (orphan / "render" / "app.jsx").write_text("const x = 1;\n", encoding="utf-8")
    result = await DashboardService(agent_config=None).list_dashboards(project_files_root=tmp_path)
    assert result.success is True
    assert len(result.data) == 1
    assert result.data[0].slug == "good"


@pytest.mark.asyncio
async def test_render_html_uses_configured_dashboard_dist(tmp_path: Path):
    _write_dashboard(tmp_path, dashboard_slug="html_offline")
    dist_dir = tmp_path / "vendor" / "web-artifact-render" / "dist"
    _seed_dist(dist_dir)
    agent_config = SimpleNamespace(agentic_nodes={"gen_visual_dashboard": {"dashboard_dist": str(dist_dir)}})
    result = await DashboardService(agent_config=agent_config).render_html(
        project_files_root=tmp_path, dashboard_slug="html_offline", query_endpoint="/api/v1/dashboard/query"
    )
    assert result.success is True
    assert "data:text/css;base64," in result.data
    assert "data:text/javascript;base64," in result.data
    assert "https://unpkg.com/" not in result.data
    assert not (tmp_path / "dashboards" / "html_offline" / "_assets").exists()


@pytest.mark.asyncio
async def test_run_query_uses_request_scoped_agent_config(monkeypatch, tmp_path: Path):
    """A projected per-request config must be used for datasource resolution."""
    _write_dashboard(tmp_path)
    captured: dict = {}
    _patch_executor(monkeypatch, captured=captured)
    shared_config = MagicMock(name="shared_config")
    projected_config = MagicMock(name="projected_config")
    result = await DashboardService(agent_config=shared_config).run_query(
        project_files_root=tmp_path,
        dashboard_slug="demo",
        query_slug="by_region",
        params={"region": "APAC"},
        agent_config=projected_config,
    )
    assert result.success is True
    assert captured["agent_config"] is projected_config


@pytest.mark.asyncio
async def test_run_query_projects_config_for_template_datasource(monkeypatch, tmp_path: Path):
    """The datasource saved in .params.json drives request-scoped projection."""
    _write_dashboard(tmp_path)
    captured: dict = {}
    _patch_executor(monkeypatch, captured=captured)
    shared_config = MagicMock(name="shared_config")
    projected_config = MagicMock(name="projected_config")
    requested_datasources: list[str | None] = []

    async def _project_config(datasource: str | None):
        requested_datasources.append(datasource)
        return projected_config

    result = await DashboardService(agent_config=shared_config).run_query(
        project_files_root=tmp_path,
        dashboard_slug="demo",
        query_slug="by_region",
        params={"region": "APAC"},
        agent_config=shared_config,
        agent_config_projector=_project_config,
    )
    assert result.success is True
    assert requested_datasources == ["warehouse"]
    assert captured["agent_config"] is projected_config
    assert captured["datasource"] == "warehouse"


@pytest.mark.asyncio
async def test_run_query_rejects_write_sql_before_execution(monkeypatch, tmp_path: Path):
    """Rendered dashboard SQL must stay read-only before connector execution."""
    _write_dashboard(tmp_path, sql_template="DELETE FROM sales WHERE region = :region;\n")
    captured: dict = {}
    _patch_executor(monkeypatch, captured=captured)
    agent_config = SimpleNamespace(
        current_datasource="warehouse",
        principal={"datasource": "warehouse", "datasource_grants": {"warehouse": {"effect": "allow"}}},
    )
    result = await DashboardService(agent_config=agent_config).run_query(
        project_files_root=tmp_path,
        dashboard_slug="demo",
        query_slug="by_region",
        params={"region": "APAC"},
        agent_config=agent_config,
    )
    assert result.success is False
    assert result.errorCode == "QUERY_EXECUTION_FAILED"
    assert "Only read-only queries" in (result.errorMessage or "")
    assert "sql" not in captured


@pytest.mark.asyncio
async def test_run_query_rejects_table_outside_grant_scope(monkeypatch, tmp_path: Path):
    """Dashboard query execution shares direct-SQL table-scope enforcement."""
    _write_dashboard(tmp_path, sql_template="SELECT * FROM denied_table WHERE region = :region;\n")
    captured: dict = {}
    _patch_executor(monkeypatch, captured=captured)
    agent_config = SimpleNamespace(
        current_datasource="warehouse",
        principal={
            "datasource": "warehouse",
            "datasource_grants": {"warehouse": {"effect": "allow", "tables": ["allowed_table"]}},
        },
    )
    result = await DashboardService(agent_config=agent_config).run_query(
        project_files_root=tmp_path,
        dashboard_slug="demo",
        query_slug="by_region",
        params={"region": "APAC"},
        agent_config=agent_config,
    )
    assert result.success is False
    assert result.errorCode == "QUERY_EXECUTION_FAILED"
    assert "outside scoped context" in (result.errorMessage or "")
    assert "sql" not in captured


@pytest.mark.asyncio
async def test_run_query_applies_sql_policy_rewrite(monkeypatch, tmp_path: Path):
    """Dashboard query executes the SQL returned by policy enforcement."""
    _write_dashboard(tmp_path)
    captured: dict = {}
    _patch_executor(monkeypatch, captured=captured)
    agent_config = SimpleNamespace(
        current_datasource="warehouse",
        principal={"datasource": "warehouse", "datasource_grants": {"warehouse": {"effect": "allow"}}},
        sql_policy_config=SqlPolicyConfig.from_dict(
            {
                "enabled": True,
                "provider": "tests.unit_tests.api.services.test_dashboard_service_downstream:RewriteDashboardSqlPolicyEnforcer",
            }
        ),
    )
    result = await DashboardService(agent_config=agent_config).run_query(
        project_files_root=tmp_path,
        dashboard_slug="demo",
        query_slug="by_region",
        params={"region": "APAC"},
        agent_config=agent_config,
    )
    assert result.success is True
    assert captured["sql"] == "SELECT 2 AS rewritten"
    assert result.data.sql == "SELECT 2 AS rewritten"


@pytest.mark.asyncio
async def test_run_query_returns_result_when_sql_policy_raises(monkeypatch, tmp_path: Path):
    """Policy backend failures must not escape the dashboard Result contract."""
    _write_dashboard(tmp_path)
    captured: dict = {}
    _patch_executor(monkeypatch, captured=captured)
    agent_config = SimpleNamespace(
        current_datasource="warehouse",
        principal={"datasource": "warehouse", "datasource_grants": {"warehouse": {"effect": "allow"}}},
        sql_policy_config=SqlPolicyConfig.from_dict(
            {
                "enabled": True,
                "provider": "tests.unit_tests.api.services.test_dashboard_service_downstream:RaisingDashboardSqlPolicyEnforcer",
            }
        ),
    )
    result = await DashboardService(agent_config=agent_config).run_query(
        project_files_root=tmp_path,
        dashboard_slug="demo",
        query_slug="by_region",
        params={"region": "APAC"},
        agent_config=agent_config,
    )
    assert result.success is False
    assert result.errorCode == "QUERY_EXECUTION_FAILED"
    assert result.errorMessage == "SQL authorization failed"
    assert "sql" not in captured


def _decl(name: str, type_: str, required: bool = True) -> TemplateParamDecl:
    return TemplateParamDecl(name=name, type=type_, required=required)


def _patch_failing_executor(monkeypatch, *, exc: Exception | None = None, exec_result=None) -> None:
    """Override the DB layer with one that either raises during execute or
    returns a controllable result envelope. Mirrors ``_patch_executor`` but
    aims at the failure branches.
    """

    class _Connector:
        dialect = "sqlite"

        def execute_query(self, sql, result_format="list"):
            if exc is not None:
                raise exc
            return exec_result

    class _FakeDBFuncTool:
        def __init__(self, *, agent_config, sub_agent_name):
            self.agent_config = agent_config

        def _get_connector(self, datasource):
            return _Connector()

    import datus.tools.func_tool as func_tool_mod

    monkeypatch.setattr(func_tool_mod, "DBFuncTool", _FakeDBFuncTool)
