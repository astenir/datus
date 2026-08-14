# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Downstream ACL and locked-edit coverage for dashboard artifact tools."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from datus.tools.func_tool import DashboardArtifactTools, DashboardFilesystemFuncTool, DBFuncTool
from tests.unit_tests.tools.func_tool.test_dashboard_artifact_tools import (
    _start_new_dashboard,
)
from tests.unit_tests.tools.func_tool.test_dashboard_artifact_tools import (
    db_func_tool as db_func_tool,
)
from tests.unit_tests.tools.func_tool.test_dashboard_artifact_tools import (
    project_root as project_root,
)
from tests.unit_tests.tools.func_tool.test_dashboard_artifact_tools import (
    sqlite_db as sqlite_db,
)


class MemoryArtifactAclStore:
    def __init__(self):
        self.acls = {}

    async def get_acl(self, *, artifact_type: str, slug: str):
        key = (artifact_type, slug)
        if key not in self.acls:
            raise KeyError(key)
        return dict(self.acls[key])

    async def put_acl(self, *, artifact_type: str, slug: str, acl: dict):
        self.acls[(artifact_type, slug)] = dict(acl)
        return dict(acl)


class LoopBoundArtifactAclStore(MemoryArtifactAclStore):
    def __init__(self):
        super().__init__()
        self.loop = None

    def _assert_current_loop(self):
        import asyncio

        loop = asyncio.get_running_loop()
        if self.loop is None:
            self.loop = loop
        elif self.loop is not loop:
            raise RuntimeError("artifact ACL store used from the wrong event loop")

    async def get_acl(self, *, artifact_type: str, slug: str):
        self._assert_current_loop()
        return await super().get_acl(artifact_type=artifact_type, slug=slug)

    async def put_acl(self, *, artifact_type: str, slug: str, acl: dict):
        self._assert_current_loop()
        return await super().put_acl(artifact_type=artifact_type, slug=slug, acl=acl)


class TestStartNewDashboard:
    def test_writes_default_private_acl_when_enterprise_context_is_available(
        self, db_func_tool: DBFuncTool, project_root: Path
    ):
        store = MemoryArtifactAclStore()
        agent_config = SimpleNamespace(
            project_root=str(project_root),
            _request_user_id="creator-1",
            _artifact_acl_store=store,
        )
        tools = DashboardArtifactTools(agent_config=agent_config, db_func_tool=db_func_tool)

        result = _start_new_dashboard(
            tools,
            slug="private_dashboard",
            name="private dashboard",
            description="Dashboard with default private ACL.",
        )

        assert result.success == 1, result.error
        assert store.acls[("dashboard", "private_dashboard")] == {
            "owner_user_id": "creator-1",
            "visibility": "private",
            "allowed_roles": [],
            "allowed_user_ids": [],
            "datasources": [],
        }

    @pytest.mark.asyncio
    async def test_writes_default_private_acl_on_current_event_loop(self, db_func_tool: DBFuncTool, project_root: Path):
        store = LoopBoundArtifactAclStore()
        await store.put_acl(
            artifact_type="dashboard",
            slug="seed",
            acl={"owner_user_id": "creator-1", "visibility": "private"},
        )
        agent_config = SimpleNamespace(
            project_root=str(project_root),
            _request_user_id="creator-1",
            _artifact_acl_store=store,
        )
        tools = DashboardArtifactTools(agent_config=agent_config, db_func_tool=db_func_tool)

        result = await tools.start_new_dashboard(
            slug="loop_safe_dashboard",
            name="loop safe dashboard",
            description="Dashboard whose ACL store must stay on this event loop.",
        )

        assert result.success == 1, result.error
        assert store.acls[("dashboard", "loop_safe_dashboard")]["owner_user_id"] == "creator-1"

    def test_locked_edit_session_rejects_new_dashboard(self, db_func_tool: DBFuncTool, project_root: Path):
        tools = DashboardArtifactTools(
            agent_config=SimpleNamespace(project_root=str(project_root)),
            db_func_tool=db_func_tool,
            locked_dashboard_slug="existing_demo",
            allow_create=False,
        )

        result = _start_new_dashboard(
            tools,
            slug="new_demo",
            name="new demo",
            description="Should not be created from a locked edit session.",
        )

        assert result.success == 0
        assert "locked to dashboards/existing_demo" in (result.error or "")
        assert not (project_root / "dashboards" / "new_demo").exists()


