# 上游差异预算

本文档记录 `datus-agent` 相对上游 release tag 的下游差异预算。目标不是把企业版改造成零 diff，而是让上游原文件中的下游逻辑保持少量、稳定、可解释，并把企业逻辑优先归位到新增模块。

## 当前基线

基线采样日期：2026-07-27

说明：这是完成正式 `v0.3.8` release 合并、企业权限回归修复、真实企业 auth/catalog/SQL smoke、公开文档恢复、第九轮测试迁移、第八轮模型契约归位、差异护栏、MCP/Report/Success Story service 归位、Dashboard service list/render 与 query SQL authorization adapter 归位、CLI connector/task owner、Chat task runtime、Chat request config/terminal sidecar runtime、应用 route projection/legacy gate、Artifact edit-session 过渡兼容清理、SubAgent 委派企业策略与 sidecar runtime、SessionManager scope/sidecar/async store/shared message parser、TokenUsage running snapshot persistence adapter、enterprise request-context policy、Enterprise auth loader policy、Visual Artifact access/locked-edit policy 与 locked-edit auto-validation adapter、DBFuncTool datasource-grant scope 与 SQL source 判定、AgenticNode permission/session/MCP runtime helper、Interactive node downstream adapter、Runtime prompt template resolver、Datasource-file project override adapter、Artifact filesystem ACL scope、Filesystem enterprise scope policy、Semantic query-time normalizer、Schema metadata sample-row normalizer、Embedding-store read selection adapter、Embedding-store storage-key adapter、Embedding-store backend repair adapter、OpenAI-compatible embedding request adapter、SSE response/error payload normalizer、Artifact HTML bundle helper、MCPManager config/runtime adapter、Model MCP connection options、Artifact creation ACL、Success Story migration CLI、CLIService/ChatService/deps/ChatTaskManager/Chat routes/feedback/Artifact tools/Database service/OpenAI/Claude stream/Dashboard renderer/Storage read path/KB cancellation 下游测试拆分、ChatService history/session、history-only SSE converter、stream cancellation 安全 wrapper 与 Success Story route 测试归位，以及 KB/Config/Report/Dashboard/Success Story/Models/Legacy Agent/Database/MCP/Table/CLI route 归位后的采样结果。`v0.3.8` 使用上游 annotated tag 的 release tree；下游仍保留企业平台、OceanBase/PG stores、本地联调和独立测试等长期差异。

对比口径：

```bash
cd /home/astenir/Code/work/datus
git diff --shortstat v0.3.8 HEAD:datus-agent
git diff --name-status -M v0.3.8 HEAD:datus-agent
```

当前结果：

```text
361 files changed, 81086 insertions(+), 3593 deletions(-)
261 added
96 modified
4 deleted
```

修改的上游既有文件按类型拆分：

```text
68 production/package files
24 tests
0 docs
4 config/meta files
```

分类口径：只统计 `modified`；`datus/` 与 `datus_enterprise/` 归 production/package，`tests/` 归 tests，`docs/` 归 docs，其余根级构建、配置、CI 和锁文件归 config/meta。新增文件另含 109 个 production/package、123 个 tests、4 个 docs 和 25 个 config/meta；它们主要是下游企业模块、脚本、测试、文档和部署资产，不与修改的上游既有文件混算。本轮按这套目录规则重新核对全量清单，并修正了根级 `CLAUDE.md` 及新增文件的历史分类误差。

这些数字是升级治理指标。每次完成一次上游 release 合并或低风险收敛后，都应该刷新这一节，说明数字变大或变小的原因。

## 收敛记录

### 2026-07-27：管理分页、Chat 输入兼容与合并前真实验收

分类：新增 enterprise production/package 文件及上游 Chat `core-hook` 兼容修复。处理方式：新增共享 `datus_enterprise/api/admin_pagination.py`，让管理用户、角色、授权、会话、额度、密钥、产物和审计接口统一使用有界分页；Chat route 通过 `getattr()` 安全读取下游可选的 `model_credential_id`，保持上游基础 `StreamChatInput` 兼容；`datus-web` API smoke 改为按数据源名称调用保存配置测试接口，避免把 `/config/agent` 返回的脱敏密码重新提交为真实凭据。

不变边界：管理分页不改变 RBAC、资源所有权或审计授权；Chat 凭据仍按认证用户所有权解析，缺少扩展字段时仅回到上游输入契约，不放宽模型策略、SQL policy、datasource grant、Artifact ACL 或 quota。保存数据源 smoke 只让后端使用服务端保存的配置，浏览器和脚本均不接触明文密码。没有新增、删除或改变 FastAPI path/method，route security matrix 无需变化。

数字变化：新增 `datus_enterprise/api/admin_pagination.py` 使 added 从 260 增至 261、总差异文件从 360 增至 361；新增文件分类中的 production/package 从 108 增至 109。modified 保持 96（production/package 68、tests 24、config/meta 4），deleted 保持 4，因此既有上游文件冲突面没有扩大。

验证：全仓 Python 验证为 `17312 passed, 21 skipped, 1 xfailed`；Admin 真实浏览器视觉 smoke 覆盖用户、角色、授权、会话、产物、额度、密钥、审计 8 个标签的桌面与移动视口，共 `16/16 passed`，无页面级横向溢出、console error 或 Admin API 4xx/5xx，并验证会话和审计翻页往返。真实企业链路验证覆盖缺失/非法/禁用 token，Alice 管理员与 Bob 受限角色上下文，Bob Admin 403 与 deny audit，Alice 用户/会话/审计分页，Alice/Bob datasource grant 与请求级配置投影、目录读取和 URI 脱敏；保存数据源连接 smoke 返回 `ok`。前端 ESLint、`71` 个 Vitest 文件的 `595` 项测试、生产构建和 `7` 项 Chromium 黑盒测试通过。

### 2026-07-27：Artifact edit-session 过渡兼容清理

分类：阶段 2 的 Chat/Artifact `core-hook` 死代码清理。处理方式：在 Report/Dashboard 已统一使用 `ArtifactEditSession` 后，删除 `ChatTaskManager` 未调用的 purge wrapper、旧 report-only capability marker/getter，以及 Chat route 对该旧接口的 fallback；同时删除 added Agent registry 中全仓无调用的 `can_view_agent()`，保留唯一实际使用的 `can_use_agent()` 授权入口。

不变边界：Report/Dashboard edit session 仍由 added runtime helper 在 create/get 时统一清理过期记录，route 仍通过 capability marker 避免动态 mock 假阳性；Artifact owner/ACL、locked slug、request-scoped config 和 dispatch 顺序均未改变。没有新增、删除或改变 FastAPI route，因此 route security matrix 无需变化。上游 `v0.3.8` 自带且标为 legacy API 的 Visual Artifact helper 即使当前无静态调用也全部保留，避免制造新的上游删除冲突。

上游 `datus/api/routes/chat_routes.py` 相对 `v0.3.8` 从 `+583/-54` 收敛为 `+578/-54`，冲突行由 637 降至 632，减少 5；`datus/api/services/chat_task_manager.py` 从 `+402/-77` 收敛为 `+389/-77`，冲突行由 479 降至 466，减少 13。modified 仍为 96（production/package 68、tests 24、config/meta 4），added 260、deleted 4、总差异文件 360 均不变；计入本记录前总差异为 `+79394/-3593`。

验证：修改前后同一组 ChatTaskManager、Chat route、feedback、downstream policy、Agent route 回归均为 `241 passed`；聚焦 Ruff、全仓静态引用复核与 `git diff --check` 通过。

### 2026-07-27：应用 route projection 与 legacy gate 归位

分类：阶段 0/1/3 的应用注册 `core-hook`。处理方式：新增 `datus_enterprise/app_integration.py`，迁入企业权威 route 对上游 route 清单的替换、enterprise-only route 追加、legacy route 注册 gate，以及 legacy OAuth/workflow endpoint 的 fail-closed audit 与 bearer client 解析。上游 `create_app()` 恢复 `v0.3.8` 原始 route 清单，只增加一次 projection 调用；`_include_api_router` 和 legacy endpoint 仅保留兼容别名/薄 wrapper。

不变边界：route projection 保持当前 authoritative handler、注册顺序和 route security matrix 覆盖；上游后续新增 route 会先进入原始清单，再由显式 override/insert 规则投影。企业模式下 legacy auth/workflow 仍在业务执行前返回 404 并审计，legacy explorer/agent/visualization/tool 仍通过注册级 dependency 返回稳定拒绝；本地非 enterprise 行为不变。没有新增、删除或改变对外 FastAPI path/method，因此 route security matrix 内容无需变化。

上游 `datus/api/service.py` 相对 `v0.3.8` 从 `+164/-59` 收敛为 `+73/-48`，冲突行由 223 降至 121，减少 102。新增 1 个 enterprise production/package 文件使 added 由 259 增至 260、总差异文件由 359 增至 360；modified 保持 96（production/package 68、tests 24、config/meta 4）、deleted 保持 4。

验证：app factory、legacy endpoint/route gate、route security matrix 与 module RBAC 的同一组合在迁移前后均为 `161 passed`；迁移文件 Ruff 与 `git diff --check` 通过。

### 2026-07-27：Chat request config 与 terminal sidecar persistence 归位

分类：阶段 2/4 的 Chat `core-hook`。处理方式：扩展 added 文件 `datus_enterprise/services/chat_task_runtime.py`，迁入已 clone 的请求级 `AgentConfig` 对 session body store、principal、user、Artifact ACL/filesystem protection 与私有 workspace 的配置，以及 established session 的 terminal sidecar 构造和 best-effort 持久化。上游 manager 保留 clone、调用时点、task admission/owner 写入、node/SSE 状态机和 terminal outcome 调用顺序；`SessionManager` 类型仍由原模块传入，保留替换边界。

不变边界：enterprise 缺认证用户仍在 workspace 与 task 创建前 fail closed；共享 `DatusService.agent_config` 不被修改；owner store 不由 body store 替代。terminal sidecar 仍只在 session 建立后写入，失败不掩盖主执行结果，cancel/error/timeout 的 task 状态与 event 顺序不变。task slot、buffer cursor、interrupt/release、node lifecycle 和 owner store 写入均未迁出 manager。

上游 `datus/api/services/chat_task_manager.py` 相对 `v0.3.8` 从 `+429/-75` 收敛为 `+402/-77`，冲突行由 504 降至 479，减少 25。复用已有 added production/package 文件，不增加文件数；added、modified 和 deleted 数量不变。

验证：ChatTaskManager、downstream terminal history、workspace 和 DatusService factory 的同一组合在两次迁移前后均为 `126 passed`；迁移文件 Ruff 与 `git diff --check` 通过。

### 2026-07-27：Chat permission-mode RBAC adapter 归位

分类：阶段 3 的企业 Chat `core-hook`。处理方式：扩展 added 文件 `datus_enterprise/services/chat_request_policy.py`，迁入 enterprise 请求省略 permission mode 时的 least-privilege 默认值，以及 `auto` / `dangerous` 模式的 `module.chat.permission_mode` RBAC 校验与稳定 403 映射。上游 `chat_routes.py` 只在 datasource projection 前调用两个 helper。

不变边界：普通 `normal`、未指定 mode 和本地非 enterprise 请求仍不触发额外 RBAC；企业 elevated mode 仍必须在请求级配置投影和 task 启动前授权失败。helper 不修改 Agent Tool Policy 或 runtime policy 上限，也不授予工具、datasource、Artifact 或 session 权限。没有新增、删除或改变 FastAPI route，因此 route security matrix 无需变化。

上游 `datus/api/routes/chat_routes.py` 相对 `v0.3.8` 从 `+611/-54` 收敛为 `+583/-54`，冲突行由 665 降至 637，减少 28。复用已有 added production/package 文件，不增加文件数；added 保持 259、modified 保持 96（production/package 68、tests 24、config/meta 4）、deleted 保持 4，总差异文件保持 359；计入本记录前总差异为 `+79283/-3602`。

验证：Chat route、downstream session/model/SQL policy、module RBAC、Agent registry 和 Artifact edit session 回归迁移前后均为 `238 passed`；downstream 测试的 dependency patch 边界同步移到 enterprise service。迁移文件 Ruff 与 `git diff --check` 通过。

### 2026-07-27：Chat request enterprise policy adapter 归位

分类：阶段 5 的企业 Chat `core-hook`。处理方式：新增 `datus_enterprise/services/chat_request_policy.py`，迁入 Chat SQL-principal denial audit、model policy deny/audit 和 request quota 消费及稳定错误组装。上游 `chat_routes.py` 保留 `v0.3.8` 已有的 SQL policy principal pre-check 与 principal path 解析，只在 stream/feedback 的既有执行顺序中调用企业 policy helpers 并映射为 SSE denial。

不变边界：认证、Agent/Artifact ACL、session owner、请求级 datasource projection 仍先于 SQL/model/quota 检查；SQL principal 缺失继续 fail closed，model deny 与 audit sink failure、quota store unavailable/exceeded 的稳定错误行为不变。helper 不解析身份、不修改共享 `DatusService.agent_config`，route 仍决定 pre-check 顺序、是否启动 task 和 SSE 响应。没有新增、删除或改变 FastAPI route，因此 route security matrix 无需变化。

上游 `datus/api/routes/chat_routes.py` 相对 `v0.3.8` 从 `+723/-54` 收敛为 `+611/-54`，冲突行由 777 降至 665，减少 112。新增 1 个 enterprise production/package 文件使 added 由 258 增至 259、总差异文件由 358 增至 359；modified 保持 96（production/package 68、tests 24、config/meta 4）、deleted 保持 4；计入本记录前总差异为 `+79253/-3602`。

验证：Chat route、downstream session/model/SQL policy、module RBAC、Agent registry 和 Artifact edit session 回归迁移前后均为 `238 passed`；迁移文件 Ruff 与 `git diff --check` 通过。迁移期间曾尝试一并移动上游已有 principal pre-check，但因会删除上游通用实现而收窄方案，最终保留其上游所有权。

### 2026-07-27：Chat Agent runtime materialization adapter 归位

分类：阶段 1/2 的企业 Chat/Artifact `core-hook`。处理方式：扩展已有 added 文件 `datus_enterprise/agent_registry.py`，迁入企业 Agent record 和已授权 Artifact edit session 对请求级 `AgentConfig.agentic_nodes` 的 runtime entry 组装。上游 `chat_routes.py` 只保留 helper import、企业 Agent 可用集遍历和 Artifact edit ACL 成功后的调用点。

不变边界：helper 不查询也不授予 Agent/Artifact ACL，不访问 metadata store；route 仍负责企业 Agent 解析、owner 校验、`require_artifact_edit_access` / query ACL、请求级配置投影、model policy、SQL policy、quota 和最终 dispatch。`_acl_authorized_artifact_edit` marker 仍只在权威 edit ACL 成功后写入请求级 clone，locked slug、bind-first 规则、跨 Artifact 禁止和本地兼容行为均未改变；共享 `DatusService.agent_config` 不被修改。没有新增、删除或改变 FastAPI route，因此 route security matrix 无需变化。

上游 `datus/api/routes/chat_routes.py` 相对 `v0.3.8` 从 `+775/-54` 收敛为 `+723/-54`，冲突行由 829 降至 777，减少 52。复用已有 added production/package 文件，不增加文件数；added 保持 258、modified 保持 96（production/package 68、tests 24、config/meta 4）、deleted 保持 4，总差异文件保持 358；计入本记录前总差异为 `+79227/-3602`。

验证：Chat route、downstream session/model/SQL policy、module RBAC、Agent registry 和 Artifact edit session 回归迁移前后均为 `238 passed`；迁移文件 Ruff 与 `git diff --check` 通过。

### 2026-07-27：Visual Artifact locked-edit auto-validation adapter 归位

分类：阶段 1/2 的企业 Artifact `core-hook`。处理方式：扩展已有 added 文件 `datus_enterprise/services/artifact_filesystem_scope.py`，迁入 locked edit 已绑定 Artifact 的 `validate_render()` 调用、结果规范化、成功/失败 `ActionHistory` 组装和 manager 写入。上游 `BaseVisualArtifactAgenticNode._build_success_result()` 只保留无既有 render 时的一次 helper 调用，以及成功动作对本地 finalize 状态的更新。

不变边界：helper 不查询也不授予 Artifact ACL；企业 edit 仍必须先经过服务端 ACL marker、locked slug 校验和 tool binding。原 node 继续决定调用时点，并负责刷新 `all_actions`、追加成功 `tool_calls`、提取 app.jsx/render files 和最终 result；异常传播、动作顺序、无锁定 Artifact 的 no-op、本地 legacy 行为和跨 slug fail-closed 均未改变。没有新增或修改 FastAPI route，因此 route security matrix 无需变化。

上游 `datus/agent/node/base_visual_artifact_agentic_node.py` 相对 `v0.3.8` 从 `+106/-12` 收敛为 `+93/-12`，冲突行由 118 降至 105，减少 13。复用已有 added production/package 文件，不增加文件数；added 保持 258、modified 保持 96（production/package 68、tests 24、config/meta 4）、deleted 保持 4，总差异文件保持 358。新增文件分类保持 production/package 106、tests 123、docs 4、config/meta 25；计入本记录前总差异为 `+79217/-3602`。

验证：Report/Dashboard 上游与 downstream node、locked-edit auto bind/validate 及 Artifact filesystem authorization 回归迁移前后均为 `64 passed`；迁移文件 Ruff 与 `git diff --check` 通过。企业平台计划与开发指南复核确认 authoritative ACL、唯一 slug 锁定和 fail-closed 边界未改变。

### 2026-07-26：TokenUsage running snapshot persistence adapter 归位

分类：阶段 2/3 的稳定 `core-hook`。处理方式：扩展已有 added 文件 `datus_enterprise/services/agentic_session_runtime.py`，迁入 running-turn usage 持久化对 async SessionManager body-store adapter 与同步本地 store 的协议选择。上游 `TokenUsageHook._persist_snapshot()` 只保留 session/turn 解析、一次 helper await、异常边界及独立 context-state 持久化。

