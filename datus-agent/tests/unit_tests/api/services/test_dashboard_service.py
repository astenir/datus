# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.

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
    _coerce_param_value,
    _load_local_template_pair,
    _validate_params,
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

    def enforce_read(
        self,
        sql: str,
        *,
        datasource: str,
        dialect: str,
        principal: dict | None,
    ) -> EnforcementResult:
        return EnforcementResult(allowed=True, sql="SELECT 2 AS rewritten", applied_policies=["rewrite"])


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


# ---------------------------------------------------------------------------
# _load_local_template_pair
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_local_template_pair_reads_files_from_disk(tmp_path: Path):
    _write_dashboard(tmp_path)

    result = await _load_local_template_pair(tmp_path, "demo", "by_region")

    assert result.success is True
    sql_template, meta_text = result.data
    assert sql_template == _SAMPLE_SQL_J2
    assert json.loads(meta_text) == _SAMPLE_META


@pytest.mark.asyncio
async def test_load_local_template_pair_missing_returns_template_not_found(tmp_path: Path):
    _write_dashboard(tmp_path, with_template=False)

    result = await _load_local_template_pair(tmp_path, "demo", "missing")

    assert result.success is False
    assert result.errorCode == "TEMPLATE_NOT_FOUND"


@pytest.mark.asyncio
async def test_load_local_template_pair_rejects_invalid_dashboard_slug(tmp_path: Path):
    # Slug with traversal / invalid chars — fails the slug regex guard.
    result = await _load_local_template_pair(tmp_path, "../escape", "by_region")

    assert result.success is False
    assert result.errorCode == "INVALID_DASHBOARD_SLUG"


# ---------------------------------------------------------------------------
# DashboardService.list_dashboards
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_dashboards_empty_when_no_dashboards_dir(tmp_path: Path):
    """No ``dashboards/`` directory → empty list, not an error."""
    result = await DashboardService(agent_config=None).list_dashboards(
        project_files_root=tmp_path,
    )

    assert result.success is True
    assert result.data == []


@pytest.mark.asyncio
async def test_list_dashboards_returns_single_dashboard(tmp_path: Path):
    _write_dashboard(tmp_path)

    result = await DashboardService(agent_config=None).list_dashboards(
        project_files_root=tmp_path,
    )

    assert result.success is True
    assert len(result.data) == 1
    assert result.data[0].slug == "demo"
    assert result.data[0].name == "Demo Dashboard"
    assert result.data[0].description == "Just a demo"
    assert result.data[0].kind == "dashboard"


@pytest.mark.asyncio
async def test_list_dashboards_returns_multiple_sorted_by_recency(tmp_path: Path):
    """Dashboards are sorted by ``updated_at ?? created_at`` descending."""
    # Write two dashboards with distinct manifests
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

    result = await DashboardService(agent_config=None).list_dashboards(
        project_files_root=tmp_path,
    )

    assert result.success is True
    assert len(result.data) == 2
    # "newer" has updated_at, "old" has only created_at → newer comes first
    assert result.data[0].slug == "newer"
    assert result.data[1].slug == "old"


@pytest.mark.asyncio
async def test_list_dashboards_skips_corrupt_manifest(tmp_path: Path):
    """A dashboard with a corrupt manifest.json is silently skipped."""
    # Write a valid dashboard
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

    # Write a dashboard with corrupt manifest
    bad_dir = tmp_path / "dashboards" / "bad"
    bad_dir.mkdir(parents=True, exist_ok=True)
    (bad_dir / "manifest.json").write_text("{not-json", encoding="utf-8")

    result = await DashboardService(agent_config=None).list_dashboards(
        project_files_root=tmp_path,
    )

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

    result = await DashboardService(agent_config=None).list_dashboards(
        project_files_root=tmp_path,
    )

    assert result.success is True
    assert len(result.data) == 1
    assert result.data[0].slug == "good"


