import stat
from types import SimpleNamespace

import pytest

from datus.tools.func_tool.filesystem_tools import FilesystemFuncTool
from datus.utils.exceptions import DatusException
from datus.utils.path_manager import DatusPathManager
from datus_enterprise.workspace import prepare_user_workspace


def _agent_config(tmp_path):
    return SimpleNamespace(
        project_name="finance",
        path_manager=DatusPathManager(
            datus_home=tmp_path / "datus-home",
            project_name="finance",
            project_root=tmp_path / "project",
        ),
    )


def test_user_workspaces_isolate_same_relative_file_and_delete(tmp_path):
    config = _agent_config(tmp_path)
    alice_root = prepare_user_workspace(config, "alice@example.com")
    bob_root = prepare_user_workspace(config, "bob@example.com")

    assert alice_root != bob_root
    assert "alice@example.com" not in str(alice_root)
    assert "bob@example.com" not in str(bob_root)
    assert stat.S_IMODE(alice_root.stat().st_mode) == 0o700
    assert stat.S_IMODE(bob_root.stat().st_mode) == 0o700

    alice_files = FilesystemFuncTool(root_path=str(alice_root), strict=True)
    bob_files = FilesystemFuncTool(root_path=str(bob_root), strict=True)
    assert alice_files.write_file("output/result.md", "alice").success == 1
    assert bob_files.write_file("output/result.md", "bob").success == 1

    assert alice_files.read_file("output/result.md").result == "alice"
    assert bob_files.read_file("output/result.md").result == "bob"
    assert alice_files.read_file(str(bob_root / "output" / "result.md")).success == 0

    assert alice_files.delete_file("output/result.md").success == 1
    assert not (alice_root / "output" / "result.md").exists()
    assert (bob_root / "output" / "result.md").read_text() == "bob"


def test_user_workspace_rejects_existing_symlink_redirect(tmp_path):
    config = _agent_config(tmp_path)
    workspace = prepare_user_workspace(config, "mallory")
    workspace.rmdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    workspace.symlink_to(outside, target_is_directory=True)

    with pytest.raises(DatusException, match="resolved outside"):
        prepare_user_workspace(config, "mallory")