不变边界：`_publish()` 仍按 node snapshot、running snapshot persistence、action enqueue、status dirty notification 的顺序执行；async 方法仍优先，缺失时仍回退同步方法。session id、当前 user turn 计算、context-window occupancy、action delta/累计值、bus fan-out 和 hook 不得打断模型 run loop 的异常吞吐均未迁移或改变。

上游 `datus/agent/node/token_usage_hook.py` 相对 `v0.3.8` 从 `+21/-11` 收敛为 `+8/-6`，冲突行由 32 降至 14，减少 18。复用已有 added production/package 文件，不增加文件数；added 保持 258、modified 保持 96（production/package 68、tests 24、config/meta 4）、deleted 保持 4，总差异文件保持 358。新增文件分类保持 production/package 106、tests 123、docs 4、config/meta 25；计入本记录前总差异为 `+79187/-3602`。

验证：TokenUsageHook 上游/downstream 与 SessionManager body-store 回归迁移前后均为 `13 passed`，覆盖同步回退、async 优先、持久化后 action/bus fan-out、node snapshot 和上下文状态；迁移文件 Ruff 与 `git diff --check` 通过。

### 2026-07-26：Embedding-store read selection adapter 归位

分类：通用 `upstreamable-fix`。处理方式：扩展已有 added 文件 `datus/storage/embedding_store_backend_downstream.py`，迁入 read-only backend 查询对 schema、vector column 和显式 `select_fields` 的实际字段选择计算。上游 `BaseEmbeddingStore._search_all()` 只保留一次 helper 调用，并继续把结果传给原 `table.search_all()`。

不变边界：默认读取仍按 schema 顺序选择除 vector 外的全部字段；显式字段仍保持调用方顺序并过滤 vector，schema 缺失或未配置 vector column 时仍原样传递。table read-only open、row count、where/limit、零行空表、backend search、结果中的防御性 vector drop 和 embedding-free 状态均未迁移或改变。

上游 `datus/storage/base.py` 相对 `v0.3.8` 从 `+31/-9` 收敛为 `+25/-9`，冲突行由 40 降至 34，减少 6。复用已有 added production/package 文件，不增加文件数；added 保持 258、modified 保持 96（production/package 68、tests 24、config/meta 4）、deleted 保持 4，总差异文件保持 358。新增文件分类保持 production/package 106、tests 123、docs 4、config/meta 25；计入本记录前总差异为 `+79163/-3607`。

验证：BaseEmbeddingStore 上游、read-only downstream 与 extension 回归迁移前后均为 `102 passed`，覆盖默认/显式字段、vector 过滤、missing/existing table、where/limit/zero limit 与 embedding-free read path；迁移文件 Ruff check/format、Python compile 与 `git diff --check` 通过。

### 2026-07-26：Embedding-store storage-key adapter 归位

分类：通用 `upstreamable-fix`。处理方式：扩展已有 added 文件 `datus/storage/embedding_store_backend_downstream.py`，迁入 datasource-scoped row 对 configurable business-key source 的 `storage_key` 填充，以及已有表 scope-column repair 使用的 legacy SQL expression 生成。上游 `BaseEmbeddingStore` 只保留默认值循环和 migration expr 字典组装两个薄调用点。

不变边界：`storage_key_source_column` 仍由 store 构造时确定；schema 仍只在 source column 存在时添加 non-null `storage_key`。显式 row key 仍不被覆盖；有 datasource 时仍生成 `<datasource>:<business-key>`，legacy row 仍使用 `legacy:` 前缀。非法 source column 仍在生成 SQL 前拒绝；scope migration 的 capability detection、调用、错误映射和执行时序均未迁移或改变。

上游 `datus/storage/base.py` 相对 `v0.3.8` 从 `+43/-8` 收敛为 `+31/-9`，冲突行由 51 降至 40，减少 11。复用已有 added production/package 文件，不增加文件数；added 保持 258、modified 保持 96（production/package 68、tests 24、config/meta 4）、deleted 保持 4，总差异文件保持 358。新增文件分类保持 production/package 106、tests 123、docs 4、config/meta 25；计入本记录前总差异为 `+79146/-3607`。

验证：BaseEmbeddingStore、read-only/extension 与 identifier-based schema metadata 的既有 106 项迁移前后均通过；新增 2 项 added 测试锁定 configurable business-key row fill 与非法 migration source 拒绝，扩展后为 `108 passed`。迁移文件 Ruff check/format、Python compile 与 `git diff --check` 通过。

### 2026-07-26：Embedding-store backend repair adapter 归位

分类：通用 `upstreamable-fix`。处理方式：新增 `datus/storage/embedding_store_backend_downstream.py`，迁入 vector backend 在 open 前接收 table schema 的可选协议，以及已有物理表的 unique-column repair capability 检测、调用和稳定 `DatusException` 映射。上游 `BaseEmbeddingStore` 保留同名薄 wrapper，并继续在既有 read/open/create 边界调用。

不变边界：read-only open 仍先确认物理表存在，再设置 backend schema、打开 table、修复 scope columns 和 unique columns；带 embedding 的 `_ensure_table()` 仍在 open/create 前设置 schema，且只对已有表执行 unique repair。新建表继续直接传入 `unique_columns`；table state、锁、embedding lazy init、scope SQL migration、storage-key 生成、search 和 index 状态机均未迁移或改变。

上游 `datus/storage/base.py` 相对 `v0.3.8` 从 `+62/-8` 收敛为 `+43/-8`，冲突行由 70 降至 51，减少 19。新增 1 个 production/package 文件使 added 由 257 增至 258、总差异文件由 357 增至 358；modified 保持 96（production/package 68、tests 24、config/meta 4）、deleted 保持 4。新增文件分类变为 production/package 106、tests 123、docs 4、config/meta 25；计入本记录前总差异为 `+79110/-3606`。

验证：BaseEmbeddingStore 上游、read-only downstream 和 extension 回归的既有 98 项迁移前后均通过；新增 2 项 added 测试锁定 unique repair 委托与 backend failure 映射，扩展后为 `100 passed`。迁移文件 Ruff check/format、Python compile 与 `git diff --check` 通过。

### 2026-07-26：OpenAI-compatible embedding request adapter 归位

分类：通用 `upstreamable-fix`。处理方式：新增 `datus/storage/embedding_openai_requests_downstream.py`，迁入 OpenAI-compatible embedding 的 batch 请求、batch `BadRequestError` 后逐条降级、显式 `single_input_only` 请求和有效输入位置到 embedding 结果的映射。上游 `OpenAIEmbeddings.generate_embeddings()` 只保留空输入过滤、一次 helper 调用、顶层错误映射和最终结果补位。

不变边界：标准 OpenAI batch 仍优先一次请求；仅在多输入 batch 被拒绝时逐条重试，单输入 batch 拒绝仍由顶层契约返回 `None`。逐条模式中单项 400 不影响其他有效结果；空输入不调用 API，原始位置和 `dimensions` 参数保持不变。模型维度推断、client lazy lifecycle、Azure/OpenAI 选择及非 `BadRequestError` 传播均未迁移或改变。

上游 `datus/storage/embedding_openai.py` 相对 `v0.3.8` 从 `+39/-4` 收敛为 `+17/-10`，冲突行由 43 降至 27，减少 16。新增 1 个 production/package 文件使 added 由 256 增至 257、总差异文件由 356 增至 357；modified 保持 96（production/package 68、tests 24、config/meta 4）、deleted 保持 4。新增文件分类变为 production/package 105、tests 123、docs 4、config/meta 25；计入本记录前总差异为 `+79039/-3606`。

验证：上游 OpenAI embedding、downstream custom dimension/single-input/batch fallback 与 EmbeddingModel 回归迁移前后均为 `46 passed`；迁移文件 Ruff check/format、Python compile 与 `git diff --check` 通过。

### 2026-07-26：Schema metadata sample-row normalizer 归位

分类：通用 `upstreamable-fix`。处理方式：新增 `datus/storage/schema_metadata/sample_rows_downstream.py`，迁入 metadata sample rows 的 list-to-CSV 规范化、超长 cell 脱敏替换、总字符数截断和稳定日志。上游 `schema_metadata/store.py` 只保留配置阈值读取及 vector storage 前的一次 helper 调用。

不变边界：空 sample 过滤、item 原地更新、datasource scope 注入、schema/value store 写入顺序和最终 batch 日志均未改变；超长内容仍在进入 embedding 前处理。identifier storage key、unique column 和 RAG 查询逻辑未迁移或改动。

上游 `datus/storage/schema_metadata/store.py` 相对 `v0.3.8` 从 `+54/-1` 收敛为 `+11/-5`，冲突行由 55 降至 16，减少 39。新增 1 个 production/package 文件使 added 由 255 增至 256、总差异文件由 355 增至 356；modified 保持 96（production/package 68、tests 24、config/meta 4）、deleted 保持 4。新增文件分类变为 production/package 104、tests 123、docs 4、config/meta 25；计入本记录前总差异为 `+78991/-3600`。

验证：上游 schema metadata store 与 downstream identifier key/sample-row sanitization 回归迁移前后均为 `66 passed`；迁移文件 Ruff check/format、Python compile 与 `git diff --check` 通过。

### 2026-07-26：SSE response/error payload normalizer 归位

分类：通用 `upstreamable-fix`。处理方式：新增 `datus/api/services/action_sse_payload_downstream.py`，迁入 final response 对嵌套 JSON envelope 的 SQL/文本提取，以及 failed action 的稳定 `error_type` payload 生成。上游 `action_sse_converter.py` 只保留两个 helper 调用和 `IMessageContent` 构造。

不变边界：`thinking_delta`/`response_delta` 的 CREATE/APPEND 顺序、`stream_thinking` gate、plain assistant 判定、message/depth/parent id、tool/interaction/finalize/usage 分派和异常兜底均未迁移。live SSE 仍产生可提交的 `user-interaction`；persisted history 仍单独通过 `action_history_sse_converter.py` 生成不含 `interactionKey` 的只读 `interaction-summary`。

上游 `datus/api/services/action_sse_converter.py` 相对 `v0.3.8` 从 `+27/-6` 收敛为 `+15/-7`，冲突行由 33 降至 22，减少 11。新增 1 个 production/package 文件使 added 由 254 增至 255、总差异文件由 354 增至 355；modified 保持 96（production/package 68、tests 24、config/meta 4）、deleted 保持 4。新增文件分类变为 production/package 103、tests 123、docs 4、config/meta 25；计入本记录前总差异为 `+78951/-3596`。

验证：上游 Action SSE converter、downstream response/error/delta/history converter 与 ChatService persisted history 回归迁移前后均为 `132 passed`；迁移文件 Ruff check/format、Python compile 与 `git diff --check` 通过。

### 2026-07-26：Dashboard query SQL authorization adapter 归位

分类：阶段 5 的稳定 `core-hook`。处理方式：扩展已有 added 文件 `datus_enterprise/services/cli_sql_policy.py`，迁入 Dashboard 对共享 read-only/table-scope/SQL-policy 结果的 `Result[SqlQueryResultEnvelope]` 适配、稳定 backend failure 映射和带 Dashboard/query 标识的异常日志。上游 `DashboardService.run_query()` 只保留 helper 调用及成功 SQL/失败 Result 分派。

不变边界：模板读取、params 校验、Jinja 渲染、request-scoped config、模板 datasource 二次投影、执行前 quota callback、connector 解析与 SQL 执行顺序均未改变。write SQL、scope 外 table、policy rewrite 和 policy backend failure 继续复用同一 `authorize_read_sql()`；错误码 `QUERY_EXECUTION_FAILED` 与文案逐字不变。没有新增或修改 FastAPI route，因此 route security matrix 无需变化。

上游 `datus/api/services/dashboard_service.py` 相对 `v0.3.8` 从 `+34/-1` 收敛为 `+28/-1`，冲突行由 35 降至 29，减少 6。复用已有 added production/package 文件，不增加文件数；added 保持 254、modified 保持 96（production/package 68、tests 24、config/meta 4）、deleted 保持 4；计入本记录前总差异为 `+78922/-3595`。

验证：上游 Dashboard service 与 downstream list/render、request config、read-only/table scope/policy 回归迁移前后均为 `61 passed`；Dashboard route 与企业模块 RBAC 补充回归 `131 passed`。补充回归暴露 added 测试中的 fake connector 仍依赖已迁出的 `CLIService` monkeypatch，已改为显式声明 `dialect="sqlite"` 并实际经过共享授权 helper，没有向生产代码添加 dialect fallback；迁移文件 Ruff check/format、Python compile 与 `git diff --check` 通过。

### 2026-07-26：Visual Artifact access 与 locked-edit policy 归位

分类：阶段 1/2 的企业 Artifact `core-hook`。处理方式：扩展已有新增文件 `datus_enterprise/services/artifact_filesystem_scope.py`，迁入 enterprise/local 访问模式解析、ACL edit marker 与 locked slug 校验、filesystem 授权绑定，以及锁定编辑会话对既有 Artifact tool 的绑定策略。上游 `BaseVisualArtifactAgenticNode` 保留三个同签名委托方法、节点 active slug 更新和运行日志。

不变边界：本地/CLI 仍为 legacy 模式；企业 create 仍在默认 private ACL 成功后才绑定 filesystem；企业 edit 缺少服务端 ACL marker、locked flag 或 slug 仍 fail closed。Artifact tool 注册、LLM 执行、自动 validate、ActionHistory、finalize/render、并发 slug owner 与文件可见性状态机均未迁移或改变。

上游 `datus/agent/node/base_visual_artifact_agentic_node.py` 相对 `v0.3.8` 从 `+131/-12` 收敛为 `+106/-12`，冲突行由 143 降至 118，减少 25。复用已有 added production/package 文件，不增加文件数；added 保持 254、modified 保持 96（production/package 68、tests 24、config/meta 4）、deleted 保持 4；计入本记录前总差异为 `+78889/-3595`。

验证：Visual Artifact ACL、Report/Dashboard downstream node 与 Artifact tool 迁移前后均为 `39 passed`；Report/Dashboard 原测试与 downstream 全集补充回归 `240 passed`；迁移文件 Ruff check/format、Python compile 与 `git diff --check` 通过。

### 2026-07-26：Enterprise auth loader policy 归位

分类：阶段 0/1 的稳定 `core-hook`。处理方式：新增 `datus_enterprise/auth_loader_policy.py`，迁入 `enterprise.enabled` 解析、缺少 `api.auth_provider.class` 和显式实例化 `NoAuthProvider` 的 fail-closed 策略。上游 `load_auth_provider()` 只保留可选 enterprise config 参数，以及 fallback 前和实例协议校验后的两次策略调用。

不变边界：`enterprise.enabled=false` 仍返回本地 `NoAuthProvider`；企业缺 provider 或显式 NoAuth 的错误码和文案逐字不变。动态 class path 解析、模块导入、kwargs 实例化、`AuthProvider` 协议校验和成功日志仍在原 loader；Bearer/userinfo、签名 header、AppContext、RBAC、projection、audit 和 route 注册均未迁移或改变。该切片不新增或修改 FastAPI route，因此 route security matrix 无需变化。

上游 `datus/api/auth/loader.py` 相对 `v0.3.8` 从 `+34/-1` 收敛为 `+8/-1`，冲突行由 35 降至 9，减少 26。数字变化：新增 1 个 production/package 文件使 added 由 253 增至 254、总差异文件由 353 增至 354；modified 保持 96，其中 production/package 68、tests 24、config/meta 4；deleted 保持 4。新增文件分类变为 production/package 102、tests 123、docs 4、config/meta 25；计入本记录前总差异为 `+78844/-3595`。

验证：auth loader、enterprise provider fail-closed、Signed Header/UserInfo Bearer 装载、request deps 与 enterprise MVP smoke 迁移前后均为 `52 passed`；迁移文件 Ruff check/format、Python compile 与 `git diff --check` 通过。

### 2026-07-26：Datasource-file project override adapter 归位

分类：稳定 `core-hook`。处理方式：新增 `datus/configuration/agent_config_loader_downstream.py`，迁入 project override 校验前对 `services.datasources_file` 的预合并。上游 `_apply_project_override()` 只保留 helper import 和一次调用，再按原流程应用 target、default datasource 与其他 project pins。

不变边界：显式 `datasources_file` 仍优先于 `DATUS_DATASOURCES_FILE`，外部 datasource 仍覆盖同名 inline 配置；非 mapping services/datasources 仍跳过。预合并后继续清空 `datasources_file`，避免 `AgentConfig` 二次加载撤销 project default flags。配置路径解析、YAML 加载、project override 读取和校验、最终 `AgentConfig` 构造均未迁移。

上游 `agent_config_loader.py` 相对 `v0.3.8` 从 `+25/-1` 收敛为 `+2/-0`，冲突行由 26 降至 2，减少 24。数字变化：新增 1 个 production/package 文件使 added 由 252 增至 253、总差异文件由 352 增至 353；modified 保持 96，其中 production/package 68、tests 24、config/meta 4；deleted 保持 4。新增文件分类变为 production/package 101、tests 123、docs 4、config/meta 25；计入本记录前总差异为 `+78818/-3595`。

验证：Agent config loader、datasources-file、project override 与 downstream AgentConfig 组合回归迁移前后均为 `139 passed`；迁移文件 Ruff check/format、Python compile 与 `git diff --check` 通过。

### 2026-07-26：Runtime prompt template resolver 归位

分类：通用 `upstreamable-fix`。处理方式：新增 `datus/prompts/prompt_runtime_template_downstream.py`，迁入 request-scoped Agent 配置中的模板名、内容和版本匹配。上游 `PromptManager.render_template()` 只保留 helper import、一次解析调用，以及 runtime content 与文件模板之间的选择。

不变边界：Jinja environment、按 home 隔离的 LRU cache、用户/内置模板 loader、版本文件扫描、文件 fallback、`from_string()` 和最终 `template.render()` 均留在原 `PromptManager`。helper 只读取 `agentic_nodes` 数据形状；非 dict 节点、空模板、名称或显式版本不匹配仍返回 `None`，不会跨请求缓存内容。