# ---------------------------------------------------------------------------
# DashboardService.get_detail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_detail_returns_bundle_and_templates(tmp_path: Path):
    _write_dashboard(tmp_path)

    result = await DashboardService(agent_config=None).get_detail(
        project_files_root=tmp_path,
        dashboard_slug="demo",
    )

    assert result.success is True
    detail = result.data
    assert detail.slug == "demo"
    assert detail.name == "Demo Dashboard"
    assert detail.description == "Just a demo"

    # Flat files list includes the render entry and the queries pair —
    # manifest.json itself is intentionally absent (structured form lives
    # on ``manifest``).
    file_paths = {f.path for f in detail.files}
    assert "render/app.jsx" in file_paths
    assert "queries/by_region.sql.j2" in file_paths
    assert "queries/by_region.params.json" in file_paths
    assert "manifest.json" not in file_paths

    # The parsed templates sidecar carries the saved params/columns/datasource
    # so the outer-panel UI can drive filter affordances without re-parsing
    # the .params.json bytes from ``files``.
    assert len(detail.templates) == 1
    assert detail.templates[0].slug == "by_region"
    assert detail.templates[0].datasource == "warehouse"

    # Publication-side fields (subagent / dashboard_id / published_version /
    # published_at) are not part of the agent-side ``DashboardDetail``
    # schema — they live on Datus-backend's ``PublishedDashboardDetail``
    # subclass. The presence of any such attribute here would mean the
    # subclass leaked into agent code.
    assert not hasattr(detail, "subagent")
    assert not hasattr(detail, "dashboard_id")
    assert not hasattr(detail, "published_version")
    assert not hasattr(detail, "published_at")


@pytest.mark.asyncio
async def test_get_detail_rejects_invalid_slug(tmp_path: Path):
    result = await DashboardService(agent_config=None).get_detail(
        project_files_root=tmp_path,
        dashboard_slug="../escape",
    )

    assert result.success is False
    assert result.errorCode == "INVALID_DASHBOARD_SLUG"


@pytest.mark.asyncio
async def test_get_detail_missing_dashboard_returns_not_found(tmp_path: Path):
    result = await DashboardService(agent_config=None).get_detail(
        project_files_root=tmp_path,
        dashboard_slug="never_existed",
    )

    assert result.success is False
    assert result.errorCode == "DASHBOARD_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_detail_missing_manifest_returns_not_found(tmp_path: Path):
    """``render/app.jsx`` exists but ``manifest.json`` is missing — the
    bundle is unrenderable and must surface a deterministic error."""
    dashboard_dir = tmp_path / "dashboards" / "demo"
    (dashboard_dir / "render").mkdir(parents=True, exist_ok=True)
    (dashboard_dir / "render" / "app.jsx").write_text(_SAMPLE_APP_JSX, encoding="utf-8")

    result = await DashboardService(agent_config=None).get_detail(
        project_files_root=tmp_path,
        dashboard_slug="demo",
    )

    assert result.success is False
    assert result.errorCode == "DASHBOARD_NOT_FOUND"


# ---------------------------------------------------------------------------
# DashboardService.run_query — live-edit (no published_version)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_query_without_published_version_uses_local_template(monkeypatch, tmp_path: Path):
    """``published_version`` omitted → on-disk template feeds the render
    and the rendered SQL substitutes the supplied param.
    """
    _write_dashboard(tmp_path)
    captured: dict = {}
    _patch_executor(monkeypatch, captured=captured)

    result = await DashboardService(agent_config=MagicMock()).run_query(
        project_files_root=tmp_path,
        dashboard_slug="demo",
        query_slug="by_region",
        params={"region": "APAC"},
        published_version=None,
    )

    assert result.success is True
    assert result.data.row_count == 1
    assert result.data.datasource == "warehouse"
    # The rendered SQL substitutes the param — confirms we read the
    # on-disk ``.sql.j2`` and ran it through ``render_dashboard_template``.
    assert "APAC" in captured["sql"]
    # The agent service hands the canonical sub-agent name to ``DBFuncTool``
    # so the connector picks the same datasource binding the LLM saved.
    assert captured["sub_agent_name"] == "gen_visual_dashboard"
    assert captured["datasource"] == "warehouse"


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
    _write_dashboard(
        tmp_path,
        sql_template="DELETE FROM sales WHERE region = :region;\n",
    )
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
    _write_dashboard(
        tmp_path,
        sql_template="SELECT * FROM denied_table WHERE region = :region;\n",
    )
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
                "provider": "tests.unit_tests.api.services.test_dashboard_service:RewriteDashboardSqlPolicyEnforcer",
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
async def test_run_query_rejects_invalid_query_slug(tmp_path: Path):
    """Defence-in-depth: the slug regex guard fires before any I/O so a
    crafted slug can't reach the filesystem walker."""
    result = await DashboardService(agent_config=MagicMock()).run_query(
        project_files_root=tmp_path,
        dashboard_slug="demo",
        query_slug="../etc/passwd",
        params={},
    )

    assert result.success is False
    assert result.errorCode == "INVALID_QUERY_SLUG"


