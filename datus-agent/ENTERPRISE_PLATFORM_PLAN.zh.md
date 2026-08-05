# 企业内网平台化开发计划

本文是本下游 fork 的企业内网平台化**架构契约**。它不记录所有历史讨论，只保留后续开发不能破坏的产品目标、安全边界、阶段划分和上线门槛。具体执行 checklist 见 `ENTERPRISE_AI_DEVELOPMENT_GUIDE.zh.md`；本地启动见 `LOCAL_ENTERPRISE_BACKEND_TESTING.zh.md`。

## 目标

Datus Agent 从本地 agent/API 服务演进为企业内网单租户、多用户、RBAC + 数据权限平台，覆盖：

- 企业身份接入和员工请求上下文。
- 用户会话隔离、运行中任务 owner 校验。
- 模块 RBAC、数据源授权、SQL policy、artifact ACL。
- 管理 API、审计、quota、secret reference。
- 单节点或粘性会话试点，以及后续多实例/HA 演进。

实现上**不引入 `tenant_id` 作为基础 metadata 维度**。默认只有一个企业上下文；部门、项目组、数据域通过 role、permission、datasource grant、artifact ACL 和 metadata 表达。

## 非目标

- 不把前端隐藏当作安全边界。
- 不把 `scoped_context`、catalog 过滤或 tool permission 单独包装成完整 RBAC。
- 不信任 token/request body/frontend 里的 roles、permissions、datasource grants 或 principal 作为最终授权事实。
- 不在第一阶段建设审批流、SCIM/SAML、列级权限、对象存储、外部任务队列、完整 HA。
- 不把 PG metadata store 误称为全平台状态迁移；RAG/vector、`subject/`、artifact bundle/export、业务 datasource 仍是独立存储面。

## 当前锚点

| 能力 | 主要位置 | 当前结论 |
| --- | --- | --- |
| 请求上下文 | `datus/api/auth/context.py` | `AppContext` 已包含 roles、permissions、datasource_grants、principal、is_admin 等字段。 |
| 默认本地认证 | `datus/api/auth/no_auth_provider.py` | 只适合本地兼容模式；生产企业模式不能信任裸 header。 |
| 企业身份 provider | `datus_enterprise/auth/providers.py` | 当前重点是 `UserInfoBearerAuthProvider` 和 `SignedHeaderAuthProvider`；`datus_enterprise/auth_provider.py` 保留旧类路径兼容。 |
| route dependency | `datus/api/enterprise/deps.py` | 模块权限、platform status、session/artifact/datasource helper 应集中在这里。 |
| route 暴露面 | `datus/api/enterprise/route_security_matrix.py` | 新增或修改 FastAPI route 必须同步分类并测试。 |
| service cache | `datus/api/services/datus_service_cache.py` | 企业模式 cache key 必须和本地兼容模式隔离。 |
| session owner | `datus_enterprise/storage/local/`、`datus/models/session_manager.py` | owner/index metadata 决定可见性；`datus/api/enterprise/defaults.py` 保留旧类路径兼容导出，正文 store 不授予访问权。 |
| config projection | `datus_enterprise/projection.py` | 用户级 datasource/principal 限制只能进入请求级 `AgentConfig` clone。 |
| PostgreSQL metadata | `datus_enterprise/postgres_stores.py` | 试点/生产 metadata store 起点；当前不是完整 migration runner。 |
| PG session body | `datus_enterprise/storage/postgres/session.py` | 可选正文/history/state backend；`datus_enterprise/postgres_session_store.py` 保留旧类路径兼容，不替代 owner store，不迁移历史 `.db`。 |

## 核心链路

所有企业请求都按以下链路思考：

```text
Authenticate -> Build Context -> Authorize -> Project Config -> Execute -> Audit
```

分层含义：

