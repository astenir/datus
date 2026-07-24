"""Downstream offline report-rendering coverage."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from datus.api.services.report_service import ReportService


def _seed_report(report_dir: Path) -> None:
    render_dir = report_dir / "render"
    render_dir.mkdir(parents=True)
    (render_dir / "app.jsx").write_text(
        "export default function Report() { return null; }\n",
        encoding="utf-8",
    )


def _seed_dist(dist_dir: Path) -> None:
    dist_dir.mkdir(parents=True)
    (dist_dir / "index.css").write_text("/* offline css */", encoding="utf-8")
    (dist_dir / "index.umd.js").write_text("/* offline js */", encoding="utf-8")


@pytest.mark.asyncio
async def test_render_html_uses_configured_report_dist(tmp_path: Path):
    report_dir = tmp_path / "reports" / "html_offline"
    _seed_report(report_dir)
    dist_dir = tmp_path / "vendor" / "web-artifact-render" / "dist"
    _seed_dist(dist_dir)
    agent_config = SimpleNamespace(
        agentic_nodes={
            "gen_visual_report": {
                "report_dist": str(dist_dir),
            },
        },
    )

    result = await ReportService(agent_config=agent_config).render_html(
        project_files_root=tmp_path,
        report_slug="html_offline",
    )

    assert result.success is True
    assert "data:text/css;base64," in result.data
    assert "data:text/javascript;base64," in result.data
    assert "https://unpkg.com/" not in result.data
    assert not (report_dir / "_assets").exists()
