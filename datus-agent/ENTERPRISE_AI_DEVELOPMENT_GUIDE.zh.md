# 企业内网平台化 AI 开发规范

本文是后续 AI agent 或开发者在本下游 fork 中实现企业内网平台化能力时必须遵循的工作标准。目标不是重复 `AGENTS.md` 的通用工程规则，而是把单租户、多用户、RBAC + 数据权限改造的安全边界、接口组织、API 组织、测试要求和文档更新要求固化下来。

相关规划文档：

- `ENTERPRISE_PLATFORM_PLAN.zh.md`：企业内网平台化总体开发计划。
- `AGENTS.md`：本 checkout 的通用工程、Git、测试和代码约束。

## 总目标

本项目的企业级改造目标是让 Datus Agent 从本地 agent/API 服务演进为企业内网单租户、多用户、RBAC + 数据权限平台。企业上下文来自部署配置，不作为业务 API 参数，也不作为基础 metadata 表的分区字段。

- 身份边界：谁在请求，是否属于当前企业上下文，是否允许调用 API。
- 资源边界：谁能访问哪些模块、数据源、会话、知识库、报表和仪表盘。
- 执行边界：SQL、LLM、MCP、文件系统、BI 查询等执行能力是否受控。
- 审计边界：关键 allow/deny、管理操作和执行决策是否可追踪。
- 运维边界：多 worker、滚动发布、状态外部化和企业级恢复是否有明确路径。

任何实现都必须服务这些边界。不要只实现前端可见性或 route 层简单判断后宣称完成企业 RBAC 或数据权限。

## 工作前检查

在开始企业级相关改造前，先完成以下检查：

1. 阅读 `ENTERPRISE_PLATFORM_PLAN.zh.md` 中对应章节。
2. 用 `rg` 找到当前真实入口，不凭印象修改：
   - 认证：`datus/api/auth/`
   - dependency：`datus/api/deps.py`
   - chat route：`datus/api/routes/chat_routes.py`
   - service cache：`datus/api/services/datus_service_cache.py`
   - task manager：`datus/api/services/chat_task_manager.py`
   - session：`datus/models/session_manager.py`
   - SQL policy：`datus/tools/sql_policy.py`
   - DB tool：`datus/tools/func_tool/database.py`
3. 确认本次变更属于哪一层：
   - `AuthProvider`
   - `AuthorizationProvider`
   - `ConfigProjector`
   - owner metadata store
   - route dependency
   - execution policy
   - audit/quota
   - admin API
4. 先写清楚验收断言，再改代码。

## 阶段与任务边界

企业内网能力必须按 `ENTERPRISE_PLATFORM_PLAN.zh.md` 的阶段推进。开始改代码前，先声明本次任务属于哪个阶段，以及明确非目标。

阶段边界：

- 阶段 0：只建立开关、兼容基线、provider fail closed 语义和最小测试 fixture。
- 阶段 1：认证、`AppContext` 扩展、RBAC 数据加载、enterprise-aware service cache。
- 阶段 2：运行中 task owner、磁盘 session scope、`session_owners` 索引。
- 阶段 3：模块 RBAC dependency 和 route/subagent 接入。
- 阶段 4：datasource grant、catalog 过滤、请求级 `AgentConfig` projection。
- 阶段 5：SQL policy principal、dashboard/report/direct SQL 兜底、审计。
- 阶段 6：用户、角色、权限、数据源授权、产物 ACL、审计查询等 admin API。

约束：

- 不要用后续阶段的大型基础设施掩盖当前阶段硬边界未完成的问题。
- 不要在阶段 0/1 引入与企业内部员工数据服务无关的运营售卖能力，也不要提前引入审批流、SCIM、列级权限。
- 如果任务跨阶段，必须说明最小可交付切片和各阶段验收断言。
- 若暂时只接入某类 route，最终说明必须列出尚未接入的 route，并说明它们是否 fail closed。
- 修改安全边界时，先补正反例测试 fixture，再实现业务路径。