@pytest.mark.asyncio
async def test_run_query_rejects_non_dict_params(tmp_path: Path):
    """``params`` must be a JSON object so the param coercion step has
    something to walk."""
    result = await DashboardService(agent_config=MagicMock()).run_query(
        project_files_root=tmp_path,
        dashboard_slug="demo",
        query_slug="by_region",
        params=["not", "a", "dict"],  # type: ignore[arg-type]
    )

    assert result.success is False
    assert result.errorCode == "INVALID_PARAMS"


# ---------------------------------------------------------------------------
# DashboardService.run_query — published_version branch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_query_published_version_without_loader_is_rejected(tmp_path: Path):
    """Agent-only deployments have no Postgres snapshot table; without an
    injected ``published_template_loader`` the published-version branch must
    refuse cleanly so callers don't silently fall through to the on-disk
    path with wrong semantics."""
    result = await DashboardService(agent_config=MagicMock()).run_query(
        project_files_root=tmp_path,
        dashboard_slug="demo",
        query_slug="by_region",
        params={"region": "APAC"},
        published_version=1,
        published_template_loader=None,
    )

    assert result.success is False
    assert result.errorCode == "INVALID_PUBLISHED_VERSION"


@pytest.mark.asyncio
async def test_run_query_published_version_below_one_is_rejected(tmp_path: Path):
    """Even with a loader wired, a non-positive ``published_version`` must
    fail validation before calling out."""

    async def _never_called(_version):  # pragma: no cover - guards a defence
        raise AssertionError("loader should not be called when version is invalid")

    result = await DashboardService(agent_config=MagicMock()).run_query(
        project_files_root=tmp_path,
        dashboard_slug="demo",
        query_slug="by_region",
        params={"region": "APAC"},
        published_version=0,
        published_template_loader=_never_called,
    )

    assert result.success is False
    assert result.errorCode == "INVALID_PUBLISHED_VERSION"


@pytest.mark.asyncio
async def test_run_query_published_version_uses_injected_loader(monkeypatch, tmp_path: Path):
    """When a loader is supplied, the on-disk tree is ignored — exercises
    the same seam the SaaS backend uses to feed
    ``visual_dashboard_versions`` snapshots into render+execute."""
    # Seed an on-disk dashboard with a sentinel SQL that would leak into
    # the rendered output if the on-disk path was hit by mistake.
    dashboard_dir = tmp_path / "dashboards" / "demo"
    (dashboard_dir / "queries").mkdir(parents=True, exist_ok=True)
    (dashboard_dir / "queries" / "by_region.sql.j2").write_text(
        "SELECT 'LOCAL_LEAKED' AS sentinel;\n", encoding="utf-8"
    )
    (dashboard_dir / "queries" / "by_region.params.json").write_text(json.dumps(_SAMPLE_META), encoding="utf-8")

    loader_calls: list = []

    async def _loader(version: int):
        from datus.api.models.base_models import Result

        loader_calls.append(version)
        return Result(success=True, data=(_SAMPLE_SQL_J2, json.dumps(_SAMPLE_META)))

    captured: dict = {}
    _patch_executor(monkeypatch, captured=captured)

    result = await DashboardService(agent_config=MagicMock()).run_query(
        project_files_root=tmp_path,
        dashboard_slug="demo",
        query_slug="by_region",
        params={"region": "APAC"},
        published_version=2,
        published_template_loader=_loader,
    )

    assert result.success is True
    assert loader_calls == [2]
    # The on-disk sentinel must NOT appear — confirms the loader's output
    # won the source-selection.
    assert "LOCAL_LEAKED" not in captured["sql"]
    assert "APAC" in captured["sql"]