上游 `prompt_manager.py` 相对 `v0.3.8` 从 `+26/-1` 收敛为 `+6/-1`，冲突行由 27 降至 7，减少 20。数字变化：新增 1 个 production/package 文件使 added 由 251 增至 252、总差异文件由 351 增至 352；modified 保持 96，其中 production/package 68、tests 24、config/meta 4；deleted 保持 4。新增文件分类变为 production/package 100、tests 123、docs 4、config/meta 25；计入本记录前总差异为 `+78801/-3596`。

验证：PromptManager、AgentConfig runtime prompt、custom Chat 与 GenSQL prompt fallback 组合回归迁移前后均为 `412 passed, 1 skipped`；迁移文件 Ruff check/format、Python compile 与 `git diff --check` 通过。

### 2026-07-26：Interactive node downstream adapter 归位

分类：稳定 `core-hook`。处理方式：新增 `datus/agent/node/node_factory_downstream.py`，迁入 custom Agent `node_class` capability fail-closed 校验，以及显式 `chat`/custom-chat 的 `ChatAgenticNode` 构造。上游 `create_interactive_node()` 在解析 canonical node class 后只调用一次 adapter，返回 `None` 时继续原 factory 分支。

不变边界：`_resolve_node_class_type()`、所有非 Chat 节点分支、默认无 subagent Chat、未知 custom Agent 的 GenSQL fallback、node input 分派和节点构造顺序均未迁移或复制。adapter 原样传递 node id/suffix、scope、execution mode、node name 与 session id；internal/non-customizable node class 仍在任何节点构造前拒绝。

上游 `node_factory.py` 相对 `v0.3.8` 从 `+22/-0` 收敛为 `+7/-0`，冲突行由 22 降至 7，减少 15。数字变化：新增 1 个 production/package 文件使 added 由 250 增至 251、总差异文件由 350 增至 351；modified 保持 96，其中 production/package 68、tests 24、config/meta 4；deleted 保持 4。新增文件分类变为 production/package 99、tests 123、docs 4、config/meta 25；计入本记录前总差异为 `+78781/-3596`。

验证：node factory、custom-chat 与 canonical capability registry 迁移前后均为 `50 passed`；ChatTaskManager interactive/workflow、builtin/custom/UUID/fallback 调用补充回归 `19 passed`；迁移文件 Ruff check/format、Python compile 与 `git diff --check` 通过。

### 2026-07-26：Success Story migration CLI 归位

分类：稳定 CLI 注册 hook。处理方式：新增 `datus_enterprise/success_story_migration_cli.py`，迁入 `migrate-success-stories` 的 parser 参数定义、企业 Success Story service 构造、迁移调用、OSError 展示和成功摘要。上游 `datus/main.py` 只保留企业模块 import、一次 parser 注册和配置加载后的提前 dispatch。

不变边界：命令名、`--source/--datasource/--subagent` 参数、默认 subagent、配置加载时机、Agent 初始化前执行、`EnterpriseSuccessStoryService`、project id、迁移参数、成功文案和 OSError 返回码均未改变。service 的 datasource 隔离、CSV schema、幂等、原子写入和 source 文件保留状态机未迁移或复制。

上游 `datus/main.py` 相对 `v0.3.8` 从 `+53/-0` 收敛为 `+5/-0`，冲突行由 53 降至 5，减少 48。数字变化：新增 1 个 production/package 文件使 added 由 249 增至 250、总差异文件由 349 增至 350；modified 保持 96，其中 production/package 68、tests 24、config/meta 4；deleted 保持 4。新增文件分类变为 production/package 98、tests 123、docs 4、config/meta 25；计入本记录前总差异为 `+78741/-3596`。

验证：上游 CLI parser/main、downstream migration CLI、上游 Success Story service 和企业 datasource/idempotency/migration 迁移前后均为 `57 passed`；迁移文件 Ruff check/format、Python compile 与 `git diff --check` 通过。

### 2026-07-26：Artifact creation ACL 归位

分类：企业策略归位。处理方式：新增 `datus_enterprise/services/artifact_creation_acl.py`，把新建 Report/Dashboard manifest 后的 owner 解析、enterprise fail-closed、默认 private ACL 持久化和稳定错误迁入企业 service。两个 artifact tool 只更换 import 来源，ACL 调用位置和返回契约不变。

不变边界：目录预留、manifest 写入、tool active state、ACL 成功后的 filesystem slug 绑定、ACL 失败后的 artifact rollback 和并发 slug owner 判定顺序均未改变。local-compatible 调用仍在没有 enterprise context 时跳过 ACL；企业模式缺少 store 或 authenticated owner 仍 fail closed。

上游 `_visual_artifact_helpers.py` 从 `+59/-0` 恢复为与 `v0.3.8` blob 字节级一致，退出 modified 和 allowlist；`report_artifact_tools.py` 保持 `+152/-28`，`dashboard_artifact_tools.py` 保持 `+155/-29`，换源没有扩大两个既有调用文件。数字变化：总差异文件保持 349；added 由 248 增至 249，modified 由 97 降至 96，其中 production/package 由 69 降至 68、tests 24、config/meta 4；deleted 保持 4。新增文件分类变为 production/package 97、tests 123、docs 4、config/meta 25；计入本记录前总差异为 `+78718/-3596`。

验证：Report/Dashboard artifact tools、downstream ACL/locked edit、visual artifact authorization 与 enterprise Artifact ACL 迁移前后均为 `197 passed`；原 helper byte compare、迁移文件 Ruff check/format、Python compile 与 `git diff --check` 通过。

### 2026-07-26：Model MCP connection options 归位

分类：通用 `upstreamable-fix`。处理方式：新增 `datus/models/mcp_connection_options_downstream.py`，把 Codex、OpenAI-compatible 和 Claude 五处重复的 `mcp_connection_failure_callback` 到 `on_connection_failure` 参数适配迁入纯 helper；三个上游模型原文件只保留 import 和一行参数展开。

不变边界：helper 只转换 kwargs，不连接 MCP server，也不负责 retry、callback 执行、cleanup 或异常处理。`multiple_mcp_servers()` 生命周期及三个模型的 Runner、原生 Claude、流式事件顺序、interrupt 和 session persistence 状态机均未迁移或改变。

原文件相对 `v0.3.8`：`codex_model.py` 从 `+106/-26` 收敛为 `+99/-26`，冲突行由 132 降至 125；`openai_compatible.py` 从 `+123/-38` 收敛为 `+116/-38`，冲突行由 161 降至 154；`claude_model.py` 从 `+77/-23` 收敛为 `+74/-23`，冲突行由 100 降至 97。合计减少 17 个上游原文件冲突行。数字变化：新增 1 个 production/package 文件使 added 由 247 增至 248、总差异文件由 348 增至 349；modified 保持 97，其中 production/package 69、tests 24、config/meta 4；deleted 保持 4。新增文件分类变为 production/package 96、tests 123、docs 4、config/meta 25；计入本记录前总差异为 `+78699/-3596`。

验证：MCP utility、Codex、OpenAI-compatible compact/stream order 与 Claude 模型组合回归迁移前后均为 `193 passed`；迁移文件 Ruff check/format、Python compile、纯参数 probe 与 `git diff --check` 通过。

### 2026-07-26：Artifact HTML bundle helper 归位

分类：通用 `upstreamable-fix`。处理方式：新增 `datus/agent/node/visual_artifact/artifact_html_bundle_downstream.py`，迁入 bundled renderer dist 路径、显式/内置 dist 校验、稳定 CDN fallback 警告，以及 CSS/JavaScript base64 data URL 生成。上游 `_artifact_html_renderer.py` 保留同签名 `_resolve_dist()` 薄 wrapper、local asset copy、`render_artifact_html_str()` 完整渲染流程和 `render_artifact_html()` 最终写盘；同时删除新增写盘 wrapper 中与字符串入口重复的长参数文档。

不变边界：显式无效 dist 仍直接回退 CDN，不会静默切换 bundled dist；未显式传 dist 时仍优先使用随包 renderer，缺失时无警告回退 CDN。字符串入口仍默认内联 data URL，文件入口仍复制 `_assets/index.css` 与 `_assets/index.umd.js`。slug 校验、symlink 防泄漏、artifact 文件读取、payload/script escaping、模板替换、query endpoint、最终写盘和 vendor bundle 内容均未迁移或改变。

原文件相对 `v0.3.8` 从 `+112/-33` 收敛为 `+50/-41`，总冲突行由 145 降至 91，减少 54。数字变化：新增 1 个 production/package 文件使 added 由 246 增至 247、总差异文件由 347 增至 348；modified 保持 97，其中 production/package 69、tests 24、config/meta 4；deleted 保持 4。新增文件分类变为 production/package 95、tests 123、docs 4、config/meta 25；计入本记录前总差异为 `+78695/-3596`。

验证：Report/Dashboard HTML、显式/bundled/CDN asset 选择、query endpoint escaping、vendor transport、Dashboard route 与安装后 wheel renderer 迁移前后均为 `27 passed`；迁移文件 Ruff check/format、Python compile 与 `git diff --check` 通过。

### 2026-07-26：Semantic query-time normalizer 归位

分类：通用 `upstreamable-fix`。处理方式：新增 `datus/tools/func_tool/semantic_query_time_downstream.py`，迁入 `now`、`-Nd/-Nw/-Nm/-Ny` 相对日期识别、统一 reference date 获取、日历月/年边界换算与稳定错误文案。上游 `SemanticTools` 只保留 `reference_date_provider` 注入字段，并在 `query_metrics()` 的原 try/日志/adapter 调用链中通过一次 helper 调用取得标准化的 `time_start/time_end`。

不变边界：provider 对同一请求仍最多求值一次；绝对日期不触发 reference date 获取；非法负号表达式仍在 adapter 调用前失败。adapter lazy load、runtime DB context、dimension preflight、query kwargs 能力探测、执行、压缩缓存、generation evidence、validation/reload 和 attribution 状态机均未迁移或改变。

原文件相对 `v0.3.8` 从 `+85/-5` 收敛为 `+15/-5`，总冲突行由 90 降至 20，减少 70。数字变化：新增 1 个 production/package 文件使 added 由 245 增至 246、总差异文件由 346 增至 347；modified 保持 97，其中 production/package 69、tests 24、config/meta 4；deleted 保持 4。新增文件分类变为 production/package 94、tests 123、docs 4、config/meta 25；计入本记录前总差异为 `+78694/-3588`。

验证：SemanticTools、relative query time、AskMetrics runtime reference date 与 ExplorerService 迁移前后均为 `240 passed`；迁移文件 Ruff check/format、Python compile 与 `git diff --check` 通过。

### 2026-07-26：Filesystem enterprise scope policy 归位

分类：`core-hook`。处理方式：扩展新增的 `datus_enterprise/services/artifact_filesystem_scope.py`，迁入企业全局 skills 只读覆盖、普通 Chat 对 report/dashboard 目录的保护判定，以及稳定的隐藏、mutation 拒绝和 glob visibility-filtered 返回格式。上游 `FilesystemFuncTool` 只保留两个构造开关、artifact-bound subclass 可覆写的保护 hook，以及 read/write/edit/delete/walk/glob/grep 执行前的薄调用点。

不变边界：`classify_path()`、hidden/external/read-only 顺序、symlink 防逃逸、gitignore、walk/glob/grep 执行和 Artifact ACL 授权均未迁移。helper 不查询也不授予 ACL；普通 Chat 仍隐藏受保护树，Artifact-bound filesystem 仍通过既有 override 绕过通用保护后，由服务端已授权 slug 的 scope 继续 fail closed。

原文件相对 `v0.3.8` 从 `+93/-0` 收敛为 `+55/-7`，总冲突行由 93 降至 62，减少 31。数字变化：复用已有 added production/package 文件，不增加文件数；added 保持 245、modified 保持 97、deleted 保持 4，总差异文件保持 346；计入本记录前总差异为 `+78669/-3588`。剩余差异同时包含通用 directory glob/sorted walk 修复与稳定 enterprise hook，因此 allowlist 从 `upstreamable-fix` 调整为 `core-hook`。

验证：Filesystem、generic artifact protection、企业 global/project skills 边界、Report/Dashboard filesystem 与 locked edit session 迁移前后均为 `260 passed`；迁移文件 Ruff check/format、Python compile 与 `git diff --check` 通过。

### 2026-07-26：MCPManager config/runtime adapter 归位

分类：通用 `upstreamable-fix`。处理方式：新增 `datus/tools/mcp_tools/mcp_manager_downstream.py`，迁入 server config replacement 事务和持久化 `ToolFilterConfig` 到 Agents SDK `ToolFilterStatic` 的形状转换。上游 `MCPManager.update_server()` 保留同签名薄 wrapper；STDIO/SSE/HTTP 工厂继续拥有参数构造和实例生命周期，只在 `tool_filter=` 参数处调用新增 adapter。

不变边界：update 仍在 manager lock 内检查存在性和禁止改名，缺省新 filter 仍继承旧配置，只有 `save_config()` 成功才返回成功。tool allow/block 判定、STDIO cwd、SSE/HTTP headers/timeout、连接、operation dispatch、cleanup 和 API service 返回契约均未迁移或改变。

原文件相对 `v0.3.8` 从 `+78/-7` 收敛为 `+36/-7`，总冲突行由 85 降至 43，减少 42。数字变化：新增 1 个 production/package 文件使 added 由 244 增至 245、总差异文件由 345 增至 346；modified 保持 97，其中 production/package 69、tests 24、config/meta 4；deleted 保持 4。新增文件分类变为 production/package 93、tests 123、docs 4、config/meta 25；计入本记录前总差异为 `+78622/-3588`。

验证：MCP manager/config/tool/service、update filter 继承、STDIO cwd 和 SDK runtime filter 迁移前后均为 `198 passed`；MCP route、fine-grained RBAC、platform-status gate、enterprise reference protection 与 route security matrix 补充回归 `76 passed`；迁移文件 Ruff check/format、Python compile 与 `git diff --check` 通过。

### 2026-07-26：Artifact filesystem ACL scope 归位

阶段：阶段 3/Artifact 资源授权执行 hook。处理方式：新增 `datus_enterprise/services/artifact_filesystem_scope.py`，迁入服务端已授权 artifact slug 的绑定状态、mutation fail-closed 判定、跨 slug read 隐藏、glob 结果提示和底层 walk 过滤。上游 `_artifact_filesystem_base.py` 保留通用 queries 只读、render 扩展名规则、原 Filesystem 执行，以及构造/绑定、三个 mutation 前置、read/glob/walk 的薄调用点。

不变边界：helper 不查询也不授予 Artifact ACL；默认 private ACL 落库与 `require_artifact_edit_access` 仍是 authoritative 授权入口。Enterprise 新建仍只在 ACL 成功持久化后绑定 slug，编辑会话仍锁定唯一 slug；正文、manifest 或磁盘目录存在不授予访问权。没有修改 route/module permission、请求 workspace、共享 `AgentConfig`、文件路径分类或 Filesystem 执行状态机。

原文件相对 `v0.3.8` 从 `+154/-1` 收敛为 `+47/-0`，总冲突行由 155 降至 47，减少 108。剩余差异是稳定的 Artifact ACL 执行前 hook，allowlist 从 `upstreamable-fix` 改归 `core-hook`。数字变化：新增 1 个 production/package 文件使 added 由 243 增至 244、总差异文件由 344 增至 345；modified 保持 97，其中 production/package 69、tests 24、config/meta 4；deleted 保持 4。新增文件分类变为 production/package 92、tests 123、docs 4、config/meta 25；计入本记录前总差异为 `+78603/-3588`。

验证：迁移前后 Artifact ACL binding、跨 slug 读写隐藏、glob/walk 过滤、Report/Dashboard 文件策略和普通 Filesystem 组合回归均为 `271 passed`；Artifact ACL authoritative store/route 与 Visual Agent 节点绑定补充回归 `202 passed`；迁移文件 Ruff check/format、Python compile 与 `git diff --check` 通过。

### 2026-07-26：AgenticNode permission/session/MCP runtime helper 归位

阶段：阶段 2/3（session 正文适配与运行时安全展示）。处理方式：新增 `datus_enterprise/services/agentic_permission_errors.py`，迁入 exception chain 上的 permission denial 识别及安全中文文案；新增 `datus_enterprise/services/agentic_session_runtime.py`，迁入 system-prompt snapshot 的 async/sync load/save/delete 和 turn 结束后的 running usage clear 适配；新增 `datus/agent/node/mcp_failure_actions_downstream.py`，迁入 MCP connection failure 去重及 failed `ActionHistory` 组装。上游 `AgenticNode` 保留原方法名作为薄兼容 wrapper，并在 compact 和 turn-finally 边界直接 await session adapter。

不变边界：permission helper 只识别并格式化既有拒绝，不参与授权决策；Tool Policy、permission profile 生效、workspace 路由、token lifecycle、模型 stream、Tool Lifecycle、ActionBus 与执行状态机均留在原节点。snapshot/body store 不替代 session owner，MCP failure action 也不代表连接成功或执行授权；没有写回共享 `AgentConfig`，没有引入 `tenant_id`。

原文件相对 `v0.3.8` 从 `+318/-30` 收敛为 `+195/-30`，总冲突行由 348 降至 225，减少 123。数字变化：新增 3 个 production/package 文件使 added 由 240 增至 243、总差异文件由 341 增至 344；modified 保持 97，其中 production/package 69、tests 24、config/meta 4；deleted 保持 4。新增文件分类变为 production/package 91、tests 123、docs 4、config/meta 25；计入本记录前总差异为 `+78566/-3589`。

验证：迁移前后 AgenticNode、prompt snapshot、workspace、permission denial、MCP failure 与 Tool Lifecycle 基线均为 `216 passed`；BodyStore、ChatTask history/permission error 和 live/history SSE 补充回归 `25 passed`；迁移文件 Ruff check/format、Python compile 与 `git diff --check` 通过。

