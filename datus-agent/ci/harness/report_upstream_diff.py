#!/usr/bin/env python3
"""Report and validate downstream divergence from an upstream release tree."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ALLOWLIST = Path("ci/harness/upstream-modified-allowlist.yml")
VALID_CATEGORIES = {
    "core-hook",
    "move-to-enterprise",
    "upstreamable-fix",
    "docs-config-meta",
    "test-only",
}


@dataclass(frozen=True)
class DiffEntry:
    status: str
    path: str
    old_path: str | None = None


@dataclass(frozen=True)
class DiffResult:
    entries: tuple[DiffEntry, ...]
    insertions: int
    deletions: int

    @property
    def status_counts(self) -> dict[str, int]:
        counts = Counter(entry.status for entry in self.entries)
        return dict(sorted(counts.items()))

    @property
    def modified_paths(self) -> set[str]:
        return {entry.path for entry in self.entries if entry.status == "M"}


@dataclass(frozen=True)
class Allowlist:
    base_ref: str
    paths_by_category: dict[str, tuple[str, ...]]

    @property
    def paths(self) -> set[str]:
        return {path for paths in self.paths_by_category.values() for path in paths}


def run_git(repo_root: Path, *args: str, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def parse_name_status(output: str) -> tuple[DiffEntry, ...]:
    entries: list[DiffEntry] = []
    for line in output.splitlines():
        if not line:
            continue
        parts = line.split("\t")
        status = parts[0][0]
        if status in {"R", "C"}:
            if len(parts) != 3:
                raise ValueError(f"Invalid rename/copy name-status line: {line}")
            entries.append(DiffEntry(status=status, old_path=parts[1], path=parts[2]))
        else:
            if len(parts) != 2:
                raise ValueError(f"Invalid name-status line: {line}")
            entries.append(DiffEntry(status=status, path=parts[1]))
    return tuple(entries)


def parse_numstat(output: str) -> tuple[int, int]:
    insertions = 0
    deletions = 0
    for line in output.splitlines():
        if not line:
            continue
        added, removed, _path = line.split("\t", 2)
        if added != "-":
            insertions += int(added)
        if removed != "-":
            deletions += int(removed)
    return insertions, deletions


def collect_ref_diff(repo_root: Path, base_ref: str, target_ref: str) -> DiffResult:
    name_status = run_git(repo_root, "diff", "--name-status", "-M", base_ref, target_ref)
    numstat = run_git(repo_root, "diff", "--numstat", base_ref, target_ref)
    insertions, deletions = parse_numstat(numstat)
    return DiffResult(parse_name_status(name_status), insertions, deletions)


def collect_worktree_diff(repo_root: Path, base_ref: str) -> DiffResult:
    git_dir = Path(run_git(repo_root, "rev-parse", "--absolute-git-dir"))
    with tempfile.TemporaryDirectory(prefix="datus-upstream-diff-") as temp_dir_text:
        temp_dir = Path(temp_dir_text)
        object_dir = temp_dir / "objects"
        object_dir.mkdir()
        env = os.environ.copy()
        env.update(
            {
                "GIT_INDEX_FILE": str(temp_dir / "index"),
                "GIT_WORK_TREE": str(repo_root),
                "GIT_OBJECT_DIRECTORY": str(object_dir),
                "GIT_ALTERNATE_OBJECT_DIRECTORIES": str(git_dir / "objects"),
            }
        )
        run_git(repo_root, "read-tree", base_ref, env=env)
        run_git(repo_root, "add", "-A", "--", ".", env=env)
        worktree_tree = run_git(repo_root, "write-tree", env=env)
        return collect_ref_diff_with_env(repo_root, base_ref, worktree_tree, env)


def collect_ref_diff_with_env(
    repo_root: Path,
    base_ref: str,
    target_ref: str,
    env: dict[str, str],
) -> DiffResult:
    name_status = run_git(repo_root, "diff", "--name-status", "-M", base_ref, target_ref, env=env)
    numstat = run_git(repo_root, "diff", "--numstat", base_ref, target_ref, env=env)
    insertions, deletions = parse_numstat(numstat)
    return DiffResult(parse_name_status(name_status), insertions, deletions)


def classify_path(path: str) -> str:
    if path.startswith(("datus/", "datus_enterprise/")):
        return "production/package"
    if path.startswith("tests/"):
        return "tests"
    if path.startswith("docs/"):
        return "docs"
    return "config/meta"


def build_report(base_ref: str, downstream: DiffResult, upstream: DiffResult | None = None) -> dict[str, Any]:
    modified_classification = Counter(classify_path(path) for path in downstream.modified_paths)
    report: dict[str, Any] = {
        "base_ref": base_ref,
        "downstream": {
            "file_count": len(downstream.entries),
            "insertions": downstream.insertions,
            "deletions": downstream.deletions,
            "status_counts": downstream.status_counts,
            "modified_classification": dict(sorted(modified_classification.items())),
            "modified_files": sorted(downstream.modified_paths),
        },
    }
    if upstream is not None:
        upstream_paths = {entry.path for entry in upstream.entries}
        overlap = sorted(downstream.modified_paths & upstream_paths)
        report["upstream"] = {
            "file_count": len(upstream.entries),
            "insertions": upstream.insertions,
            "deletions": upstream.deletions,
            "status_counts": upstream.status_counts,
        }
        report["overlap"] = {"file_count": len(overlap), "files": overlap}
    return report


def load_allowlist(path: Path) -> Allowlist:
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError(f"{path}: schema_version must be 1")
    base_ref = data.get("base_ref")
    if not isinstance(base_ref, str) or not base_ref:
        raise ValueError(f"{path}: base_ref must be a non-empty string")
    categories = data.get("categories")
    if not isinstance(categories, dict):
        raise ValueError(f"{path}: categories must be a mapping")

    unknown = set(categories) - VALID_CATEGORIES
    if unknown:
        raise ValueError(f"{path}: unknown categories: {', '.join(sorted(unknown))}")

    paths_by_category: dict[str, tuple[str, ...]] = {}
    seen: set[str] = set()
    for category in sorted(VALID_CATEGORIES):
        raw_paths = categories.get(category, [])
        if not isinstance(raw_paths, list) or not all(isinstance(item, str) and item for item in raw_paths):
            raise ValueError(f"{path}: categories.{category} must be a list of non-empty paths")
        paths = tuple(raw_paths)
        duplicates = seen & set(paths)
        if duplicates:
            raise ValueError(f"{path}: paths listed more than once: {', '.join(sorted(duplicates))}")
        seen.update(paths)
        paths_by_category[category] = paths
    return Allowlist(base_ref=base_ref, paths_by_category=paths_by_category)


def check_allowlist(allowlist: Allowlist, downstream: DiffResult, base_ref: str) -> list[str]:
    errors: list[str] = []
    if allowlist.base_ref != base_ref:
        errors.append(f"allowlist base_ref={allowlist.base_ref} does not match requested base_ref={base_ref}")
    unexpected = sorted(downstream.modified_paths - allowlist.paths)
    missing = sorted(allowlist.paths - downstream.modified_paths)
    if unexpected:
        errors.append("unregistered modified files:\n  " + "\n  ".join(unexpected))
    if missing:
        errors.append("allowlisted files no longer modified:\n  " + "\n  ".join(missing))
    return errors


def print_human_report(report: dict[str, Any], target_ref: str | None) -> None:
    downstream = report["downstream"]
    counts = downstream["status_counts"]
    print(f"base: {report['base_ref']}")
    print(
        "downstream: "
        f"files={downstream['file_count']} "
        f"A={counts.get('A', 0)} M={counts.get('M', 0)} D={counts.get('D', 0)} "
        f"+{downstream['insertions']} -{downstream['deletions']}"
    )
    for category, count in downstream["modified_classification"].items():
        print(f"  modified {category}: {count}")
    if target_ref is not None:
        upstream = report["upstream"]
        overlap = report["overlap"]
        print(f"upstream target: {target_ref} changed={upstream['file_count']}")
        print(f"overlap: {overlap['file_count']}")
        for path in overlap["files"]:
            print(f"  {path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="v0.3.8", help="Previous upstream release ref.")
    parser.add_argument("--target", help="New upstream release ref used to calculate overlap.")
    parser.add_argument("--allowlist", type=Path, default=DEFAULT_ALLOWLIST)
    parser.add_argument("--check", action="store_true", help="Fail when modified files differ from the allowlist.")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Print the report as JSON.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    downstream = collect_worktree_diff(repo_root, args.base)
    upstream = collect_ref_diff(repo_root, args.base, args.target) if args.target else None
    report = build_report(args.base, downstream, upstream)

    errors: list[str] = []
    if args.check:
        allowlist_path = args.allowlist if args.allowlist.is_absolute() else repo_root / args.allowlist
        errors = check_allowlist(load_allowlist(allowlist_path), downstream, args.base)
        report["allowlist"] = {
            "path": str(allowlist_path),
            "ok": not errors,
            "modified_file_count": len(downstream.modified_paths),
        }

    if args.json_output:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_human_report(report, args.target)

    if args.check:
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        if not args.json_output:
            print(f"allowlist: ok ({len(downstream.modified_paths)} modified files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
