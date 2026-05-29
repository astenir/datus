# Repository Guidelines

## Project Structure & Module Organization

`datus/` contains the Python package. Major areas include `agent/` for agent workflows, `cli/` for the `datus` and `datus-agent` command surfaces, `api/`, `gateway/`, `tools/`, `storage/`, `schemas/`, `prompts/`, and shared helpers in `utils/`. Configuration examples live in `conf/`. Tests are under `tests/`, split into `unit_tests/`, `integration/`, `regression/`, plus shared fixtures in `tests/data/` and `tests/conf/`. Documentation is in `docs/`, documentation assets in `docs/assets/`, benchmark tooling in `benchmark/`, packaging scripts in `build_scripts/`, and CI helpers in `ci/`.

## Build, Test, and Development Commands

Use Python 3.12 and `uv` for local development.

```bash
uv venv -p 3.12
uv sync --dev
uv run datus --version
uv run datus-agent --version
```

Run tests with `uv run pytest`. Limit scope while iterating, for example `uv run pytest tests/unit_tests/utils/test_json_utils.py`. Build and packaging flows are exposed through `make`: `make build` builds distributions, `make check` validates them, `make test` smoke-tests the package, and `make all` runs clean, build, check, and test. Build docs with `uv run --with mkdocs-material --with mike --with mkdocs-static-i18n mkdocs build --strict`.

## Coding Style & Naming Conventions

Ruff is the formatter, import sorter, and linter. Use `uv run ruff format datus/ tests/` and `uv run ruff check datus/ tests/` before submitting. The configured line length is 120 and the target runtime is Python 3.12. Prefer typed, focused functions; keep first-party imports under `datus`. Python files and functions use `snake_case`, classes use `PascalCase`, and tests use `test_*.py`.

## Testing Guidelines

Pytest discovers `tests/test_*.py` and runs with verbose output from `pytest.ini`. Add unit tests near the matching subsystem under `tests/unit_tests/`; use `tests/integration/` only when multiple components or external adapters are involved. Mark specialized tests with existing markers such as `acceptance`, `component`, `integration`, `nightly`, `benchmark`, or `regression`. Avoid real provider or service dependencies in routine unit tests.

## Commit & Pull Request Guidelines

Recent commits and PR checks use prefixes such as `[BugFix]`, `[Feature]`, `[Enhancement]`, `[Refactor]`, `[UT]`, `[Doc]`, `[Tool]`, or `[Others]`; keep titles in that style. PRs should include `Why`, `Solution`, and `Test Cases`, link related issues when applicable, and explain omitted tests. Include screenshots or terminal output for CLI, TUI, docs, or visual changes.

## Security & Configuration Tips

Do not commit secrets. Copy `conf/agent.yml.example` to `conf/agent.yml` for local work and reference credentials through environment variables such as `${OPENAI_API_KEY}`. Keep generated local state in `.datus/` or `~/.datus/` out of commits.