| 层级 | 负责内容 | 典型控制点 |
| --- | --- | --- |
| 认证 | 谁在请求、是否来自企业身份域 | Bearer + userinfo、签名 header、后续 OIDC/JWKS |
| 模块 RBAC | 能不能进入独立业务 API 或管理 API | `module.sql_executor`、`module.report.query`、`module.admin.users` |
| 资源授权 | 能访问哪些 datasource/session/artifact/agent | datasource grant、session owner、artifact ACL、agent ACL |
| 执行策略 | 真正执行时能不能过 | SQL policy、tool permission、DB 账号、quota、platform status |
| 审计 | 为什么 allow/deny、谁做了 mutation | `AuditSink`、audit logs、request_id |

## 企业模式硬规则

- `enterprise.enabled=false`：保持开源/本地兼容模式，允许 `NoAuthProvider`。
- `enterprise.enabled=true`：必须 fail closed。缺少用户、权限、datasource grant、session owner、artifact ACL、SQL principal、audit/quota 必需 provider 时不得静默放行。
- 试点/生产配置必须显式配置 auth provider、authorization provider、datasource grant store、config projector、audit sink。passthrough projector fallback 只允许本地/历史兼容验证。
- 生产模式不得信任裸 `X-Datus-User-Id`、前端 roles/permissions/principal 或 request body 企业上下文字段。
- 本地 dev admin 开关只能用于开发联调；不能作为真实员工试点或生产身份边界。
- 共享 `DatusService.agent_config` 保持基线配置，只读使用。用户级 datasource、principal、tool 限制必须进入请求级 clone。
- legacy route 若尚未进入完整企业安全链，在 `enterprise.enabled=true` 下必须返回禁用错误并审计。
- 运行中 task/SSE/event buffer 当前仍有进程内状态；多 worker/pod 必须粘性路由，除非已外部化对应运行态。

## 身份方案

MVP 支持两种生产可接受形态：

| 形态 | 说明 | 要求 |
| --- | --- | --- |
| Bearer access token + userinfo | Datus 读取 `Authorization: Bearer <token>`，调用企业 userinfo 换取员工身份 | token 和 userinfo 原文不得落日志；userinfo 失败 fail closed；Datus metadata store 才是授权事实来源 |
| 签名 header | 网关完成 SSO/JWT/OIDC 校验，向 Datus 注入 HMAC 签名身份 header | 后端不能被绕过网关直连；签名包含 method/path/timestamp/身份字段并校验时间窗口 |

直接 JWT/JWKS 校验、issuer/audience/kid、key rotation、JWKS cache 属于后续 provider 扩展。

首次访问自动开通必须通过 `enterprise.user_auto_provisioning.enabled` 显式开启，默认关闭。只允许创建最小用户档案并绑定预先存在的低权限默认角色；默认角色缺失、用户写入失败或角色绑定失败时 fail closed 并审计。

## 权限模型

权限 key 使用稳定字符串，不绑定 URL。基础 key：

```text
module.chat
module.chat.permission_mode
module.sql_executor
module.datasource_catalog
module.report.view
module.report.query
module.report.export
module.report.edit
module.dashboard.view
module.dashboard.query
module.dashboard.export
module.dashboard.edit
module.kb
module.mcp
mcp.server.list
mcp.server.add
mcp.server.edit
mcp.server.remove
mcp.server.connectivity
mcp.server.tools
mcp.filter.view
mcp.filter.set
mcp.filter.remove
mcp.{server}.{tool}
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
module.admin.agents
module.system.status
```

规则：

- `view` 只表示列表/详情/静态 HTML 可见，不自动包含实时查询、导出、编辑。
- `module.chat.permission_mode` 只允许请求 `auto` / `dangerous` 对话模式；该模式只调整本轮工具确认策略，不授予 Agent 新工具，也不绕过 Agent Tool Policy、文件路径或 Artifact ACL。
- `query` 表示实时查数或执行保存 SQL，必须叠加 datasource grant、SQL policy、quota、audit。
- `export` 单独授权，并需要 ACL、quota、审计、脱敏策略。
- admin 也必须拆成显式 permission，不用硬编码超级用户绕过授权链。
- 新增 key 必须同步 route security matrix、测试 fixture、`/me` 能力返回和文档。