企业开关语义：

- `enterprise.enabled=false` 只表示本地/开源兼容模式；允许 `NoAuthProvider`，但不得把该行为带入生产企业模式。
- `enterprise.enabled=true` 时必须启用生产 auth provider、RBAC store、AuthorizationProvider、ConfigProjector 和 AuditSink，缺任一关键接线都必须 fail closed 或在启动时失败。
- 生产企业模式不得信任裸 `X-Datus-User-Id`、前端传入的 roles、permissions、principal 或企业上下文字段。
- 企业开关不引入 `tenant_id`，也不允许把企业上下文当作业务 API 参数由客户端提交。

## 架构约束

### 主包与企业包边界

主包 `datus/` 只放稳定协议、默认实现和薄接线。企业实现放在下游扩展包，例如 `datus_enterprise/`。

允许放在主包：

- `Protocol`、dataclass、Pydantic schema。
- no-op 默认实现。
- FastAPI dependency helper。
- provider loader。
- 与当前开源行为兼容的薄接线。

优先放在企业包：

- JWT/OIDC provider 具体实现。
- RBAC store/service。
- datasource grant 合并逻辑。
- admin API。
- audit sink。
- quota limiter。
- Postgres/Redis/object storage 集成。

### 请求安全链

实现必须按以下链路思考：

```text
Authenticate -> Build Context -> Authorize -> Project Config -> Execute -> Audit
```

不要跳过中间层：

- 不要让 `AuthProvider` 同时承担所有授权、投影、审计和 quota。
- 不要把 RBAC 判断散进每个 route 的 if/else。
- 不要让 `ChatHooks.pre_chat()` 成为核心安全接口。
- 不要直接信任 request body 或普通 header 提供的 permissions、roles、principal 或企业上下文字段。
- 不要在共享 `DatusService.agent_config` 上写用户级状态。

### Fail closed

生产企业模式必须 fail closed：

- 缺少 `user_id`：拒绝。
- 缺少模块 permission：拒绝。
- 缺少 datasource grant：拒绝。
- 缺少 SQL policy 必需 principal：拒绝。
- session owner 不匹配：拒绝或返回统一 not found。
- artifact ACL 不匹配：拒绝或返回统一 not found。

本地 `NoAuthProvider` 兼容模式可以继续匿名友好，但不得把该行为带入生产 provider。

## API 规范

普通业务 API 不在路径里传企业上下文字段。企业上下文来自部署配置和认证后的用户身份。

推荐分区：

```text
/api/v1/me/*
/api/v1/chat/*
/api/v1/datasources/*
/api/v1/sql/*
/api/v1/reports/*
/api/v1/dashboards/*
/api/v1/kb/*
/api/v1/mcp/*
/api/v1/admin/*
/api/v1/system/*
/api/v1/internal/*
```

约束：

- `/me` 只返回当前用户可见能力，不做管理操作。
- `/admin` 只管理当前企业上下文，使用 `module.admin.*` 显式权限。
- `/system` 只面向系统内部和部署运维，不给普通浏览器前端使用。
- `/internal` 使用独立服务认证，不复用普通用户 JWT。
- `view`、`query`、`export` 权限分开，不要让 view 自动包含实时查询或导出。
- 现有旧 API 可保留兼容层，新企业 API 使用更清晰的资源命名。

错误响应继续兼容 `Result[T]`，但错误码要稳定。优先使用：

```text
AUTH_REQUIRED
ENTERPRISE_DISABLED
USER_DISABLED
PERMISSION_DENIED
DATASOURCE_FORBIDDEN
SESSION_FORBIDDEN
ARTIFACT_FORBIDDEN
QUOTA_EXCEEDED
POLICY_DENIED
APPROVAL_REQUIRED
RESOURCE_NOT_FOUND
```

### 权限 key