# ---------------------------------------------------------------------------
# _coerce_param_value — type coercion for one declared param
# ---------------------------------------------------------------------------


def _decl(name: str, type_: str, required: bool = True) -> TemplateParamDecl:
    return TemplateParamDecl(name=name, type=type_, required=required)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "type_, raw, expected",
    [
        ("string", "hello", "hello"),
        ("integer", 42, 42),
        ("integer", "-7", -7),
        ("number", 3.14, 3.14),
        ("number", 1, 1),
        ("number", "2.5", 2.5),
        ("boolean", True, True),
        ("boolean", False, False),
        ("date", "2026-05-28", "2026-05-28"),
    ],
)
def test_coerce_param_value_scalar_happy_paths(type_, raw, expected):
    assert _coerce_param_value(_decl("p", type_), raw) == expected


@pytest.mark.parametrize(
    "type_, raw",
    [
        ("string", 1),
        ("integer", True),  # bool must not pass as int
        ("integer", "abc"),
        ("number", True),
        ("number", "not-a-number"),
        ("number", object()),
        ("boolean", 1),
        ("date", "2026/05/28"),
        ("date", 20260528),
    ],
)
def test_coerce_param_value_scalar_rejects_bad_types(type_, raw):
    with pytest.raises(ValueError):
        _coerce_param_value(_decl("p", type_), raw)


def test_coerce_param_value_array_coerces_each_element():
    coerced = _coerce_param_value(_decl("ids", "integer[]"), ["1", 2, "3"])
    assert coerced == [1, 2, 3]


def test_coerce_param_value_array_rejects_non_list():
    with pytest.raises(ValueError, match="expected array"):
        _coerce_param_value(_decl("ids", "integer[]"), "1,2,3")


# ---------------------------------------------------------------------------
# _validate_params — full request payload against the declared params
# ---------------------------------------------------------------------------


def test_validate_params_returns_coerced_copy():
    decls = [_decl("region", "string"), _decl("count", "integer")]
    coerced = _validate_params(decls, {"region": "APAC", "count": "10"})
    assert coerced == {"region": "APAC", "count": 10}


def test_validate_params_rejects_unknown_param():
    with pytest.raises(ValueError, match="unknown params"):
        _validate_params([_decl("region", "string")], {"region": "APAC", "ghost": 1})


def test_validate_params_rejects_missing_required():
    decls = [_decl("region", "string"), _decl("count", "integer")]
    with pytest.raises(ValueError, match="missing required params"):
        _validate_params(decls, {"region": "APAC"})


def test_validate_params_required_null_rejected():
    """Supplying a required param explicitly as null must fail before render."""
    decls = [_decl("region", "string", required=True)]
    with pytest.raises(ValueError, match="missing required params"):
        _validate_params(decls, {"region": None})


def test_validate_params_optional_null_is_dropped():
    """Optional + None passes coercion (caller may render the absence-of-value
    branch of the Jinja template)."""
    decls = [_decl("region", "string", required=False)]
    coerced = _validate_params(decls, {"region": None})
    assert coerced == {}


def test_validate_params_wraps_per_param_coercion_error():
    """Per-param coercion failures bubble up with the param name attached so
    the wire error tells the client which filter to fix."""
    decls = [_decl("count", "integer")]
    with pytest.raises(ValueError, match="param 'count'"):
        _validate_params(decls, {"count": "not-a-number"})


# ---------------------------------------------------------------------------
# run_query — error branches around template / params / execution
# ---------------------------------------------------------------------------


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


