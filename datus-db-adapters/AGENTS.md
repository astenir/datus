# Datus Database Adapters Guidelines

## Canonical Instructions

This file is the canonical guide for Codex and Claude when working under `datus-db-adapters/`. Keep shared adapter rules here. Keep `CLAUDE.md` as a short Claude entry point only.

## Project Structure

This directory is a Python `uv` workspace of independent database adapter packages for Datus. Shared package code is in `datus-db-core/`; concrete adapters live in directories such as `datus-postgresql/`, `datus-mysql/`, `datus-trino/`, `datus-starrocks/`, and `datus-snowflake/`.

Each adapter should keep source under `datus_<adapter>/`, unit tests under `tests/unit/`, integration tests under `tests/integration/`, optional setup scripts under `scripts/`, and a local `docker-compose.yml` when integration tests need a database container.

## Build, Test, and Development Commands

Use Python 3.12. Prefer `uv` for workspace development.

```bash
uv sync --dev
uv run pytest datus-postgresql/tests/unit
uv run pytest datus-postgresql/tests/integration
uv run ruff check .
uv run ruff format .
```

For adapter-local execution, use:

```bash
cd datus-<adapter>
python -m pytest tests/unit/ -v
python -m pytest tests/integration/ -v
```

Integration tests require the relevant database service. Use the adapter’s `docker-compose.yml` and setup scripts when present.

## Coding Style & Naming Conventions

Ruff, Black-compatible formatting, Flake8, and isort conventions are used. Keep line length at 120. Use type hints for public APIs, Google-style docstrings for public classes/functions, `snake_case` functions and methods, `PascalCase` classes, `UPPER_CASE` constants, and `_leading_underscore` for private helpers. Keep comments concise and in English.

## Adapter Patterns

Most SQLAlchemy-based adapters use a Pydantic `Config` object plus a `Connector` class inheriting from `SQLAlchemyConnector`; execute through `connector.execute({"sql_query": "..."}, result_format="list")`. StarRocks and Trino add catalog-level addressing. ClickZetta is independent: it uses keyword-argument construction, `connector.execute_query(sql, result_format)`, and does not inherit from `SQLAlchemyConnector`.

Respect dialect differences. MySQL, StarRocks, ClickHouse, Spark, and Hive use backtick identifiers. PostgreSQL, Redshift, Trino, and ClickZetta use double quotes. Trino and StarRocks may require catalog-qualified names.

## Testing Guidelines

Unit tests must be fast and mocked; integration tests may use real database containers. Mark integration tests with `@pytest.mark.integration` and skip cleanly when the service is unavailable. Do not hard-code credentials; use fixtures and environment variables. For new adapters, include coverage for connection initialization, metadata retrieval, query execution, error handling, and representative SQL dialect behavior.

## Commit & Pull Request Guidelines

Commit messages in this downstream monorepo should use Chinese after the bracketed category, for example `[Doc] 补充适配器维护说明`.

PR titles must start with one of `[BugFix]`, `[Enhancement]`, `[Feature]`, `[Refactor]`, `[UT]`, `[Doc]`, `[Tool]`, or `[Others]`; title-check CI rejects other prefixes. Example: `[Enhancement] MySQL: Add TPC-H integration tests`.

PRs should include a clear summary, affected adapter(s), linked issue when applicable, and test evidence. If using a fork, create PRs with:

```bash
gh pr create --repo Datus-ai/datus-db-adapters \
  --head <fork-owner>:<branch-name> --base main \
  --title "[Enhancement] ..." --body "..."
```

## Parallel Work

When working on multiple adapters in parallel, use separate git worktrees and unique branches. Do not have parallel agents share a worktree; git branch state, `index.lock`, staging, and commits will conflict.

## Security & Configuration

Do not commit credentials, generated caches, or local database state. Keep test secrets in environment variables and document required variables in the adapter README or integration test README.
