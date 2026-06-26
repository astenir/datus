import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from datus.api.auth.context import AppContext
from datus.api.service import create_app
from datus.api.services.dashboard_service import DashboardService
from datus.api.services.report_service import ReportService
from datus_enterprise.api import artifact_routes


def _svc(tmp_path: Path):
    agent_config = SimpleNamespace(project_root=str(tmp_path))
    return SimpleNamespace(
        agent_config=agent_config,
        dashboard=DashboardService(agent_config=agent_config),
        report=ReportService(agent_config=agent_config),
    )


def _write_manifest(root: Path, kind: str, slug: str) -> None:
    base = root / f"{kind}s" / slug
    (base / "render").mkdir(parents=True, exist_ok=True)
    (base / "render" / "app.jsx").write_text("export default function App() { return null; }\n", encoding="utf-8")
    (base / "manifest.json").write_text(
        json.dumps(
            {
                "slug": slug,
                "name": slug,
                "description": "Test artifact",
                "kind": kind,
                "created_at": "2026-01-01T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_report_list_filters_through_enterprise_acl(tmp_path: Path):
    _write_manifest(tmp_path, "report", "visible")
    _write_manifest(tmp_path, "report", "hidden")
    ctx = AppContext(principal={"artifact_acl": {"report": ["visible"]}})

    result = await artifact_routes.list_reports(_svc(tmp_path), ctx)

    assert result.success is True
    assert [item.slug for item in result.data] == ["visible"]


@pytest.mark.asyncio
async def test_dashboard_list_filters_through_enterprise_acl(tmp_path: Path):
    _write_manifest(tmp_path, "dashboard", "visible")
    _write_manifest(tmp_path, "dashboard", "hidden")
    ctx = AppContext(principal={"artifact_acl": {"dashboard": ["hidden"]}})

    result = await artifact_routes.list_dashboards(_svc(tmp_path), ctx)

    assert result.success is True
    assert [item.slug for item in result.data] == ["hidden"]


def test_enterprise_artifact_routes_expose_resource_paths_only():
    args = argparse.Namespace(config="", datasource="default", output_dir="./output", log_level="INFO")
    app = create_app(args)
    route_paths = {route.path for route in app.routes if hasattr(route, "path")}

    assert "/api/v1/reports" in route_paths
    assert "/api/v1/reports/{slug}/html" in route_paths
    assert "/api/v1/dashboards" in route_paths
    assert "/api/v1/dashboards/{slug}/html" in route_paths
    assert "/api/v1/report/list" not in route_paths
    assert "/api/v1/report/html" not in route_paths
    assert "/api/v1/dashboard/list" not in route_paths
    assert "/api/v1/dashboard/html" not in route_paths
