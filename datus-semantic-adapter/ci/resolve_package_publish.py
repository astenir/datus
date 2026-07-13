#!/usr/bin/env python3

"""Resolve a safe, resumable package publication state."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tomllib
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from packaging.version import Version

try:
    from package_release import (
        REPO_ROOT,
        load_workspace_packages,
        parse_canonical_version,
        require_package,
    )
except ModuleNotFoundError:  # Imported as ci.resolve_package_publish in tests.
    from ci.package_release import (
        REPO_ROOT,
        load_workspace_packages,
        parse_canonical_version,
        require_package,
    )


SUPPORTED_PACKAGES = frozenset(
    {
        "datus-semantic-core",
        "datus-semantic-metricflow",
        "datus-semantic-osi",
    }
)


@dataclass(frozen=True)
class PublishState:
    package: str
    current_version: str
    version: str
    tag: str
    branch: str
    state: str
    release_commit: str
    pypi_exists: bool


def run_git(repo_root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=check,
        capture_output=True,
        text=True,
    )


def next_patch_version(current_version: Version) -> Version:
    if current_version.pre or current_version.dev or current_version.post or current_version.local:
        raise ValueError(
            f"Automatic patch increments require a final release version; found {current_version}"
        )
    release = list(current_version.release)
    if len(release) > 3:
        raise ValueError(f"Automatic patch increments do not support {current_version}")
    while len(release) < 3:
        release.append(0)
    release[2] += 1
    return Version(".".join(str(part) for part in release))


def resolve_requested_version(current_version: Version, requested_version: str) -> Version:
    requested_version = requested_version.strip()
    if requested_version:
        return parse_canonical_version(requested_version)
    return next_patch_version(current_version)


def pypi_release_exists(package_name: str, version: Version) -> bool:
    url = f"https://pypi.org/pypi/{package_name}/{version}/json"
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False
        raise

    published_name = str(payload.get("info", {}).get("name", ""))
    published_version = Version(str(payload.get("info", {}).get("version", "")))
    if published_name.lower() != package_name.lower() or published_version != version:
        raise ValueError(
            f"Unexpected PyPI response for {package_name} {version}: "
            f"found {published_name or '<missing>'} {published_version}"
        )
    return True


def tag_commit(repo_root: Path, tag: str) -> str | None:
    result = run_git(repo_root, "rev-list", "-n", "1", tag, check=False)
    if result.returncode != 0:
        return None
    commit = result.stdout.strip()
    return commit or None


def package_version_at_commit(repo_root: Path, package_path: Path, commit: str) -> Version:
    relative_pyproject = package_path.relative_to(repo_root) / "pyproject.toml"
    result = run_git(repo_root, "show", f"{commit}:{relative_pyproject.as_posix()}")
    payload = tomllib.loads(result.stdout)
    project = payload.get("project", {})
    if not isinstance(project, dict) or "version" not in project:
        raise ValueError(f"{relative_pyproject} at {commit} has no project version")
    return Version(str(project["version"]))


def resolve_publish_state(
    repo_root: Path,
    package_name: str,
    requested_version: str = "",
    *,
    release_exists: Callable[[str, Version], bool] = pypi_release_exists,
) -> PublishState:
    repo_root = repo_root.resolve()
    if package_name not in SUPPORTED_PACKAGES:
        supported = ", ".join(sorted(SUPPORTED_PACKAGES))
        raise ValueError(f"Unsupported package {package_name!r}; choose one of: {supported}")

    packages = load_workspace_packages(repo_root)
    target = require_package(packages, package_name)
    version = resolve_requested_version(target.version, requested_version)
    tag = f"{target.name}-v{version}"
    branch = f"release/{target.name}-{version}"
    existing_tag_commit = tag_commit(repo_root, tag)
    exists_on_pypi = release_exists(target.name, version)

    if exists_on_pypi and existing_tag_commit is None:
        raise ValueError(
            f"{target.name} {version} exists on PyPI but release tag {tag} is missing; "
            "investigate the published artifact before repairing the tag manually"
        )

    if existing_tag_commit is not None:
        tagged_version = package_version_at_commit(repo_root, target.path, existing_tag_commit)
        if tagged_version != version:
            raise ValueError(
                f"Release tag {tag} points to {target.name} {tagged_version}, expected {version}"
            )
        state = "complete" if exists_on_pypi else "retry"
        release_commit = existing_tag_commit
    else:
        if version <= target.version:
            raise ValueError(
                f"Release version must advance current {target.name} version {target.version}; "
                f"got {version}"
            )
        state = "new"
        release_commit = run_git(repo_root, "rev-parse", "HEAD").stdout.strip()

    return PublishState(
        package=target.name,
        current_version=str(target.version),
        version=str(version),
        tag=tag,
        branch=branch,
        state=state,
        release_commit=release_commit,
        pypi_exists=exists_on_pypi,
    )


def write_github_output(path: Path, state: PublishState) -> None:
    values = asdict(state)
    values["pypi_exists"] = str(state.pypi_exists).lower()
    with path.open("a", encoding="utf-8") as output:
        for key, value in values.items():
            print(f"{key}={value}", file=output)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--package", required=True)
    parser.add_argument("--requested-version", default="")
    parser.add_argument(
        "--github-output",
        type=Path,
        default=Path(os.environ["GITHUB_OUTPUT"]) if os.environ.get("GITHUB_OUTPUT") else None,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        state = resolve_publish_state(args.repo_root, args.package, args.requested_version)
    except Exception as exc:
        print(f"Package publish state check failed: {exc}", file=sys.stderr)
        return 1

    if args.github_output is not None:
        write_github_output(args.github_output, state)
    print(json.dumps(asdict(state), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
