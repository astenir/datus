#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PACKAGES=(
  "datus-semantic-core"
  "datus-semantic-metricflow"
)

usage() {
  cat <<'USAGE'
Usage: ci/run-build.sh [--list] [--dry-run] [--skip-smoke] [package ...]

Builds semantic adapter workspace packages and smoke-checks the built wheels.

Options:
  --list        List configured packages.
  --dry-run     Print selected build commands without running them.
  --skip-smoke  Skip install/import smoke checks for built wheels.
  -h, --help    Show this help.
USAGE
}

require_command() {
  local command_name="$1"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Missing required command: $command_name" >&2
    exit 127
  fi
}

list_packages() {
  local package
  for package in "${PACKAGES[@]}"; do
    printf '%s\n' "$package"
  done
}

requested_packages=()
dry_run=0
skip_smoke=0
dist_dir="${DIST_DIR:-$ROOT_DIR/dist}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --list)
      list_packages
      exit 0
      ;;
    --dry-run)
      dry_run=1
      shift
      ;;
    --skip-smoke)
      skip_smoke=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      while [ "$#" -gt 0 ]; do
        requested_packages+=("$1")
        shift
      done
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      requested_packages+=("$1")
      shift
      ;;
  esac
done

should_run_package() {
  local package="$1"
  if [ "${#requested_packages[@]}" -eq 0 ]; then
    return 0
  fi

  local requested
  for requested in "${requested_packages[@]}"; do
    if [ "$requested" = "$package" ]; then
      return 0
    fi
  done
  return 1
}

require_command uv

single_artifact() {
  local package="$1"
  local output_dir="$2"
  local pattern="$3"
  local label="$4"
  local count

  count="$(find "$output_dir" -maxdepth 1 -type f -name "$pattern" | wc -l | tr -d ' ')"
  if [ "$count" != "1" ]; then
    echo "Expected exactly one $label for $package in $output_dir, found $count" >&2
    find "$output_dir" -maxdepth 1 -type f -print >&2
    exit 1
  fi

  find "$output_dir" -maxdepth 1 -type f -name "$pattern" | sort | head -n 1
}

smoke_check_package() {
  local package="$1"
  local wheel_path="$2"
  local core_wheel_path

  echo ""
  echo "=== Package smoke: $package ==="

  case "$package" in
    datus-semantic-core)
      uv run --no-project --isolated \
        --with "$wheel_path" \
        python - <<'PY'
from datus_semantic_core import BaseSemanticAdapter, SemanticAdapterConfig
from datus_semantic_core.models import MetricDefinition, SemanticModelInfo

assert BaseSemanticAdapter is not None
assert SemanticAdapterConfig(type="metricflow") is not None
assert MetricDefinition(name="orders") is not None
assert SemanticModelInfo(name="sales") is not None
PY
      ;;
    datus-semantic-metricflow)
      core_wheel_path=""
      if [ -d "$dist_dir/datus-semantic-core" ]; then
        core_wheel_path="$(single_artifact \
          "datus-semantic-core" \
          "$dist_dir/datus-semantic-core" \
          "*.whl" \
          "wheel")"
      fi

      if [ -n "$core_wheel_path" ]; then
        uv run --no-project --isolated \
          --with "$core_wheel_path" \
          --with "$wheel_path" \
          python - <<'PY'
from importlib import metadata

from datus_semantic_core import semantic_adapter_registry
import datus_semantic_metricflow

assert datus_semantic_metricflow is not None
entry_points = metadata.entry_points(group="datus.semantic_adapters")
metricflow = [entry_point for entry_point in entry_points if entry_point.name == "metricflow"]
assert metricflow, "metricflow semantic adapter entry point is missing"
register = metricflow[0].load()
assert callable(register)
register()
metadata = semantic_adapter_registry.get_metadata("metricflow")
assert metadata is not None
assert metadata.adapter_class.__name__ == "MetricFlowAdapter"
PY
      else
        uv run --no-project --isolated \
          --with "$wheel_path" \
          python - <<'PY'
from importlib import metadata

from datus_semantic_core import semantic_adapter_registry
import datus_semantic_metricflow

assert datus_semantic_metricflow is not None
entry_points = metadata.entry_points(group="datus.semantic_adapters")
metricflow = [entry_point for entry_point in entry_points if entry_point.name == "metricflow"]
assert metricflow, "metricflow semantic adapter entry point is missing"
register = metricflow[0].load()
assert callable(register)
register()
metadata = semantic_adapter_registry.get_metadata("metricflow")
assert metadata is not None
assert metadata.adapter_class.__name__ == "MetricFlowAdapter"
PY
      fi
      ;;
    *)
      echo "No package smoke configured for package: $package" >&2
      exit 2
      ;;
  esac
}

for package in "${PACKAGES[@]}"; do
  if ! should_run_package "$package"; then
    continue
  fi

  output_dir="$dist_dir/$package"

  echo ""
  echo "=== Build package: $package ==="
  if [ "$dry_run" -eq 1 ]; then
    echo "uv build --package $package --out-dir $output_dir"
    if [ "$skip_smoke" -ne 1 ]; then
      echo "package smoke: $package"
    fi
    continue
  fi

  rm -rf "$output_dir"
  mkdir -p "$output_dir"
  uv build --package "$package" --out-dir "$output_dir"

  single_artifact "$package" "$output_dir" "*.whl" "wheel" >/dev/null
  single_artifact "$package" "$output_dir" "*.tar.gz" "sdist" >/dev/null

  if [ "$skip_smoke" -ne 1 ]; then
    smoke_check_package "$package" "$(single_artifact "$package" "$output_dir" "*.whl" "wheel")"
  fi
done
