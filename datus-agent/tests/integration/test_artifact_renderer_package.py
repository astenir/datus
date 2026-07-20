from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PATCHED_RENDERER_SHA256 = "4c8c89cc47578b80b8732a180f4a245655c00429e9f0ba2b7d6a0c6f57561745"
RENDERER_PATH = "datus/agent/node/visual_artifact/vendor/web_artifact_render_dist/index.umd.js"
TEMPLATE_PATH = "datus/agent/node/visual_artifact/templates/dashboard_index.html"


def _copy_package_source(destination: Path) -> None:
    destination.mkdir()
    for filename in ("pyproject.toml", "README.md", "LICENSE"):
        shutil.copy2(PROJECT_ROOT / filename, destination / filename)
    for dirname in ("conf", "datus", "datus_enterprise"):
        shutil.copytree(
            PROJECT_ROOT / dirname,
            destination / dirname,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )


def _seed_dashboard(project_root: Path) -> None:
    dashboard_dir = project_root / "dashboards" / "package_check"
    render_dir = dashboard_dir / "render"
    render_dir.mkdir(parents=True)
    (render_dir / "app.jsx").write_text(
        "export default function App() { return null; }\n",
        encoding="utf-8",
    )


@pytest.mark.integration
def test_wheel_ships_patched_renderer_and_renders_from_installed_package(tmp_path: Path):
    source_dir = tmp_path / "source"
    wheel_dir = tmp_path / "wheel"
    _copy_package_source(source_dir)

    build_result = subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--no-isolation", "--outdir", str(wheel_dir)],
        cwd=source_dir,
        check=False,
        capture_output=True,
        text=True,
    )
    assert build_result.returncode == 0, build_result.stdout + build_result.stderr

    wheels = list(wheel_dir.glob("*.whl"))
    assert len(wheels) == 1
    with zipfile.ZipFile(wheels[0]) as wheel:
        names = set(wheel.namelist())
        assert TEMPLATE_PATH in names
        assert RENDERER_PATH in names
        assert "datus/agent/node/visual_artifact/vendor/web_artifact_render_dist/index.css" in names
        renderer = wheel.read(RENDERER_PATH)
        assert hashlib.sha256(renderer).hexdigest() == PATCHED_RENDERER_SHA256
        assert b"DatusPostMessageQueryProvider" in renderer
        wheel.extractall(tmp_path / "site-packages")

    runtime_root = tmp_path / "runtime"
    _seed_dashboard(runtime_root)
    script = """
import base64
import hashlib
import json
import re
from pathlib import Path

import datus.agent.node.visual_artifact.dashboard_html_renderer as renderer

html = renderer.render_dashboard_html_str(
    project_root=Path.cwd(),
    dashboard_slug="package_check",
)
inline_renderer = re.search(r'src="data:text/javascript;base64,([^"]+)"', html)
print(json.dumps({
    "module": renderer.__file__,
    "has_transport": "queryTransport: window.__DATUS_ARTIFACT_QUERY_TRANSPORT__" in html,
    "inline_renderer_sha256": hashlib.sha256(base64.b64decode(inline_renderer.group(1))).hexdigest(),
    "has_http_fallback": renderer.DEFAULT_QUERY_ENDPOINT in html,
}))
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(tmp_path / "site-packages")
    env["PYTHONNOUSERSITE"] = "1"
    render_result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=runtime_root,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert render_result.returncode == 0, render_result.stdout + render_result.stderr
    result = json.loads(render_result.stdout.strip().splitlines()[-1])
    assert Path(result["module"]).is_relative_to(tmp_path / "site-packages")
    assert result["has_transport"] is True
    assert result["inline_renderer_sha256"] == PATCHED_RENDERER_SHA256
    assert result["has_http_fallback"] is True