### 2026-07-26：DBFuncTool datasource-grant scope 与 SQL source 判定归位

阶段：阶段 1/执行边界（数据源授权与 SQL policy 分层）。处理方式：新增 `datus_enterprise/services/database_tool_scope.py`，迁入 projected principal 中 datasource grant 的 legacy 维度匹配、目录树 union、namespace/table/listing 判定；新增 `datus/tools/func_tool/sql_scope_downstream.py`，迁入 SQLGlot 通用抽取以外的 `TABLE` expression、read-backed DML/DDL 源表识别。上游 `database.py` 保留 table coordinate、connector/physical database 路由、read/write/DDL/transfer 调用顺序与稳定错误返回，只通过薄 policy/helper 调用完成判定。policy 按调用即时读取 `principal`、default datasource 与 field order，继续兼容 CLI policy 使用 `object.__new__(DBFuncTool)` 构造轻量 guard 的既有入口。

不变边界：`read_query()` 继续先做只读校验，再执行 datasource scope 与 SQL policy；datasource grant 不替代 SQL policy。`_sql_context.database`、config `default_database`、datasource fallback 的物理数据库优先级未改。读取源表的 write/DDL 仍在执行前强制 SQL policy，policy rewrite 仍因不支持安全回写而拒绝；补充表名解析仍覆盖 `CREATE ... AS TABLE`、partition attach/detach/exchange、`INSERT ... TABLE` 与 parenthesized `TABLE` expression。普通 permission profile 的 ASK/deny 语义和 connector 执行状态机均未迁移或复制。

原文件相对 `v0.3.8` 从 `+470/-60` 收敛为 `+221/-60`，总冲突行由 530 降至 281，减少 249。数字变化：新增 2 个 production/package 文件使 added 由 238 增至 240、总差异文件由 339 增至 341；modified 保持 97，其中 production/package 69、tests 24、config/meta 4；deleted 保持 4。新增文件分类变为 production/package 88、tests 123、docs 4、config/meta 25；计入本记录后总差异为 `+78503/-3589`。

验证：DBFuncTool、database tool、datasource scope 与 SQL policy 聚焦回归 `276 passed`；CLI datasource-grant、metadata scope、physical database 与 SQL policy 路径 `90 passed`；迁移文件 Ruff check/format、Python compile 与 `git diff --check` 通过。

### 2026-07-26：Deps 企业 request context policy 归位

阶段：阶段 1（身份、RBAC 与数据源授权上下文）。处理方式：新增 `datus_enterprise/services/request_context_policy.py`，迁入企业用户状态校验、首次登录最小权限建档、role/permission 刷新、role 与 user datasource grant 合并、scope union/intersection、dev-admin provider context 合并以及 fail-closed deny audit 组装。上游 `deps.py` 保留认证入口、module singleton、DatusService cache、request-state 缓存和两个薄策略 wrapper；metadata/audit timeout 仍由原模块 callback 注入，因此既有 `datus.api.deps` timeout monkeypatch 契约不变。

不变边界：请求链仍是 Authenticate -> Validate User -> Refresh RBAC/Grants -> Build/Reuse DatusService；缺失用户、禁用用户、role metadata 或 datasource grant store 异常继续 fail closed，audit 写入失败不掩盖稳定 deny。没有信任前端角色/权限，没有写回共享 `DatusService.agent_config`，没有引入 `tenant_id`，也没有把 route/module authorization 混入 request-context policy。`deps._refresh_enterprise_context()`、`deps._intersect_allow_grants()` 与 `deps._intersect_scope_patterns()` 兼容入口继续可用。

原文件相对 `v0.3.8` 从 `+577/-10` 收敛为 `+167/-10`，总冲突行由 587 降至 177，减少 410。数字变化：新增 1 个 production/package 文件使 added 由 237 增至 238、总差异文件由 338 增至 339；modified 保持 97，其中 production/package 69、tests 24、config/meta 4；deleted 保持 4。新增文件分类变为 production/package 86、tests 123、docs 4、config/meta 25；计入本记录前代码总差异为 `+78395/-3589`。

验证：迁移前后 deps、downstream enterprise context 与 enterprise smoke 均为 `40 passed`；authorization、module RBAC、app main/lifespan 与 enterprise legacy-disable 组合回归 `198 passed`；迁移文件 Ruff check/format 通过。

### 2026-07-26：SessionManager 共享消息解析器归位

阶段：阶段 2（session 隔离与正文存储）。处理方式：新增 `datus/models/session_message_parser.py`，将 SQLite 与 PG BodyStore 共用的 SDK message row 解析迁入单一新增模块；`SessionManager._message_rows_to_raw_messages()` 保留为兼容入口，只注入 final-output、Claude native tool call 与 tool result 三个既有回调。`get_session_messages()` 继续只负责 session id/path 校验和 SQLite/BodyStore row 获取，没有复制 history 聚合状态机，也没有把 async BodyStore 路径导回同步 event-loop bridge。

不变契约：PG 与 SQLite history 仍经过同一个 parser；Responses API reasoning summary、Anthropic thinking/text、native `tool_use`/`tool_result`、web search/fetch result、reasoning/response action 分类、UTC timestamp 与 markdown content type 均保持原行为。`SessionManager` 的兼容入口及 native tool helper 仍可按原路径调用或替换。

原文件相对 `v0.3.8` 从 `+488/-282` 收敛为 `+171/-289`，总冲突行由 770 降至 460，减少 310。数字变化：新增 1 个 production/package 文件使 added 由 236 增至 237、总差异文件由 337 增至 338；modified 保持 97，其中 production/package 69、tests 24、config/meta 4；deleted 保持 4。新增文件分类变为 production/package 85、tests 123、docs 4、config/meta 25；计入本记录前代码总差异为 `+78297/-3589`。

验证：SessionManager、BodyStore、running usage、PG store 与 Chat history 组合回归 `187 passed`；Claude native stream、OpenAI-compatible stream order 与 PG history route 扩展回归 `174 passed`；迁移文件 Ruff check/format 通过。

### 2026-07-26：SessionManager downstream 扩展归位

阶段：阶段 2（session 隔离与正文存储）。处理方式：新增 `datus_enterprise/services/session_sidecar_mixin.py`，迁入 terminal/subagent display sidecar 的 SQLite/BodyStore 读写、async 入口与 payload 校验；新增 `session_async_store_mixin.py`，迁入 snapshot/copy/running usage 的 7 个 async-only adapter；新增 `session_scope.py`，迁入 user scope 安全化与 body-store project id 解析。`SessionManager` 保留原类名并继承两个 mixin，`session_scope_from_user_id` 仍从原模块显式重导出。

不变边界：`_store_kwargs()` 与 `_run_body_store_sync()` 留在原模块，保持既有 module-level `run_async` 替换点；SQLite session CRUD、copy/rewind/history 主流程、body-store 分支和 owner 授权边界未改。body store 有正文仍不代表已授权；运行中 task/SSE 状态仍未外部化。

原文件相对 `v0.3.8` 从 `+799/-281` 收敛为 `+488/-282`，总冲突行由 1080 降至 770，减少 310。数字变化：新增 3 个 production/package 文件使 added 由 233 增至 236、总差异文件由 334 增至 337；modified 保持 97，其中 production/package 69、tests 24、config/meta 4；deleted 保持 4。新增文件分类变为 production/package 84、tests 123、docs 4、config/meta 25；计入本记录后总差异为 `+78292/-3582`。

验证：BodyStore/PG sync bridge 聚焦回归 `10 passed`，scope 重导出 `2 passed`；SessionManager、BodyStore、running usage、PG store、Chat history/task 与 SubAgent sidecar 组合回归 `212 passed`；相关文件 Ruff check/format 通过。

### 2026-07-26：SubAgent 委派企业策略与 sidecar runtime 归位

处理方式：将父 Agent 请求级 permission profile 继承、Agent ACL denial 与 discovery predicate 迁入新增 `datus_enterprise/services/sub_agent_task_policy.py`，将委派 display sidecar 的事件构造与 best-effort 持久化迁入新增 `datus_enterprise/services/sub_agent_task_runtime.py`。上游 `SubAgentTaskTool` 直接调用执行前策略 helper、dispatch ACL 和目录 ACL predicate，并在 child stream 启动前调用持久化 helper；profile 仍在 child node 执行前继承，Agent ACL 仍在目录可见性与 task dispatch 两处生效，sidecar 失败仍不阻断 child execution，且不修改共享 `AgentConfig`。仅为 downstream 测试保留的两个私有 wrapper 已删除，测试改为直接覆盖新策略模块。

原文件相对 `v0.3.8` 从 `+112/-3` 收敛为 `+35/-2`，总冲突行由 115 降至 37，减少 78；其中 sidecar runtime 迁移将冲突行从 71 降至 56，ACL discovery predicate 降至 52，执行前策略与 wrapper 收口再降至 37。剩余差异均位于 dispatch ACL、child 执行前策略、stream 前 sidecar 与目录 ACL 四个不可后置边界，继续归 `core-hook`。数字变化：新增 2 个 production/package 文件使 added 由 231 增至 233、总差异文件由 332 增至 334；modified 保持 97，其中 production/package 69、tests 24、config/meta 4；deleted 保持 4。新增文件分类变为 production/package 81、tests 123、docs 4、config/meta 25；计入本记录后总差异为 `+78236/-3581`。

验证：sidecar 持久化时序与失败降级 `2 passed`，Agent ACL 目录可见性与 dispatch gate `5 passed`，downstream 契约 `12 passed`；SubAgent 工具、downstream 委派、skill creator 与 permission profiles 聚焦回归 `246 passed`；委派、ChatTaskManager、Chat routes、Agent routes 与 route security matrix 企业组合回归 `287 passed`；相关文件 Ruff check/format 通过。

### 2026-07-26：KB 运行中取消下游测试拆分

处理方式：将 KB 组件与平台文档初始化在运行中收到取消信号后必须报告失败的两个纯新增测试迁入新增 `tests/unit_tests/api/services/test_kb_service_downstream.py`。新文件直接复用原测试的 `_bootstrap_input`；仅随两个测试唯一使用者迁出 `threading.Event`，没有复制 KB service、fixture 或流状态机。

上游原测试不能伪恢复：`BootstrapKbInput` 已迁到 downstream 模型并要求显式 datasource，`_run_component()` 新增 request-scoped config 参数，现有 build/init/component/acceptance 测试都必须适配这些真实契约。原文件相对 `v0.3.8` 从 `+114/-24` 收敛为 `+29/-24`，总冲突行由 138 降至 53，减少 85；剩余差异继续归 `test-only`。

数字变化：新增 1 个 tests 文件使 added 由 230 增至 231、总差异文件由 331 增至 332；modified 保持 97，其中 production/package 69、tests 24、config/meta 4；deleted 保持 4。新增文件分类变为 production/package 79、tests 123、docs 4、config/meta 25；计入本记录后总差异为 `+78128/-3582`。

验证：拆分前后 AST 测试集合均为 46，missing/extra 都为空；KB service 两文件 `46 passed`；连同 KB 模型、普通/企业路由、route security matrix 与 document init 的组合回归 `195 passed`；两文件 Ruff format/check 与 `git diff --check` 通过。

### 2026-07-26：Storage read path 下游测试拆分

处理方式：将现有 storage table 的默认只读 `_search_all()` 不读取 vector、不初始化 embedding model 的纯新增测试迁入新增 `tests/unit_tests/storage/test_base_downstream.py`。调用记录 helper 随唯一使用者迁出，并通过薄子类调用原 `_ReadOnlyTable.search_all()`；新文件继续复用原测试的 vector DB 与 store 工厂，没有复制 storage 查询实现。

上游原测试不能伪恢复：打开现有 table 后同步 schema，以及 `_add_with_retry()` 输入先应用默认值，都是当前 storage 的真实契约。相关 helper 与既有测试改写继续留在原文件。原文件相对 `v0.3.8` 从 `+23/-1` 收敛为 `+6/-1`，总冲突行由 24 降至 7，减少 17；剩余差异继续归 `test-only`。

数字变化：新增 1 个 tests 文件使 added 由 229 增至 230、总差异文件由 330 增至 331；modified 保持 97，其中 production/package 69、tests 24、config/meta 4；deleted 保持 4。新增文件分类变为 production/package 79、tests 122、docs 4、config/meta 25；计入本记录后总差异为 `+78101/-3582`。

验证：拆分前后 AST 测试集合均为 67，missing/extra 都为空；Storage 两文件 `79 passed`；base/extensions、embedding lazy loading、schema metadata 与 Subject Tree storage 组合回归 `244 passed`；两文件 Ruff format/check 通过。

### 2026-07-26：Dashboard vendored renderer 下游测试拆分

处理方式：将 vendored dashboard renderer 支持可选 post-message query transport 的纯新增 bundle 检查迁入新增 `tests/unit_tests/agent/node/test_dashboard_html_renderer_downstream.py`。该测试直接读取随包分发的 UMD bundle，不依赖原测试的 dashboard fixture，因此没有复制 `_seed_dashboard`、payload 解析或 HTML render helper。

上游原测试不能伪恢复：Dashboard 模板现在显式选择 `window.__DATUS_ARTIFACT_QUERY_TRANSPORT__`，默认资源也从 unpkg CDN 改为随包 bundled dist 并复制到 artifact `_assets`。因此 bundled-default 测试是对上游 CDN-default 测试的真实替换，继续留在原文件。原文件相对 `v0.3.8` 从 `+36/-7` 收敛为 `+11/-7`，总冲突行由 43 降至 18，减少 25；剩余差异继续归 `test-only`。

数字变化：新增 1 个 tests 文件使 added 由 228 增至 229、总差异文件由 329 增至 330；modified 保持 97，其中 production/package 69、tests 24、config/meta 4；deleted 保持 4。新增文件分类变为 production/package 79、tests 121、docs 4、config/meta 25；计入本记录后总差异为 `+78072/-3582`。

验证：拆分前后 AST 测试集合均为 13，missing/extra 都为空；Dashboard 两文件 `13 passed`；Dashboard/Report renderer 与 visual artifact finalize 组合回归 `120 passed`；两文件 Ruff format/check 通过。

### 2026-07-26：Claude native thinking 下游测试拆分

处理方式：将 Claude native API 的 thinking block 与普通 text block 分离为 thinking/response action 的纯新增测试迁入新增 `tests/unit_tests/models/test_claude_model_downstream.py`。新文件直接复用原测试的 model/config/response 工厂、stream event 和 async stream manager，没有复制 native MCP 流生成器或 session/action-history 状态机。

上游原测试不能伪恢复：普通 text delta 已从 `thinking_delta` 改为 `response_delta`，最终 response 明确携带 markdown content type；non-text/empty delta 过滤与无 block-start 的 fallback stream ID 也必须遵循 response stream 契约。因此改名测试属于上游既有行为的真实替换，继续留在原文件。原文件相对 `v0.3.8` 从 `+77/-10` 收敛为 `+11/-10`，总冲突行由 87 降至 21，减少 66；剩余差异继续归 `test-only`。

数字变化：新增 1 个 tests 文件使 added 由 227 增至 228、总差异文件由 328 增至 329；modified 保持 97，其中 production/package 69、tests 24、config/meta 4；deleted 保持 4。新增文件分类变为 production/package 79、tests 120、docs 4、config/meta 25；计入本记录后总差异为 `+78059/-3582`。

验证：拆分前后 AST 测试集合均为 111，missing/extra 都为空；Claude 两文件 `111 passed`；Claude/OpenAI stream、builtin web tools 与 live/history SSE converter 组合回归 `289 passed`；两文件 Ruff format/check 通过。

### 2026-07-26：OpenAI-compatible stream order 下游测试拆分

处理方式：将 delegated task 完成后等待 session turn 持久化再响应中断，以及 reasoning/final answer 分离为不同 action 类型两个纯新增测试迁入新增 `tests/unit_tests/models/test_openai_compatible_stream_order_downstream.py`。reasoning delta/done fake 随其唯一使用者迁出；新文件直接复用原测试的事件构造和 `_collect_actions`，没有复制模型流生成器或 action-history 状态机。

上游原测试不能伪恢复：普通输出 delta 已从 `thinking_delta` 改为 `response_delta`，最终 response 明确携带 markdown content type，所有既有 ordering 断言必须同时过滤 thinking/response delta，同一响应流也改用 `response_stream_` ID。因此两个改名测试属于上游既有契约的真实替换，继续留在原文件。原文件相对 `v0.3.8` 从 `+137/-14` 收敛为 `+15/-14`，总冲突行由 151 降至 29，减少 122；剩余差异继续归 `test-only`。

数字变化：新增 1 个 tests 文件使 added 由 226 增至 227、总差异文件由 327 增至 328；modified 保持 97，其中 production/package 69、tests 24、config/meta 4；deleted 保持 4。新增文件分类变为 production/package 79、tests 119、docs 4、config/meta 25；计入本记录后总差异为 `+78034/-3582`。

验证：拆分前后 AST 测试集合均为 28，missing/extra 都为空；两文件 `28 passed`；OpenAI-compatible 基础/compact/retry/stream order 与 live/history SSE converter 组合回归 `348 passed`；两文件 Ruff format/check 通过。

### 2026-07-26：Database service 下游测试拆分

处理方式：将 request-scoped `DBManager` 复用、企业目录合并 views/materialized views，以及显式 `enumerate_databases` 三个纯新增测试迁入新增 `tests/unit_tests/api/services/test_database_service_downstream.py`；仅随唯一使用者迁出 `_FakeViewConnector` 与企业 service import，并显式复用原测试的 server connector 和 no-schema fixture。

上游原测试不能伪恢复：当前 service 延迟打开 connector，`current_db_name` 由首次 datasource 操作解析，因此 lazy-name 测试必须替代上游 eager 初始化断言；显式 request database filter 也必须在 datasource 开启 server enumeration 时继续优先。原文件相对 `v0.3.8` 从 `+57/-4` 收敛为 `+13/-4`，总冲突行由 61 降至 17，减少 44；剩余差异继续归 `test-only`。