## API 分区

普通业务 API 不接受企业上下文参数；上下文来自认证后的 `AppContext`。

```text
/api/v1/me/*
/api/v1/chat/*
/api/v1/datasources/* 或当前兼容 catalog/table/semantic route
/api/v1/sql/*
/api/v1/reports/*
/api/v1/dashboards/*
/api/v1/kb/*
/api/v1/mcp/*
/api/v1/agents/*
/api/v1/admin/*
/api/v1/system/*
/api/v1/internal/*
```

约束：

- `/me` 只返回当前用户能力和可见工作区 view，不做管理操作。
- `/admin` 只管理当前企业上下文，使用 `module.admin.*`。
- Agent ACL 管理使用由 `module.admin.agents` 守卫的脱敏用户、角色候选目录；不复用用户/角色管理详情接口或其他资源的分享候选目录。
- 普通用户的内置与自定义 Agent 目录、详情和分发统一由 Agent 状态与 ACL 控制，不再与 `module.chat*` 或 node class 对应的模块权限绑定；直接 `subagent_id` 和 `task()` 委派必须重做同一 ACL 校验。
- `module.sql_executor`、`module.report.query`、`module.dashboard.query` 继续保护直接 SQL、报表、仪表盘等独立业务 API，但不决定对应 Agent 是否显示或可调用。
- `/system` 给部署运维和系统状态，不默认开放普通前端用户。
- `/internal` 使用独立服务认证，不复用普通用户 JWT。
- 不存在和无权限的可猜测资源可统一返回 `RESOURCE_NOT_FOUND`，避免泄漏存在性。

稳定错误码优先使用：

```text
AUTH_REQUIRED
AUTH_TOKEN_INVALID
ENTERPRISE_DISABLED
ENTERPRISE_ROUTE_DISABLED
USER_DISABLED
ENTERPRISE_USER_NOT_PROVISIONED
PERMISSION_DENIED
DATASOURCE_FORBIDDEN
SESSION_FORBIDDEN
ARTIFACT_FORBIDDEN
QUOTA_EXCEEDED
POLICY_DENIED
PLATFORM_STATUS_FORBIDDEN
RESOURCE_NOT_FOUND
```

## Datasource Grant

MVP grant 采用每个 `(subject_type, subject_id, datasource_key)` 一条记录，细粒度 scope 写在 `scope_json`。

合并规则：

- role grants 先合并，user grants 后合并。
- 没有 grant 默认不可见、不可用。
- 显式 `deny` 优先于 `allow`。
- user grant 对未授权 datasource 可直接授权；对已有 role grant 只能收窄或显式拒绝，不能扩大。
- 宽 allow + 窄 deny 时，窄 deny 生效。
- 宽 deny + 窄 allow 时，除非 schema 明确支持例外白名单，否则 deny 生效。
- admin API 保存前校验 subject、datasource key、scope schema、effect；语义不清时拒绝并审计。

执行点：

- catalog/database/schema/table list 只返回授权范围。
- chat/direct SQL/dashboard query/table detail/semantic model 必须校验请求 datasource/table scope。
- 请求级 `AgentConfig.services.datasources` clone 只保留授权 datasource。
- SQL policy principal 写入服务端构造的 user、role、datasource/table scope 等字段。

Catalog 过滤不是执行安全。SQL 执行仍必须叠加 SQL parser/policy 和数据库最小权限账号。

## Session、Task 与 Artifact

Session 访问必须以 `SessionOwnerStore` 为入口。

必须校验 owner 的路径包括：

- `chat/resume`
- `chat/stop`
- `chat/user_interaction`
- `chat/insert`
- `chat/tool_result`
- `chat/history`
- `chat/sessions/{session_id}` delete/compact
- admin session 管理路径

规则：

