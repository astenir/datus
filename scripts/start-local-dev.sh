#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PIDS=()

cleanup() {
  trap - EXIT INT TERM

  for pid in "${PIDS[@]}"; do
    kill -- -"$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
  done

  for pid in "${PIDS[@]}"; do
    wait "$pid" 2>/dev/null || true
  done
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

start_service() {
  local name="$1"
  local workdir="$2"
  shift 2

  printf '[start] %s\n' "$name"
  setsid bash -c 'cd -- "$1" && shift && exec "$@"' _ "$workdir" "$@" &
  PIDS+=("$!")
}

start_service "Datus API :8000" "$ROOT_DIR/datus-agent" \
  uv run datus-api --port 8000 --debug

start_service "Mock userinfo :8010" "$ROOT_DIR/datus-agent" \
  uv run scripts/enterprise_mock_userinfo.py --port 8010

start_service "Datus Web / Alice :5173" "$ROOT_DIR/datus-web" \
  env VITE_DEV_ACCESS_TOKEN=dev-alice-token npm run dev -- --port 5173

start_service "Datus Web / Bob :5174" "$ROOT_DIR/datus-web" \
  env VITE_DEV_ACCESS_TOKEN=dev-bob-token npm run dev -- --port 5174

printf '\n本地联调服务已启动：\n'
printf '  Alice:       http://127.0.0.1:5173\n'
printf '  Bob:         http://127.0.0.1:5174\n'
printf '  Datus API:   http://127.0.0.1:8000\n'
printf '  Mock userinfo: http://127.0.0.1:8010\n'
printf '\n按 Ctrl-C 会停止全部服务。\n\n'

if wait -n "${PIDS[@]}"; then
  printf '\n某个服务已退出，正在停止其余服务。\n' >&2
else
  status=$?
  printf '\n某个服务异常退出，正在停止其余服务。\n' >&2
  exit "$status"
fi