数字变化：新增 1 个 tests 文件使 added 由 225 增至 226、总差异文件由 326 增至 327；modified 保持 97，其中 production/package 69、tests 24、config/meta 4；deleted 保持 4。新增文件分类变为 production/package 79、tests 118、docs 4、config/meta 25；计入本记录后总差异为 `+78001/-3582`。

验证：迁出的 3 个测试方法均由组合 AST 审计保留；database service 两文件 `37 passed`；连同企业 database service、database routes、module RBAC、route security matrix 与 config projection 的组合回归 `203 passed`；两文件 Ruff format/check 通过。

### 2026-07-25：Chat feedback 下游安全测试拆分

处理方式：将 datasource grant deny、显式 model policy deny、malformed model deny 与 feedback quota exceeded 四个纯新增测试迁入新增 `tests/unit_tests/api/routes/test_chat_routes_feedback_downstream.py`。新增文件直接复用原测试的 service/context/request/enterprise extensions/audit helpers；仅 `DatasourceGrantConfigProjector` import 随其唯一使用者迁出，没有复制共享 fixture。

上游原测试不能伪恢复：prompt routing、optional reaction 与 SQL-policy principal deny 三个既有测试已经适配认证 context、request dependency 中解析 DatusService、async session existence，以及完整 deny audit。原文件相对 `v0.3.8` 从 `+203/-7` 收敛为 `+77/-7`，总冲突行由 210 降至 84，减少 126；剩余差异继续归 `test-only`。

数字变化：新增 1 个 tests 文件使 added 由 224 增至 225、总差异文件由 325 增至 326；modified 保持 97，其中 production/package 69、tests 24、config/meta 4；deleted 保持 4。新增文件分类变为 production/package 79、tests 117、docs 4、config/meta 25；计入本记录后总差异为 `+77975/-3582`。

验证：拆分前后测试名集合均为 9，missing/extra 都为空；pytest 参数展开后的两文件 `17 passed`；连同 Chat routes、route security matrix、module RBAC、ChatService、ChatTaskManager 和 live/history SSE converter 的组合回归 `510 passed`；两文件 Ruff format/check 与 `git diff --check` 通过。

### 2026-07-25：Chat routes 下游安全测试拆分

处理方式：按 AST class/method 边界将 permission mode、enterprise builtin dispatch、resume buffer expiry、stream/feedback session owner、model policy、session insert owner、tool-result delivery、PG body-store list/delete/history，以及 SQL/model audit sink failure 等 33 个纯新增测试方法迁入新增 `tests/unit_tests/api/routes/test_chat_routes_downstream.py`。企业 owner extensions helper 与仅被迁出测试使用的 failing audit sink 同步迁出；session insert 测试只复制两个必要 static helper，没有复制上游原测试方法。

上游原测试不能伪恢复：33 个既有方法已经适配认证 context 与 request dependency 中解析 DatusService 的新 route signature、`StreamChatInput` 下游模型位置、SQL policy deny audit、async session list/delete/history、session owner/task existence 检查以及 live SSE 调用协议。原文件相对 `v0.3.8` 从 `+992/-56` 收敛为 `+111/-55`，总冲突行由 1048 降至 166，减少 882；剩余差异继续归 `test-only`。

数字变化：新增 1 个 tests 文件使 added 由 223 增至 224、总差异文件由 324 增至 325；modified 保持 97，其中 production/package 69、tests 24、config/meta 4；deleted 保持 4。新增文件分类变为 production/package 79、tests 116、docs 4、config/meta 25；计入本记录后总差异为 `+77943/-3582`。

验证：拆分前后测试名集合均为 75，missing/extra 都为空；Chat routes 两文件 `77 passed`；连同 route security matrix、feedback、module RBAC、ChatService、ChatTaskManager 和 live/history SSE converter 的组合回归 `510 passed`；两文件 Ruff format/check 与 `git diff --check` 通过。

### 2026-07-25：Report/Dashboard Artifact tools 下游测试拆分

处理方式：按 AST class/method 边界，将 Report 的 11 个、Dashboard 的 7 个纯新增 ACL、当前 event loop、locked-edit bootstrap 与 filesystem isolation 测试迁入新增 `test_report_artifact_tools_downstream.py` 和 `test_dashboard_artifact_tools_downstream.py`。新增文件显式复用原测试的 SQLite/project fixtures 与 async 启动 helper；测试方法本身不改写、不合并。

上游原测试不能伪恢复：`ReportArtifactTools.start_new_report()` 与 `DashboardArtifactTools.start_new_dashboard()` 已从同步方法改为 async，原有 fixture 及 6 个既有 start 测试必须经 `run_async()` 调用。Report 原文件从 `+276/-7` 收敛为 `+17/-7`，冲突行由 283 降至 24，减少 259；Dashboard 原文件从 `+222/-7` 收敛为 `+16/-7`，冲突行由 229 降至 23，减少 206。两文件剩余差异继续归 `test-only`。

数字变化：新增 2 个 tests 文件使 added 由 221 增至 223、总差异文件由 322 增至 324；modified 保持 97，其中 production/package 69、tests 24、config/meta 4；deleted 保持 4。新增文件分类变为 production/package 79、tests 115、docs 4、config/meta 25；计入本记录后总差异为 `+77883/-3583`。

验证：拆分前后 Report 测试名集合均为 59、Dashboard 均为 90，missing/extra 都为空；四文件 `176 passed`，连同 Artifact ACL、renderer、manifest、replacement 与 filesystem authorization 的组合回归 `586 passed`；Ruff 与 `git diff --check` 通过。既有 `test_ask_artifact_agentic_node.py` 产生 84 条 pytest asyncio 标记警告，本轮未改动该文件。

### 2026-07-25：ChatTaskManager 下游测试拆分

处理方式：按 AST class/method 边界将 terminal event 持久化、permission denial/interrupted history、旧任务清理与同 session 新任务隔离、owner store 回滚与 task owner、session ID 前置校验、graceful stop、request-scoped session body store、企业 workspace/Bash hardening 以及 legacy Agent permission ceiling 等 13 个纯新增测试方法迁入既有的 `tests/unit_tests/api/services/test_chat_task_manager_downstream.py`。permission ceiling 测试只复制 `_make_agent_config` 和 `_make_node` 两个必要 helper，没有搬运对应上游测试 class 的其他方法。

上游原测试不能伪恢复：live SSE 的 delta 判断已经从 thinking-only 扩展到 thinking/markdown stream delta，coalescing 必须保留不同 presentation 的边界；degraded capability warning 现在还包含 `mcp.remote`；`ChatTask` 初始状态新增 `session_established`、`terminal_event_persisted` 与 `stop_requested`。因此这些既有断言继续留在原文件。原文件相对 `v0.3.8` 从 `+368/-21` 收敛为 `+30/-21`，总冲突行由 389 降至 51，减少 338；剩余差异继续归 `test-only`。

数字变化：本轮使用的是已经计入 added 的既有 downstream 测试文件，因此总差异文件、added、modified 与 deleted 均不变，仍为 322、221、97、4；modified 分类仍为 production/package 69、tests 24、config/meta 4。迁移复用既有 imports/helpers 后净减少 8 行新增；计入本记录自身的 10 行文档增量后，最终总差异为 `+77811/-3583`。新增文件分类仍为 production/package 79、tests 113、docs 4、config/meta 25。

验证：拆分前后测试名集合均为 118，missing/extra 都为空；ChatTaskManager、ChatService、live/history SSE converter、Chat route/feedback、module RBAC 与 route security matrix 组合回归 `510 passed`；两份 ChatTaskManager 测试 Ruff 通过。

### 2026-07-25：CLIService 下游测试拆分

处理方式：按 AST class/method 边界将 direct SQL JSON typed cell、request-scoped config/connector、database/schema/table/catalog grant、StarRocks metadata SHOW、SQL policy deny/rewrite、task owner、projected context/internal metadata、chat info 和 session list 等纯新增覆盖迁入新增 `tests/unit_tests/api/services/test_cli_service_downstream.py`。新增文件只保留这些测试所需的 policy provider 类与 imports；policy provider 配置路径同步指向 downstream 测试模块，没有复制上游 `cli_svc` fixture 或其他既有测试。

上游原测试不能伪恢复：`CLIService._sql_tasks` 的值已从裸 `asyncio.Task` 改为携带 `owner_user_id` 的 `_SQLTaskRecord`，三个既有 stop/duplicate task 测试必须按新 record 结构注入任务。原文件相对 `v0.3.8` 从 `+1399/-4` 收敛为 `+5/-4`，总冲突行由 1403 降至 9，减少 1394；剩余差异继续归 `test-only`。拆分前后测试名集合均为 72，missing/extra 都为空。

数字变化：新增 1 个 tests 文件使 added 由 220 增至 221、总差异文件由 321 增至 322；modified 保持 97，其中 production/package 69、tests 24、config/meta 4；deleted 保持 4。写入本记录后的总差异为 `+77809/-3583`。

验证：CLIService 两文件测试名集合一致，迁移文件 Ruff 通过；CLI service/route、Database service、Dashboard query、module RBAC/datasource projection/SQL executor 和 route security matrix 组合回归 `332 passed`。首次组合命令引用了不存在的企业 CLI route 测试路径，pytest 在收集前退出；按 `rg --files` 的真实测试清单重跑后全量通过。

### 2026-07-25：ChatService 下游测试拆分

处理方式：按 AST class/method 边界将 async body-store list/delete、canonical reasoning/response history、Anthropic thinking、terminal sidecar、持久化 ask-user summary、nested/interrupted subagent history、async nested scope、session info scope、capacity admission 和 owner-store failure 等 13 个纯新增测试迁入新增 `tests/unit_tests/api/services/test_chat_service_downstream.py`。迁移同时显式复制 downstream 测试所需的 `chat_svc` fixture，并为 `test_get_session_info_passes_scope` 保留其唯一 class helper `_patched_sm`；没有复制其他上游测试。

上游原测试不能伪恢复：`Session.add_items()` 已改为 async API，`test_list_sessions_with_created_session` 必须使用 `asyncio.run()` 写入测试消息。原文件相对 `v0.3.8` 从 `+771/-2` 收敛为 `+1/-1`，总冲突行由 773 降至 2，减少 771；剩余差异继续归 `test-only`。拆分前后测试名集合均为 39，missing/extra 都为空。

数字变化：新增 1 个 tests 文件使 added 由 219 增至 220、总差异文件由 320 增至 321；modified 保持 97，其中 production/package 69、tests 24、config/meta 4；deleted 保持 4。写入本记录后的总差异为 `+77783/-3583`。

验证：ChatService 两文件测试名集合一致，迁移文件 Ruff 通过；ChatService、live/history SSE converter、Chat route/feedback、Success Story route/service/source、企业 service 和 route security matrix 组合回归 `307 passed`。首次组合命令引用了不存在的 `test_action_sse_converter_history.py`，pytest 在收集前退出；按 `rg --files` 的真实测试清单重跑后全量通过。

### 2026-07-25：Deps 企业依赖测试拆分

处理方式：按 AST 测试节点边界将 request context refresh、企业用户/角色/datasource grant、cache key、fail-closed status/audit、scope intersection 和 enterprise eviction 等纯新增覆盖迁入新增 `tests/unit_tests/api/test_deps_downstream.py`。上游原 `test_deps.py` 不做伪恢复：`init_deps()` 现在注册按 enterprise mode 计算 cache key 的异步 eviction wrapper，上游原“直接绑定 `cache.evict`”断言已经不成立；同时 `_chat_admission` 与 `_enterprise_extensions` 必须在 autouse fixture 中复位，避免 module singleton 跨测试泄漏。

原测试相对 `v0.3.8` 从 `+1174/-3` 收敛为 `+10/-2`，总冲突行由 1177 降至 12，减少 1165。剩余差异仅包含 `asyncio` import、两个新增 singleton 的前后清理，以及 mode-aware eviction callback 的真实行为断言；文件继续保留在 `test-only` allowlist。新增 downstream 文件共 1200 行，保留所有原企业测试节点，没有把企业安全链测试复制回上游原文件。

数字变化：新增 1 个 tests 文件使 added 由 218 增至 219、总差异文件由 319 增至 320；modified 保持 97，其中 production/package 69、tests 24、config/meta 4；deleted 保持 4。写入本记录后的总差异为 `+77738/-3584`。

验证：拆分后的 deps 两文件 `37 passed`；连同 auth loader、NoAuth/legacy auth、企业 auth provider、authorization、config projection、enterprise MVP smoke 和 route security matrix 的组合回归 `119 passed`；两文件 Ruff 与 AST 收集通过。

### 2026-07-25：Success Story route 测试归位

处理方式：当前原测试路径已经整体改写为企业权威 route 契约，直接导入 `datus_enterprise.api.success_story_routes`，不再测试上游 legacy handler。将这 173 行企业测试原样迁入新增 `tests/unit_tests/datus_enterprise/api/test_success_story_routes.py`，并把 `tests/unit_tests/api/routes/test_success_story_routes.py` 完整恢复到 `v0.3.8`，使 legacy 上游 handler 与 authoritative 企业 handler 各自在对应目录保留独立覆盖。

原测试相对 `v0.3.8` 从迁移前的 `+144/-33` 恢复为零差异。新增企业测试继续覆盖唯一 authoritative route 注册、canonical source、session owner 拒绝、失败 source code、只读 SQL、安全 OSError copy 和无完整 SQL audit；恢复的原测试继续覆盖 legacy success、subagent-not-found 400 与写入失败结果。数字变化：added 由 217 增至 218，modified 由 98 降至 97，其中 tests 由 25 降至 24；production/package 69、config/meta 4、deleted 4 均不变，总差异文件保持 319。写入本记录后的总差异为 `+77692/-3585`。

验证：原测试与 `v0.3.8` 字节级一致；legacy/enterprise route、Success Story service/downstream、ChatService canonical source 和 route security matrix 组合回归 `85 passed`；两份测试 Ruff 通过。

### 2026-07-25：Stream cancellation 安全边界归位

处理方式：将 owner/project metadata、重复 stream ID 拒绝、ownership 校验和同步 cleanup 迁入新增 `datus.api.utils.stream_cancellation_metadata` 安全 wrapper；普通 `datus.api.utils.stream_cancellation` 与其上游原测试完整恢复为 `v0.3.8`。普通/legacy KB 路径继续使用上游覆盖式 token 行为，企业权威 `datus_enterprise.api.kb_routes` 则只导入安全 wrapper，不会绕过 owner/project 校验。

安全 wrapper 创建 token 前检查基础 `_tokens`，碰到 UUID collision 时抛 `ValueError` 且不覆盖活动 event；取消时要求 ownership metadata 必须存在并与请求 user/project 匹配，因而对 foreign owner、project mismatch 以及只有基础 token、没有企业 metadata 的 legacy token 都 fail closed；cleanup 同时移除基础 token 和 metadata。上游原实现相对 `v0.3.8` 从迁移前的 `+56/-6` 恢复为零差异，原测试从 `+36/-5` 恢复为零差异；安全契约转入新增 downstream 测试。

数字变化：新增 metadata wrapper 和 downstream 测试使 added 由 215 增至 217；恢复 1 个 production 文件与 1 个原测试使 modified 由 100 降至 98，其中 production/package 由 70 降至 69、tests 由 26 降至 25；config/meta 保持 4，deleted 保持 4，总差异文件仍为 319。写入本记录后的总差异为 `+77656/-3618`。两个恢复文件已从 modified allowlist 删除，旧的 `move-to-enterprise` 候选也不再包含 cancellation 原模块。

验证：两份恢复文件与 `v0.3.8` 字节级一致；基础 cancellation、下游安全契约、普通 KB route、企业 authoritative KB route 和 route security matrix 组合回归 `89 passed`；迁移文件 Ruff 通过。

### 2026-07-25：History-only SSE converter 归位

处理方式：新增 `datus.api.services.action_history_sse_converter`，迁入持久化 `ask_user` question/result 解析、成功状态兼容、`interaction-summary` 只读 payload 和 history-only action conversion。上游原 `action_sse_converter.py` 在文件末尾直接重新导出同名函数；新模块对 live converter 的私有 helper 使用函数内懒加载，因此无论先 import live converter 还是先 import history converter 都不会形成循环初始化，`from datus.api.services.action_sse_converter import action_to_history_sse_event` 的现有调用路径保持不变。

原文件相对 `v0.3.8` 从 `+183/-6` 收敛为 `+27/-6`，总冲突行由 189 降至 33，减少 156。剩余差异继续归 `upstreamable-fix`：response JSON envelope 展开、`content_type=markdown` 的 final-response 判断、结构化 `error_type` 传递和 `response_delta` markdown streaming 都位于通用 live SSE 主分派中；把它们迁到 enterprise 模块或执行后补偿会分叉 wire contract，适合整理成一份小型上游补丁而不是继续抽离状态机。

数字变化：新增 1 个 production 文件使 added 由 214 增至 215，总差异文件由 318 增至 319；modified 保持 100，其中 production/package 70、tests 26、config/meta 4；deleted 保持 4。写入本记录后的总差异为 `+77544/-3629`。

验证：live/history converter 两种 import 顺序探针通过；上游 converter、下游 response/error/history/delta 契约 `118 passed`；连同 ChatService 和 Chat routes/feedback 的组合回归 `251 passed`；迁移文件 Ruff 通过。

### 2026-07-25：ChatService history/session 扩展归位与核心 hook 收口

处理方式：新增 `datus_enterprise.services.chat_service_mixin.EnterpriseChatServiceMixin`，迁入上游 tag 中不存在的 Success Story canonical source 恢复、SQL tool/action 解析、history payload 重建、terminal/subagent sidecar 合并、nested subagent history、session body-store adapter，以及异步 session exists/list/delete/history、session info、stream 启动错误事件和 canonical history 组装。`ChatService` 继续保留原导入路径；`SuccessStorySourceError` 通过显式同对象别名导出，所有实例方法和既有 instance monkeypatch 入口不变。

