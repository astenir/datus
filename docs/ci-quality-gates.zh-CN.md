# CI 质量门禁维护指南

本文说明根级 GitHub Actions 质量门禁的稳定契约。修改 `.github/workflows/`、`.github/scripts/`、受控路径或 GitHub Ruleset 前，应先核对本文并运行对应的本地检查。

## 目标与边界

根级 CI 负责在一个 monorepo 中协调以下子项目：

- `datus-agent/`
- `datus-db-adapters/`
- `datus-storage-adapters/`
- `datus-semantic-adapter/`
- `metricflow/`
- `datus-web/`
- Agent 内嵌的 visual artifact renderer

门禁必须满足：

- 相关改动运行对应实体测试。
- 无关改动跳过昂贵实体测试，但仍产生稳定的 required check。
- 删除、重命名和跨目录移动不能漏检。
- detector 输出和实体 job 结果不一致时 fail closed。
- 默认门禁不依赖 secrets、远程 LLM、真实共享数据库或 self-hosted 路径。

三个 required check 名称是外部契约：

```text
Agent renderer gate
Web quality gate
Python quality gate
```

除非同步迁移 GitHub Ruleset，否则不要重命名这些 job。

## Workflow 结构

| Workflow | Detector | 实体 job | Required gate |
| --- | --- | --- | --- |
| `.github/workflows/python-quality.yml` | `Detect Python changes` | Agent、DB adapters、Storage adapters、Semantic adapter、MetricFlow | `Python quality gate` |
| `.github/workflows/agent-artifact-renderer.yml` | `Detect relevant changes` | `Renderer package` | `Agent renderer gate` |
| `.github/workflows/web-quality.yml` | `Detect relevant changes` | `Tests and build` | `Web quality gate` |

另有非门禁辅助 workflow `.github/workflows/title-check.yml`：监听 `pull_request_target`
（opened/edited/reopened/labeled/unlabeled），校验 PR 标题符合 Conventional Commits 规范
`<type>(<scope>): <描述>`，失败时打 `title needs formatting` label 并评论。它不参与三个
required gate，也不运行任何子项目实体测试；带 `dont-check-PRs-with-this-label` 或 `meta`
label 的 PR 跳过检查。校验脚本 `.github/scripts/check-pr-title.cjs` 在 workflow 内自带
`node --test` 自检，只读取 PR 元数据，不执行 PR 代码。

三个质量 workflow 都监听：

```text
pull_request
merge_group
workflow_dispatch
```

不要在 workflow 顶层增加 `paths` 过滤。无关 PR 也需要运行 detector 和汇总 gate，才能稳定产生 Ruleset 要求的 context；是否运行实体 job 由仓库内 detector 决定。

`merge_group` 和 `workflow_dispatch` 不读取 PR 文件列表，而是强制相关 workflow 的所有实体 job 运行。

## 本地默认检查与 PR 检查范围

本地命令和 PR gate 的依赖锁定方式、测试选择和外部服务边界并不完全相同：

- `datus-agent/AGENTS.md` 的 `uv run pytest` 是本地全量入口；PR 使用
  `uv sync --locked --group ci` 和 portable/focused pytest 集合，包含 route matrix、企业用户
  拒绝先于 service cache、请求级 datasource/model config 隔离、MCP request credential 隔离和
  history/tool summary 脱敏的定向用例；
- DB adapter、Storage adapter、Semantic adapter 和 MetricFlow 的 PR job 也使用锁定或
  portable 命令，integration/真实数据库检查不属于默认 required gate；
- Web PR job 运行 lint、maintenance rule tests、committed OpenAPI -> generated TypeScript stale check、Vitest、
  Playwright/browser test、typography 和 build，但不从运行中 backend 执行 `api:sync`，也不运行
  live enterprise smoke。

因此，“本地默认 pytest/build 可运行”不能写成“PR 已验证全部运行时依赖”；需要外部服务、
凭据或目标部署的检查必须单独标注。

## OpenAPI 生成契约（当前为部分自动规则）

`datus-web/openapi.json` 和 `datus-web/src/types/openapi.ts` 是由脚本生成的契约 artifact；
维护规则要求不得把它们手工维护成第二套 API 定义。当前静态审计能确认生成链，不能仅凭
Git 历史证明它们从未被手工编辑：

