from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

MODULE_PATH = Path(__file__).resolve().parents[4] / "ci" / "harness" / "report_upstream_diff.py"
MODULE_SPEC = importlib.util.spec_from_file_location("report_upstream_diff", MODULE_PATH)
if MODULE_SPEC is None or MODULE_SPEC.loader is None:
    raise RuntimeError(f"Unable to load upstream diff reporter from {MODULE_PATH}")
report_upstream_diff = importlib.util.module_from_spec(MODULE_SPEC)
sys.modules[MODULE_SPEC.name] = report_upstream_diff
MODULE_SPEC.loader.exec_module(report_upstream_diff)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.name", "Test User")
    _git(tmp_path, "config", "user.email", "test@example.com")
    (tmp_path / "changed.txt").write_text("before\n", encoding="utf-8")
    (tmp_path / "deleted.txt").write_text("delete me\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "base")
    _git(tmp_path, "tag", "v1")
    return tmp_path


def test_collect_worktree_diff_includes_added_modified_and_deleted(git_repo: Path):
    (git_repo / "changed.txt").write_text("after\n", encoding="utf-8")
    (git_repo / "added.txt").write_text("new\n", encoding="utf-8")
    (git_repo / "deleted.txt").unlink()

    result = report_upstream_diff.collect_worktree_diff(git_repo, "v1")

    assert result.status_counts == {"A": 1, "D": 1, "M": 1}
    assert result.modified_paths == {"changed.txt"}
    assert result.insertions == 2
    assert result.deletions == 2
    assert _git(git_repo, "status", "--short").splitlines() == [
        "M changed.txt",
        " D deleted.txt",
        "?? added.txt",
    ]
    assert _git(git_repo, "diff", "--cached", "--name-only") == ""


def test_collect_worktree_diff_resolves_base_from_common_object_directory(git_repo: Path, tmp_path: Path):
    worktree = tmp_path / "linked-worktree"
    _git(git_repo, "worktree", "add", "--detach", str(worktree), "v1")
    (worktree / "changed.txt").write_text("after\n", encoding="utf-8")

    result = report_upstream_diff.collect_worktree_diff(worktree, "v1")

    assert result.status_counts == {"M": 1}
    assert result.modified_paths == {"changed.txt"}


def test_build_report_calculates_modified_overlap():
    downstream = report_upstream_diff.DiffResult(
        entries=(
            report_upstream_diff.DiffEntry("M", "shared.py"),
            report_upstream_diff.DiffEntry("M", "local.py"),
            report_upstream_diff.DiffEntry("A", "new.py"),
        ),
        insertions=3,
        deletions=1,
    )
    upstream = report_upstream_diff.DiffResult(
        entries=(
            report_upstream_diff.DiffEntry("M", "shared.py"),
            report_upstream_diff.DiffEntry("A", "upstream.py"),
        ),
        insertions=2,
        deletions=1,
    )

    report = report_upstream_diff.build_report("v1", downstream, upstream)

    assert report["overlap"] == {"file_count": 1, "files": ["shared.py"]}
    assert report["downstream"]["status_counts"] == {"A": 1, "M": 2}


def test_load_and_check_allowlist(tmp_path: Path):
    allowlist_path = tmp_path / "allowlist.yml"
    allowlist_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "base_ref": "v1",
                "categories": {
                    "core-hook": ["expected.py"],
                    "move-to-enterprise": [],
                    "upstreamable-fix": [],
                    "docs-config-meta": [],
                    "test-only": [],
                },
            }
        ),
        encoding="utf-8",
    )
    downstream = report_upstream_diff.DiffResult(
        entries=(
            report_upstream_diff.DiffEntry("M", "unexpected.py"),
            report_upstream_diff.DiffEntry("A", "expected.py"),
        ),
        insertions=1,
        deletions=0,
    )

    errors = report_upstream_diff.check_allowlist(report_upstream_diff.load_allowlist(allowlist_path), downstream, "v1")

    assert errors == [
        "unregistered modified files:\n  unexpected.py",
        "allowlisted files no longer modified:\n  expected.py",
    ]


def test_allowlist_rejects_duplicate_paths(tmp_path: Path):
    allowlist_path = tmp_path / "allowlist.yml"
    allowlist_path.write_text(
        """\
schema_version: 1
base_ref: v1
categories:
  core-hook: [duplicate.py]
  move-to-enterprise: [duplicate.py]
  upstreamable-fix: []
  docs-config-meta: []
  test-only: []
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="paths listed more than once: duplicate.py"):
        report_upstream_diff.load_allowlist(allowlist_path)


def test_json_check_output_remains_machine_readable(git_repo: Path, tmp_path: Path, capsys):
    allowlist_path = tmp_path / "allowlist.yml"
    allowlist_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "base_ref": "v1",
                "categories": {category: [] for category in sorted(report_upstream_diff.VALID_CATEGORIES)},
            }
        ),
        encoding="utf-8",
    )

    exit_code = report_upstream_diff.main(
        [
            "--repo-root",
            str(git_repo),
            "--base",
            "v1",
            "--allowlist",
            str(allowlist_path),
            "--check",
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["allowlist"]["ok"] is True
    assert payload["allowlist"]["modified_file_count"] == 0
