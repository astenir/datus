"""Enterprise ACL-binding tests shared by visual report/dashboard tools."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from datus.agent.node.base_visual_artifact_agentic_node import BaseVisualArtifactAgenticNode
from datus.tools.func_tool import (
    DashboardArtifactTools,
    DashboardFilesystemFuncTool,
    ReportArtifactTools,
    ReportFilesystemFuncTool,
)


class MemoryArtifactAclStore:
    def __init__(self) -> None:
        self.acls: dict[tuple[str, str], dict] = {}

    async def get_acl(self, *, artifact_type: str, slug: str):
        key = (artifact_type, slug)
        if key not in self.acls:
            raise KeyError(key)
        return dict(self.acls[key])

    async def put_acl(self, *, artifact_type: str, slug: str, acl: dict):
        self.acls[(artifact_type, slug)] = dict(acl)
        return dict(acl)


CASES = [
    pytest.param(
        "dashboard",
        "dashboards",
        DashboardArtifactTools,
        DashboardFilesystemFuncTool,
        "start_new_dashboard",
        "bind_existing_dashboard",
        id="dashboard",
    ),
    pytest.param(
        "report",
        "reports",
        ReportArtifactTools,
        ReportFilesystemFuncTool,
        "start_new_report",
        "bind_existing_report",
        id="report",
    ),
]


def test_enterprise_edit_config_without_acl_marker_fails_closed() -> None:
    node = object.__new__(BaseVisualArtifactAgenticNode)
    node.agent_config = SimpleNamespace(_enterprise_enabled=True)
    node.node_config = {"edit_locked": True, "artifact_slug": "existing"}

    with pytest.raises(ValueError, match="ACL-authorized edit session"):
        node._artifact_access_mode()

    node.node_config["_acl_authorized_artifact_edit"] = True
    assert node._artifact_access_mode() == "edit"


def _seed_artifact(project_root: Path, root_name: str, slug: str) -> None:
    render_dir = project_root / root_name / slug / "render"
    render_dir.mkdir(parents=True)
    (project_root / root_name / slug / "manifest.json").write_text("{}\n", encoding="utf-8")
    (render_dir / "app.jsx").write_text("export default function App() {}\n", encoding="utf-8")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("artifact_type", "root_name", "tools_cls", "filesystem_cls", "start_name", "bind_name"),
    CASES,
)
async def test_enterprise_create_binds_filesystem_only_after_private_acl(
    tmp_path: Path,
    artifact_type,
    root_name,
    tools_cls,
    filesystem_cls,
    start_name,
    bind_name,
):
    project_root = tmp_path / "project"
    project_root.mkdir()
    _seed_artifact(project_root, root_name, "other_user")
    store = MemoryArtifactAclStore()
    agent_config = SimpleNamespace(
        project_root=str(project_root),
        _enterprise_enabled=True,
        _request_user_id="alice",
        _artifact_acl_store=store,
    )
    filesystem = filesystem_cls(root_path=str(project_root), require_authorized_artifact=True)
    tools = tools_cls(
        agent_config=agent_config,
        db_func_tool=object(),
        allow_bind_existing=False,
        on_artifact_authorized=filesystem.bind_authorized_artifact,
    )

    tool_names = {tool.name for tool in tools.available_tools()}
    assert start_name in tool_names
    assert bind_name not in tool_names
    assert filesystem.write_file(f"{root_name}/alice_view/render/app.jsx", "before ACL").success == 0
    assert filesystem.read_file(f"{root_name}/other_user/manifest.json").success == 0

    result = await getattr(tools, start_name)(
        slug="alice_view",
        name="Alice view",
        description="Private visual artifact owned by Alice.",
    )

    assert result.success == 1, result.error
    assert store.acls[(artifact_type, "alice_view")]["owner_user_id"] == "alice"
    assert filesystem.write_file(
        f"{root_name}/alice_view/render/app.jsx", "export default function App() {}\n"
    ).success == 1
    assert filesystem.write_file("unrelated.txt", "not an artifact").success == 0
    assert filesystem.write_file(f"{root_name}/other_user/render/app.jsx", "cross-user").success == 0
    assert filesystem.read_file(f"{root_name}/other_user/manifest.json").success == 0
    visible = filesystem.glob(f"{root_name}/*/manifest.json")
    assert visible.success == 1
    assert visible.result["files"] == [f"{root_name}/alice_view/manifest.json"]

    bind_result = getattr(tools, bind_name)("other_user")
    assert bind_result.success == 0
    assert "ACL-authorized edit session" in (bind_result.error or "")
    second_create = await getattr(tools, start_name)(
        slug="alice_second",
        name="Second",
        description="A second artifact must not be created in one bound request.",
    )
    assert second_create.success == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("artifact_type", "root_name", "tools_cls", "filesystem_cls", "start_name", "bind_name"),
    CASES,
)
async def test_enterprise_create_without_acl_store_rolls_back(
    tmp_path: Path,
    artifact_type,
    root_name,
    tools_cls,
    filesystem_cls,
    start_name,
    bind_name,
):
    del artifact_type, filesystem_cls, bind_name
    project_root = tmp_path / "project"
    project_root.mkdir()
    agent_config = SimpleNamespace(
        project_root=str(project_root),
        _enterprise_enabled=True,
        _request_user_id="alice",
    )
    tools = tools_cls(agent_config=agent_config, db_func_tool=object(), allow_bind_existing=False)

    result = await getattr(tools, start_name)(
        slug="orphan",
        name="Orphan",
        description="Must roll back when no ACL owner can be persisted.",
    )

    assert result.success == 0
    assert "requires an ACL store" in (result.error or "")
    assert not (project_root / root_name / "orphan").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("artifact_type", "root_name", "tools_cls", "filesystem_cls", "start_name", "bind_name"),
    CASES,
)
async def test_enterprise_create_rejects_slug_reserved_by_other_owner(
    tmp_path: Path,
    artifact_type,
    root_name,
    tools_cls,
    filesystem_cls,
    start_name,
    bind_name,
):
    del bind_name
    project_root = tmp_path / "project"
    project_root.mkdir()
    store = MemoryArtifactAclStore()
    store.acls[(artifact_type, "reserved")] = {"owner_user_id": "bob", "visibility": "private"}
    agent_config = SimpleNamespace(
        project_root=str(project_root),
        _enterprise_enabled=True,
        _request_user_id="alice",
        _artifact_acl_store=store,
    )
    filesystem = filesystem_cls(root_path=str(project_root), require_authorized_artifact=True)
    tools = tools_cls(
        agent_config=agent_config,
        db_func_tool=object(),
        allow_bind_existing=False,
        on_artifact_authorized=filesystem.bind_authorized_artifact,
    )

    result = await getattr(tools, start_name)(
        slug="reserved",
        name="Reserved",
        description="A stale or concurrent ACL owned by Bob must win.",
    )

    assert result.success == 0
    assert "different owner" in (result.error or "")
    assert not (project_root / root_name / "reserved").exists()
    assert filesystem.write_file(f"{root_name}/reserved/render/app.jsx", "unauthorized").success == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("artifact_type", "root_name", "tools_cls", "filesystem_cls", "start_name", "bind_name"),
    CASES,
)
async def test_concurrent_enterprise_create_allows_only_one_slug_owner(
    tmp_path: Path,
    artifact_type,
    root_name,
    tools_cls,
    filesystem_cls,
    start_name,
    bind_name,
):
    del root_name, filesystem_cls, bind_name
    project_root = tmp_path / "project"
    project_root.mkdir()
    store = MemoryArtifactAclStore()

    def make_tools(user_id: str):
        return tools_cls(
            agent_config=SimpleNamespace(
                project_root=str(project_root),
                _enterprise_enabled=True,
                _request_user_id=user_id,
                _artifact_acl_store=store,
            ),
            db_func_tool=object(),
            allow_bind_existing=False,
        )

    alice_tools = make_tools("alice")
    bob_tools = make_tools("bob")
    alice_result, bob_result = await asyncio.gather(
        getattr(alice_tools, start_name)(
            slug="same_slug",
            name="Alice",
            description="Alice and Bob race for the same project-level slug.",
        ),
        getattr(bob_tools, start_name)(
            slug="same_slug",
            name="Bob",
            description="Alice and Bob race for the same project-level slug.",
        ),
    )

    assert sorted([alice_result.success, bob_result.success]) == [0, 1]
    winner = "alice" if alice_result.success == 1 else "bob"
    assert store.acls[(artifact_type, "same_slug")]["owner_user_id"] == winner


@pytest.mark.parametrize(
    ("artifact_type", "root_name", "tools_cls", "filesystem_cls", "start_name", "bind_name"),
    CASES,
)
def test_enterprise_edit_exposes_only_locked_authorized_artifact(
    tmp_path: Path,
    artifact_type,
    root_name,
    tools_cls,
    filesystem_cls,
    start_name,
    bind_name,
):
    del artifact_type
    project_root = tmp_path / "project"
    project_root.mkdir()
    _seed_artifact(project_root, root_name, "allowed")
    _seed_artifact(project_root, root_name, "other_user")
    filesystem = filesystem_cls(
        root_path=str(project_root),
        locked_artifact_slug="allowed",
        require_authorized_artifact=True,
    )
    locked_kwarg = {f"locked_{'dashboard' if root_name == 'dashboards' else 'report'}_slug": "allowed"}
    tools = tools_cls(
        agent_config=SimpleNamespace(project_root=str(project_root)),
        db_func_tool=object(),
        allow_create=False,
        allow_bind_existing=True,
        on_artifact_authorized=filesystem.bind_authorized_artifact,
        **locked_kwarg,
    )

    tool_names = {tool.name for tool in tools.available_tools()}
    assert start_name not in tool_names
    assert bind_name in tool_names
    assert getattr(tools, bind_name)("other_user").success == 0
    bound = getattr(tools, bind_name)("allowed")
    assert bound.success == 1, bound.error
    assert filesystem.read_file(f"{root_name}/allowed/manifest.json").success == 1
    assert filesystem.read_file(f"{root_name}/other_user/manifest.json").success == 0
    assert filesystem.write_file(
        f"{root_name}/allowed/render/app.jsx", "export default function App() {}\n"
    ).success == 1
    assert filesystem.write_file(f"{root_name}/other_user/render/app.jsx", "cross-user").success == 0
