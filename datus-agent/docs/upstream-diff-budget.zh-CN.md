# 上游差异预算

本文档记录 `datus-agent` 相对上游 release tag 的下游差异预算。目标不是把企业版改造成零 diff，而是让上游原文件中的下游逻辑保持少量、稳定、可解释，并把企业逻辑优先归位到新增模块。

## 当前基线

基线采样日期：2026-07-24

说明：这是完成正式 `v0.3.8` release 合并、企业权限回归修复和真实企业 auth/catalog/SQL smoke 后的采样结果。`v0.3.8` 使用上游 annotated tag 的 release tree；下游仍保留企业平台、OceanBase/PG stores、本地联调和独立测试等长期差异。

对比口径：

```bash
cd /home/astenir/Code/work/datus
git diff --shortstat v0.3.8 HEAD:datus-agent
git diff --name-status -M v0.3.8 HEAD:datus-agent
```

当前结果：

```text
331 files changed, 76426 insertions(+), 6824 deletions(-)
150 added
177 modified
4 deleted
```

修改的上游既有文件按类型拆分：

```text
97 production/package files
63 tests
9 docs
8 config/meta files
```

分类口径：只统计 `modified`；`datus/` 归 production/package，`tests/` 归 tests，`docs/` 归 docs，其余根级构建、配置、CI 和锁文件归 config/meta。新增文件另含 29 个 production、69 个 tests、11 个 docs 和 41 个 config/meta；它们主要是下游企业模块、脚本、测试、文档和部署资产，不与修改的上游既有文件混算。

这些数字是升级治理指标。每次完成一次上游 release 合并或低风险收敛后，都应该刷新这一节，说明数字变大或变小的原因。

## 收敛记录

### 2026-07-24：浏览器文件工具策略显式化

问题：上游 `v0.3.8` 默认在 `normal` 权限模式下把 Web 文件写工具代理给客户端；当前下游 Vue 客户端没有浏览器文件执行器。升级后的临时兼容修复直接改写了 `ChatTaskManager` 默认行为，导致直接实例化的契约偏离上游，也把下游前端能力假设写进了上游核心默认值。

处理方式：`ChatTaskManager.web_filesystem_executor` 默认保持上游语义 `client`；`DatusService` 从 `agent.api.chat.web_filesystem_executor` 显式装配下游策略，并在未配置时使用兼容默认值 `server`。下游完整配置和企业配置片段都显式写出 `server`；接入真正实现代理执行和结果回传的上游兼容客户端时可以切换为 `client`。非法值在服务构造时直接失败。

测试边界：恢复上游原测试中的 Web 默认行为断言，把下游 `server` 行为放到新增的 `test_chat_task_manager_downstream.py`；聚焦服务测试同时覆盖缺省值、显式 `client` 和非法配置。

同时恢复为 `v0.3.8` 原内容的低风险上游文件：

```text
conf/agent.yml.example
conf/auth_clients.yml.example
docs/configuration/introduction.md
docs/configuration/introduction.zh.md
mkdocs.yml
```

下游配置选择、legacy auth 边界、OceanBase Oracle 示例和 embedding 限制仍保留在 `conf/README.zh-CN.md`、`conf/agent.downstream.zh-CN.yml.example` 与独立下游文档中。相对本轮开始时，modified 上游文件由 182 降到 177；新增 1 个下游测试文件后，总差异文件由 335 降到 331。

### 2026-07-24：升级到正式 v0.3.8

处理方式：通过 GitHub 镜像获取并校验正式 annotated tag，以 `v0.3.7` 为显式三方合并基线，将 `v0.3.8` release tree 合入隔离分支；冲突处理同时保留上游 plugin、metadata FTS、OSI authoring 和 prompt 更新，以及下游企业 runtime/tool policy、datasource grant、存储和安全边界。

本轮额外修复的交叉回归：

```text
canonical history 的模型 JSON envelope 展示
qualified datasource tree scope 与 catalog 过滤
direct SQL 的 tree-scope database 祖先可达性
CLI 临时 DB guard 的 request principal
reference SQL 缺省 ID 与非空 storage_key 兼容
KB bootstrap datasource_id 测试契约
```

依赖边界：`datus-agent` 更新为 `0.3.8`，CI 组要求的 `datus-semantic-metricflow>=0.2.9` 已与相邻 workspace 的实际包版本对齐到 `0.2.9`，两个锁文件均重新解析。没有通过降低约束掩盖本地 source 版本不一致。