- `npm run api:pull` 从运行中的 FastAPI `/openapi.json` 拉取并写入 `openapi.json`；
- `npm run api:types` 使用 `openapi-typescript` 生成 `src/types/openapi.ts`；
- `npm run api:sync` 串联两个步骤；
- `npm run api:check` 在系统临时目录从 committed `openapi.json` 重新生成并规范化 TypeScript，
  与 committed `src/types/openapi.ts` 比较，不连接 backend，也不覆盖工作区；
- `datus-web/docs/openapi-implementation-map.md` 只记录前端覆盖状态，不替代 schema。

当前 tracked snapshot 的静态事实是 OpenAPI `3.1.0`、164 个 paths、201 个 operations；
`src/types/openapi.ts` 包含相同的 164 个 path keys。该比较不能替代对目标运行中 FastAPI
`/openapi.json` 的验证。此前实现映射中的 `149 operations` 摘要和表格合计 `137` 都不是
当前 schema 的 operation 总数，不能继续作为门禁基线。

当前 `StreamChatInput` 还存在一个需要保留在文档中的生成类型差异：OpenAPI/backend 只将
`message` 列为必填，`plan_mode`、`max_turns`、`prompt_language` 由 backend 默认值补齐；
生成的 TypeScript 却将这三个字段标为非 optional，而 Web request builder 不发送它们。
这是生成类型比 wire contract 更严格的已确认事实，不应通过手工修改生成文件来解决。

当前 Web quality workflow 执行 `npm run api:check`，能够阻止只修改 `openapi.json` 或只修改
`src/types/openapi.ts` 导致的生成产物漂移。该检查只验证 committed schema -> generated type；
它不会证明 committed `openapi.json` 与目标运行中 FastAPI 一致。

因此，修改 FastAPI route、Pydantic response model、SSE schema 或错误码时，开发者仍必须在
目标 backend 上运行 `npm run api:sync`，审阅生成 diff，并同步 API helper、composable、UI 和
测试。需要 backend、企业配置或凭据的 live schema/smoke 检查仍不是默认 PR gate。

OpenAPI 变更还必须保留以下错误层：HTTP status、`Result` application envelope 和 Chat
SSE `error` event 不能在 schema/前端类型同步时被压成一个通用错误。

### 生成文件检查边界

| 生成或 vendor 内容 | 当前生成源/命令 | 当前自动检查 | 例外与人工要求 |
| --- | --- | --- | --- |
| `datus-web/src/types/openapi.ts` | `openapi.json` + `npm run api:types` | Web PR 运行 `npm run api:check` | backend -> `openapi.json` 仍需目标环境 `api:sync`/smoke |
| `datus-agent/datus/agent/node/visual_artifact/vendor/web_artifact_render_dist/index.umd.js` | 固定 upstream bundle + documented patch | Renderer PR gate 校验 patched SHA | 升级时更新 upstream/patched provenance，禁止直接改 minified bundle |
| `datus-web/src/components/ui/**`、`src/components/ai-elements/**` | shadcn-vue/AI Elements registry | 未做逐文件 provenance 自动比较 | 默认只读；共享 build/a11y/runtime blocker 例外须说明来源并验证所有调用方 |
| `datus-agent/requirements-test.txt` | 文件头记录的 `uv export --locked` | 当前 root PR workflows 无通用 stale diff | 依赖变更需记录命令并审阅 lock/export diff |

不能仅凭目录名或 Git 历史断言生成文件从未手工修改。新增生成 artifact 时，至少记录 source、
generator version、生成命令、只读校验方式和允许的 manual patch/provenance 例外。

### Route security matrix 事实边界

`create_app()` 当前通过 enterprise route projection 替换或插入路由；
`datus-agent/tests/unit_tests/api/enterprise/test_route_security_matrix.py` 收集实际注册的
`APIRoute` method/path，并与 `ROUTE_SECURITY_MATRIX` 做集合相等断言。当前 tracked 源码的
静态结果为 201 个唯一 matrix keys，归一化 FastAPI path converter 后与 tracked OpenAPI
operation 集合没有差异。这个静态结果不等于当前运行环境中的最终路由集合；动态 import
失败、可选依赖缺失或配置差异仍需运行该测试确认。

## 路径检测契约

检测实现位于：

```text
.github/scripts/detect-python-changes.cjs
.github/scripts/detect-frontend-changes.cjs
```

PR Files API 的重命名记录同时包含：

```text
filename          新路径
previous_filename 旧路径
```

detector 必须同时检查两个字段。只检查 `filename` 会漏掉“从受控目录移出”的文件。

### Python