- 普通用户只能操作自己的 session/task。
- 管理员跨用户操作必须具备 `module.admin.sessions`。
- body store 中存在正文不代表可访问，也不得自动补写 owner metadata。
- owner 缺失或不一致时 fail closed 或统一不可见。

Artifact 访问必须按 artifact type + slug 校验 ACL：

- 静态 HTML/detail/list 需要 `*.view` + ACL。
- 实时 query/export 需要 `*.query`/`*.export` + ACL + datasource grant + SQL policy + quota + audit。
- 创建编辑会话需要对应的 `*.edit` 且当前用户是 owner；`module.admin.artifacts` 管理员可跨 owner 编辑。
- 创建后默认 private：owner 和 `module.admin.artifacts` 管理员可见。
- 创建者自助分享只能使用脱敏用户/角色目录，不复用 admin 用户/角色详情接口。

## Agent 用户 Workspace

企业请求中的通用文件操作不能直接使用共享 `agent.project_root`。当前最小边界为：

- `ChatTaskManager` 在所有授权、SQL policy、model policy 和 quota 前置检查通过后，根据服务端认证得到的 `user_id` 创建请求级私有目录：`{agent.home}/workspace/{project_name}/{sha256(user_id)}`。
- 目录使用不暴露原始用户标识的固定摘要段，并设置为 `0700`；路径由服务端构造，不接受请求体或 Agent 提交 workspace root。
- Chat、Feedback 和 GenSQL 节点的通用文件工具优先使用请求级 workspace，覆盖节点配置中的 `workspace_root`；共享 `DatusService.agent_config` 和原始 `project_root` 不得被修改。
- Enterprise Chat 缺少认证用户时拒绝启动；通用 Bash 始终禁用，因为工作目录不是文件系统沙箱。
- 全局 `{agent.home}/skills` 对 Enterprise 文件工具只读；用户 workspace 内的 `.datus/skills` 和 `.datus/plans` 仍可按工具权限写入。
- Visual Report/Dashboard 继续写入共享 `project_root/reports|dashboards/<slug>`，但 Enterprise 新建节点只暴露 `start_new_*`；默认 private ACL 成功持久化后，文件工具才绑定新 slug。缺少 ACL store/认证 owner 时创建失败并回滚。
- 已有 Visual Report/Dashboard 只能由通过 `require_artifact_edit_access` 的服务端 edit session 绑定；节点和文件工具锁定到唯一 slug，不能创建第二个 Artifact、绑定其他 slug、枚举其他 Artifact 或写入 Artifact 外路径。
- 语义模型、指标和 SQL summary 等其他项目级作者节点暂时继续使用共享 `project_root`，必须依赖各自 module permission 或专用生成路径。它们不属于本轮用户 workspace 隔离完成面，后续迁移前不得宣称“全部 Agent 项目文件已按用户隔离”。

当前实现是同一 API 进程内的应用级路径隔离，不是任意代码执行沙箱。若重新开放 Bash、Python、任意 MCP 文件工具或用户代码执行，必须使用仅挂载当前 workspace 的独立 worker/container，不能把 `cwd` 或工具确认提示当作隔离边界。

## Platform Status

`DATUS_PLATFORM_STATUS` 支持：

- `active`：允许执行类请求和写入类 mutation。
- `readonly`：只读查询可用，执行/写入拒绝。
- `maintenance`：维护期拒绝执行/写入，保留必要只读和停止类例外。

执行类请求和 mutation 必须在构造 `DatusService`、写 metadata store、访问外部系统前校验状态。拒绝返回 `PLATFORM_STATUS_FORBIDDEN` 并写 `system.platform_status` 审计。未知状态按 fail closed 处理。

## Metadata 与存储边界

配置样例：

