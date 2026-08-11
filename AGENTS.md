# Repository Guidelines

## Canonical Scope

This root guide only covers cross-project coordination for the Datus monorepo. Each sub-project may have its own `AGENTS.md`; read that file before editing inside the sub-project, and treat the local guide as the more specific rule.

## Project Structure

- `datus-agent/`: Python agent package, API, CLI, configuration, docs, benchmarks, and tests.
- `datus-db-adapters/`: Python `uv` workspace for database adapter packages such as `datus-postgresql/`, `datus-mysql/`, and `datus-db-core/`.
- `datus-storage-adapters/`: Python `uv` workspace for storage adapter packages.
- `datus-semantic-adapter/`: Python `uv` workspace for semantic adapter packages such as `datus-semantic-core/` and `datus-semantic-metricflow/`.
- `metricflow/`: Datus MetricFlow fork and SQL engine implementations.
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
- `cd datus-semantic-adapter && uv sync --locked --all-packages --all-extras`
- `cd datus-semantic-adapter && .venv/bin/python -m pytest --asyncio-mode=auto`
- `cd metricflow && ../datus-agent/.venv/bin/python -m pytest -p no:rerunfailures metricflow/test/sql metricflow/test/sql_clients`
- `cd datus-web && npm install`
- `cd datus-web && npm run lint`
- `cd datus-web && npm test`
- `cd datus-web && npm run build`

## Coding Style

Python projects target modern typed Python and use Ruff for linting and formatting. Prefer clear module boundaries and keep adapter-specific behavior inside the relevant adapter package.

Vue code should use Vue 3 Composition API with `<script setup lang="ts">`. Keep backend-specific adaptation in feature or library code rather than generated UI primitives.

## Testing

Use pytest for Python packages and Vitest/Playwright where configured for the frontend. Prefer focused tests for the package being changed, then run broader checks when touching shared contracts or workspace-level behavior.

## Maintenance Change Rules

- When changing a test assertion or fixture, record the old expectation, the new expectation, and the production contract that justifies the change. Do not widen permissions, replace exact deny assertions with ambiguous outcomes, or remove `assert_not_called` protection merely to make tests pass.
- Before adding or upgrading a dependency, explain the concrete use site, why the standard library or existing dependencies are insufficient, the alternatives considered, and any runtime, license, security, or lockfile impact.
- Treat a PR as broad when it changes three or more sub-projects, or crosses two or more of these boundaries: authentication/authorization, public API/configuration, storage/data migration, and request/runtime state. Generated-only and lockfile-only mechanical diffs do not count by themselves.
- Broad changes should be split into independently verifiable and revertible steps. If an atomic change cannot be split safely, document the compatibility window, migration order, rollback point, and why partial delivery would be riskier.
- Generated or vendored files may change only through their documented source and command. Record the generator version and provenance; keep any unavoidable manual patch separate and reproducible.

## CI Maintenance

Read `docs/ci-quality-gates.zh-CN.md` before changing root GitHub Actions workflows, path detectors, gate verification, or required status contexts. Keep `Agent renderer gate`, `Web quality gate`, and `Python quality gate` stable unless the GitHub Ruleset is migrated deliberately.

- `node --test .github/scripts/*.test.cjs`
- `actionlint .github/workflows/*.yml`
- `git diff --check`

## Commits

Commit messages should follow Conventional Commits.

- Format: `<type>(<scope>): <description>`
- Use a lowercase English `type` from the allowed list below.
- Use a short scope when it clarifies the touched sub-project or domain, such as `agent`, `web`, `db-adapters`, `storage-adapters`, `api`, `auth`, `docs`, `build`, or `ci`.
- Keep the subject line concise, preferably 72 characters or fewer.
- Use a concise Chinese description after the colon, preferably a short verb-object phrase such as `修复会话加载` or `补充提交规范`.
- Use a body when the commit needs rationale, migration notes, verification details, or tradeoffs.
- Use `!` after the type or scope for breaking changes, and include a `BREAKING CHANGE:` footer when needed.
- Do not use vague messages such as `update`, `fix bug`, `change stuff`, `调整代码`, or `wip`.

Allowed Conventional Commit types:

- `feat`: user-facing feature or visible capability.
- `fix`: bug fix or behavioral regression fix.
- `docs`: documentation-only change.
- `style`: formatting or purely visual style change that does not alter behavior.
- `refactor`: code structure change without feature or bug-fix intent.
- `perf`: performance improvement.
- `test`: tests, fixtures, or test utilities.
- `build`: dependencies, package scripts, generated contract artifacts, or build tooling.
- `ci`: CI or automation configuration.
- `chore`: repository maintenance that does not fit the categories above.
- `revert`: revert a previous commit.

Examples:

- `docs(agents): 补充提交信息规范`
- `feat(web): 新增数据源选择器`
- `fix(agent): 修复会话加载`
- `build(db-adapters): 更新锁文件`

## Security

Do not commit secrets, local credentials, real tokens, generated caches, dependency folders, virtual environments, build outputs, or machine-local configuration. Request- or user-scoped credentials must not be persisted in logs, history, caches, traces, audit payloads, error messages, or generated diagnostics. Dedicated credential stores and static credential configuration are outside that ban only when their persistence method, owner scope, at-rest protection, and redacted API/log behavior are documented and tested.
