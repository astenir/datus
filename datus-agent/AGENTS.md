# Repository Guidance

This file is the agent-facing working contract for this checkout. Keep it aligned with `CLAUDE.md`, but treat the Git model below as the repo-specific override for this personal downstream fork.

## Project Overview

Datus Agent is an AI-powered data-analysis agent for NL to SQL workflows, multi-database access, RAG knowledge bases, and MCP integration.

- Stack: Python 3.12+, OpenAI Agents SDK + LiteLLM, LanceDB, FastAPI, FastMCP, Streamlit.
- Package manager: `uv`.
- License: Apache-2.0.

## Enterprise Platform Plan

This downstream fork has a productization target documented in:

- `ENTERPRISE_PLATFORM_PLAN.zh.md`: enterprise internal platform development plan, focused on single-tenant enterprise deployment, multi-user access, RBAC, datasource authorization, execution safety, audit, API organization, and high-availability evolution. Do not add `tenant_id` as a baseline metadata dimension; model one enterprise scope with users, roles, departments/projects, datasource grants, and artifact ACLs.
- `ENTERPRISE_AI_DEVELOPMENT_GUIDE.zh.md`: implementation standard for future AI agents and developers working on the enterprise platform plan.

For enterprise-related work, read both files before changing code. Keep route logic thin: authenticate, authorize through shared dependencies, project request-scoped config, execute through services, and audit security decisions. Do not scatter hard-coded role checks in routes, do not treat frontend hiding or `scoped_context` as a complete security boundary, and do not mutate shared `DatusService.agent_config` with user-specific authorization state. Assume one enterprise scope with many employees; model departments, projects, and roles through permissions and datasource grants.

## Downstream Git Model

- Treat `main` as the stable downstream branch for this fork, not as a mirror of `upstream/main`.
- Track official Datus Agent updates through release tags fetched from `upstream`.
- Keep `upstream` as a read-only source for official branches and tags. Do not push to `upstream`.
- Current observed upstream release baseline: `v0.3.6`. Verify current tags with `git fetch upstream --tags` before any upgrade.
- Do not rewrite `main` or reset it to `upstream/main` unless the user explicitly asks for that operation.

## Branch Workflow

Create feature work from `main`:

```bash
git switch main
git pull --ff-only origin main
git switch -c feature/<name>
```

Merge completed feature work back to `main` after verification:

```bash
git switch main
git merge --no-ff feature/<name>
git push origin main
```

Before making Git writes, check:

```bash
git status --short --branch
```

Push only to `origin`, never to `upstream`.

## Upstream Release Upgrades

Do not merge `upstream/main` directly into `main` for routine synchronization. For each official release, fetch tags and stage the upgrade on a dedicated branch:

```bash
git fetch upstream --tags
git switch main
git pull --ff-only origin main
git switch -c upgrade/upstream-vX.Y.Z
git merge vX.Y.Z
```

Resolve conflicts, run the relevant tests, then merge the upgrade branch back to `main`:

```bash
git switch main
git merge --no-ff upgrade/upstream-vX.Y.Z
git push origin main
```

Use commit messages that name the upstream release, for example:

```text
[Others] 合并上游 v0.3.7 release
```

If an unreleased upstream fix is needed before the next release tag, cherry-pick the specific upstream commit on a short-lived branch instead of merging `upstream/main`:

```bash
git fetch upstream
git switch main
git switch -c hotfix/upstream-<topic>
git cherry-pick <upstream_commit_sha>
```

After validation, merge the hotfix branch back to `main`.

## Build And Run

```bash
uv sync
uv run python ci/run-pr-tests.py upstream/main
uv run pytest -m nightly tests/
uv run pytest -m "nightly or regression" tests/
uv run ruff format datus/ tests/
uv run ruff check --fix datus/ tests/
bash build_scripts/build_test_data.sh
```

Use the PR CI harness for ordinary upstream-style changes. For local downstream feature branches, choose the diff base deliberately, usually `main` or `origin/main`, so the harness does not treat the whole downstream fork as the change set. Use nightly or regression suites when the touched code depends on real external services, model APIs, or broader compatibility behavior.

## Coding Conventions