权限 key 必须使用稳定字符串，不直接绑定 URL。新增 key 前先检查 `ENTERPRISE_PLATFORM_PLAN.zh.md` 的 RBAC 权限模型，优先复用已有 key。

当前基础和预留 key：

```text
module.chat
module.sql_executor
module.datasource_catalog
module.report.view
module.report.query
module.report.export
module.dashboard.view
module.dashboard.query
module.dashboard.export
module.kb
module.mcp
module.config.view
module.config.edit
module.admin.users
module.admin.roles
module.admin.datasources
module.admin.sessions
module.admin.artifacts
module.admin.audit
module.admin.audit.export
module.admin.quotas
module.admin.secrets
```

规则：

- `view` 只表示列表、详情或静态 HTML 可见，不自动包含实时查询、导出、编辑或授权管理。
- `query` 表示实时查数或执行保存 SQL；它必须叠加 datasource grant 和 SQL policy。
- `export` 必须单独授权，并接入 artifact/datasource 权限、审计和结果脱敏策略。
- `admin` 也必须拆成显式 permission；不要用硬编码超级用户绕过授权链。
- 新增 permission key 必须同步更新计划文档、测试 fixture 和 `/me` 能力返回。
- 允许 role template 或 glob 作为管理便利，但运行时检查应落到稳定 permission key。

## 接口实现规范

### AuthorizationProvider

所有模块、session、artifact、datasource 访问都应走统一授权接口或 dependency。不要在业务代码里写角色名判断。

当前骨架位置：

- 协议和数据结构位于 `datus/api/enterprise/`。
- 本地兼容默认实现位于 `datus/api/enterprise/defaults.py`，缺少权限列表时允许访问；一旦 `AppContext.permissions` 或兼容的 `principal.permissions` 存在，就按稳定 permission key 或 glob 判断。
- 生产企业模式通过 `enterprise.authorization_provider.class` 动态加载实现；`enterprise.enabled=true` 且缺失该 provider 时启动失败，不降级为 allow。
- `enterprise.config_projector.class` 在阶段 1 只是可加载扩展点，未配置时使用 passthrough skeleton；不要在 `get_datus_service()` 中把用户级 projection 写入 project 级缓存。Datasource grant 与 request-level projection 的真实执行接入属于阶段 4。

正确方向：

```python
decision = await authz.check(
    ctx,
    action="module.dashboard.query",
    resource=ResourceRef(type="dashboard", id=slug),
)
```

避免：

```python
if "enterprise_admin" in ctx.roles:
    ...
```

管理员能力也必须由 permission 表达，例如 `module.admin.sessions`。

### ConfigProjector

所有请求级 datasource、principal、tool 限制都应通过 config projection 生成 clone。

必须保证：

- 不修改缓存里的 `DatusService.agent_config`。
- 未授权 datasource 从 clone 中删除。
- `request.datasource` 未授权时拒绝。
- principal 由服务端构造，不由前端覆盖。
- dashboard/report/direct SQL 与 chat 使用同一投影逻辑。

### Datasource Grant

MVP 中 `datasource_grants` 采用每个 `(subject_type, subject_id, datasource_key)` 一条记录，细粒度 scope 写入 `scope_json`。实现 admin API 时必须使用 upsert，不能为同一主体和数据源写出多条语义可能冲突的 grant。

合并和冲突处理必须稳定：

- role grants 先合并，user grants 后合并。
- 显式 `deny` 优先于 `allow`。
- 宽范围 allow 与窄范围 deny 同时命中时，窄范围 deny 生效。
- 宽范围 deny 与窄范围 allow 同时命中时，除非 `scope_json` 明确支持例外白名单，否则 deny 生效。
- 保存 grant 前校验 subject、datasource key、scope schema 和 effect；语义不明确时拒绝保存并写审计。

### Session Owner

运行中 task 和磁盘 session 都必须有 owner 校验。

必须覆盖：

- `chat/resume`
- `chat/stop`
- `chat/user_interaction`
- `chat/insert`
- `chat/tool_result`
- `chat/history`
- `chat/sessions/{session_id}` delete/compact