- `conf/agent.enterprise.mvp.yml.example`：SQLite / in-memory metadata store，适合本地单节点或小范围试点。
- `conf/agent.enterprise.pg.yml.example`：PostgreSQL user/role/datasource grant/enterprise agent/session owner/artifact ACL/audit/quota/secret metadata，并可启用 PG session body backend。
- `conf/agent.enterprise.ob.yml.example`：OceanBase MySQL user/role/datasource grant/enterprise agent/session owner/artifact ACL/audit/quota/secret metadata，并可启用 OceanBase session body backend。
- `conf/agent.local-enterprise-pg.yml.example`：本地联调用完整配置，配合 seed/mock userinfo/签名工具使用。

PG metadata 当前只做最小 `CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS` bootstrap，不是生产 migration runner。新增字段或 schema 变更必须说明人工 DDL、迁移、回滚、滚动发布兼容和备份恢复策略。

用户默认 Agent 使用独立的 `enterprise_user_chat_preferences` 表，由当前 `user_store` 的 SQLite、PostgreSQL 或 OceanBase 实现持久化。企业默认 Agent、内置 Agent overlay、Tool Policy 和委派 runtime policy 写入现有 enterprise agent 记录的保留策略元数据，API 和运行时会从业务 `scoped_context` 中剥离该保留键。默认解析顺序固定为“用户个人默认 -> 企业默认 -> ACL 可用的内置 `chat` -> 第一个 ACL 可用 Agent -> 无可用 Agent”；`chat` 不可用时仍只在当前用户已经通过状态与 ACL 过滤的 Agent 中回退，不得在安全 Agent 失效时静默回退到权限更大的系统 Agent。该用户偏好表是增量且不带外键：滚动发布时旧版本会忽略它，新版本可先执行仓库 `_SCHEMA_SQL` 中对应的 `CREATE TABLE IF NOT EXISTS`；回滚应用不需要删除表，确认不再回滚且完成备份后才可人工清理。生产环境应先按目标数据库方言执行同构建表 DDL，再发布读取该偏好的应用版本。

Agent Tool Policy 使用 deny 优先规则；`mode=allowlist` 时只暴露允许工具，并在调用前追加服务端 DENY 规则形成二次校验。交互节点的澄清、计划确认和会话 Todo 控件统一归入 `tools.*`，进入管理目录并在交互型 Agent 的工具参考中默认启用；orchestrator 和 Skill 作者工具使用独立类别，不能被 `tools.*` 隐式授权；管理员仍可通过精确 deny 关闭某个交互控件。Visual Report/Dashboard 的受限文件方法和 Artifact 创建、绑定、保存、校验方法，以及 Chat 默认启用的平台文档方法，都必须进入各自节点的管理目录与默认引用，避免默认 allowlist 删除节点必需工具或让下拉框只能显示不可展开的默认占位。新建、更新 Agent 或单独更新策略时，服务端必须校验 allowed/denied 模式：allowed 只能引用该节点管理目录内的原生工具或当前 Agent 已绑定的 MCP Server，不能通过策略启用 Bash 或未绑定 MCP；denied 独立保留 Bash、BI、scheduler、sub-agent、Skill、Web、orchestrator、Skill 作者和 MCP 等已知运行时类别的防御性规则，但拒绝未知类别或方法。历史已存记录在只读加载时不强制迁移。workflow、sub-agent、Artifact create/edit 状态和 Plan Mode 继续由执行模式、ACL 与节点状态决定实际注册哪些工具，allowlist 不会凭空创建未注册工具。运行时必须先完成本轮工具装配、再应用 Tool Policy，系统 Prompt 随后基于最终 LLM 工具面生成；所有节点的 Prompt 能力标记都从过滤后的最终工具面计算，Prompt 快照身份包含执行模式、最终原生工具面以及可宣传的 MCP server/tool 面，避免旧快照宣称已被策略移除的工具。对话 permission mode 属于用户和本轮会话的确认策略，由 `module.chat.permission_mode` 控制，Agent 不再配置第二套模式上限。`allow_subagent_delegation=false` 时移除 `task()`；允许委派时，`task()` 由 runtime policy 保留而不要求混入普通工具 allowlist，但显式 Tool Policy deny 仍优先，被委派 Agent 仍重新校验自己的 ACL 和 Tool Policy。