迁移中先机械移动原文件第 486 行以后的纯新增方法，再逐 hunk 迁出位于上游方法之间的纯新增 async/session 方法与无状态组装 helper。曾把 `_session_manager()` 一并迁入 mixin，但聚焦测试证明这会使 `datus.api.services.chat_service.SessionManager` 的模块级 patch 失效，因此立即把该 13 行工厂 hook 留回上游壳。上游原 import 也保持原行结构，并仅在兼容壳文件声明 `F401/I001`，避免格式器把已迁出实现曾使用的 import 变成无谓删除。最终 `chat_service.py` 相对 `v0.3.8` 从迁移前的 `+881/-70` 收敛为 `+57/-71`，总冲突行由 951 降至 128，减少 823。

逐 hunk 审计后，剩余差异从 `move-to-enterprise` 改归 `core-hook`：构造函数只注入 project/session body store 和 mixin；`stream_chat()` 只保留 request-scoped config 与启动失败边界；同步 session CRUD 只通过 scoped manager；compact 只投影 body-store-aware config/scope；`get_history()` 只在上游读取入口调用 canonical enterprise reconstruction。`_session_manager()` 必须留在本模块以保持已有依赖替换契约。没有复制 stream/session/history 主状态机，也没有恢复会丢失 terminal sidecar、nested subagent reasoning/response 或可信 Success Story SQL/datasource 的旧 history 行为。

数字变化：新增 1 个 enterprise production 文件使 added 由 213 增至 214，总差异文件由 317 增至 318；modified 保持 100，其中 production/package 70、tests 26、config/meta 4；deleted 保持 4。写入本记录后的总差异为 `+77517/-3629`。`move-to-enterprise` allowlist 已清空，`chat_service.py` 转入 `core-hook`。

验证：mixin 基类、异常别名和 13 个继承方法入口的兼容性探针通过；ChatService、Success Story、Chat route/feedback、SSE converter、module RBAC、route security matrix 和企业 MVP smoke 合并回归 `406 passed`；迁移文件 Ruff 通过。沙箱内 CPython 3.12.13 的 `asyncio.run()` 在关闭默认线程池时可复现环境性挂起，同一只读测试在沙箱外完整通过，未为环境问题修改生产代码。

### 2026-07-25：Chat task runtime 辅助逻辑归位与核心 hook 收口

处理方式：新增 `datus_enterprise.services.chat_task_runtime`，迁入完全新增的 Chat buffer limits/异常、Web filesystem executor 类型、report/dashboard edit-session registry、ChatTask owner/buffer/admission/terminal 扩展字段初始化、terminal outcome 解析、bounded buffer trim 和 admin task snapshot 格式化。上游 `chat_task_manager.py` 保留 `ChatTask`、delta coalescing、database context、start/stop/consume、node factory 和 `_run_loop` 主体，只通过 import、同签名 wrapper 与 `staticmethod` 别名调用新增 helper；原有 `ChatTaskManager`、`ChatTask`、buffer exception 和 gateway helper 导入路径不变。

迁移过程中曾尝试把上游已有的 `ChatTask` 和 SSE delta/context helper 整体移出，真实差异从 `+522/-73` 变为 `+410/-247`，删除冲突面明显扩大，因此立即撤回；最终版本只移动 tag 基线中不存在的扩展，原文件差异收敛到 `+394/-72`，总冲突行减少 129。

逐 hunk 审计后，剩余差异从 `move-to-enterprise` 改归 `core-hook`：构造函数中的 owner/body/ACL/admission/buffer 注入，`start_chat()` 的 request-scoped config、workspace、Bash/model/datasource hardening与 owner/admission 占位，`consume_events()` 的绝对 cursor，terminal event 持久化，以及 `_run_loop` 中的 node/session/proxy/policy/SSE lifecycle 和 task-slot cleanup 都必须位于上游主状态机内部。整体覆盖 manager 会复制约 1000 行 task/SSE 状态机，执行后补偿又不能满足 fail-closed 与 durable terminal history，因此不再保留整体迁移候选分类。

数字变化：新增 1 个 enterprise production 文件使 added 由 212 增至 213，总差异文件由 316 增至 317；modified 保持 100，其中 production/package 70、tests 26、config/meta 4；deleted 保持 4。写入本记录后的总差异为 `+77456/-3630`。

验证：ChatTaskManager、node dispatch、permission override、task owner、SSE delta/buffer/admission、terminal persistence 和 Web filesystem executor `130 passed`；ChatService、Chat route/feedback、admin session 与 system status `161 passed`。最终 ChatTask 扩展字段迁移另以 task initialization、bounded buffer 和 admin runtime snapshot 7 项聚焦复核通过；Ruff、兼容别名身份和 helper 导入路径检查均通过。

### 2026-07-25：CLI connector/task owner 辅助逻辑归位与核心 hook 收口

处理方式：新增 `datus_enterprise.services.cli_execution`，迁入 SQL task owner record、request-scoped `DBManager` factory/cleanup 和 connector database switch。上游 `CLIService` 继续通过 `_SQLTaskRecord` import、`_switch_connector_database` 静态别名和一个显式传入 `DBManager` 的薄 wrapper 保持既有调用与 monkeypatch 契约；后者避免企业模块反向 import 上游 service，也保证测试替换 `datus.api.services.cli_service.DBManager` 后仍作用于 request-scoped manager。`cli_service.py` 相对 `v0.3.8` 的新增行由 324 降至 310，删除行保持 172。

逐 hunk 审计后，剩余差异从 `move-to-enterprise` 改归 `core-hook`：`execute_sql()` 的 request-scoped connector、database grant、只读 SQL policy、task owner 与 JSON 结果规范化，`execute_context()` 的 projected config 和 catalog/table scope，以及 `execute_internal_command()` 的 metadata grant、session owner 都嵌在各自主状态机的 dispatch 前或资源 cleanup 边界。把参数检查放到执行后会削弱 fail-closed 链；整体覆盖三个方法则会复制约 600 行上游执行、context 和 internal command 流程。当前保留的是向后兼容的可选参数和策略/生命周期 hook，不再保留待整体迁移的分类。

数字变化：新增 1 个 enterprise production 文件使 added 由 211 增至 212，总差异文件由 315 增至 316；modified 保持 100，其中 production/package 70、tests 26、config/meta 4；deleted 仍为 4。写入本记录后的总差异为 `+77368/-3631`。

验证：CLI SQL/task/context/internal、datasource grant、metadata SHOW、SQL policy、Dashboard query 与企业 CLI route 拆组回归 `90 passed` 和 `63 passed`；module RBAC、route security matrix 与企业 MVP auth/catalog/SQL smoke `143 passed`。Ruff、迁移别名身份检查和 helper monkeypatch 契约均通过。首次 153 项组合在首个真实 SQLite SQL 用例发生一次线程池超时；中止后该用例与迁移 helper 的 4 项边界单跑通过，随后完整 CLI 90 项和 Dashboard/route 63 项拆组均通过。

### 2026-07-25：Database status/prewarm 与企业目录能力归位

处理方式：新增 `datus_enterprise.services.database_service.EnterpriseDatasourceService`，迁入 datasource connection status cache、route timeout 记录、prewarm 去重与后台连接测试，以及企业目录需要的 views/materialized views 合并和显式 `enumerate_databases`。`DatusService.datasource` 统一构造企业子类；status 测试迁入新增 `tests/unit_tests/datus_enterprise/services/test_database_service.py`。普通 `DatasourceService` 仍只列上游 tables，并保留配置数据库优先、未配置数据库时才枚举服务器的原语义。

上游 service 仅保留共享 `DBManager` 注入、lazy current connector、`_record_connection_status`、`_get_table_like_names` 和 `_should_enumerate_databases` 薄 hook，以及 `list_databases()` 内成功/失败状态回调。没有覆盖目录主状态机，也没有把普通用户 `/catalog/list` 的 grant pruning 混入 service；管理员 grant-editor 的 view 候选继续复用既有 `tables: list[str]` shape。`database_service.py` 相对 `v0.3.8` 从 `+189/-24` 收敛到 `+97/-24`，累计减少 92 行新增差异。

剩余差异从 `move-to-enterprise` 改归 `core-hook`：共享 manager 与 lazy connector 是 request-scoped Table/semantic-model 隔离边界；view/table hook 和显式 server enumeration 可单独向上游贡献；semantic-model 文件写入、OSI/MetricFlow sync 与 validate 的 `asyncio.to_thread()` 属于通用 event-loop 修复。为了减少数字而复制 `_get_connection_info()`、`list_databases()` 或 semantic-model 状态机不符合后续升级目标。

数字变化：新增 enterprise service 与企业测试使 added 由 209 增至 211，总差异文件由 313 增至 315；modified 保持 100，其中 production/package 70、tests 26、config/meta 4；deleted 仍为 4。写入本记录后的总差异为 `+77337/-3631`。

验证：Database/Datus/Table service、route、factory、cache、status/prewarm、views、server enumeration 和 request-scoped projection `121 passed`；module RBAC、route security matrix 与企业 MVP auth/catalog/SQL smoke `143 passed`。Ruff、`git diff --check` 和 allowlist 均通过。

### 2026-07-25：CLI SQL/grant 静态策略第二轮归位

处理方式：继续把 `CLIService` 中无实例状态的 `_authorize_read_sql`、metadata scope 校验、database/catalog/schema/table grant 过滤、field-order/scoped-pattern 计算和当前 datasource grant 解析迁入 `datus_enterprise.services.cli_sql_policy`。上游 service 只保留 11 个同名 `staticmethod` 别名，因此 Dashboard 的 `CLIService._authorize_read_sql`、既有单测的 `_database_grant_denial`、内部实例调用及 monkeypatch 点都保持不变。

本轮仍未迁出 `_execution_connector`、`_request_scoped_db_manager`、SQL task owner 或 execute/context/internal command 主流程；这些方法直接参与 connector 生命周期和上游状态机，后续必须单独审计，不能与纯策略函数一起机械搬迁。`cli_service.py` 相对 `v0.3.8` 的新增行由 632 降至 324，删除行由 170 变为 172；原文件长度由 1240 行降至 905 行。新增企业策略模块由 95 行增至 447 行，集中承载可独立测试和复用的下游 SQL policy 边界。

数字变化：文件级分类不变，仍为 313 files、209 added、100 modified、4 deleted；modified 继续拆分为 production/package 70、tests 26、config/meta 4。写入本收敛记录后的总插入为 77269。

验证：CLI SQL/task/context/internal、全层级 datasource grant、metadata SHOW、SQL policy、Dashboard query 与企业 CLI route `153 passed`；module RBAC、route security matrix 和企业 MVP auth/catalog/SQL smoke `143 passed`。Ruff、静态别名一致性、`git diff --check` 和 allowlist 检查均通过。

### 2026-07-25：CLI datasource scope 纯策略辅助逻辑迁出

处理方式：把 `CLIService` 中不依赖执行状态的 datasource scope pattern 归一化、scope token 组合、dialect coordinate 判断和 metadata `SHOW` target 正则迁入新增 `datus_enterprise.services.cli_sql_policy`。上游 service 仍保留 `_authorize_read_sql`、request-scoped connector、SQL task owner、context/internal command 以及 SQL 执行状态机，只通过显式 import 使用企业策略 helper；`CLIService._authorize_read_sql` 等既有调用入口不变，Dashboard query 和测试 monkeypatch 契约也未改变。

本轮没有整体覆盖 `CLIService`：当前 request-scoped connector、只读校验、SQL policy、grant 过滤和 task owner 与 execute/context/internal 三套上游流程交错，直接子类化会复制约 700 行主体。先迁出纯 helper 后，原 `cli_service.py` 相对 `v0.3.8` 的新增行由 703 降至 632、删除行由 171 降至 170；剩余边界继续保留在 `move-to-enterprise` 供后续按方法审计。

数字变化：新增 1 个 enterprise production 文件使 added 由 208 增至 209，总差异文件由 312 增至 313；modified 保持 100，其中 production/package 70、tests 26、config/meta 4；deleted 保持 4。总插入由 77210 增至 77242，是上游原文件减少 71 行差异、同时新增 95 行独立策略模块、import 调整及本收敛记录后的净结果。

验证：CLI SQL/task/context/internal、datasource grant、metadata SHOW、Dashboard query 和企业 CLI route 聚焦回归 `153 passed`；迁移文件 Ruff 与 `git diff --check` 通过，差异 allowlist 仍为 `ok (100 modified files)`。

### 2026-07-25：Chat route 安全核心分类归位

处理方式：逐端点对照 `v0.3.8` 后确认，当前 Chat router 的 13 个 endpoint 与上游完全同构，没有可以独立迁出的下游新增 route。差异分布在 `/stream`、`/feedback`、resume/stop/compact/list/delete/history 以及 user-interaction/insert/tool-result 的 dispatch 前安全链，分别承载 permission-mode RBAC、Agent/Artifact ACL、request-scoped datasource 与 principal 投影、用户模型凭据、model/SQL policy、quota、session owner、platform status、audit 和过期 SSE event buffer 等边界。

没有把整份 Chat router 复制到 `datus_enterprise/`：这会把上游主 SSE/interaction 状态机变成难追踪的新增副本，并让后续 release 更新只能人工比对；也没有让企业 wrapper 在委托上游 handler 后补权限，因为授权、投影和配额必须在 service resolution/dispatch 前完成。因此 `datus/api/routes/chat_routes.py` 从 `move-to-enterprise` 改归 `core-hook`，保留单一权威实现。原 Chat route 测试仍为 `test-only`：上游测试直接调用 handler，而当前安全链需要 request context、request-scoped service 和 owner store，无法在字节级恢复原测试的同时保持真实调用契约。

数字变化：分类调整不改变文件差异；modified 保持 100，其中 production/package 70、tests 26、config/meta 4；added 208、deleted 4，总差异文件 312。

同轮复核还把 `DatusService` 与 `DashboardService` 从 `move-to-enterprise` 改归 `core-hook`。前者只负责向上游 facade 注入 request-scoped session stores、Chat task limits/执行边界，以及构造已经迁入 `datus_enterprise.services` 的 MCP、Success Story、Dashboard、Report 实现；后者相对上游只保留 Dashboard query 状态机内部的 request-scoped config、执行前 quota callback 和 SQL read-policy hook。把整个 facade 迁走会让所有上游 service property 分叉，把 `run_query()` 整体覆盖到企业子类则会复制模板加载、参数校验、渲染和 connector 执行状态机；两者都比保留现有薄 hook 更难随上游更新。

### 2026-07-25：KB route 与原测试归位

处理方式：把浏览器 upload staging、upload owner/admin 访问、purpose/file 选择、success-story datasource provenance、request-scoped datasource projection、路径防逃逸、用户/项目绑定 cancel token、platform status、audit 和 SSE 响应契约迁入新增 `datus_enterprise.api.kb_routes`。`create_app()` 只注册企业 KB router，并逐项验证 upload、bootstrap、bootstrap-docs 和两个 cancel 路径均只有一个企业 handler。上游 KB router 和原测试恢复为 `v0.3.8` 内容，下游 route 测试迁入新增企业测试文件。

没有把企业 bootstrap wrapper 委托给上游 handler：投影配置必须在 service 调用前创建，upload-derived 路径和 datasource provenance 必须在启动线程前校验，cancel token 也必须绑定当前 user/project；委托上游 handler 会重新创建无 owner token 并使用共享 config，无法满足安全链。

数字变化：modified 由 102 降到 100，其中 production/package 由 71 降到 70、tests 由 27 降到 26；新增企业 route 与下游测试使 added 由 206 增至 208。deleted 保持 4，总差异文件保持 312。

验证：上游原 KB route、企业 upload/owner/provenance/projection/SSE/cancellation、KB service 和 route security matrix 聚焦回归合计 `120 passed`；迁移相关 Ruff 与 `git diff --check` 通过。`kb_routes.py` 与 `v0.3.8` blob `40386a8ea227d7a32f29841923bb6745a23003a5` 字节级一致，原测试 blob `25091d2a9242fbba15cfe853c569e64906d6fbfc` 也字节级一致。

### 2026-07-25：Config route 与原测试归位

处理方式：把配置读取脱敏、provider/structured target 更新、redacted placeholder 回填、保存失败回滚、saved model/datasource probe、module RBAC 和 platform status gate 迁入新增 `datus_enterprise.api.config_routes`。`create_app()` 只注册企业 Config router，个人模型凭据与个人数据源路由也统一复用企业 probe helper，避免 datasource probe 退回旧的嵌套 `DBManager` 配置形状。上游 Config router 和原测试均恢复为 `v0.3.8` 内容，下游安全与管理契约测试迁入新增企业测试文件。

没有把企业 wrapper 委托给上游 mutation handler：上游 handler 会直接覆盖原始 secrets、缺少 provider/structured target、保存失败回滚和 platform gate，委托后再补偿无法保证 fail-closed。迁移保留了一份下游权威实现，但从上游升级冲突面中完整移除。

数字变化：modified 由 104 降到 102，其中 production/package 由 72 降到 71、tests 由 28 降到 27；新增企业 route 与下游测试使 added 由 204 增至 206。deleted 保持 4，总差异文件保持 312。

验证：上游原 Config route、企业脱敏/更新/回滚/probe、RBAC、platform status、唯一 app 注册、route security matrix、个人模型凭据和个人数据源聚焦回归合计 `116 passed`；迁移相关 Ruff 与 `git diff --check` 通过。`config_routes.py` 与 `v0.3.8` blob `36a16c66cc6d4394d1ce706357cffe404f2c6115` 字节级一致，原测试 blob `b5155122e83e43ec2b0105fb1293db82c66a8e35` 也字节级一致。

### 2026-07-25：Success Story service 与原测试归位

处理方式：把 datasource 隔离目录、server-resolved source、稳定 story ID、幂等写入、旧 CSV schema 兼容、原子替换和显式迁移能力迁入新增 `datus_enterprise.services.success_story_service.EnterpriseSuccessStoryService`。`DatusService.success_story` 和 `migrate-success-stories` CLI 统一构造企业子类，上游 append-only `SuccessStoryService` 保持原契约；下游持久化测试迁入新增 `_downstream.py`，上游原 service 及原测试均恢复为 `v0.3.8` 内容。