| 输出 | 路径前缀 |
| --- | --- |
| `agent` | `datus-agent/` |
| `db_adapters` | `datus-db-adapters/` |
| `storage_adapters` | `datus-storage-adapters/` |
| `semantic_adapter` | `datus-semantic-adapter/` |
| `metricflow` | `metricflow/` |

根级 Agent Compose 部署配置也会触发 `agent`：

```text
.env.compose.example
docker-compose.yml
deploy/docker/agent/
```

Python detector 同时表达依赖传播：`metricflow/` 改动还会触发 Semantic adapter 和
Agent；`datus-semantic-adapter/` 改动还会触发 Agent。这样本地 path dependency 的下游
初始化回归不会被跳过。

以下共享文件变化时，五个 Python 输出都必须为 `true`：

```text
.github/workflows/python-quality.yml
.github/scripts/detect-python-changes.cjs
.github/scripts/detect-python-changes.test.cjs
.github/scripts/check-workflow-policy.cjs
.github/scripts/check-workflow-policy.test.cjs
.github/scripts/verify-quality-gate.cjs
.github/scripts/verify-quality-gate.test.cjs
```

### Renderer

Renderer 响应以下精确路径：

```text
.github/workflows/agent-artifact-renderer.yml
datus-agent/tests/integration/test_artifact_renderer_package.py
datus-agent/tests/unit_tests/agent/node/test_dashboard_html_renderer.py
datus-agent/pyproject.toml
datus-agent/uv.lock
```

以及目录前缀：

```text
datus-agent/datus/agent/node/visual_artifact/
```

### Web

Web 响应：

```text
.github/workflows/web-quality.yml
datus-web/
datus-agent/datus/agent/node/visual_artifact/
```

Visual artifact 代码同时影响 Agent 内嵌 renderer 和浏览器行为，因此该目录必须同时触发 Renderer 与 Web。

### 共享控制文件

以下文件变化时，Renderer 与 Web 都必须运行：

```text
.github/scripts/detect-frontend-changes.cjs
.github/scripts/detect-frontend-changes.test.cjs
.github/scripts/check-workflow-policy.cjs
.github/scripts/check-workflow-policy.test.cjs
.github/scripts/verify-quality-gate.cjs
.github/scripts/verify-quality-gate.test.cjs
```

校验器文件同时登记在 Python detector 中，因此修改严格 gate 规则时，七个实体 job 都会运行。

## 严格 Gate 契约

统一校验器位于：

```text
.github/scripts/verify-quality-gate.cjs
```

真值表如下：

| Detector relevance | 实体 job result | Gate 结果 |
| --- | --- | --- |
| `true` | `success` | 通过 |
| `false` | `skipped` | 通过 |
| `true` | `skipped` | 失败 |
| `false` | `success` | 失败 |
| 任意 | `failure`、`cancelled` 或空值 | 失败 |
| 空值或非 `true`/`false` | 任意 | 失败 |

此外，changes job 必须为 `success`。这可以拦截 output 名称、`if` 条件、job id 或环境变量接线错误导致的假阳性。

各 workflow 通过 `QUALITY_JOBS` 和配套环境变量声明实体 job。例如：

```text
QUALITY_JOBS=WEB
WEB_RELEVANT=<detector output>
WEB_RESULT=<job result>
```

Python gate 同时声明 `AGENT`、`DB_ADAPTERS`、`STORAGE_ADAPTERS`、
`SEMANTIC_ADAPTER` 和 `METRICFLOW`。

## Timeout 与重试

### Timeout

| Job 类型 | Timeout |
| --- | ---: |
| changes/control | 5 分钟 |
| required gate | 5 分钟 |
| Agent quality | 20 分钟 |
| DB adapters quality | 15 分钟 |
| Storage adapters quality | 15 分钟 |
| Semantic adapter quality | 15 分钟 |
| MetricFlow quality | 15 分钟 |
| Renderer package | 20 分钟 |
| Web Tests and build | 25 分钟 |

短 timeout 只用于 checkout、detector 和 gate verifier 等控制任务。不要把 5 分钟限制直接套到安装依赖、浏览器测试或完整构建。

### GitHub API 重试

三个 detector 的 `actions/github-script` 对只读 PR Files API 使用：

```yaml
retries: 3
retry-exempt-status-codes: 400,401,403,404,422
```

重试仅用于可恢复的网络或服务端故障。400/401/403/404/422 通常表示请求、身份、权限或资源状态错误，应立即失败。

