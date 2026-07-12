# CI 质量门禁维护指南

本文说明根级 GitHub Actions 质量门禁的稳定契约。修改 `.github/workflows/`、`.github/scripts/`、受控路径或 GitHub Ruleset 前，应先核对本文并运行对应的本地检查。

## 目标与边界

根级 CI 负责在一个 monorepo 中协调以下子项目：

- `datus-agent/`
- `datus-db-adapters/`
- `datus-storage-adapters/`
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
| `.github/workflows/python-quality.yml` | `Detect Python changes` | Agent、DB adapters、Storage adapters | `Python quality gate` |
| `.github/workflows/agent-artifact-renderer.yml` | `Detect relevant changes` | `Renderer package` | `Agent renderer gate` |
| `.github/workflows/web-quality.yml` | `Detect relevant changes` | `Tests and build` | `Web quality gate` |

三个 workflow 都监听：

```text
pull_request
merge_group
workflow_dispatch
```

不要在 workflow 顶层增加 `paths` 过滤。无关 PR 也需要运行 detector 和汇总 gate，才能稳定产生 Ruleset 要求的 context；是否运行实体 job 由仓库内 detector 决定。

`merge_group` 和 `workflow_dispatch` 不读取 PR 文件列表，而是强制相关 workflow 的所有实体 job 运行。

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

以下共享文件变化时，三个 Python 输出都必须为 `true`：

```text
.github/workflows/python-quality.yml
.github/scripts/detect-python-changes.cjs
.github/scripts/detect-python-changes.test.cjs
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
.github/scripts/verify-quality-gate.cjs
.github/scripts/verify-quality-gate.test.cjs
```

校验器文件同时登记在 Python detector 中，因此修改严格 gate 规则时，五个实体 job 都会运行。

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

Python gate 同时声明 `AGENT`、`DB_ADAPTERS` 和 `STORAGE_ADAPTERS`。

## Timeout 与重试

### Timeout

| Job 类型 | Timeout |
| --- | ---: |
| changes/control | 5 分钟 |
| required gate | 5 分钟 |
| Agent quality | 20 分钟 |
| DB adapters quality | 15 分钟 |
| Storage adapters quality | 15 分钟 |
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

- Actions 必须固定到完整 commit SHA，并保留版本注释。
- 默认权限保持只读：`contents: read` 和 detector 所需的 `pull-requests: read`。
- 不向 PR workflow 注入部署 secrets、真实数据库凭据或远程 LLM key。
- 不提交本地缓存、下载的 actionlint 二进制、构建产物或浏览器文件。
- 修改上游依赖或 renderer vendor 内容时，仍需遵守对应子项目的 `AGENTS.md`。

## 本地验证

从仓库根运行全部 CI 合约测试：

```bash
node --test .github/scripts/*.test.cjs
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
- [ ] 新 Action 固定完整 SHA。
- [ ] 实体测试没有自动重试。
- [ ] 本地 Node 合约测试、actionlint 和 `git diff --check` 通过。
- [ ] PR 上核对相关和无关 job 的实际状态。
- [ ] 高风险 workflow 变更合并后在 `main` 手动复验。