@pytest.mark.asyncio
async def test_run_query_template_corrupt_returns_template_corrupt(tmp_path: Path):
    """``.params.json`` that's not valid JSON → TEMPLATE_CORRUPT (not silently
    swallowed). Caller can surface the parse error to the UI."""
    dashboard_dir = tmp_path / "dashboards" / "demo"
    queries = dashboard_dir / "queries"
    queries.mkdir(parents=True)
    (queries / "q.sql.j2").write_text("SELECT 1\n", encoding="utf-8")
    (queries / "q.params.json").write_text("{not-json", encoding="utf-8")

    result = await DashboardService(agent_config=MagicMock()).run_query(
        project_files_root=tmp_path,
        dashboard_slug="demo",
        query_slug="q",
        params={},
    )

    assert result.success is False
    assert result.errorCode == "TEMPLATE_CORRUPT"


@pytest.mark.asyncio
async def test_run_query_invalid_param_value_returns_invalid_params(tmp_path: Path):
    """A param value the declared type can't coerce → INVALID_PARAMS, not
    a downstream render or execution error."""
    _write_dashboard(tmp_path)

    result = await DashboardService(agent_config=MagicMock()).run_query(
        project_files_root=tmp_path,
        dashboard_slug="demo",
        query_slug="by_region",
        params={"region": 42},  # declared as string
    )

    assert result.success is False
    assert result.errorCode == "INVALID_PARAMS"


@pytest.mark.asyncio
async def test_run_query_render_error_returns_template_render_error(tmp_path: Path, monkeypatch):
    """A Jinja2 render failure surfaces TEMPLATE_RENDER_ERROR — not a
    QUERY_EXECUTION_FAILED — so callers know the template, not the data,
    is the problem."""
    _write_dashboard(tmp_path)

    import datus.api.services.dashboard_service as service_mod

    def _boom(sql_template, decls, params):
        raise ValueError("synthetic render failure")

    monkeypatch.setattr(service_mod, "render_dashboard_template", _boom)

    result = await DashboardService(agent_config=MagicMock()).run_query(
        project_files_root=tmp_path,
        dashboard_slug="demo",
        query_slug="by_region",
        params={"region": "APAC"},
    )

    assert result.success is False
    assert result.errorCode == "TEMPLATE_RENDER_ERROR"


@pytest.mark.asyncio
async def test_run_query_datasource_resolution_failure_returns_datasource_unavailable(tmp_path: Path, monkeypatch):
    """``DBFuncTool._get_connector`` raising → DATASOURCE_UNAVAILABLE.
    Distinct error code so the UI can prompt the user to fix the binding
    rather than retry the query."""
    _write_dashboard(tmp_path)

    class _Broken:
        def __init__(self, *, agent_config, sub_agent_name):
            pass

        def _get_connector(self, datasource):
            raise RuntimeError(f"no datasource named {datasource!r}")

    import datus.tools.func_tool as func_tool_mod

    monkeypatch.setattr(func_tool_mod, "DBFuncTool", _Broken)

    result = await DashboardService(agent_config=MagicMock()).run_query(
        project_files_root=tmp_path,
        dashboard_slug="demo",
        query_slug="by_region",
        params={"region": "APAC"},
    )

    assert result.success is False
    assert result.errorCode == "DATASOURCE_UNAVAILABLE"


@pytest.mark.asyncio
async def test_run_query_connector_raises_returns_query_execution_failed(tmp_path: Path, monkeypatch):
    _write_dashboard(tmp_path)
    _patch_failing_executor(monkeypatch, exc=RuntimeError("connection lost"))

    result = await DashboardService(agent_config=MagicMock()).run_query(
        project_files_root=tmp_path,
        dashboard_slug="demo",
        query_slug="by_region",
        params={"region": "APAC"},
    )

    assert result.success is False
    assert result.errorCode == "QUERY_EXECUTION_FAILED"