同时复核了剩余 service 分类：`AgentService` 的 capability registry 去重、`action_sse_converter` 的通用 SSE/history 修复和 `ExplorerService` 的 event-loop offload 改归 `upstreamable-fix`；`KbService` 的 request-scoped config 归 `core-hook`，运行中 cancellation 可独立向上游贡献。它们都不适合为减少数字而复制上游状态机或恢复阻塞行为。

数字变化：modified 由 106 降到 104，其中 production/package 由 73 降到 72、tests 由 29 降到 28；新增企业 service 与下游测试使 added 由 202 增至 204。deleted 保持 4，总差异文件保持 312。

验证：上游原 service、下游 datasource/idempotency/migration、service 工厂、canonical source、Success Story route、安全错误、CLI migration 和 route security matrix 合计 `49 passed`；迁移相关 Ruff 与 `git diff --check` 通过。`success_story_service.py` 与 `v0.3.8` blob `d62b4e952f88e3cdd7034f9ee987b6f5c26b5ba8` 字节级一致，原测试 blob `90d33e2cfbb242a4576909c7b52167778a623cce` 也字节级一致。

### 2026-07-25：Dashboard service list/render 归位

处理方式：把企业 Artifact API 使用的 dashboard manifest 列表和离线 HTML 渲染迁入新增 `datus_enterprise.services.dashboard_service.EnterpriseDashboardService`，并由已有 `DatusService.dashboard` 工厂统一构造企业子类。上游 `DashboardService` 继续保留 detail、模板解析、参数校验和 query 状态机。

`run_query()` 没有机械迁出：request-scoped config、模板 datasource 二次投影、执行前 quota 回调和 `CLIService._authorize_read_sql()` 位于模板加载、校验、渲染与 connector 执行之间。移到 route 会让无效模板提前消耗 quota，整体复制到企业子类则会复制上游查询状态机。因此当前原文件仍保留这些必要薄钩子和 connector `dialect` 安全契约，但相对 `v0.3.8` 的差异已从 `+141/-1` 缩小为 `+30/-1`。

数字变化：modified 保持 106，其中 production/package 保持 73；新增企业 Dashboard service 使 added 由 201 增至 202，总差异文件由 311 增至 312。tests 保持 29 modified，deleted 保持 4。

验证：上游 Dashboard detail/query、下游 list/render、request-scoped datasource、SQL read-only/table scope/policy、企业 service 工厂、Artifact ACL、edit-session、quota、audit 和 module RBAC 拆分回归合计 `100 passed`，迁移文件 Ruff 通过。首次大组合在未修改的 `asyncio.to_thread()` 文件读取处发生线程池超时；拆成基础 service、下游 service、Dashboard route、Artifact route 和 RBAC 五组后全部通过。

### 2026-07-25：Report service 归位

处理方式：把企业 Artifact API 使用的 report manifest 列表和离线 HTML 渲染迁入新增 `datus_enterprise.services.report_service.EnterpriseReportService`，继续继承上游的 slug/path 防逃逸与 detail bundle 读取实现。已经属于 core hook 的 `DatusService.report` 统一构造企业子类，Artifact ACL、分享、编辑会话和 HTML route 的调用契约不变。上游 `datus/api/services/report_service.py` 已恢复为 `v0.3.8` 原内容。

数字变化：modified 由 107 降到 106，其中 production/package 由 74 降到 73；新增企业 Report service 使 added 由 200 增至 201。tests 保持 29 modified，deleted 保持 4，总差异文件保持 311。

验证：上游 report detail/bundle、下游离线 HTML、企业 service 工厂、report list/ACL/share/edit-session 和 module RBAC 聚焦回归 `46 passed`；迁移文件 Ruff 通过，`report_service.py` 与 `v0.3.8` blob `3676f94b589600e55b9ec6b3ba3c4c15628e87d6` 字节级一致。首次运行暴露新增企业测试 helper 仍手工构造上游 service，改为企业子类后同组测试全部通过。

### 2026-07-25：MCP service 归位

处理方式：把只服务于下游 MCP server update 和删除前 Agent 引用检查的逻辑迁入新增 `datus_enterprise.services.mcp_service.EnterpriseMCPService`，上游 `MCPService` 继续负责不变的配置文件管理、server CRUD、连通性、工具调用和过滤。已经属于 core hook 的 `DatusService.mcp` 统一构造企业子类，企业 MCP router 的调用契约保持不变；引用存储不可用时仍拒绝删除，未削弱 fail-closed 边界。上游 `datus/api/services/mcp_service.py` 已恢复为 `v0.3.8` 原内容。

同时审计了 7 个较小 `test-only` 候选。它们均修改了必要的上游原断言，包括企业扩展 fixture、异步 session 写入、stream owner、reasoning/response 分类、storage read path 和 connector dialect，因此没有为了减少数字而增加生产兼容回退。

数字变化：modified 由 108 降到 107，其中 production/package 由 75 降到 74；新增 enterprise services package 和 MCP service 子类使 added 由 198 增至 200。tests 保持 29 modified，deleted 保持 4，总差异文件由 310 增至 311。

验证：上游 MCP service、下游 update/Agent 引用保护、`DatusService.mcp` 工厂、MCP module/fine-grained RBAC、platform readonly 和 route security 行为组合回归 `83 passed`；迁移文件 Ruff 通过，`mcp_service.py` 与 `v0.3.8` blob `5f939fa5a7f93e8ffcaf1248dcea910ea7aa2b45` 字节级一致。首次包含无关 datasource/explorer lazy property 的大组合测试在已知 LanceDB 后台初始化处超时，随后按 MCP 边界拆分重跑并全部通过。

### 2026-07-25：CLI route 归位

处理方式：新增 `datus_enterprise.api.cli_routes` 作为 `/api/v1/sql/*`、`/api/v1/context/*` 和 `/api/v1/internal/*` 的唯一权威实现。企业 router 继续在 service resolution 前执行 SQL executor、datasource catalog 和 chat module RBAC；SQL 执行保留 platform status、request-scoped datasource/database projection、quota、user-owned task 和脱敏 audit，context/internal metadata 命令继续传入投影后配置。由于这些下游执行参数不在上游 handler 签名中，企业 router 直接调用扩展后的 CLI service，没有引入仅为形式委托的 adapter。上游 `datus/api/routes/cli_routes.py` 已恢复为 `v0.3.8` 原内容。

数字变化：modified 由 109 降到 108，其中 production/package 由 76 降到 75；新增企业 CLI router 使 added 由 197 增至 198。tests 保持 29 modified，deleted 保持 4，总差异文件保持 310。

验证：SQL/CLI/context/internal 相关 route 与 RBAC `46 passed`，CLI service、企业 MVP smoke 和 route security matrix `104 passed`；迁移文件 Ruff 通过，`cli_routes.py` 与 `v0.3.8` blob `6f4a75fad12fa9ce7ebc0f437cb67b7b2ab34229` 字节级一致。一次包含无关 chat TestClient 的大组合运行出现环境性停滞，已主动中止并按受影响边界拆分重跑，不影响上述通过结果。

### 2026-07-25：Table route 归位

处理方式：新增 `datus_enterprise.api.table_routes` 作为 `/api/v1/table/detail` 和 `/api/v1/semantic_model*` 的唯一权威实现。企业 wrapper 先完成 datasource catalog/config-edit RBAC、request-scoped datasource projection、dialect-aware table scope 授权、拒绝审计和 semantic-model save 的 platform status gate，然后通过请求级 `DatasourceService` 委托上游 handler 执行 table schema 与 semantic-model read/save/validate。迁移没有改写共享 `svc.agent_config`，显式 datasource 请求继续使用投影后的独立 service。上游 `datus/api/routes/table_routes.py` 已恢复为 `v0.3.8` 原内容。

数字变化：modified 由 110 降到 109，其中 production/package 由 77 降到 76；新增企业 Table wrapper 使 added 由 196 增至 197。tests 保持 29 modified，deleted 保持 4，总差异文件保持 310。

验证：Table/Semantic Model 企业 route、module RBAC、datasource projection、table scope、audit failure fail-closed、readonly platform status、唯一注册以及 route security matrix 组合回归 `158 passed`；迁移文件 Ruff 通过，`table_routes.py` 与 `v0.3.8` blob `6c85ee9bc5650b46b0f447cbab066af731054b24` 字节级一致。

### 2026-07-25：MCP route 归位

处理方式：新增 `datus_enterprise.api.mcp_routes` 作为 `/api/v1/mcp*` 的唯一权威实现。企业 wrapper 在解析 `DatusService` 前完成 module RBAC、细粒度 MCP server/tool/filter 授权与 platform status gate，然后委托上游 handler 执行 list/add/connectivity/tools/call/filter 操作。只有下游新增的 server update 和带 Agent 引用检查的 remove 保留直接 service 调用；客户端 `apply_filter=false` 仍无法绕过服务端工具过滤。上游 `datus/api/routes/mcp_routes.py` 已恢复为 `v0.3.8` 原内容。

数字变化：modified 由 111 降到 110，其中 production/package 由 78 降到 77；新增企业 MCP wrapper 使 added 由 195 增至 196。tests 保持 29 modified，deleted 保持 4，总差异文件保持 310。

验证：MCP module/fine-grained RBAC、拒绝先于 service resolution、platform readonly、Agent 引用冲突、服务端工具过滤、MCP service update 以及 route security matrix 组合回归 `75 passed`；迁移文件 Ruff 通过，`mcp_routes.py` 与 `v0.3.8` blob `a5345fea2ccae983e79354451551c03af3bd47dd` 字节级一致。

### 2026-07-25：Database route 与测试归位

处理方式：新增 `datus_enterprise.api.database_routes` 作为 `/api/v1/catalog/list|status|prewarm` 的唯一权威实现。企业 catalog wrapper 在调用前完成 module RBAC 和 request-scoped datasource projection，然后委托上游 `list_catalogs()` 处理 datasource I/O 及超时，最后按 datasource grant 裁剪 catalog/table 结果；下游没有复制上游的查询实现。缓存状态读取和平台状态保护的 prewarm 继续保留在企业 router。上游 `datus/api/routes/database_routes.py` 及其原测试已恢复为 `v0.3.8` 原内容，下游 delegation、grant pruning、status/prewarm 和唯一注册覆盖迁入新测试文件。

数字变化：modified 由 113 降到 111，其中 production/package 由 79 降到 78、tests 由 30 降到 29；新增企业 Database router 和下游测试使 added 由 193 增至 195。deleted 保持 4，总差异文件保持 310。

验证：上游 route 原测试、企业 wrapper 测试、module RBAC/datasource projection、企业 MVP smoke 和 route security matrix 组合回归 `159 passed`；迁移文件 Ruff 通过。`database_routes.py` 与 `v0.3.8` blob `987f2ee30871b16afa9e1e3c49ef3b7b092ac0d0` 字节级一致，原测试 blob `de0291f184131d46cf7491625a142c3170acf701` 也字节级一致。

### 2026-07-25：Legacy Agent route 归位

处理方式：新增 `datus_enterprise.api.legacy_agent_routes` 作为旧 `/api/v1/agent*` 本地兼容路径的唯一权威实现。下游 wrapper 仅声明已有的结构化 response models，并委托对应上游 handler；没有复制 `AgentService` 或 Agent 配置逻辑。`create_app()` 的注册名保持为 `agent`，因此 `enterprise.enabled=true` 时仍由 `agent.config_legacy` 禁用并审计旧路径；正式企业 Agent API 继续由 `datus_enterprise.api.agent_routes` 的 `/api/v1/agents*` 路径承载。上游 `datus/api/routes/agent_routes.py` 已恢复为 `v0.3.8` 原内容。

数字变化：modified 由 114 降到 113，其中 production/package 由 80 降到 79；新增企业 Legacy Agent wrapper 使 added 由 192 增至 193，其中 production/package 由 60 增至 61。deleted 保持 4，总差异文件保持 310。

验证：AgentService、上游 handler delegation、legacy route enterprise-disabled gate、企业 Agent ACL/tool policy/default Agent/admin routes 以及 route security matrix 组合回归 `198 passed`；迁移文件 Ruff 通过，`agent_routes.py` 与 `v0.3.8` blob `8c78652b45aa533766144e1a11691a84a1747cd9` 字节级一致。

### 2026-07-25：Models route 归位

处理方式：新增 `datus_enterprise.api.models_routes` 作为 `/api/v1/models` 的唯一权威实现，`create_app()` 不再直接注册上游 router。下游 wrapper 调用上游 `list_models()` 生成 provider/custom model catalog，只在返回边界补充 chat/embedding capability、重算可用 current model，并应用 `module.config.view|module.chat` RBAC 和服务端 model policy 过滤；没有复制上游 catalog、cache、pricing 或 `model_specs` 解析逻辑。上游 `datus/api/routes/models_routes.py` 已恢复为 `v0.3.8` 原内容。

数字变化：modified 由 115 降到 114，其中 production/package 由 81 降到 80；新增企业 Models wrapper 使 added 由 191 增至 192，其中 production/package 由 59 增至 60。deleted 保持 4，总差异文件保持 310。

验证：22 项上游原 catalog 测试、6 项下游唯一注册/RBAC/model-policy/capability 测试以及 11 项 route security matrix 测试合计 `39 passed`；迁移文件 Ruff 通过，`models_routes.py` 与 `v0.3.8` blob 字节级一致。

### 2026-07-25：Success Story route 归位

处理方式：新增 `datus_enterprise.api.success_story_routes` 作为 `/api/v1/success-stories` 的唯一权威实现，`create_app()` 不再注册旧上游 handler。下游实现继续从 canonical session history 解析成功 SQL，依次保留 module KB RBAC、platform active、session owner、只读 SQL、幂等持久化、安全错误信息和脱敏 audit 边界；上游 `datus/api/routes/success_story_routes.py` 已恢复为 `v0.3.8` 原内容。

数字变化：modified 由 116 降到 115，其中 production/package 由 82 降到 81；新增企业 Success Story router 使 added 由 190 增至 191，其中 production/package 由 58 增至 59。deleted 保持 4，总差异文件保持 310。

验证：唯一 app 注册、canonical source、session owner、只读 SQL、持久化、CSV 安全、audit 和 route security matrix 组合回归 `33 passed`；迁移文件 Ruff 通过，`success_story_routes.py` 与 `v0.3.8` blob 字节级一致。原上游 route 测试没有机械恢复：它依赖已被新持久化契约移除的 `SubagentNotFoundError`，为恢复测试而向生产 service 添加旧 API fallback 会扩大核心差异，因此当前下游安全契约测试继续作为 `test-only` 保留。

### 2026-07-25：Dashboard route 归位

处理方式：新增 `datus_enterprise.api.dashboard_routes` 作为 `/api/v1/dashboard/detail`、`/api/v1/dashboard/query` 和 `/api/v1/dashboards/{slug}/edit-sessions` 的唯一权威实现，`create_app()` 不再注册未保护的上游 Dashboard router。详情读取在 module RBAC 和 Artifact ACL 后复用上游 handler；编辑会话继续保留 platform active、edit permission、owner/admin 和锁定 subagent 边界；实时查询继续保留 Artifact ACL、请求级 datasource projection、模板 datasource 再投影、执行前 quota 和安全审计。上游 `datus/api/routes/dashboard_routes.py` 已恢复为 `v0.3.8` 原内容。

数字变化：modified 由 117 降到 116，其中 production/package 由 83 降到 82；新增企业 Dashboard router 使 added 由 189 增至 190，其中 production/package 由 57 增至 58。deleted 保持 4，总差异文件保持 310。

验证：Dashboard route、module RBAC、Artifact ACL、request-scoped projection、quota、audit、platform status、app 唯一注册和 route security matrix 组合回归 `185 passed`；迁移文件 Ruff 通过，`dashboard_routes.py` 与 `v0.3.8` blob 字节级一致。

### 2026-07-25：上游差异护栏与 Report route 归位

处理方式：新增 `ci/harness/report_upstream_diff.py`，使用隔离临时 index 统计包含未跟踪文件的当前 `datus-agent` 工作树；`--target` 计算当前下游 modified 与新上游 release changed 的交集，`--check` 对照 `ci/harness/upstream-modified-allowlist.yml` 拒绝未登记增长和已经恢复上游的过期条目。当前 117 个 modified 已按 core hook、move-to-enterprise、upstreamable fix、docs/config/meta 和 test-only 五类登记。

同时把 `/api/v1/report/detail` 的 module RBAC、Artifact ACL 以及 `/api/v1/reports/{slug}/edit-sessions` 从上游原 `report_routes.py` 迁入新增的 `datus_enterprise.api.artifact_routes`。`create_app()` 不再注册未保护的上游 report router；企业 Artifact router 成为上述路径的唯一权威实现，并继续覆盖 platform status、edit 权限、owner/admin 判定和锁定 edit subagent。上游 `datus/api/routes/report_routes.py` 已恢复为 `v0.3.8` 原内容。

数字变化：新增报告器、allowlist 和单元测试使 added 由 186 增至 189；Report route 归位使 modified 由 118 降到 117，其中 production/package 由 84 降到 83。deleted 保持 4，总差异文件由 308 增至 310。新增文件分类为 57 个 production/package、103 个 tests、4 个 docs 和 25 个 config/meta。

验证：报告器临时 Git 仓库、overlap、allowlist 和机器可读 JSON 契约测试通过；当前真实工作树 `--check` 返回 `allowlist: ok (117 modified files)`。Artifact routes、app 注册、module RBAC、Artifact ACL、edit session 和 route security matrix 组合回归 `83 passed`；迁移文件 Ruff 与 `git diff --check` 通过，`report_routes.py` 与 `v0.3.8` blob 字节级一致。

### 2026-07-25：下游 API 测试归位第九轮

