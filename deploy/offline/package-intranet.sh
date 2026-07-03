#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'EOF'
Usage: deploy/offline/package-intranet.sh [options]

Build a local intranet release package containing:
  - Git bundle for the current branch HEAD
  - datus-web production dist
  - small manifest and install hints

Options:
  --output-dir DIR      Output directory. Default: dist/offline
  --branch REF          Git ref to bundle. Default: current HEAD branch/ref
  --name NAME           Package name prefix. Default: datus-offline
  --web-mode MODE       Vite mode for frontend build. Default: intranet
  --npm-ci              Run npm ci --legacy-peer-deps before building web
  --strict-clean        Fail if the working tree has uncommitted changes
  --skip-web            Only create the Git bundle, no frontend dist
  -h, --help            Show this help

Examples:
  deploy/offline/package-intranet.sh
  deploy/offline/package-intranet.sh --npm-ci --strict-clean
  deploy/offline/package-intranet.sh --output-dir /tmp/datus-release
EOF
}

log() {
  printf '[package-intranet] %s\n' "$*"
}

die() {
  printf '[package-intranet] ERROR: %s\n' "$*" >&2
  exit 1
}

OUTPUT_DIR="dist/offline"
PACKAGE_NAME="datus-offline"
WEB_MODE="intranet"
RUN_NPM_CI=0
STRICT_CLEAN=0
SKIP_WEB=0
BRANCH=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --output-dir)
      OUTPUT_DIR="${2:-}"
      [ -n "$OUTPUT_DIR" ] || die "--output-dir requires a value"
      shift 2
      ;;
    --branch)
      BRANCH="${2:-}"
      [ -n "$BRANCH" ] || die "--branch requires a value"
      shift 2
      ;;
    --name)
      PACKAGE_NAME="${2:-}"
      [ -n "$PACKAGE_NAME" ] || die "--name requires a value"
      shift 2
      ;;
    --web-mode)
      WEB_MODE="${2:-}"
      [ -n "$WEB_MODE" ] || die "--web-mode requires a value"
      shift 2
      ;;
    --npm-ci)
      RUN_NPM_CI=1
      shift
      ;;
    --strict-clean)
      STRICT_CLEAN=1
      shift
      ;;
    --skip-web)
      SKIP_WEB=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac
done

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

command -v git >/dev/null 2>&1 || die "git is required"
command -v tar >/dev/null 2>&1 || die "tar is required"

if [ -z "$BRANCH" ]; then
  BRANCH="$(git symbolic-ref --quiet --short HEAD || git rev-parse --verify HEAD)"
fi

git rev-parse --verify "$BRANCH" >/dev/null 2>&1 || die "git ref not found: $BRANCH"
SHORT_SHA="$(git rev-parse --short "$BRANCH")"
FULL_SHA="$(git rev-parse "$BRANCH")"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
RELEASE_NAME="${PACKAGE_NAME}-${TIMESTAMP}-${SHORT_SHA}"
OUTPUT_DIR_ABS="$(mkdir -p "$OUTPUT_DIR" && cd "$OUTPUT_DIR" && pwd)"
STAGING_DIR="$OUTPUT_DIR_ABS/$RELEASE_NAME"
ARCHIVE_PATH="$OUTPUT_DIR_ABS/$RELEASE_NAME.tar.gz"

if [ -n "$(git status --porcelain)" ]; then
  if [ "$STRICT_CLEAN" -eq 1 ]; then
    git status --short
    die "working tree is dirty; commit/stash changes or rerun without --strict-clean"
  fi
  log "working tree has uncommitted changes; source.bundle will contain committed history at $FULL_SHA only"
fi

rm -rf "$STAGING_DIR" "$ARCHIVE_PATH"
mkdir -p "$STAGING_DIR/source" "$STAGING_DIR/config-templates"

log "creating Git bundle for $BRANCH ($FULL_SHA)"
git bundle create "$STAGING_DIR/source/datus-${SHORT_SHA}.bundle" "$BRANCH"

if [ "$SKIP_WEB" -eq 0 ]; then
  command -v npm >/dev/null 2>&1 || die "npm is required to build datus-web; use --skip-web to bundle source only"
  [ -d datus-web ] || die "datus-web directory is missing"

  if [ "$RUN_NPM_CI" -eq 1 ]; then
    log "installing frontend dependencies with npm ci"
    (cd datus-web && npm ci --legacy-peer-deps)
  elif [ ! -d datus-web/node_modules ]; then
    die "datus-web/node_modules is missing; run with --npm-ci or install dependencies first"
  fi

  log "building frontend dist with Vite mode: $WEB_MODE"
  (cd datus-web && npm run build -- --mode "$WEB_MODE")
  mkdir -p "$STAGING_DIR/web-dist"
  cp -a datus-web/dist/. "$STAGING_DIR/web-dist/"
fi

if [ -f .env.compose.example ]; then
  cp .env.compose.example "$STAGING_DIR/config-templates/env.compose.example"
fi
if [ -f deploy/docker/agent/datasources.example.yml ]; then
  cp deploy/docker/agent/datasources.example.yml "$STAGING_DIR/config-templates/datasources.example.yml"
fi
if [ -f deploy/docker/agent/models.example.yml ]; then
  cp deploy/docker/agent/models.example.yml "$STAGING_DIR/config-templates/models.example.yml"
fi

cat > "$STAGING_DIR/MANIFEST.txt" <<EOF
name=$RELEASE_NAME
created_at=$TIMESTAMP
git_ref=$BRANCH
git_sha=$FULL_SHA
web_dist=$([ "$SKIP_WEB" -eq 0 ] && printf 'included' || printf 'skipped')

Notes:
- source/datus-${SHORT_SHA}.bundle contains committed Git history only.
- web-dist/ is generated from datus-web using Vite mode "${WEB_MODE}".
- Runtime secrets and real datasource/model configs should be maintained on the intranet host, not in this package.
EOF

cat > "$STAGING_DIR/README-INTRANET.md" <<EOF
# Datus intranet package

## Unpack source

\`\`\`bash
git clone source/datus-${SHORT_SHA}.bundle datus
\`\`\`

## Deploy frontend dist

Copy \`web-dist/\` to the static root used by Nginx, for example:

\`\`\`bash
rsync -a --delete web-dist/ /opt/datus/current/web-dist/
\`\`\`

## Backend

Install Python packages from your intranet wheelhouse or PyPI mirror, then start:

\`\`\`bash
datus-api --config /opt/datus/config/agent.yml --host 0.0.0.0 --port 8000
\`\`\`

Keep \`/opt/datus/config/agent.yml\`, model keys, datasource passwords, and runtime data outside this release package.
EOF

log "creating archive: $ARCHIVE_PATH"
tar -C "$OUTPUT_DIR_ABS" -czf "$ARCHIVE_PATH" "$RELEASE_NAME"

log "done"
printf '%s\n' "$ARCHIVE_PATH"