- Use Ruff for formatting and linting. The project uses line length 120, excludes `mcp/`, and groups imports as stdlib, third-party, then `datus.*`.
- Use type hints throughout; use Pydantic for structured data.
- Use `from datus.utils.loggings import get_logger`; do not add `print()` for application logging.
- Raise `DatusException(ErrorCode.XXX, ...)` from `datus.utils.exceptions` for domain errors.
- Error-code ranges: `1xxxxx` common, `2xxxxx` node, `3xxxxx` model, `4xxxxx` tool/storage, `5xxxxx` database, `6xxxxx` semantic.
- Use English in code and comments. For upstream PRs, use English commit and PR text. For this downstream fork's local commits, keep the existing bracketed category plus Chinese summary style unless the user asks otherwise, for example `[Others] 合并上游 v0.3.7 release`.
- Chinese is acceptable in user-facing docs explicitly targeted to Chinese readers.

## CLI UI Rules

All CLI colors, symbols, and helpers live in `datus/cli/cli_styles.py`.

- Use `print_error`, `print_success`, `print_warning`, `print_info`, `print_status`, `print_usage`, and `print_empty_set` instead of inline Rich markup.
- Colors should not be `bold`; reserve `bold` for headers and prompt labels.
- Use Unicode `✓` and `✗` only; do not add emoji in new code.
- Use short closing tags like `[/]`.
- Tables should use `header_style=TABLE_HEADER_STYLE`; prefer `build_row_table()` from `_render_utils.py`.
- Use `CODE_THEME = "monokai"` for all `Syntax()` rendering.
- Interactive selectors should import `CLR_CURSOR` and `CLR_CURRENT` from `cli_styles`.

For full-screen TUI components, follow `ModelApp` in `model_app.py`: wrap `app.run()` in `tui_app.suspend_input()`, never nest `asyncio.run()`, use `DynamicContainer` plus `Condition` guards, and exit via `app.exit(result=Selection(...))`.

## Async Tests

Use `@pytest.mark.asyncio` and `pytest_asyncio.fixture`. For event-loop helpers, especially Windows compatibility, use `datus/utils/async_utils.py`.

## Architecture Notes

### Storage Layout

Per-project paths anchored to the current working directory:

- `./subject/{semantic_models, sql_summaries}/` stores KB content.
- `./.datus/skills/` stores project skills and overrides `~/.datus/skills`.
- `./.datus/config.yml` stores whitelisted project overrides for `target`, `default_datasource`, and `project_name`; it is written by the `/model` slash command.

Global paths are sharded by project:

- `~/.datus/sessions/{project}/{session_id}.db`
- `~/.datus/data/{project}/datus_db/`
- `~/.datus/{conf, logs, cache, template, run, benchmark, workspace, skills}`

`project_name` is derived from CWD via `_normalize_project_name` in `agent_config.py`; long paths get an md5 suffix. `agent.knowledge_base_home` has been removed; KB content always lives under `{project_root}/subject/`, and the YAML field is silently ignored.

### LLM Configuration

Prefer provider-level configuration under `agent.providers.<name>` in `agent.yml`. Credentials live there, while available models come from `conf/providers.yml`. The `/model` CLI command switches active provider/model without YAML edits.

Use `agent.models.<name>` only for self-hosted or legacy endpoints not covered by `providers.yml`.

Active selection persists in `./.datus/config.yml`:

```yaml
target: { provider: openai, model: gpt-4.1 }
```

Resolution order is `.datus/config.yml`, then `agent.target` in `agent.yml`.

### Extension Points

- New node: add a file under `datus/agent/node/`, inherit `Node` or `AgenticNode`, register the type in `datus/configuration/node_type.py`, and add the factory mapping in `Node.new_instance()` in `node.py`.
- New LLM provider using the existing interface: add entries to `conf/providers.yml` and `datus/conf/providers.yml`; optionally add `model_specs`. No Python change is normally required.
- New LLM model requiring new SDK/auth behavior: add a file under `datus/models/`, inherit `LLMBaseModel`, register in `MODEL_TYPE_MAP`, and add to `PROVIDER_MODELS` in `tests/regression/test_regression_llm.py`.
- New MCP tool: add the function under `datus/tools/func_tool/` and register it in the MCP server tool list.

## Guardrails

- Use `ConnectorRegistry` and `db_manager_instance`; do not add direct database imports.
- Route LLM calls through `LLMBaseModel`; do not hardcode LLM calls in nodes.
- CI tests must not depend on API keys, pre-built data, network access, or external services.
- Keep secrets out of code. Use environment variables or `${ENV_VAR}` substitution in `agent.yml`.
- New tunable parameters belong in YAML config, not hardcoded constants.
- Keep downstream changes small and reviewable so future release merges stay manageable.

## PR Conventions

PR titles must start with one of:

```text
[BugFix] [Enhancement] [Feature] [Refactor] [UT] [Doc] [Tool] [Others]
```