数字变化说明：本文旧快照来自 `v0.3.7` 时期的历史采样；本轮统一改为正式 `v0.3.8` tag tree 口径，并把当前仍存在的全部下游新增模块和上游既有文件修改纳入统计，因此不能把 `335` 与旧文档中的 `199` 简单解释为本次 release 新增了 136 个业务改动。后续 release 应持续使用同一 tag-tree 和分类口径比较趋势。

### 2026-07-07：公开文档低风险迁移

处理方式：把下游前端契约、多库枚举和 OceanBase MySQL 存储说明从上游公开文档迁到新增下游文档，避免这些文件在后续 release 合并时反复冲突。

已恢复为 `v0.3.7` 内容的上游文档：

```text
docs/API/chat.md
docs/API/chat.zh.md
docs/API/introduction.md
docs/configuration/datasources.md
docs/configuration/datasources.zh.md
docs/configuration/storage.md
docs/configuration/storage.zh.md
```

下游补充内容迁入：

```text
docs/API/frontend_contract.md
docs/downstream-enterprise-notes.zh-CN.md
```

预期效果：提交后，上述 7 个公开文档不再计入相对 `v0.3.7` 的 modified 文件；下游信息保留在新增文档中。

### 2026-07-07：默认配置示例低风险迁移

处理方式：把下游中文化、本地开发和前端联调常用的配置示例迁到新增下游示例文件，并恢复上游默认示例。

已恢复为 `v0.3.7` 内容的上游示例：

```text
conf/agent.yml.example
```

下游补充内容迁入：

```text
conf/agent.downstream.zh-CN.yml.example
```

预期效果：提交后，`conf/agent.yml.example` 不再计入相对 `v0.3.7` 的 modified 文件；下游中文示例保留在新增文件中。企业平台片段仍保留在 `conf/agent.enterprise.*.yml.example`。

### 2026-07-07：legacy auth 示例低风险恢复

处理方式：恢复上游 `conf/auth_clients.yml.example`。该文件只是 legacy OAuth2 client credentials 的示例配置，当前下游没有把企业认证逻辑迁入这里；恢复后可以减少一个 deleted 上游文件。

已恢复为 `v0.3.7` 内容的上游示例：

```text
conf/auth_clients.yml.example
```

预期效果：提交后，`conf/auth_clients.yml.example` 不再计入相对 `v0.3.7` 的 deleted 文件；企业认证仍以 `conf/agent.enterprise.*.yml.example` 和企业认证 provider 配置为准。

### 2026-07-07：legacy route gate 注册层迁移

处理方式：把企业模式下禁用 legacy route 的依赖从多个上游 route 模块迁到 `create_app()` 的 route registration 层。这样保留企业 fail-closed 行为和审计 operation，同时让不承载下游业务逻辑的上游 route 文件回到 `v0.3.7` 内容。

已恢复为 `v0.3.7` 内容的上游 route：

```text
datus/api/routes/explorer_routes.py
datus/api/routes/success_story_routes.py
datus/api/routes/tool_routes.py
datus/api/routes/visualization_routes.py
```

仍保留的下游 hook：

```text
datus/api/service.py
```

预期效果：提交后，上述 4 个 route 文件不再计入相对 `v0.3.7` 的 modified 文件；legacy 禁用策略集中在 app 注册边界，后续上游 route 合并冲突更少。

### 2026-07-07：通用修复测试迁移

处理方式：把 MCP、CSV 和 proxy timeout 等通用修复的新增测试从上游原测试文件迁到下游独立测试文件。`test_tool_result_channel.py` 中有一条新增 timeout 用例与上游已有 timeout 用例语义重复，直接恢复上游原文件。

已恢复为 `v0.3.7` 内容的上游测试：

```text
tests/unit_tests/api/services/test_mcp_service.py
tests/unit_tests/tools/mcp_tools/test_mcp_config.py
tests/unit_tests/tools/mcp_tools/test_mcp_manager.py
tests/unit_tests/tools/proxy/test_tool_result_channel.py
tests/unit_tests/utils/test_csv_utils.py
```

下游新增测试迁入：

```text
tests/unit_tests/api/services/test_mcp_service_downstream.py
tests/unit_tests/tools/mcp_tools/test_mcp_config_downstream.py
tests/unit_tests/tools/mcp_tools/test_mcp_manager_downstream.py
tests/unit_tests/utils/test_csv_utils_downstream.py
```

预期效果：提交后，上游原测试 modified 文件减少 5 个；对应下游覆盖仍保留在独立测试文件中。

