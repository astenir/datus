"""Downstream filesystem ACL and skill-boundary coverage."""

from datus.tools.func_tool.filesystem_tools import FilesystemFuncTool


def test_protected_artifact_path_is_hidden_from_generic_chat(tmp_path):
    dashboard = tmp_path / "dashboards" / "sales" / "manifest.json"
    dashboard.parent.mkdir(parents=True)
    dashboard.write_text('{"slug":"sales"}')
    tool = FilesystemFuncTool(
        root_path=str(tmp_path),
        current_node="chat",
        protect_artifact_paths=True,
    )

    result = tool.read_file("dashboards/sales/manifest.json")

    assert result.success == 0
    assert "not found" in result.error.lower()


def test_protected_artifact_path_rejects_generic_chat_write(tmp_path):
    tool = FilesystemFuncTool(
        root_path=str(tmp_path),
        current_node="chat",
        protect_artifact_paths=True,
    )

    result = tool.write_file("reports/private/render/app.jsx", "export default null")

    assert result.success == 0
    assert "protected by report/dashboard ACLs" in result.error
    assert not (tmp_path / "reports" / "private" / "render" / "app.jsx").exists()


def test_glob_returns_matching_directories(tmp_path):
    (tmp_path / "reports" / "fund_analysis").mkdir(parents=True)
    (tmp_path / "reports" / "risk_review").mkdir(parents=True)
    tool = FilesystemFuncTool(root_path=str(tmp_path), current_node="test_node")

    result = tool.glob("reports/*")

    assert result.success == 1
    assert result.result["files"] == ["reports/fund_analysis", "reports/risk_review"]


def test_protected_artifact_tree_is_pruned_from_generic_chat_glob(tmp_path):
    dashboard = tmp_path / "dashboards" / "sales" / "manifest.json"
    dashboard.parent.mkdir(parents=True)
    dashboard.write_text('{"slug":"sales"}')
    (tmp_path / "README.md").write_text("ok")
    tool = FilesystemFuncTool(
        root_path=str(tmp_path),
        current_node="chat",
        protect_artifact_paths=True,
    )

    root_result = tool.glob("**/*.json")
    root_wildcard_result = tool.glob("*")
    root_jsx_result = tool.glob("**/*.jsx")
    direct_result = tool.glob("**/*.json", path="dashboards")

    assert root_result.success == 1
    assert root_result.result["files"] == []
    assert root_result.result["visibility_filtered"] is True
    assert root_result.result["visibility_reason"] == "artifact_acl"
    assert "Artifact ACLs" in root_result.result["message"]
    for result in (root_wildcard_result, root_jsx_result):
        assert result.success == 1
        assert result.result["visibility_filtered"] is True
        assert result.result["visibility_reason"] == "artifact_acl"
        assert "authorization scope" in result.result["message"]
    assert direct_result.success == 1
    assert direct_result.result["files"] == []
    assert direct_result.result["visibility_filtered"] is True
    assert direct_result.result["visibility_reason"] == "artifact_acl"
    assert "Artifact ACLs" in direct_result.result["message"]
    assert "authorization scope" in direct_result.result["message"]


def test_enterprise_global_skills_are_read_only(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    datus_home = tmp_path / "datus-home"
    global_skill = datus_home / "skills" / "shared" / "SKILL.md"
    global_skill.parent.mkdir(parents=True)
    global_skill.write_text("# shared\n")
    tool = FilesystemFuncTool(
        root_path=str(project),
        datus_home=str(datus_home),
        strict=True,
        global_skills_read_only=True,
    )

    assert tool.read_file(str(global_skill)).result == "# shared\n"
    assert "read-only" in (tool.write_file(str(global_skill), "changed").error or "").lower()
    assert "read-only" in (tool.edit_file(str(global_skill), "shared", "changed").error or "").lower()
    assert "read-only" in (tool.delete_file(str(global_skill)).error or "").lower()
    assert global_skill.read_text() == "# shared\n"


def test_enterprise_project_skills_remain_private_workspace_writable(tmp_path):
    tool = FilesystemFuncTool(
        root_path=str(tmp_path),
        datus_home=str(tmp_path / "datus-home"),
        strict=True,
        global_skills_read_only=True,
    )

    result = tool.write_file(".datus/skills/private/SKILL.md", "# private\n")

    assert result.success == 1
    assert (tmp_path / ".datus" / "skills" / "private" / "SKILL.md").exists()