PR bodies must follow `.github/PULL_REQUEST_TEMPLATE.md` and fill all sections:

- `## Why`: problem solved; link issues if any.
- `## Solution`: approach, key decisions, and tradeoffs.
- `## Test Cases`: added or changed integration/nightly tests; justify if none.

When using `gh pr create --body`, copy `.github/PULL_REQUEST_TEMPLATE.md` as the starting point. Empty or missing sections must be revised before review.

## Commit Workflow

Run the same gates that protect ordinary PRs before pushing, and keep extra full-suite runs targeted to high-risk changes.

1. Pre-format:

   ```bash
   uv run ruff format datus/ tests/
   uv run ruff check --fix datus/ tests/
   ```

2. PR coverage harness:

   ```bash
   uv run python ci/run-pr-tests.py upstream/main
   ```

   Inspect `ci/test-report.md` and `ci/diff-cover-report.md` on failure. For downstream feature branches, use the appropriate downstream base instead of `upstream/main` when the goal is to validate only local feature changes.

3. Test-quality audit:

   ```bash
   uv run python ci/audit_tests.py --repo-root . --diff-only upstream/main
   ```

   It must report `P0=0`. For downstream feature branches, use the appropriate downstream base instead of `upstream/main` when auditing only local feature changes. Use `--all` when many test files changed. Use `# audit-noqa: <rule>` only with justification.

4. Merge-queue rehearsal:

   ```bash
   uv run python ci/run-merge-queue-tests.py
   ```

   Run this when changing acceptance harness targets, CI scripts, or code likely to affect merge-queue-only integration coverage.

5. Never use `--no-verify`; auto-fix and retry until pre-commit hooks pass.

## Testing Rules

### Tiers And Mocking

| Tier | Marker | Mock policy |
| --- | --- | --- |
| CI | PR acceptance harness plus impacted `tests/unit_tests/`; under 5 s/test, deterministic | Mock all external calls: LLM, remote DBs, network, optional packages. |
| Nightly | `@pytest.mark.nightly` | Real LLM APIs are OK; mock unstable services. |
| Regression | `@pytest.mark.regression` | Real services; gate missing keys with `@pytest.mark.skipif`. |

CI runs without optional packages such as `datus-bi-superset` and `datus-bi-grafana`. Tests touching code that imports them must work whether or not the package is installed. `datus-bi-core` is a hard dependency and always available.

### Test File Naming

| Location | Pattern |
| --- | --- |
| `tests/unit_tests/` | `test_{module}.py`, mirroring source path: `datus/a/b/c.py` -> `tests/unit_tests/a/b/test_c.py`. |
| `tests/integration/` | `test_{scenario}.py`. |
| `tests/regression/` | `test_regression_{dimension}.py`. |

Create intermediate `__init__.py` files when adding new test subdirectories. Use `@pytest.mark.skipif(not os.getenv("KEY"), reason=...)` for missing API keys. Use parametrization such as `@pytest.mark.parametrize("db_type", [DBType.SQLITE, DBType.DUCKDB])` when behavior should cover multiple database backends.

### Additional Test Targets

| Modified module | Additional tests |
| --- | --- |
| `datus/models/{provider}_model.py` | `integration/models/test_*_model.py`, `regression/test_regression_llm.py` |
| `datus/agent/node/` | `unit_tests/agent/node/test_node.py`, `test_schema_linking.py`, `test_date_parser_*.py` |
| `datus/cli/repl.py` | `integration/cli/test_cli_commands.py`, `regression/test_regression_web_e2e.py` |
| `datus/tools/func_tool/` | `integration/tools/test_func_tools_db.py`, `integration/tools/test_mcp_server.py` |
| `datus/tools/skill_tools/` | `unit_tests/tools/skill_tools/test_skill_*.py` |
| `datus/tools/permission/` | `unit_tests/tools/permission/test_permission_*.py` |
| `datus/mcp_server.py` | `unit_tests/test_mcp_server.py`, `integration/tools/test_mcp_server.py` |
| `datus/storage/reference_template/` | `unit_tests/storage/reference_template/test_*.py`, `integration/tools/test_reference_template.py` |
| `datus/storage/document/` | `integration/storage/test_doc_search.py`, `integration/storage/test_platform_doc.py` |

Beyond happy paths, test input format variants, return-type contracts, cross-component contracts, adversarial inputs for regex/SQL/path sandboxes, recursive or nested structures at depth 3 or more, and standards compliance such as `.gitignore` and SQL dialect behavior.