class TestBindExistingDashboard:
    def test_locked_edit_session_allows_only_locked_slug(self, db_func_tool: DBFuncTool, project_root: Path):
        for slug in ("existing_demo", "other_demo"):
            existing = project_root / "dashboards" / slug
            (existing / "queries").mkdir(parents=True)
            (existing / "render").mkdir()
            (existing / "render" / "app.jsx").write_text("export default function D() { return null; }\n")
        tools = DashboardArtifactTools(
            agent_config=SimpleNamespace(project_root=str(project_root)),
            db_func_tool=db_func_tool,
            locked_dashboard_slug="existing_demo",
            allow_create=False,
        )

        rejected = tools.bind_existing_dashboard("other_demo")
        accepted = tools.bind_existing_dashboard("existing_demo")

        assert rejected.success == 0
        assert "locked to dashboards/existing_demo" in (rejected.error or "")
        assert accepted.success == 1, accepted.error
        assert tools.dashboard_slug == "existing_demo"

    def test_bind_bumps_manifest_updated_at_without_losing_fields(self, db_func_tool: DBFuncTool, project_root: Path):
        existing = project_root / "dashboards" / "existing_demo"
        (existing / "render").mkdir(parents=True)
        (existing / "render" / "app.jsx").write_text("export default function D() { return null; }\n")
        (existing / "manifest.json").write_text(
            json.dumps(
                {
                    "slug": "existing_demo",
                    "name": "Existing Demo",
                    "description": "An existing dashboard.",
                    "kind": "dashboard",
                    "created_at": "2026-01-01T00:00:00Z",
                    "datasources": ["finance"],
                }
            ),
            encoding="utf-8",
        )
        tools = DashboardArtifactTools(
            agent_config=SimpleNamespace(project_root=str(project_root)),
            db_func_tool=db_func_tool,
        )

        result = tools.bind_existing_dashboard("existing_demo")

        assert result.success == 1, result.error
        assert "manifest_warning" not in result.result
        manifest = json.loads((existing / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["created_at"] == "2026-01-01T00:00:00Z"
        assert manifest["datasources"] == ["finance"]
        assert manifest["updated_at"].endswith("Z")
        assert manifest["updated_at"] > "2026-01-01T00:00:00Z"

    def test_locked_edit_session_can_bind_incomplete_dashboard_dir(
        self,
        db_func_tool: DBFuncTool,
        project_root: Path,
    ):
        incomplete = project_root / "dashboards" / "existing_demo"
        incomplete.mkdir(parents=True)
        tools = DashboardArtifactTools(
            agent_config=SimpleNamespace(project_root=str(project_root)),
            db_func_tool=db_func_tool,
            locked_dashboard_slug="existing_demo",
            allow_create=False,
        )

        result = tools.bind_existing_dashboard("existing_demo")

        assert result.success == 1, result.error
        assert result.result["mode"] == "edit"
        assert "bootstrap_warning" in result.result
        assert tools.dashboard_slug == "existing_demo"
        assert (incomplete / "manifest.json").is_file()
        assert (incomplete / "render").is_dir()
        assert (incomplete / "queries").is_dir()

    def test_locked_edit_session_repairs_missing_manifest_after_bind(
        self,
        db_func_tool: DBFuncTool,
        project_root: Path,
    ):
        incomplete = project_root / "dashboards" / "existing_demo"
        (incomplete / "render").mkdir(parents=True)
        (incomplete / "render" / "app.jsx").write_text("export default function D() { return null; }\n")
        tools = DashboardArtifactTools(
            agent_config=SimpleNamespace(project_root=str(project_root)),
            db_func_tool=db_func_tool,
            locked_dashboard_slug="existing_demo",
            allow_create=False,
        )

        result = tools.bind_existing_dashboard("existing_demo")

        assert result.success == 1, result.error
        assert result.result["manifest_path"] == "dashboards/existing_demo/manifest.json"
        assert "manifest.json" in result.result["bootstrap_warning"]
        assert (incomplete / "manifest.json").is_file()
        assert (incomplete / "queries").is_dir()
        assert (incomplete / "analysis").is_dir()
        fs = DashboardFilesystemFuncTool(root_path=str(project_root), locked_artifact_slug="existing_demo")
        read_manifest = fs.read_file("dashboards/existing_demo/manifest.json")
        tree = fs.glob("dashboards/existing_demo/**/*")
        assert read_manifest.success == 1, read_manifest.error
        assert "dashboards/existing_demo/manifest.json" in tree.result["files"]
        assert "dashboards/existing_demo/render/app.jsx" in tree.result["files"]


class TestDashboardFilesystemFuncTool:
    def test_locked_edit_session_bypasses_generic_artifact_protection(self, project_root: Path):
        for slug in ("allowed", "other"):
            render = project_root / "dashboards" / slug / "render"
            render.mkdir(parents=True)
            (project_root / "dashboards" / slug / "manifest.json").write_text(
                f'{{"slug":"{slug}","name":"{slug}","description":"demo","kind":"dashboard",'
                '"created_at":"2026-07-08T00:00:00Z"}\n',
                encoding="utf-8",
            )
            (render / "app.jsx").write_text("export default function App() { return null; }\n", encoding="utf-8")
        fs = DashboardFilesystemFuncTool(
            root_path=str(project_root),
            current_node="dashboard_edit__dynamic",
            protect_artifact_paths=True,
            locked_artifact_slug="allowed",
        )

        manifest = fs.read_file("dashboards/allowed/manifest.json")
        tree = fs.glob("dashboards/*/manifest.json")

        assert manifest.success == 1, manifest.error
        assert tree.success == 1
        assert tree.result["files"] == ["dashboards/allowed/manifest.json"]
