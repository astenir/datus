#!/usr/bin/env python3
"""
Intelligent build script that automatically resolves workspace dependencies
and builds packages in the correct order using topological sort.
"""

import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Set

if sys.version_info < (3, 11):
    print("Error: This script requires Python 3.11 or higher")
    sys.exit(1)

import tomllib


class DependencyResolver:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.packages: Dict[str, Path] = {}
        self.dependencies: Dict[str, Set[str]] = {}

    def discover_packages(self) -> None:
        """Find all datus-* packages with pyproject.toml."""
        for pkg_dir in self.root_dir.glob("datus-*"):
            if pkg_dir.is_dir() and (pkg_dir / "pyproject.toml").exists():
                self.packages[pkg_dir.name] = pkg_dir

        if not self.packages:
            print("Error: No packages found")
            sys.exit(1)

    def parse_dependencies(self) -> None:
        """Parse workspace dependencies from pyproject.toml files."""
        for pkg_name, pkg_dir in self.packages.items():
            self.dependencies[pkg_name] = set()

            pyproject_path = pkg_dir / "pyproject.toml"
            try:
                with open(pyproject_path, "rb") as f:
                    data = tomllib.load(f)

                sources = data.get("tool", {}).get("uv", {}).get("sources", {})
                for dep_name, dep_config in sources.items():
                    if isinstance(dep_config, dict) and dep_config.get("workspace"):
                        dep_dir_name = dep_name.replace("_", "-")
                        if dep_dir_name in self.packages:
                            self.dependencies[pkg_name].add(dep_dir_name)

            except Exception as e:
                print(f"Warning: Failed to parse {pyproject_path}: {e}")

    def topological_sort(self) -> List[str]:
        """Perform topological sort to determine build order."""
        in_degree = {pkg: 0 for pkg in self.packages}
        for pkg in self.dependencies:
            in_degree[pkg] = len(self.dependencies[pkg])

        queue = [pkg for pkg, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            queue.sort()
            pkg = queue.pop(0)
            result.append(pkg)

            for other_pkg in self.packages:
                if pkg in self.dependencies[other_pkg]:
                    in_degree[other_pkg] -= 1
                    if in_degree[other_pkg] == 0:
                        queue.append(other_pkg)

        if len(result) != len(self.packages):
            remaining = set(self.packages.keys()) - set(result)
            print(f"Error: Circular dependencies detected in: {remaining}")
            sys.exit(1)

        return result

    def build_packages(self, build_order: List[str]) -> None:
        """Build packages in the resolved order."""
        print(f"Building {len(build_order)} packages in dependency order...")
        print()

        for i, pkg in enumerate(build_order, 1):
            print(f"[{i}/{len(build_order)}] Building {pkg}...")

            try:
                subprocess.run(["uv", "build"], cwd=self.packages[pkg], check=True, capture_output=True, text=True)
                print("  ✓ Success")

            except subprocess.CalledProcessError as e:
                print("  ✗ Failed")
                print(f"\nError:\n{e.stderr}")
                sys.exit(1)

            print()


def main():
    root_dir = Path.cwd()

    print("\n" + "=" * 60)
    print("Building Datus Adapters")
    print("=" * 60 + "\n")

    # Clean old builds
    dist_dir = root_dir / "dist"
    if dist_dir.exists():
        import shutil

        shutil.rmtree(dist_dir)
    dist_dir.mkdir()

    # Resolve and build
    resolver = DependencyResolver(root_dir)
    resolver.discover_packages()
    resolver.parse_dependencies()
    build_order = resolver.topological_sort()
    resolver.build_packages(build_order)

    # Summary
    wheels = sorted(dist_dir.glob("*.whl"))
    print("=" * 60)
    print(f"✓ Successfully built {len(wheels)} packages")
    print(f"Location: {dist_dir}/")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