管理员跨用户操作必须要求 `module.admin.sessions`，且只能在当前企业上下文内。

当前阶段 2 主包接线已覆盖上述 chat/session 路径。后续继续扩展时，不要绕过 `SessionOwnerStore` 和 route owner helper；多 worker 或滚动发布场景应使用共享 metadata store 替换默认 SQLite/内存骨架，并明确 sticky session 或 SSE event buffer 外部化策略。

### Module RBAC

当前阶段 3 主包接线已覆盖：

- chat route：统一使用 `module.chat`。
- chat subagent dispatch：`gen_sql` 使用 `module.sql_executor`，report 类 subagent 使用 `module.report.query`，dashboard 类 subagent 使用 `module.dashboard.query`。
- datasource catalog route：`/api/v1/catalog/list` 使用 `module.datasource_catalog`。
- direct SQL executor route：`/api/v1/sql/execute` 和 `/api/v1/sql/stop_execute` 使用 `module.sql_executor`。
- report route：`/api/v1/report/detail`、`/api/v1/reports`、`/api/v1/reports/{slug}` 和 `/api/v1/reports/{slug}/html` 使用 `module.report.view`。
- dashboard route：`/api/v1/dashboard/detail`、`/api/v1/dashboards`、`/api/v1/dashboards/{slug}` 和 `/api/v1/dashboards/{slug}/html` 使用 `module.dashboard.view`，`/api/v1/dashboard/query` 使用 `module.dashboard.query`。
- config route：`/api/v1/config/agent` 使用 `module.config.view`，配置更新和连接探测接口使用 `module.config.edit`。
- KB route：KB bootstrap、platform docs bootstrap 和 cancel 接口使用 `module.kb`。
- MCP route：MCP server/tool/filter 的列表、管理和调用接口使用 `module.mcp`。
- admin datasource route：`/api/v1/admin/datasource-default` 使用 `module.admin.datasources`。
- admin user route：`/api/v1/admin/users`、`/api/v1/admin/users/{user_id}`、`/api/v1/admin/users/{user_id}/disable` 和 `/api/v1/admin/users/{user_id}/enable` 使用 `module.admin.users`，用户管理变更写入脱敏审计摘要；企业模式新请求会基于 `EnterpriseUserStore` 拒绝已禁用用户。

后续新增 route 时应继续使用 `require_module()` dependency 接入模块权限；其余 admin roles/datasource grants/sessions/artifacts/audit/quotas/secrets API 属于阶段 6。不要把 report/dashboard 的 query 权限合并进 `module.chat`；自然语言入口只能证明用户可用 chat，不能自动证明用户可实时查询报表或仪表盘。当前已先将可配置 datasource grant projection 接入 `/api/v1/chat/stream`、`/api/v1/chat/feedback`、`/api/v1/catalog/list` 和 `/api/v1/sql/execute`，用于校验请求 datasource/database、过滤请求级 `AgentConfig` clone、按 catalog/database/schema/table scope 裁剪目录结果并注入 principal；`/api/v1/sql/execute` 还会在执行前复用 grant scope 和 SQL policy principal 校验手写 SQL。report/dashboard projection 和执行审计兜底仍属于阶段 4/5/6 后续子阶段。

### SQL 与数据安全

不要把 catalog 过滤当成执行安全。

SQL 执行必须叠加：

- module permission。
- datasource grant。
- request-level projected config。
- SQL policy principal。
- DB account 最小权限。
- audit log。

`DBFuncTool.read_query()` 的只读和 SQL policy 链路不能被 direct SQL、dashboard query、report query 绕过。

### 非 SQL 执行面

SQL 不是唯一执行风险。以下能力也必须进入 `Authenticate -> Build Context -> Authorize -> Project Config -> Execute -> Audit` 链路：