处理方式：继续把只覆盖下游请求契约和服务启动参数的断言迁出上游原测试文件。KB bootstrap 的必填 `datasource_id`、自动 trim、空白拒绝和 `refresh-profile` 组合测试归入独立模型测试；API graceful-shutdown 参数的默认值和三种 Uvicorn 启动模式透传测试归入独立 API 测试。`_run_server()` 在已经 modified 的启动模块内集中解析一次 graceful-shutdown 默认值，使上游测试和其他仍构造旧版 `argparse.Namespace` 的内部调用保持兼容；CLI 默认值和运行时透传语义不变。

本轮恢复为 `v0.3.8` 原内容的上游测试：

```text
tests/unit_tests/api/models/test_kb_models.py
tests/unit_tests/api/test_main.py
```

对应下游覆盖迁入：

```text
tests/unit_tests/api/models/test_kb_models_downstream.py
tests/unit_tests/api/test_main_downstream.py
```

`tests/unit_tests/api/services/test_kb_service.py` 没有机械恢复：当前服务为请求级 datasource 配置隔离向 `_run_component()` 传递 `config`，而上游 acceptance fake 仍使用旧签名；为减少一个 modified 增加生产兼容分支会扩大核心差异，因此保留现有测试适配和运行中取消覆盖。

数字变化：modified 由 120 降到 118，added 由 184 增至 186，deleted 保持 4；总差异文件保持 308。当前 modified 分类为 84 个 production/package、30 个 tests、0 个 docs 和 4 个 config/meta；新增文件分类为 57 个 production/package、102 个 tests、4 个 docs 和 23 个 config/meta。本轮同时修正了根级 `CLAUDE.md` 及新增文件的历史分类误差。

验证：两个恢复文件均与 `v0.3.8` blob 字节级一致；API main 原测试和新增 downstream 测试合计 `52 passed`。KB 模型、route/service、route security matrix 与 API main 的最终组合回归为 `170 passed`；迁移文件 Ruff 与 `git diff --check` 通过。

### 2026-07-25：下游 API 模型契约归位第二轮

处理方式：继续把只服务于下游 HTTP、企业投影和持久化 sidecar 的模型从上游原模块迁出。配置摘要、模型 capability、success-story canonical source、Agent 列表/详情/工具、SQL datasource、个人模型凭据、chat terminal/subagent event、KB upload 和 request-scoped bootstrap 契约分别归入新增模型模块；route/service 显式绑定下游类型，上游请求基类、公共枚举和未变化的事件模型继续复用。迁移没有新增、删除或改分类路由，也没有调整认证、RBAC、Agent ACL、datasource projection、session owner、Artifact ACL、platform status、quota 或 audit 决策。

本轮新增恢复为 `v0.3.8` 原内容的上游文件：

```text
datus/api/models/config_models.py
datus/api/models/success_story_models.py
datus/api/models/agent_models.py
datus/api/models/cli_models.py
datus/api/models/kb_models.py
```

对应下游契约归入：

```text
datus/api/models/downstream.py
datus/api/models/kb_downstream.py
```

数字变化：modified 由 125 降到 120，added 由 183 增至 184，deleted 保持 4；总差异文件由 312 降到 308。当前 modified 分类为 85 个 production/package、32 个 tests、0 个 docs 和 3 个 config/meta。

验证：上述 5 个恢复文件均与 `v0.3.8` blob 字节级一致；迁移前后的 24 个 Pydantic JSON Schema 稳定哈希逐项一致。配置/model catalog/success-story、个人模型凭据、个人 datasource 和 route security matrix 合并验证 `120 passed`；Agent/API/RBAC 组合 `344 passed`，CLI/chat/session 组合 `375 passed`，KB upload/bootstrap/SSE 组合 `117 passed`。迁移文件 Ruff 与 `git diff --check` 通过。

### 2026-07-25：下游 API 模型与维护文档归位

处理方式：把只服务于下游 route/service 的 Artifact edit session、datasource status/prewarm 和 MCP update 请求模型集中到新增 `datus/api/models/downstream.py`；semantic model 的 `datasource_id` 只在请求投影阶段使用，因此改由已经 modified 的 `table_routes.py` 定义同名请求子类。仓库内没有调用方依赖 `datus.api.models` 对下游新增模型的顶层 re-export，因此同时恢复该上游聚合模块。类名、字段和 OpenAPI 请求/响应契约保持不变，企业认证、RBAC、datasource projection、Artifact ACL、platform status 和 audit 链没有调整。

本轮恢复为 `v0.3.8` 原内容的上游文件：

```text
README.md
datus/api/models/__init__.py
datus/api/models/table_models.py
datus/api/models/dashboard_models.py
datus/api/models/report_models.py
datus/api/models/database_models.py
datus/api/models/mcp_models.py
```

对应下游内容归入：

```text
datus/api/models/downstream.py
datus/api/routes/table_routes.py
docs/downstream-maintenance.zh-CN.md
AGENTS.md
```

根 `README.md` 中的 monorepo adapter 扩展列表迁到新增下游维护文档，公开 README 恢复上游内容。`BUILD.md` 曾尝试精确恢复，但上游 `v0.3.8` 文件自身包含尾随空格，会使当前提交触发 `git diff --check`；因此本轮保留现有 `BUILD.md`，不为减少一个 modified 引入确定的 whitespace 失败。

数字变化：相对第六轮基线，modified 由 132 降到 125，其中 production/package 由 95 降到 89、config/meta 由 5 降到 4，tests 保持 32、docs 保持 0；added 由 181 增至 183；deleted 保持 4。总差异文件由 317 降到 312。

验证：上述 7 个恢复文件均与 `v0.3.8` blob 字节级一致；迁移相关 Ruff 和 `git diff --check` 通过。semantic model 投影、datasource status/prewarm、MCP update、report/dashboard edit session 及 route security matrix 聚焦测试合计 `335 passed`。

### 2026-07-24：无行为差异恢复与测试迁移第六轮

处理方式：恢复冗余声明、重复注释和重复 acceptance 说明；继续把只承载下游回归的测试迁入独立 `_downstream.py` 文件。BIRD 最小 acceptance fixture 从上游根 `tests/conftest.py` 迁入新增模块，引用它的两个既有 integration 文件只调整导入路径。OceanBase Oracle 发布与真实租户指南迁入 `datus_enterprise/docs/`，从而恢复上游 `ci/harness/coverage-map.yml`。DashboardService 原测试不能完全恢复，因为当前生产代码要求 fake connector 提供 `dialect`；原文件仅保留两行必要测试兼容，其余下游测试已迁出。

本轮恢复为 `v0.3.8` 原内容的上游文件：

```text
datus/agent/node/base_artifact_ask_agentic_node.py
conf/providers.yml
datus/conf/providers.yml
ci/harness/coverage-map.yml
tests/integration/adapters/README.md
tests/conftest.py
tests/unit_tests/tools/db_tools/test_db_func_tools.py
tests/unit_tests/tools/func_tool/test_database.py
tests/unit_tests/tools/func_tool/test_sub_agent_task_tool.py
tests/unit_tests/api/routes/test_models_routes.py
tests/unit_tests/configuration/test_agent_config.py
tests/unit_tests/api/test_service_app.py
tests/unit_tests/api/services/test_action_sse_converter.py
```

对应下游覆盖迁入：

```text
tests/downstream_acceptance_fixtures.py
tests/unit_tests/tools/db_tools/test_db_func_tools_downstream.py
tests/unit_tests/tools/func_tool/test_database_downstream.py
tests/unit_tests/tools/func_tool/test_sub_agent_task_tool_downstream.py
tests/unit_tests/api/routes/test_models_routes_downstream.py
tests/unit_tests/api/services/test_dashboard_service_downstream.py
tests/unit_tests/configuration/test_agent_config_downstream.py
tests/unit_tests/api/test_service_app_downstream.py
tests/unit_tests/api/services/test_action_sse_converter_downstream.py
```

数字变化：相对第五轮基线，modified 由 145 降到 132，其中 production/package 由 97 降到 95、tests 由 41 降到 32、config/meta 由 7 降到 5；added 由 172 增至 181；deleted 保持 4。总差异文件由 321 降到 317。

验证：13 个恢复文件均与 `v0.3.8` 字节级一致；DashboardService 原测试另外仅保留两行 fake connector `dialect`。上游 `create-skill/SKILL.md` 自身带有额外 EOF 空行，精确恢复会触发 `git diff --check`，因此保留规范化结尾而不为数字引入 whitespace 错误。迁移文件的 Ruff、`git diff --check` 和 coverage map strict validation 均通过；上游原测试和新增 downstream 测试合计 `949 passed`。BIRD fixture 集成测试在仓库目录首次被本地 `.datus/config.yml` 的 `default_datasource=datus_enterprise` 覆盖；从 `/tmp` 隔离目录重跑后通过配置加载并进入初始化，但阻塞于当前环境已知的 LanceDB 初始化路径，已中止且未误报为通过。

### 2026-07-24：测试迁移第五轮

处理方式：继续把只承载下游回归覆盖的测试从上游原测试文件迁到独立 `_downstream.py` 文件。对 proxy timeout 保留上游可 monkeypatch 的 `DEFAULT_RESULT_TIMEOUT` 兼容入口，同时保留下游显式 `timeout_seconds` 参数；对应上游测试恢复为 `v0.3.8`，精确超时断言迁入新增文件。未恢复会削弱 fail-closed、ACL、liveness、bundled renderer、路由签名或数据模型必填边界的原测试。

本轮新增恢复为 `v0.3.8` 原内容的上游测试：

```text
tests/unit_tests/api/services/test_mcp_service.py
tests/unit_tests/models/test_codex_model.py
tests/unit_tests/test_main.py
tests/unit_tests/tools/db_tools/test_db_manager.py
tests/unit_tests/agent/node/test_agentic_node.py
tests/unit_tests/tools/func_tool/test_filesystem_tools.py
tests/unit_tests/tools/func_tool/test_semantic_tools.py
tests/unit_tests/agent/node/test_gen_visual_report_agentic_node.py
tests/unit_tests/agent/node/test_gen_visual_dashboard_agentic_node.py
tests/unit_tests/tools/proxy/test_proxy_tool.py
tests/unit_tests/storage/test_subject_tree_store.py
tests/unit_tests/storage/schema_metadata/test_store.py
tests/unit_tests/tools/permission/test_permission_hooks.py
tests/unit_tests/storage/test_embedding_openai.py
tests/unit_tests/agent/node/test_chat_agentic_node.py
```

对应下游测试迁入：

```text
tests/unit_tests/api/services/test_mcp_service_enterprise_downstream.py
tests/unit_tests/models/test_codex_model_downstream.py
tests/unit_tests/test_main_downstream.py
tests/unit_tests/tools/db_tools/test_db_manager_downstream.py
tests/unit_tests/agent/node/test_agentic_node_downstream.py
tests/unit_tests/tools/func_tool/test_filesystem_tools_downstream.py
tests/unit_tests/tools/func_tool/test_semantic_tools_downstream.py
tests/unit_tests/agent/node/test_gen_visual_report_agentic_node_downstream.py
tests/unit_tests/agent/node/test_gen_visual_dashboard_agentic_node_downstream.py
tests/unit_tests/tools/proxy/test_proxy_tool_downstream.py
tests/unit_tests/storage/test_subject_tree_store_downstream.py
tests/unit_tests/storage/schema_metadata/test_store_downstream.py
tests/unit_tests/tools/permission/test_permission_hooks_downstream.py
tests/unit_tests/storage/test_embedding_openai_downstream.py
tests/unit_tests/agent/node/test_chat_agentic_node_downstream.py
```

数字变化：相对上一轮基线，modified 由 160 降到 145，其中 tests 由 56 降到 41；added 因新增 15 个独立测试文件由 157 增至 172；总差异文件仍为 321，deleted 保持 4。

验证：各迁移批次的 Ruff 均通过；已完成的定向 pytest 分别为 `173 passed`、`49 passed`、`208 passed`、`121 passed`、`53 passed`、`41 passed`、`284 passed` 和 `21 passed`。ChatAgenticNode 原文件与新增文件的 Ruff 通过且原文件字节级一致，但当前环境在节点初始化时阻塞于 LanceDB 后台路径；既有首测与新增首测均可复现，使用 30 秒单测超时确认后中止，未把环境阻塞误报为通过。

### 2026-07-24：公开文档恢复与测试迁移第三、四轮

处理方式：把知识库 bootstrap、datasource-isolated success story、metadata embedding 限制、MetricFlow/OceanBase Oracle 边界等下游说明集中到 `docs/downstream-enterprise-notes.zh-CN.md`，并恢复 10 个上游公开文档。继续把 7 组纯下游新增测试迁到独立的 `_downstream.py` 文件；原测试文件均与 `v0.3.8` 字节级一致，生产代码和运行行为未改动。

已恢复为 `v0.3.8` 原内容的上游文档：

```text
docs/API/knowledge_base.md
docs/API/knowledge_base.zh.md
docs/adapters/metricflow_semantic_adapter.md
docs/adapters/metricflow_semantic_adapter.zh.md
docs/configuration/storage.md
docs/configuration/storage.zh.md
docs/metricflow/introduction.md
docs/metricflow/introduction.zh.md
docs/web_chatbot/introduction.md
docs/web_chatbot/introduction.zh.md
```

已恢复为 `v0.3.8` 原内容的上游测试：

```text
tests/unit_tests/api/auth/test_loader.py
tests/unit_tests/api/services/test_agent_service.py
tests/unit_tests/api/services/test_report_service.py
tests/unit_tests/configuration/test_agent_config_loader.py
tests/unit_tests/agent/node/test_gen_semantic_model_agentic_node.py
tests/unit_tests/agent/node/test_gen_sql_agentic_node.py
tests/unit_tests/prompts/test_prompt_manager.py
```

下游测试迁入：

```text
tests/unit_tests/api/auth/test_loader_downstream.py
tests/unit_tests/api/services/test_agent_service_downstream.py
tests/unit_tests/api/services/test_report_service_downstream.py
tests/unit_tests/configuration/test_agent_config_loader_downstream.py
tests/unit_tests/agent/node/test_gen_semantic_model_agentic_node_downstream.py
tests/unit_tests/agent/node/test_gen_sql_agentic_node_downstream.py
tests/unit_tests/prompts/test_prompt_manager_downstream.py
```

数字变化：相对上一轮基线，总差异文件由 331 降到 321；modified 由 177 降到 160，其中 tests 由 63 降到 56、docs 由真实的 10 降到 0；added 因新增 7 个独立测试文件由 150 增至 157；deleted 保持 4。两批定向 Ruff 均通过；第一批原文件与下游文件合计 `240 passed`，第二批合计 `200 passed, 1 skipped`。

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
datus/api/services/chat_service.py
datus/api/services/kb_service.py
datus/tools/db_tools/db_manager.py
```

保留理由：

- `create_app()` 和 lifespan 需要加载企业扩展、注册企业路由、关闭企业存储资源。
- 请求上下文需要在 service 初始化前完成认证、企业用户状态检查、角色/权限/数据源授权刷新。
- 企业模式需要 request-scoped config projection，不能把用户授权状态写回共享 `DatusService.agent_config`。
- PostgreSQL/OceanBase session body store 需要挂入原 session 管理和 streaming 路径。
- 数据源/connector 入口需要承接企业授权和多库枚举等执行侧限制。

### 已完成主体归位的稳定核心 hook

以下文件曾是 `move-to-enterprise` 候选，现已完成逐 hunk 收敛并归入 `core-hook`。当前 allowlist 的 `move-to-enterprise` 为空；后续不为减少 modified 数字整体复制 route/service 状态机，只在发现可独立验证且能降低三方冲突面的新主体时继续迁移。

```text
datus/api/routes/chat_routes.py
datus/api/services/chat_task_manager.py
datus/api/services/cli_service.py
datus/api/services/dashboard_service.py
datus/api/services/database_service.py
```

当前停止线：

- Chat route 只保留认证后的 Agent/Artifact/session/datasource 安全调用顺序、请求级 projection 和 SSE dispatch；Agent materialization、model/quota/audit/permission-mode 策略主体已进入 added 模块。
- ChatTaskManager 只保留 task/SSE/node 状态所有权、owner/admission、request-config 与 terminal persistence 调用点；workspace/config/sidecar 实现已进入 added runtime。
- CLIService 的 connector cleanup、SQL task owner 和 execute/context/internal command 前置 policy hook 与上游主状态机不可拆；静态 SQL/datasource 策略主体已进入 added 模块。
- DashboardService 只保留 query 状态机中的 request-scoped config、quota 和 SQL authorization hook；DatabaseService 只保留共享 manager、lazy connector、目录扩展与 status callback hook。
- 新增企业执行面继续优先建在 `datus_enterprise/api/`；同路径覆盖通过应用 route projection 维护，不在多个上游 handler 中堆条件。

### 通用修复或上游化候选

这些修改看起来不专属于企业模式。后续应拆成小 commit，评估是否可以贡献给上游；如果不能贡献，也要和企业补丁分开维护。

```text
datus/tools/proxy/proxy_tool.py
datus/tools/proxy/tool_result_channel.py
datus/utils/csv_utils.py
datus/api/services/action_sse_converter.py
datus/api/services/agent_service.py
datus/api/services/explorer_service.py
datus/tools/mcp_tools/mcp_config.py
datus/tools/mcp_tools/mcp_manager.py
datus/tools/func_tool/database.py
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

当前 modified 基线记录在：

```text
ci/harness/upstream-modified-allowlist.yml
```

报告器使用隔离临时 index 构造当前 `datus-agent` 工作树，不会修改真实 Git index。日常收敛后运行：

```bash
uv run python ci/harness/report_upstream_diff.py --base v0.3.8 --check
```

准备升级新 release 时，同时提供新上游 tag，报告器会列出“当前下游 modified”与“新上游 changed”的交集：

```bash
uv run python ci/harness/report_upstream_diff.py \
  --base v0.3.8 \
  --target v0.3.9 \
  --check
```

需要机器可读结果时增加 `--json`。`--check` 出现未登记 modified 或 allowlist 中已经恢复上游的过期路径时应失败；只有在完成行为、测试和移除条件审查后才能更新 allowlist。

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