### 2026-07-07：测试迁移第二轮

处理方式：继续把下游新增测试从上游原测试文件迁到独立下游测试文件，减少升级时原测试文件的 merge 冲突。`tests/unit_tests/api/test_api_endpoints.py` 中的 `enterprise_config = {}` 是为了避免 `MagicMock` 影响 app 初始化，本轮保留不动。

已恢复为 `v0.3.7` 内容的上游测试：

```text
tests/unit_tests/agent/node/test_node_factory.py
tests/unit_tests/agent/node/test_token_usage_hook.py
tests/unit_tests/api/services/test_datus_service.py
tests/unit_tests/models/test_session_manager.py
```

下游新增测试迁入：

```text
tests/unit_tests/agent/node/test_node_factory_downstream.py
tests/unit_tests/agent/node/test_token_usage_hook_downstream.py
tests/unit_tests/api/services/test_datus_service_downstream.py
tests/unit_tests/models/test_session_manager_downstream.py
```

预期效果：提交后，上游原测试 modified 文件再减少 4 个；对应下游覆盖仍保留在独立测试文件中。

## 收敛原则

1. 下游企业能力优先放在 `datus_enterprise/`、企业配置示例、企业脚本和企业测试中。
2. 上游原文件只保留薄 hook：启动注册、依赖注入、请求上下文、配置投影、存储/执行扩展点。
3. 不把企业 RBAC、审计、quota、数据源授权、artifact ACL 的主体逻辑散写进多个上游 route/service 文件。
4. 能独立成立的通用 bugfix 或扩展点，应拆成上游可接受的小补丁，而不是和企业补丁混在一起。
5. 文档、示例、部署说明优先新增下游文档；不要为了下游部署体验大幅重写上游公开文档或默认示例。
6. 测试覆盖优先新增到企业测试目录；只有原行为契约确实改变时，才修改上游原测试。

## 文件分类

### 必须保留的核心 hook

这些文件的修改直接连接企业模式和上游主执行链。短期不追求删除，目标是保持修改稳定、薄、容易重新套用。

```text
datus/api/service.py
datus/api/deps.py
datus/api/auth/context.py
datus/api/auth/loader.py
datus/configuration/agent_config.py
datus/configuration/agent_config_loader.py
datus/models/session_manager.py
datus/api/services/datus_service.py
datus/tools/db_tools/db_manager.py
```

保留理由：

- `create_app()` 和 lifespan 需要加载企业扩展、注册企业路由、关闭企业存储资源。
- 请求上下文需要在 service 初始化前完成认证、企业用户状态检查、角色/权限/数据源授权刷新。
- 企业模式需要 request-scoped config projection，不能把用户授权状态写回共享 `DatusService.agent_config`。
- PostgreSQL/OceanBase session body store 需要挂入原 session 管理和 streaming 路径。
- 数据源/connector 入口需要承接企业授权和多库枚举等执行侧限制。

### 应继续迁入企业模块的候选

这些文件目前承载了企业权限、平台状态、审计或前端企业契约。后续收敛应优先把主体逻辑移入 `datus_enterprise/`，上游原文件只留下通用 hook 或 route matrix 调用。

```text
datus/api/routes/agent_routes.py
datus/api/routes/chat_routes.py
datus/api/routes/cli_routes.py
datus/api/routes/config_routes.py
datus/api/routes/dashboard_routes.py
datus/api/routes/database_routes.py
datus/api/routes/kb_routes.py
datus/api/routes/mcp_routes.py
datus/api/routes/models_routes.py
datus/api/routes/report_routes.py
datus/api/routes/table_routes.py
datus/api/services/action_sse_converter.py
datus/api/services/chat_service.py
datus/api/services/chat_task_manager.py
datus/api/services/cli_service.py
datus/api/services/dashboard_service.py
datus/api/services/database_service.py
datus/api/services/kb_service.py
datus/api/services/mcp_service.py
datus/api/services/report_service.py
datus/api/utils/stream_cancellation.py
```

迁移方向：

- 模块级 RBAC 和平台状态检查集中到 `datus/api/enterprise/route_security_matrix.py` 与企业依赖中。
- 资源级检查保留在最靠近资源的位置，但实际策略和审计写入应放在企业模块。
- 原 route 文件不要继续增长企业分支；新增企业执行面优先建在 `datus_enterprise/api/`。
- 如果企业模式需要覆盖上游同一路径，优先使用明确的 route registration / dedupe 机制，而不是在多个上游 handler 中堆条件。

### 通用修复或上游化候选