- LLM/model：按企业、角色、部门或项目限制可用 provider/model；外部 LLM 出境、私有 endpoint、fallback 和成本统计必须可审计。
- MCP：MCP server/tool 的列表、启停、调用都需要 `module.mcp` 或更细 permission，且仍叠加 tool permission。
- 文件系统与 skills：路径、写入、执行类工具必须使用 tool permission 和 path policy；企业数据、secret、artifact 路径不能被自然语言绕过。
- KB/RAG：知识库导入、索引、检索结果进入 LLM 前必须做企业/项目/用户/角色 ACL 和脱敏；向量索引需要按企业、项目或权限域隔离。
- BI/report/dashboard：静态 HTML 可见不代表实时 query/export 可用；query/export 必须重新校验 artifact ACL、模块权限、datasource grant 和 SQL policy。
- export/download：导出文件必须有 owner/ACL、过期时间、审计和脱敏策略；不能把临时文件路径直接暴露为长期访问权限。
- quota/rate limit：高成本 LLM、长 SQL、导出、大结果集、MCP 调用都应预留 quota hook；缺失生产 quota provider 时按配置 fail closed 或显式降级。

如果新增执行能力暂时不能完整接入上述链路，必须默认关闭或只在本地兼容模式启用，并在文档和测试中说明。

### 审计与错误语义

审计不是普通日志。以下事件必须进入 `AuditSink` 或等价审计表：

- 登录、token/API token 校验失败、用户禁用或系统维护停用。
- 模块 allow/deny、datasource allow/deny、session owner deny、artifact ACL deny。
- SQL policy deny、SQL policy rewrite、dashboard/report/direct SQL query。
- MCP 调用、文件写入/导出、KB 导入/检索、LLM provider/model 选择和高成本请求。
- 用户、角色、权限、datasource grant、artifact ACL、secret、quota 等 admin mutation。

审计字段至少包含 `user_id`、`request_id`、`action`、`resource_type`、`resource_id`、`decision`、`reason` 和时间。metadata 可以记录摘要和策略版本，但禁止写入 secret、完整凭证、未脱敏 datasource 配置、完整大结果集或敏感 prompt。

管理变更必须有明确语义：

- 禁用用户后，新请求、长任务续写、session resume 和实时 query 必须拒绝；历史 audit、session ownership 和产物记录不自动删除。
- 删除 role 前必须处理现有 `user_roles`、`role_permissions` 绑定；默认应阻止删除仍被使用的 role，强制删除必须清理关联并审计。
- datasource grant 撤销后，新 catalog、chat projection、dashboard/report/direct SQL 请求立即按新授权判定。
- artifact ACL 修改后，新 list/detail/query/export 请求立即按新 ACL 判定。
- admin mutation 审计只记录脱敏摘要，不记录 secret、完整连接串或大结果集。

错误语义：

- 对外 API error code 使用本规范的稳定字符串。
- 内部领域错误仍按项目约定使用 `DatusException(ErrorCode.XXX, ...)`；如果 route 返回 `Result[T]`，必须有清晰映射，不要在不同 route 返回互不兼容的错误形态。
- 对可猜测资源，例如 `session_id`、artifact slug、导出文件 id，不存在和无权限可以统一返回 `RESOURCE_NOT_FOUND`，避免泄漏存在性。
- 401 用于未认证或无效身份；403 用于已认证但无权限；生产企业模式缺少必要 provider/config 时不得静默降级为 allow。

### 运维与状态边界

企业化改造不能只在单进程 happy path 成立。

必须检查：

- `DatusServiceCache` key 必须区分企业生产模式和本地兼容模式，避免配置互相污染。
- `DatusService.agent_config` 必须保持共享只读语义；用户级 projection 只能写 clone。
- user/project/session 用于路径或 cache key 前必须转成 safe slug，不直接拼接外部输入。
- 运行中 task 在多 worker 下如果仍保存在进程内，必须明确 sticky session 要求；长期方案应把 task metadata、SSE event buffer 或长任务状态外部化。
- Postgres/Redis/object storage/vector store 等外部状态引入时，必须说明迁移、回滚、清理、备份恢复和企业级隔离策略。
- 滚动发布期间，新旧代码对 session owner、artifact ACL、audit schema 和 permission key 的兼容性必须有测试或迁移说明。