### Agent Prompt 不可变版本库

企业自定义 Agent 的 Prompt 版本使用两张增量 companion 表，不直接给既有 `enterprise_agents` 增加外键列：

- `enterprise_agent_prompt_versions` 保存不可变正文、版本标签、语言、正文 SHA-256、变更说明、基线版本和创建人；同一 Agent 内版本标签唯一。
- `enterprise_agent_active_prompt_versions` 保存每个 Agent 唯一的当前版本引用和激活审计字段。
- `enterprise_agents.prompt_template`、`prompt_language`、`prompt_version` 继续作为运行时当前版本投影。激活版本时必须在同一存储事务内更新 active 引用和这三个投影字段，既有运行时加载器不直接读取历史表。

管理 API 固定为：

```text
GET  /api/v1/admin/agents/{agent_id}/prompt-versions
GET  /api/v1/admin/agents/{agent_id}/prompt-versions/{version_id}
POST /api/v1/admin/agents/{agent_id}/prompt-versions
PUT  /api/v1/admin/agents/{agent_id}/prompt-version
```

四个接口都要求 `module.admin.agents`；POST/PUT 还必须先通过 `require_platform_active`。列表不返回 Prompt 正文，详情只在管理权限校验后返回正文。创建后的版本不可覆盖；激活必须携带 `expected_active_version_id` 做乐观并发校验。审计只保存版本 ID、版本标签、正文 SHA-256 和 old/new active 信息，不保存 Prompt 正文。内置 Agent 定义保持只读；企业 Agent 使用内置模板回退时，详情需要明确返回 `prompt_source=builtin_fallback`、配置版本、生效版本和正文修订，避免把配置标签误当成实际模板版本。

内置模板与企业 Agent 回退模板的管理详情必须使用当前请求对应 `DatusService.agent_config.path_manager` 解析，和 Chat 运行时共享同一 `agent.home/template -> repository builtin` 优先级；不得在路由中裸构造缺少 `AgentConfig` 的 `PromptManager` 后静默回退到进程用户的 `~/.datus`。`prompt_source` 需要区分 `builtin`、`user_override`、`runtime`，回退场景分别使用 `builtin_fallback`、`user_override_fallback`、`runtime_fallback`。管理界面展示的是带 Jinja 条件的原始模板，不等同于某个会话最终发送给模型的已渲染 system-prompt snapshot。

历史 Agent 的迁移采用只读穿透：GET 在尚无版本记录时返回确定性的 `legacy_*` 合成当前版本，但不写 metadata；第一次 Prompt 版本 mutation 才幂等持久化旧正文并建立 active 引用。若旧版本标签已存在但正文 SHA-256 不同，迁移必须冲突退出，不能覆盖。Agent 一旦进入版本库，普通 Agent upsert 只能保存其他配置字段，不能改变当前 Prompt 的版本、语言或正文；Prompt 变化必须创建新版本并显式激活。

发布与回滚规则：

- 当前仓库仍没有正式 migration runner。生产发布前应按 PostgreSQL 或 OceanBase 目标方言，先执行仓库 `_SCHEMA_SQL` 中两张 companion 表的同构 `CREATE TABLE IF NOT EXISTS`、唯一键和索引 DDL，并备份 `enterprise_agents` 与新增版本表。
- 滚动发布时旧应用会忽略 companion 表；新应用可读取既有 Agent 投影，并对 legacy 记录执行无写入的 read-through。应先建表，再发布新应用，最后开放版本 mutation。
- 回滚应用继续读取激活事务写回的 `enterprise_agents` 当前投影，不需要删除新表。回滚期间应暂停新版本 mutation，避免旧管理界面与新版本管理并行修改。
- 不自动删除 companion 表。只有确认不再回滚、版本历史与审计已完成备份、运行时已无读取需求后，才能人工制定清理方案。
- 激活只影响下一次 Prompt 解析；正在执行的轮次不被修改。已有会话的后续轮次按版本和正文修订指纹重新判断 Prompt 快照是否有效。

