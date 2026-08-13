# Repository Guidance

This file is the agent-facing entry point for `datus-agent`. Keep it concise. Put durable implementation details in project docs and keep `CLAUDE.md` as a pointer here.

## Project

Datus Agent is a Python 3.12+ `uv` project for natural-language data analysis, SQL generation/execution, RAG context, MCP tools, FastAPI APIs, and CLI workflows.

Common commands:

```bash
uv sync --dev
uv run ruff format datus/ tests/
uv run ruff check datus/ tests/
uv run pytest
uv run datus-api --config conf/agent.yml --port 8000 --reload
```

Use narrower tests first, then broaden when a change touches shared contracts, route security, storage, or execution paths.

## Canonical Docs

Read the most specific doc before editing:

- Enterprise product/security contract: `ENTERPRISE_PLATFORM_PLAN.zh.md`
- Enterprise implementation checklist: `ENTERPRISE_AI_DEVELOPMENT_GUIDE.zh.md`
- Local enterprise backend bring-up: `LOCAL_ENTERPRISE_BACKEND_TESTING.zh.md`
- Monorepo upstream handover and sync: `../docs/upstream-sync-manifest.yml` and `../docs/upstream-diff-budget.zh-CN.md`
- Public user/developer overview: `README.md` and `docs/develop/`

For enterprise-related code, read both enterprise docs before changing code. They define the stage boundary and fail-closed requirements. Do not rely on chat history alone.

## Enterprise Hard Rules

The downstream enterprise target is one enterprise scope with many employees. Do not add `tenant_id` as a baseline metadata dimension. Model departments, projects, roles, permissions, datasource grants, session ownership, artifact ACLs, audit, and quota inside that enterprise scope.

Follow this request chain:

```text
Authenticate -> Build Context -> Authorize -> Project Config -> Execute -> Audit
```

Rules that must not be weakened:

- Production enterprise mode must not trust bare `X-Datus-User-Id`, frontend roles, frontend permissions, request-body principal, or client-submitted enterprise context.
- Use `UserInfoBearerAuthProvider` when the gateway cannot change; use `SignedHeaderAuthProvider` when the gateway can inject signed identity headers. Direct OIDC/JWKS validation is a later provider, not the default MVP path.
- Enterprise pilot/production configs must explicitly configure real auth provider, authorization provider, datasource grant store, config projector, and audit sink. Loader fallback behavior is only for local compatibility.
- Keep route logic thin. Routes authenticate, authorize through shared dependencies, project request-scoped config, call services, and audit decisions.
- Never write user-specific authorization state into shared `DatusService.agent_config`; project into a request-scoped clone.
- Module RBAC, datasource grant, SQL policy principal, session owner, artifact ACL, platform status, quota, and audit are separate boundaries. Do not treat one as a substitute for another.
- Legacy routes that are not in the enterprise security chain must be disabled in `enterprise.enabled=true` and audited.
- Multi-worker or multi-pod deployments still need sticky chat/SSE/session routing unless task/event state has been externalized. Do not describe the current trial boundary as stateless HA.

When adding or changing any FastAPI route registered by `create_app()`, update `datus/api/enterprise/route_security_matrix.py` and the matching tests.

## Configuration Notes

Configuration load order is:

1. Explicit `--config`
2. `./conf/agent.yml` from the current working directory
3. `~/.datus/conf/agent.yml`

Project overrides live in `./.datus/config.yml` and may set `target`, `default_datasource`, and `project_name`. `/model` and `/datasource` commands may write these values.

Prefer provider-level model config under `agent.providers.<name>`; provider metadata and model lists come from `conf/providers.yml`. Use `agent.models.<name>` only for self-hosted or private endpoints not covered by the provider catalog.

Per-project KB content lives under `./subject/{semantic_models,sql_summaries}/`. Project skills live under `./.datus/skills/` and override global `~/.datus/skills`.

## Coding Rules

- Use type hints and Pydantic for structured data.
- Use `from datus.utils.loggings import get_logger`; do not add application `print()`.
- Raise `DatusException(ErrorCode.XXX, ...)` for domain errors.
- Route LLM calls through `LLMBaseModel`.
- Use `ConnectorRegistry` and `db_manager_instance`; do not import connector implementations directly in business logic.
- New tunables belong in YAML config, not hardcoded constants.
- Keep downstream changes small and isolated so upstream release merges stay manageable.
- Use English in code and comments. Chinese is fine in Chinese user-facing docs.
- Do not commit secrets, real tokens, generated caches, venvs, build output, or machine-local config.

## Upstream Diff Budget

