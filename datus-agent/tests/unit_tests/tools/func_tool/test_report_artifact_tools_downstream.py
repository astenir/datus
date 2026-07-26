# Copyright 2025-present DatusAI, Inc.
# Licensed under the Apache License, Version 2.0.
# See http://www.apache.org/licenses/LICENSE-2.0 for details.

"""Downstream ACL and locked-edit coverage for report artifact tools."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from datus.tools.func_tool import DBFuncTool, ReportArtifactTools, ReportFilesystemFuncTool
from tests.unit_tests.tools.func_tool.test_report_artifact_tools import (
    _start_new_report,
)
from tests.unit_tests.tools.func_tool.test_report_artifact_tools import (
    db_func_tool as db_func_tool,
)
from tests.unit_tests.tools.func_tool.test_report_artifact_tools import (
    project_root as project_root,
)
from tests.unit_tests.tools.func_tool.test_report_artifact_tools import (
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


class TestStartNewReport:
    def test_writes_default_private_acl_when_enterprise_context_is_available(
        self, db_func_tool: DBFuncTool, project_root: Path
    ):
        store = MemoryArtifactAclStore()
        agent_config = SimpleNamespace(
            project_root=str(project_root),
            _request_user_id="creator-1",
            _artifact_acl_store=store,
        )
        tools = ReportArtifactTools(agent_config=agent_config, db_func_tool=db_func_tool)

        result = _start_new_report(
            tools,
            slug="private_report",
            name="private report",
            description="Report with default private ACL.",
        )

        assert result.success == 1, result.error
        assert store.acls[("report", "private_report")] == {
            "owner_user_id": "creator-1",
            "visibility": "private",
            "allowed_roles": [],
            "allowed_user_ids": [],
            "datasources": [],
        }

    def test_locked_edit_session_rejects_new_report(self, db_func_tool: DBFuncTool, project_root: Path):
        tools = ReportArtifactTools(
            agent_config=SimpleNamespace(project_root=str(project_root)),
            db_func_tool=db_func_tool,
            locked_report_slug="existing_demo",
            allow_create=False,
        )

        result = _start_new_report(
            tools,
            slug="new_demo",
            name="new demo",
            description="Should not be created from a locked edit session.",
        )

        assert result.success == 0
        assert "locked to reports/existing_demo" in (result.error or "")
        assert not (project_root / "reports" / "new_demo").exists()

    @pytest.mark.asyncio
    async def test_writes_default_private_acl_on_current_event_loop(self, db_func_tool: DBFuncTool, project_root: Path):
        store = LoopBoundArtifactAclStore()
        await store.put_acl(
            artifact_type="report",
            slug="seed",
            acl={"owner_user_id": "creator-1", "visibility": "private"},
        )
        agent_config = SimpleNamespace(
            project_root=str(project_root),
            _request_user_id="creator-1",
            _artifact_acl_store=store,
        )
        tools = ReportArtifactTools(agent_config=agent_config, db_func_tool=db_func_tool)

        result = await tools.start_new_report(
            slug="loop_safe_report",
            name="loop safe report",
            description="Report whose ACL store must stay on this event loop.",
        )

        assert result.success == 1, result.error
        assert store.acls[("report", "loop_safe_report")]["owner_user_id"] == "creator-1"


class TestBindExistingReport:
    def test_locked_edit_session_allows_only_locked_slug(self, db_func_tool: DBFuncTool, project_root: Path):
        for slug in ("existing_demo", "other_demo"):
            existing = project_root / "reports" / slug
            (existing / "queries").mkdir(parents=True)
            (existing / "render").mkdir()
            (existing / "render" / "app.jsx").write_text("export default function R() { return null; }\n")
        tools = ReportArtifactTools(
            agent_config=SimpleNamespace(project_root=str(project_root)),
            db_func_tool=db_func_tool,
            locked_report_slug="existing_demo",
            allow_create=False,
        )

        rejected = tools.bind_existing_report("other_demo")
        accepted = tools.bind_existing_report("existing_demo")

        assert rejected.success == 0
        assert "locked to reports/existing_demo" in (rejected.error or "")
        assert accepted.success == 1, accepted.error
        assert tools.report_slug == "existing_demo"

    def test_locked_edit_session_can_bind_incomplete_report_dir(self, db_func_tool: DBFuncTool, project_root: Path):
        incomplete = project_root / "reports" / "existing_demo"
        incomplete.mkdir(parents=True)
        tools = ReportArtifactTools(
            agent_config=SimpleNamespace(project_root=str(project_root)),
            db_func_tool=db_func_tool,
            locked_report_slug="existing_demo",
            allow_create=False,
        )

        result = tools.bind_existing_report("existing_demo")

        assert result.success == 1, result.error
        assert result.result["mode"] == "edit"
        assert "bootstrap_warning" in result.result
        assert tools.report_slug == "existing_demo"
        assert (incomplete / "manifest.json").is_file()
        assert (incomplete / "render").is_dir()
        assert (incomplete / "queries").is_dir()

    def test_locked_edit_session_repairs_missing_manifest_after_bind(
        self,
        db_func_tool: DBFuncTool,
        project_root: Path,
    ):
        incomplete = project_root / "reports" / "existing_demo"
        (incomplete / "render").mkdir(parents=True)
        (incomplete / "render" / "app.jsx").write_text("export default function R() { return null; }\n")
        tools = ReportArtifactTools(
            agent_config=SimpleNamespace(project_root=str(project_root)),
            db_func_tool=db_func_tool,
            locked_report_slug="existing_demo",
            allow_create=False,
        )

        result = tools.bind_existing_report("existing_demo")

        assert result.success == 1, result.error
        assert result.result["manifest_path"] == "reports/existing_demo/manifest.json"
        assert "manifest.json" in result.result["bootstrap_warning"]
        assert (incomplete / "manifest.json").is_file()
        assert (incomplete / "queries").is_dir()
        assert (incomplete / "analysis").is_dir()
        fs = ReportFilesystemFuncTool(root_path=str(project_root), locked_artifact_slug="existing_demo")
        read_manifest = fs.read_file("reports/existing_demo/manifest.json")
        tree = fs.glob("reports/existing_demo/**/*")
        assert read_manifest.success == 1, read_manifest.error
        assert "reports/existing_demo/manifest.json" in tree.result["files"]
        assert "reports/existing_demo/render/app.jsx" in tree.result["files"]


class TestReportFilesystemFuncTool:
    def test_locked_edit_session_rejects_sibling_report_write(self, project_root: Path):
        (project_root / "reports" / "allowed" / "render").mkdir(parents=True)
        (project_root / "reports" / "other" / "render").mkdir(parents=True)
        fs = ReportFilesystemFuncTool(root_path=str(project_root), locked_artifact_slug="allowed")

        result = fs.write_file("reports/other/render/app.jsx", "export default () => null;\n")

        assert result.success == 0
        assert "locked to reports/allowed" in (result.error or "")
        assert not (project_root / "reports" / "other" / "render" / "app.jsx").exists()

    def test_locked_edit_session_hides_sibling_report_reads_and_globs(self, project_root: Path):
        for slug in ("allowed", "other"):
            render = project_root / "reports" / slug / "render"
            render.mkdir(parents=True)
            (render / "app.jsx").write_text(f"export default function {slug.title()}() {{ return null; }}\n")

        fs = ReportFilesystemFuncTool(root_path=str(project_root), locked_artifact_slug="allowed")

        sibling_read = fs.read_file("reports/other/render/app.jsx")
        glob_result = fs.glob("reports/*/render/app.jsx")

        assert sibling_read.success == 0
        assert glob_result.success == 1
        assert glob_result.result["files"] == ["reports/allowed/render/app.jsx"]

    def test_locked_edit_session_directory_glob_returns_only_locked_report(self, project_root: Path):
        for slug in ("allowed", "other"):
            (project_root / "reports" / slug / "render").mkdir(parents=True)
        fs = ReportFilesystemFuncTool(root_path=str(project_root), locked_artifact_slug="allowed")

        result = fs.glob("reports/*")

        assert result.success == 1
        assert result.result["files"] == ["reports/allowed"]

    def test_unbound_enterprise_create_glob_explains_acl_filtering(self, project_root: Path):
        (project_root / "reports" / "existing" / "render").mkdir(parents=True)
        (project_root / "subject" / "sales").mkdir(parents=True)
        fs = ReportFilesystemFuncTool(
            root_path=str(project_root),
            require_authorized_artifact=True,
        )

        before_bind = fs.glob("reports/*")
        unrelated = fs.glob("subject/*")
        fs.bind_authorized_artifact("existing")
        after_bind = fs.glob("reports/*")

        assert before_bind.success == 1
        assert before_bind.result["files"] == []
        assert before_bind.result["visibility_filtered"] is True
        assert "No report is bound" in before_bind.result["message"]
        assert unrelated.result["files"] == ["subject/sales"]
        assert "visibility_filtered" not in unrelated.result
        assert after_bind.result["files"] == ["reports/existing"]
        assert after_bind.result["visibility_filtered"] is True

    def test_locked_edit_session_bypasses_generic_artifact_protection(self, project_root: Path):
        for slug in ("allowed", "other"):
            render = project_root / "reports" / slug / "render"
            render.mkdir(parents=True)
            (project_root / "reports" / slug / "manifest.json").write_text(
                f'{{"slug":"{slug}","name":"{slug}","description":"demo","kind":"report",'
                '"created_at":"2026-07-08T00:00:00Z"}\n',
                encoding="utf-8",
            )
            (render / "app.jsx").write_text("export default function App() { return null; }\n", encoding="utf-8")
        fs = ReportFilesystemFuncTool(
            root_path=str(project_root),
            current_node="report_edit__dynamic",
            protect_artifact_paths=True,
            locked_artifact_slug="allowed",
        )

        manifest = fs.read_file("reports/allowed/manifest.json")
        tree = fs.glob("reports/*/manifest.json")

        assert manifest.success == 1, manifest.error
        assert tree.success == 1
        assert tree.result["files"] == ["reports/allowed/manifest.json"]