每个 PG metadata/body store 独立持有 asyncpg pool。连接预算按：

```text
store 数量 * max_size * API 进程数 + 业务 datasource + 运维/监控余量
```

启用 `session_body_store` 后，新 session 正文/history/state 写 PG；历史 SQLite `.db` 不自动迁移。回滚方式是移除该配置并重启，新请求回本地 SQLite，但 PG 中已写正文不会自动回写。

对话展示 sidecar 事件使用 session body 内的独立表：本地 SQLite 为 `chat_session_terminal_events`，PostgreSQL/OceanBase 为 `enterprise_session_terminal_events`。当前保存两类展示事实：已建立会话后的终态（error/cancelled/timeout），以及父 `task` 调用与嵌套子 Agent session 的委派关联。后者在子 Agent 启动前落库，使父 turn 尚未提交就被停止时，history 仍能恢复子 session 中已经持久化的 reasoning summary、assistant message、工具调用和结果。企业 child session 的标准 scope 为 `<user_scope>__<parent_session_id>`；history 对早期只写入 `<parent_session_id>` 的记录保留只读回退。两类 sidecar 事件都只参与 history 展示，不进入 Agent SDK/model 上下文；feedback copy/rewind 不复制旧 sidecar，避免把上一次失败或委派关系重放到新分支。该表通过 `CREATE TABLE IF NOT EXISTS` 增量引入，新增事件类型不需要 schema migration，滚动发布时旧版本会忽略它；生产发布前应按目标方言预建同构 DDL。回滚应用无需删表，确认不再回滚且完成 session body 备份后才可人工清理。

备份恢复必须分别考虑：

- enterprise metadata
- PG session body
- `subject/` 项目文件
- RAG/vector store
- artifact bundle/export 文件
- 业务 datasource
- 配置和 secret reference

## 开发阶段

| 阶段 | 目标 | 不可缺少的验收 |
| --- | --- | --- |
| 0 开关与兼容 | enterprise 开关、默认兼容、fail-closed skeleton | 本地 NoAuth 行为不破坏；企业缺 provider 不放行 |
| 1 身份与上下文 | auth provider、AppContext、RBAC 刷新、service cache 隔离 | 禁用用户/缺身份拒绝；本地与企业 cache 不串 |
| 2 会话隔离 | task owner、session scope、session owner index | 用户不能操作他人 session/task |
| 3 模块 RBAC | `require_module()` 覆盖独立业务 API、管理 API、MCP、KB、config | 无权限 403；legacy enterprise disabled |
| 4 数据源投影 | datasource grant、request config clone、metadata 裁剪 | 未授权 datasource/table 不可见也不可执行 |
| 5 SQL 与审计兜底 | direct SQL/dashboard/report query 接 SQL policy/quota/audit | principal 缺失 fail closed；执行路径有审计 |
| 6 管理 API | 用户、角色、grant、artifact ACL、audit、quota、secret、agent 管理 | mutation 脱敏审计；新请求立即按新授权生效 |

后续阶段：Redis/task event 外部化、对象存储、审批流、列级权限、模型治理、KB/RAG ACL、完整 HA。

## Route Security Matrix

任何 `create_app()` 注册 route 的新增、删除或行为改变，都必须同步更新 `datus/api/enterprise/route_security_matrix.py`。

矩阵分类至少表达：

- module RBAC permission
- session owner
- datasource projection/grant/table scope/SQL policy
- artifact ACL
- platform status gate 或例外
- audit
- legacy disabled
- system/local compatible 边界

对应测试必须比较矩阵和真实注册 route，新增 route 未分类应失败。

## 测试最低要求

企业相关改动至少覆盖正反例：