Use `../docs/upstream-diff-budget.zh-CN.md` and the root `../docs/upstream-sync-manifest.yml` when changing files inherited from upstream. New downstream enterprise behavior should default to `datus_enterprise/`, enterprise config examples, scripts, or enterprise tests. Keep upstream-owned files as thin hooks only: startup registration, dependency adapters, request context, config projection, storage/execution extension points, and route security matrix integration.

When a change adds or keeps a modification to an upstream original file, classify it as one of: core hook, move-to-enterprise candidate, upstreamable fix, docs/config/meta, or test-only. Prefer moving enterprise policy logic out of route/service bodies before adding more branches there. For release upgrades, refresh the diff budget numbers after comparing `vX.Y.Z` with `HEAD:datus-agent`.

CLI UI colors, symbols, and helpers live in `datus/cli/cli_styles.py`. Use existing helpers such as `print_error`, `print_success`, `print_warning`, `print_info`, `print_status`, `print_usage`, and `print_empty_set`. For full-screen TUI components, follow `ModelApp` in `model_app.py`.

## Extension Points

- New node: add under `datus/agent/node/`, inherit `Node` or `AgenticNode`, register in `datus/configuration/node_type.py`, and add the factory mapping in `Node.new_instance()`.
- New provider using existing OpenAI-compatible behavior: update `conf/providers.yml` and `datus/conf/providers.yml`; add `model_specs` when needed.
- New model runtime requiring new SDK/auth behavior: add under `datus/models/`, inherit `LLMBaseModel`, register in `MODEL_TYPE_MAP`, and update regression provider coverage.
- New MCP tool: add under `datus/tools/func_tool/` and register in the MCP server tool list.
- New enterprise route or execution surface: update route security matrix, permissions, audit action, quota resource if applicable, and tests.

## Testing

Use `@pytest.mark.asyncio` and `pytest_asyncio.fixture` for async tests. Use `datus/utils/async_utils.py` for event-loop helpers.

Default verification levels:

| Change | Suggested checks |
| --- | --- |
| Docs/config examples | YAML/format check plus focused doc/config tests if referenced |
| Python unit behavior | `uv run ruff check ...` and focused `uv run pytest tests/unit_tests/...` |
| Typed code in `datus/`/`datus_enterprise/` | `uv run --with basedpyright==1.39.9 basedpyright datus datus_enterprise`；错误数不得超基线（CI 强制） |
| API route/security | route security matrix tests, auth/deps tests, focused API route tests |
| Enterprise auth/projection/session | enterprise smoke, owner/projection/legacy-disabled/platform-status tests |
| Provider/model changes | focused model tests plus provider coverage/regression targets |
| Broad shared contracts | `uv run python ci/run-pr-tests.py <base>` and test audit |

CI must not depend on API keys, remote LLMs, real network services, optional packages, or prebuilt external data. Gate true integration tests with environment variables and `skipif`.

### basedpyright 增量基线

根级 `python-quality.yml` 的 Agent quality job 运行 basedpyright（固定版本 `1.39.9`）并对比
`ci/basedpyright-baseline.json`：存量错误不阻塞，**新增错误或警告即失败**。基线由
`uv run --with basedpyright==1.39.9 basedpyright --outputjson datus datus_enterprise`
生成。基线更新方式：先修复并量化减少，再运行
`node ../.github/scripts/check-basedpyright-baseline.cjs --report <新报告> --baseline ci/basedpyright-baseline.json --update-baseline`
提交新的基线文件。升级 basedpyright 版本时必须在同一 PR 中同步重生成基线并说明规则变化；
不允许通过提高基线掩盖新增错误。

Test file naming:

- `tests/unit_tests/.../test_{module}.py`, mirroring the source path.
- `tests/integration/test_{scenario}.py`.
- `tests/regression/test_regression_{dimension}.py`.

## Git

Treat `main` as the stable downstream branch. Keep `upstream` read-only. Do not reset or rewrite `main` unless explicitly asked.

For new work:

```bash
git status --short --branch
git switch main
git pull --ff-only origin main
git switch -c feature/<name>
```

For upstream release updates, merge release tags on `upgrade/upstream-vX.Y.Z`; do not routinely merge `upstream/main` into `main`. Cherry-pick unreleased upstream fixes on short-lived hotfix branches.

Commit messages follow Conventional Commits:

```text
<type>(<scope>): <中文描述>
```

Allowed types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`.

Examples:

- `feat(api): 新增企业用户查询接口`
- `fix(auth): 修复用户信息认证失败处理`
- `docs(config): 中文化配置示例`
- `chore(upstream): 合并上游 v0.3.7 release`

Before pushing non-doc code, run the relevant focused tests and the harness required by the change. Never use `--no-verify`; fix hook failures instead.