@pytest.mark.asyncio
async def test_run_query_connector_returns_unsuccessful_envelope(tmp_path: Path, monkeypatch):
    """``execute_query`` returns ``success=False`` (e.g. SQL error caught by
    the connector) → QUERY_EXECUTION_FAILED."""
    _write_dashboard(tmp_path)

    class _Bad:
        success = False
        error = "syntax error near 'SELEC'"

    _patch_failing_executor(monkeypatch, exec_result=_Bad())

    result = await DashboardService(agent_config=MagicMock()).run_query(
        project_files_root=tmp_path,
        dashboard_slug="demo",
        query_slug="by_region",
        params={"region": "APAC"},
    )

    assert result.success is False
    assert result.errorCode == "QUERY_EXECUTION_FAILED"
    assert "syntax error" in (result.errorMessage or "")


@pytest.mark.asyncio
async def test_run_query_rejects_non_list_sql_return(tmp_path: Path, monkeypatch):
    """A connector that returns ``sql_return`` as something other than a list
    means the protocol is broken — fail hard, don't try to recover."""
    _write_dashboard(tmp_path)

    class _Bad:
        success = True
        sql_return = {"rows": []}  # not a list

    _patch_failing_executor(monkeypatch, exec_result=_Bad())

    result = await DashboardService(agent_config=MagicMock()).run_query(
        project_files_root=tmp_path,
        dashboard_slug="demo",
        query_slug="by_region",
        params={"region": "APAC"},
    )

    assert result.success is False
    assert result.errorCode == "QUERY_EXECUTION_FAILED"


@pytest.mark.asyncio
async def test_run_query_rejects_non_dict_row(tmp_path: Path, monkeypatch):
    """Each row must be a dict (column→value); rejecting positional lists
    keeps the wire schema unambiguous."""
    _write_dashboard(tmp_path)

    class _Bad:
        success = True
        sql_return = [["APAC", 100]]  # positional, not dict — must fail

    _patch_failing_executor(monkeypatch, exec_result=_Bad())

    result = await DashboardService(agent_config=MagicMock()).run_query(
        project_files_root=tmp_path,
        dashboard_slug="demo",
        query_slug="by_region",
        params={"region": "APAC"},
    )

    assert result.success is False
    assert result.errorCode == "QUERY_EXECUTION_FAILED"


# ---------------------------------------------------------------------------
# get_detail — corruption + bundle-shape error branches
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_detail_corrupt_manifest_returns_not_found(tmp_path: Path):
    """``manifest.json`` exists but isn't valid JSON / schema → callers see
    DASHBOARD_NOT_FOUND with a parse-error reason rather than crashing the
    request."""
    dashboard_dir = tmp_path / "dashboards" / "demo"
    (dashboard_dir / "render").mkdir(parents=True)
    (dashboard_dir / "render" / "app.jsx").write_text(_SAMPLE_APP_JSX, encoding="utf-8")
    (dashboard_dir / "manifest.json").write_text("{not-json", encoding="utf-8")

    result = await DashboardService(agent_config=None).get_detail(
        project_files_root=tmp_path,
        dashboard_slug="demo",
    )

    assert result.success is False
    assert result.errorCode == "DASHBOARD_NOT_FOUND"
    assert "corrupt" in (result.errorMessage or "").lower()


@pytest.mark.asyncio
async def test_get_detail_skips_malformed_template_meta(tmp_path: Path):
    """A junk ``.params.json`` sibling must not abort the detail call — it
    just drops out of the parsed ``templates`` list (the file itself still
    surfaces in ``files`` so the IDE can show the parse error)."""
    dashboard_dir = _write_dashboard(tmp_path)
    bad_meta = dashboard_dir / "queries" / "broken.params.json"
    bad_meta.write_text("{not-json", encoding="utf-8")
    # The sibling .sql.j2 keeps the pair shape consistent with what the
    # walker would normally see; the walker still surfaces the file in
    # ``files`` even though the meta parse fails.
    (dashboard_dir / "queries" / "broken.sql.j2").write_text("SELECT 1\n", encoding="utf-8")

    result = await DashboardService(agent_config=None).get_detail(
        project_files_root=tmp_path,
        dashboard_slug="demo",
    )

    assert result.success is True
    template_slugs = [t.slug for t in result.data.templates]
    assert "broken" not in template_slugs
    assert "by_region" in template_slugs