- 有权限允许，无权限拒绝。
- 用户 A 不能访问用户 B 的 session/task/artifact。
- 未授权 datasource/table 不出现在 list，也不能通过 chat/direct SQL/dashboard query/table detail/semantic model 绕过。
- SQL policy principal 缺失 fail closed。
- `NoAuthProvider` 本地兼容不被改坏。
- 禁用用户的新请求、resume、实时 query 被拒绝。
- role/permission/grant/artifact ACL 变更后，新请求按新规则生效。
- legacy route 在 enterprise mode 禁用并审计。
- `readonly`/`maintenance` 在服务初始化或外部副作用前拒绝。
- userinfo、PG metadata、audit sink、quota store、SQL policy backend 不可用时稳定失败，不静默 allow。

外部服务、真实 PG、真实 LLM 测试必须 gated，默认 CI 不依赖外部网络、API key 或共享数据库。

## 试点上线门槛

进入真实员工试点前，必须满足：

- 使用 `UserInfoBearerAuthProvider` 或 `SignedHeaderAuthProvider`，且生产模式不信任裸 header。
- 显式配置 auth、authorization、datasource grant store、config projector、audit sink；需要 quota 的路径有 quota store。
- 角色、permission、datasource grant、artifact ACL 来自服务端 metadata store，新请求会刷新。
- Agent chat 经过 Agent ACL、Tool/runtime policy、datasource/table grant、request projection、SQL policy principal 和审计；direct SQL/dashboard query/table/semantic metadata 仍经过各自模块权限及对应数据边界。
- 未进入安全链的 legacy route 在企业模式禁用。
- session owner index、用户级 scope、运行中 task owner 校验开启。
- 审计覆盖 auth deny、permission deny、datasource deny、session/artifact deny、SQL/dashboard 执行、admin mutation、platform status deny。
- `readonly`/`maintenance` 能在执行/写入前拒绝主要路径。
- 单节点可用 SQLite MVP；多 worker/HA 试点必须用共享 metadata store，并明确 sticky session 或外部化方案。
- 有最小 runbook：部署拓扑、sticky session、发布 drain、状态切换、故障处理、连接数预算、备份恢复、审计留存。

未满足时，只能标注为本地开发、演示或单节点兼容验证，不能描述为生产可用或 HA 可用。

## 运维与观测基线

试点前至少要能回答“为什么被拒绝、慢在哪里、成本花在哪”。

必须有来源或计划的观测项：

- request_id 贯穿 auth、dependency、projection、SQL policy、quota、audit、错误响应。
- deny 计数：auth、user disabled、permission、datasource、session owner、artifact ACL、SQL policy、quota、platform status、legacy disabled。
- 延迟：userinfo、context refresh、projection、catalog、chat 首事件/首 token、direct SQL、dashboard query、audit write。
- 资源：enterprise PG pool、连接数、quota store 错误率、audit sink 错误率、LLM token/cost。
- 质量：chat stream 中断、SSE resume 失败、SQL/dashboard query 错误、policy deny 原因分布。

完整 APM 不要求第一版全部落地，但进入可运维试点前必须明确指标来源和故障处理。

## 上游升级复核

合并 upstream release tag 或 cherry-pick 上游提交后，必须复核：

1. 新增 route 是否进入 route security matrix。
2. chat/session/task 是否仍走 owner store 和用户级 scope。
3. datasource/SQL/dashboard/report/table/semantic model 是否仍走 projection、grant、SQL policy 和审计。
4. MCP/filesystem/skills/export/LLM/model 是否有 module permission、tool/path policy、quota、audit。
5. `DatusServiceCache`、`DatusService.agent_config`、`ConfigProjector` 是否没有缓存用户级授权状态。
6. 新 metadata schema、permission key、audit action、quota resource 是否有迁移/兼容说明和测试。

至少运行 route security matrix、enterprise smoke、auth provider、session owner、projection/SQL policy、legacy disabled、platform status gate 相关测试；无法全跑时在提交说明中写明缺口和风险。
