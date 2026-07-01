# Repository Guidelines

## Canonical Scope

This root guide only covers cross-project coordination for the Datus monorepo. Each sub-project may have its own `AGENTS.md`; read that file before editing inside the sub-project, and treat the local guide as the more specific rule.

## Project Structure

- `datus-agent/`: Python agent package, API, CLI, configuration, docs, benchmarks, and tests.
- `datus-db-adapters/`: Python `uv` workspace for database adapter packages such as `datus-postgresql/`, `datus-mysql/`, and `datus-db-core/`.
- `datus-storage-adapters/`: Python `uv` workspace for storage adapter packages.
- `datus-web/`: Vue 3 + Vite frontend. Source lives under `datus-web/src/`.

Keep the repository root minimal. Do not add application code, generated artifacts, dependency directories, virtual environments, or per-service operational scripts at the root unless they are explicitly shared by multiple sub-projects.

## Common Commands

- `cd datus-agent && uv sync --dev`
- `cd datus-agent && uv run ruff check .`
- `cd datus-agent && uv run pytest`
- `cd datus-db-adapters && uv sync --dev`
- `cd datus-db-adapters && uv run ruff check .`
- `cd datus-db-adapters && uv run pytest --import-mode=importlib datus-postgresql/tests/unit`
- `cd datus-storage-adapters && uv sync --dev`
- `cd datus-storage-adapters && uv run ruff check .`
- `cd datus-storage-adapters && uv run pytest`
- `cd datus-web && npm install`
- `cd datus-web && npm test`
- `cd datus-web && npm run build`

## Coding Style

Python projects target modern typed Python and use Ruff for linting and formatting. Prefer clear module boundaries and keep adapter-specific behavior inside the relevant adapter package.

Vue code should use Vue 3 Composition API with `<script setup lang="ts">`. Keep backend-specific adaptation in feature or library code rather than generated UI primitives.

## Testing

Use pytest for Python packages and Vitest/Playwright where configured for the frontend. Prefer focused tests for the package being changed, then run broader checks when touching shared contracts or workspace-level behavior.

## Commits

Use concise Chinese commit messages with a bracketed or parenthesized category, for example `（同步）迁移个人版 Datus 子项目`.

## Security

Do not commit secrets, local credentials, real tokens, generated caches, dependency folders, virtual environments, build outputs, or machine-local configuration.