## 测试标准

企业级安全改造必须至少覆盖以下测试维度。

### 必测正反例

- 有权限允许，无权限拒绝。
- 用户 A 不能访问用户 B 的同名 project/session/artifact，除非具备显式管理员权限。
- 用户 A 不能 resume/stop/insert 用户 B 的 session。
- 用户 A 不能提交用户 B 的 interaction/tool result。
- 未授权 datasource 不出现在 list，也不能被 request.datasource 使用。
- 未授权表不能通过手写 SQL、dashboard query、report query 绕过。
- principal 缺失时 SQL policy fail closed。
- NoAuthProvider 本地兼容行为不被改坏。
- `enterprise.enabled=true` 但生产 auth/RBAC/authorization/config projection 缺失时 fail closed。
- 禁用用户的新请求、resume 和实时 query 被拒绝。
- 角色、permission、datasource grant、artifact ACL 变更后，新请求立即按新规则生效。
- datasource grant 合并时 deny 优先于 allow。
- datasource grant admin upsert 不产生同主体同数据源的重复 grant。
- permission glob 或 role template 展开结果稳定。
- request body 试图覆盖 `principal`、roles、permissions 或企业上下文字段时被拒绝或忽略。
- config projection 后原始 `DatusService.agent_config` 不变。
- 同一进程内两个用户或两个权限域并发请求不同 datasource grants 时互不污染。
- artifact slug、导出文件 id、KB 文档 id 等可猜测资源不能跨用户或跨权限域泄漏。
- 多 worker 或 sticky session 相关行为与文档声明一致。

### 测试位置

按现有项目约定放置：

- `tests/unit_tests/api/auth/`
- `tests/unit_tests/api/`
- `tests/unit_tests/tools/permission/`
- `tests/unit_tests/tools/func_tool/`
- `tests/integration/` 中只放必要的跨组件验证。

涉及外部 OIDC、Postgres、Redis、真实 LLM 的测试必须 mock 或 gated，普通 CI 不依赖外部服务、网络和 API key。

## 文档更新标准

企业级相关变更必须同步更新文档：

- 改变总体目标、阶段、API 分区：更新 `ENTERPRISE_PLATFORM_PLAN.zh.md`。
- 改变 AI/开发实施约束：更新 `ENTERPRISE_AI_DEVELOPMENT_GUIDE.zh.md`。
- 改变 repo 通用工作契约：更新 `AGENTS.md`，并保持 `CLAUDE.md` 继续指向 `AGENTS.md`。
- 新增 API：说明权限、企业上下文来源、错误码和审计行为。
- 新增 provider/protocol：说明默认实现、生产 fail closed 行为和测试要求。

## 禁止清单

- 禁止用前端隐藏替代后端授权。
- 禁止用 `scoped_context` 替代 RBAC 或 SQL policy。
- 禁止直接信任 `X-Datus-User-Id` 作为生产身份。
- 禁止直接信任前端传入的 permissions、roles、principal。
- 禁止在 route 中散落硬编码角色判断。
- 禁止把 secret 写入 session、trace、tool result、prompt、audit 明文字段或错误信息。
- 禁止在共享 config/service 上写用户级授权状态。
- 禁止无测试地修改 chat task、session、datasource、SQL 执行路径。

## 完成定义

企业级相关任务完成时，最终说明必须包含：

- 改了哪些接口或 API。
- 新增了哪些授权/投影/审计边界。
- 哪些路径仍未覆盖，是否 fail closed。
- 跑了哪些测试，未跑哪些测试及原因。
- 是否需要更新 `ENTERPRISE_PLATFORM_PLAN.zh.md` 或本规范。