不要给实体测试、lint 或构建增加自动重试。真实回归不能通过重复执行掩盖。

## 安全与供应链约束

- `.github/scripts/check-workflow-policy.cjs` 自动扫描 `.github/workflows/*.yml` 和 `*.yaml`。
- 远程 Actions 必须固定到 40 位小写 commit SHA，并保留版本注释；仓库内 `uses: ./...` 可以使用相对路径。
- 每个 workflow 必须登记显式权限白名单；质量 workflow 只允许 `contents: read` 和 `pull-requests: read`，title-check 额外允许 `pull-requests: write`（用于打 label 和评论，是白名单中唯一的 write 权限）。
- 禁止 job 级 `permissions` 覆盖。新增 workflow 或权限必须先更新并评审显式白名单。
- 不向 PR workflow 注入部署 secrets、真实数据库凭据或远程 LLM key。
- 不提交本地缓存、下载的 actionlint 二进制、构建产物或浏览器文件。
- 修改上游依赖或 renderer vendor 内容时，仍需遵守对应子项目的 `AGENTS.md`。

## 本地验证

从仓库根运行全部 CI 合约测试：

```bash
node --test .github/scripts/*.test.cjs
```

验证 committed OpenAPI snapshot 与 generated TypeScript：

```bash
cd datus-web
npm run api:check
```

直接检查 Action 固定与权限策略：

```bash
node .github/scripts/check-workflow-policy.cjs
```

检查所有 CommonJS 文件语法：

```bash
for file in .github/scripts/*.cjs; do node --check "$file"; done
```

安装 `actionlint` 后检查三个 workflow：

```bash
actionlint \
  .github/workflows/python-quality.yml \
  .github/workflows/agent-artifact-renderer.yml \
  .github/workflows/web-quality.yml
```

最后检查 diff：

```bash
git diff --check
```

修改 workflow、detector、gate verifier 或共享路径时，不能只依赖本地单元测试。PR 上应确认预期实体 job 是 `success` 或 `skipped`，合并后按风险手动触发对应 workflow：

```bash
gh workflow run python-quality.yml --ref main
gh workflow run agent-artifact-renderer.yml --ref main
gh workflow run web-quality.yml --ref main
```

## 故障定位顺序

### Detector 失败

1. 查看 checkout 和 detector 测试是否通过。
2. 查看 `actions/github-script` 的 API 错误和状态码。
3. 确认权限仍包含 `pull-requests: read`。
4. 确认 `filename` 与 `previous_filename` 都被保留。
5. 对照路径表检查精确路径和带 `/` 的目录前缀。

### 实体 job 被意外跳过

1. 查看 detector output 是否为 `true`。
2. 检查实体 job 的 `if: needs.changes.outputs.* == 'true'`。
3. 检查 output 名称、job id 和 `needs` 是否一致。
4. 如果 detector 为 `true` 但实体 job 为 `skipped`，严格 gate 应失败，不要放宽 gate。

### Gate 失败

1. 先确认 changes job 是否为 `success`。
2. 查看 gate 日志中的 `*_RELEVANT` 与 `*_RESULT`。
3. `true/success` 和 `false/skipped` 之外的组合都是错误。
4. 空 relevance 通常表示 output 名称或 `needs` 接线漂移。
5. 不要通过允许任意 `skipped` 来修复 gate。

### Ruleset 长时间等待

1. 确认 workflow 仍监听当前事件。
2. 确认 required gate job 名称未变化。
3. 确认没有在 workflow 顶层添加阻止其启动的 `paths`。
4. 读取默认分支的生效 Ruleset，核对三个 required context。
5. 检查 concurrency 是否取消了旧运行，并确认新运行已经接管。

## 修改检查清单

修改 CI 控制面时至少确认：

- [ ] 路径新增、删除、重命名和跨目录移动都有测试。
- [ ] 共享控制文件登记在所有受影响 detector 中。
- [ ] `previous_filename` 没有被丢弃。
- [ ] detector output、实体 job `if`、gate 环境变量名称一致。
- [ ] required gate 名称未变化，或已计划同步迁移 Ruleset。
- [ ] 新 Action 固定完整 40 位小写 SHA，workflow 权限已登记显式白名单。
- [ ] 实体测试没有自动重试。
- [ ] 本地 Node 合约测试、actionlint 和 `git diff --check` 通过。
- [ ] PR 上核对相关和无关 job 的实际状态。
- [ ] 高风险 workflow 变更合并后在 `main` 手动复验。
