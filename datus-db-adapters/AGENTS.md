# Datus Database Adapters Work Manual

## Scope and Source of Truth

This file is the repository-level working manual for Codex, Claude, and other coding agents working under
`datus-db-adapters/`. Keep shared adapter rules here. Keep `CLAUDE.md` as a short Claude entry point that points to
this file; do not duplicate shared rules there.

Before changing code, read the affected adapter package and prefer the package's existing style over generic examples.
When repository docs conflict with implementation, verify the implementation and update docs conservatively.

## Project Structure

This directory is a Python 3.12 `uv` workspace of independent database adapter packages for Datus. The root
`pyproject.toml` is for development only; end users install individual adapter packages.

Important areas:

- `datus-db-core/`: shared package code and core abstractions.
- `datus-sqlalchemy/`: shared SQLAlchemy connector layer used by most relational adapters.
- `datus-postgresql/`, `datus-mysql/`, `datus-trino/`, `datus-starrocks/`, `datus-snowflake/`, and other
  `datus-<adapter>/` directories: concrete adapter packages.
- `docs/` and package `README.md` files: user-facing and adapter-specific documentation.
- `ci/`: CI helper scripts and checks.

Each adapter should keep package source under `datus_<adapter>/`, tests under `tests/`, unit tests under
`tests/unit/` when that split exists, integration tests under `tests/integration/`, optional setup scripts under
`scripts/`, and a local `docker-compose.yml` when integration tests need a database container.

## Build, Test, and Development Commands

Use Python 3.12. Prefer `uv` for workspace development.

```bash
uv sync --dev
uv run pytest datus-postgresql/tests/unit
uv run pytest datus-postgresql/tests/integration
uv run ruff check .
uv run ruff format .
```

For adapter-local execution, use the workspace environment where possible. If you intentionally run from inside an
adapter directory, use:

```bash
cd datus-<adapter>
python -m pytest tests/unit/ -v
python -m pytest tests/integration/ -v
```

Integration tests require the relevant database service. Use the adapter's `docker-compose.yml` and setup scripts when
present. If a service is unavailable, tests should skip cleanly instead of failing during import or fixture setup.

## Coding Style & Naming Conventions

Ruff, Black-compatible formatting, Flake8, and isort conventions are used. Keep line length at 120. Use type hints for
public APIs, Google-style docstrings for public classes/functions, `snake_case` functions and methods, `PascalCase`
classes, `UPPER_CASE` constants, and `_leading_underscore` for private helpers. Keep comments concise and in English.

Prefer small, adapter-scoped changes. Do not introduce broad abstractions unless at least two adapters already need the
same behavior and the shared layer is the right ownership boundary.

## Adapter Patterns

Most SQLAlchemy-based adapters use a Pydantic `Config` object plus a `Connector` class inheriting from
`SQLAlchemyConnector`; execute through `connector.execute({"sql_query": "..."}, result_format="list")`. StarRocks and
Trino add catalog-level addressing. ClickZetta is independent: it uses keyword-argument construction,
`connector.execute_query(sql, result_format)`, and does not inherit from `SQLAlchemyConnector`.

Respect dialect differences:

- MySQL, StarRocks, ClickHouse, Spark, and Hive use backtick identifiers.
- PostgreSQL, Redshift, Trino, and ClickZetta use double quotes.
- Trino and StarRocks may require catalog-qualified names.
- Do not assume metadata table names, pagination syntax, sample-row syntax, or schema/catalog semantics are portable
  across adapters.

When adding or changing an adapter, check these surfaces:

- connection initialization and config validation
- metadata discovery for databases, schemas, tables, views, and columns
- query execution and result formatting
- error wrapping and user-facing error messages
- dialect-specific identifier quoting and catalog/schema handling
- README examples and required environment variables

## Testing Guidelines

Unit tests must be fast and mocked; integration tests may use real database containers. Mark integration tests with
`@pytest.mark.integration` and skip cleanly when the service is unavailable. Do not hard-code credentials; use fixtures
and environment variables.

For new adapters or behavior changes, include focused coverage for connection initialization, metadata retrieval, query
execution, error handling, and representative SQL dialect behavior. For bug fixes, add the smallest regression test that
would have failed before the fix.

Run the narrowest meaningful test first, then run broader checks when the touched code is shared:

```bash
uv run pytest datus-<adapter>/tests/unit
uv run pytest datus-<adapter>/tests/integration
uv run ruff check .
```

If you cannot run an integration test because a local service or secret is unavailable, say so explicitly in the final
handoff and report which tests were run.

## Documentation Guidelines

Keep package READMEs aligned with actual connector behavior. Do not document unimplemented features as supported.
Document required environment variables for integration tests and examples close to the adapter that needs them.

When changing shared behavior, update the relevant shared docs or adapter docs in the same change. If a documentation
claim is uncertain, verify it in code before preserving it.

## Commit & Pull Request Guidelines

Commit messages follow the root monorepo Conventional Commits convention:

```text
<type>(<scope>): <中文描述>
```

Use a lowercase type such as `feat`, `fix`, `docs`, `test`, `refactor`, `build`, `ci`, or `chore`. Prefer
`db-adapters` as the shared workspace scope, or a short adapter scope such as `postgresql`, `mysql`, or `trino` when it
makes the affected package clearer. Keep the Chinese description concise and action-oriented.

Examples:

- `fix(db-adapters): 修复 PostgreSQL 跨库表结构查询`
- `feat(mysql): 增加元数据分页查询`
- `test(postgresql): 补充连接失败回归测试`
- `docs(db-adapters): 补充适配器维护说明`

PR titles use a separate upstream CI convention and must start with one of `[BugFix]`, `[Enhancement]`, `[Feature]`,
`[Refactor]`, `[UT]`, `[Doc]`, `[Tool]`, or `[Others]`; title-check CI rejects other prefixes. Example:
`[Enhancement] MySQL: Add TPC-H integration tests`.

PRs should include a clear summary, affected adapter(s), linked issue when applicable, and test evidence. If using a fork, create PRs with:

```bash
gh pr create --repo Datus-ai/datus-db-adapters \
  --head <fork-owner>:<branch-name> --base main \
  --title "[Enhancement] ..." --body "..."
```

## Parallel Work

When working on multiple adapters in parallel, use separate git worktrees and unique branches. Do not have parallel
agents share a worktree; git branch state, `index.lock`, staging, and commits will conflict.

## Security & Configuration

Do not commit credentials, generated caches, or local database state. Keep test secrets in environment variables and
document required variables in the adapter README or integration test README.

Check `.gitignore` before adding generated outputs. Avoid committing `.venv/`, database volumes, logs, coverage output,
or local IDE metadata.