这些修改看起来不专属于企业模式。后续应拆成小 commit，评估是否可以贡献给上游；如果不能贡献，也要和企业补丁分开维护。

```text
datus/tools/proxy/proxy_tool.py
datus/tools/proxy/tool_result_channel.py
datus/utils/csv_utils.py
datus/tools/mcp_tools/mcp_config.py
datus/tools/mcp_tools/mcp_manager.py
datus/tools/func_tool/database.py
datus/tools/func_tool/_visual_artifact_helpers.py
datus/tools/func_tool/dashboard_artifact_tools.py
datus/tools/func_tool/report_artifact_tools.py
datus/agent/node/visual_artifact/_artifact_html_renderer.py
datus/agent/node/visual_artifact/dashboard_html_renderer.py
datus/agent/node/visual_artifact/report_html_renderer.py
datus/resources/skills/create-skill/SKILL.md
```

处理规则：

- 先判断是否是上游 bugfix、通用稳定性修复或通用扩展点。
- 能独立验证的，拆出 focused tests，并保持 commit message 不含企业语义。
- 如果修复只为企业前端路径服务，优先迁到企业或前端适配层。

### 文档、示例和元信息

这些文件的修改不应成为升级冲突热点。后续收敛优先恢复上游默认文档，把下游内容放到新增文档或企业示例。

本轮已经恢复的上游公开文档见“2026-07-07：公开文档低风险迁移”。仍需继续评估的文件：

```text
CLAUDE.md
datus/api/README.md
pyproject.toml
uv.lock
```

处理规则：

- `CLAUDE.md` 保持为 `AGENTS.md` 的薄入口，不承载第二份规则。
- `conf/agent.yml.example` 保持接近上游默认配置；企业、内网、PostgreSQL、OceanBase 示例放到 `conf/agent.enterprise.*.yml.example`。
- 下游部署说明放在根目录中文文档或新增下游文档中，不混入上游 mkdocs 主文档，除非该内容也适合公开上游用户。
- `pyproject.toml` 和 `uv.lock` 的变更要注明依赖来源。可选企业依赖优先评估 extras 或部署 requirements。

### 测试文件

当前修改了大量上游原测试。后续收敛时，优先把企业语义测试放到新增企业目录，减少上游测试文件 churn。

优先承载企业语义的目录：

```text
tests/unit_tests/api/enterprise/
tests/unit_tests/datus_enterprise/
tests/integration/datus_enterprise/
tests/unit_tests/scripts/
```

保留修改上游原测试的条件：

- 原 API 行为在企业模式下必须 fail closed。
- 原 service/route 需要证明仍兼容非企业模式。
- 修改的是共享 hook 的回归覆盖，而不是企业业务策略本身。

## 收敛流程

每次做低风险收敛，按下面顺序执行：

1. 从 monorepo 根目录刷新上游对比：

   ```bash
   git diff --shortstat v0.3.8 HEAD:datus-agent
   git diff --name-status -M v0.3.8 HEAD:datus-agent
   git diff --name-status -M v0.3.8 HEAD:datus-agent | awk '$1=="M"{print $2}'
   ```

2. 对新增或仍保留的上游原文件修改标注分类：核心 hook、迁移候选、上游化候选、文档/示例、测试。
3. 先处理文档、示例、测试迁移等低风险项，不在同一提交中重排安全执行链。
4. 对 route/service 收敛单独开提交，必须同时更新 route security matrix 和 focused tests。
5. 对可上游化修复单独开提交，避免混入企业配置、企业模型或前端契约。
6. 收敛结束后刷新本文的基线数字和分类变化。

## 验证建议

纯文档或清单更新：

```bash
git diff --check
```

配置示例更新：

```bash
uv run python - <<'PY'
import yaml
from pathlib import Path
for path in Path("conf").glob("*.yml*"):
    with path.open(encoding="utf-8") as f:
        yaml.safe_load(f)
print("yaml ok")
PY
```

企业 route/security 收敛：

```bash
uv run pytest tests/unit_tests/api/enterprise tests/unit_tests/datus_enterprise
uv run pytest tests/unit_tests/api/routes/test_module_rbac_routes.py
uv run pytest tests/unit_tests/api/enterprise/test_route_security_matrix.py
```

上游 release 合并完成前，还应执行本地企业 auth/data smoke。当前 checkout 的已验证 smoke 包括 `UserInfoBearerAuthProvider`、mock userinfo、企业 metadata seed、启用/禁用用户、catalog 和 SQL 权限路径。
