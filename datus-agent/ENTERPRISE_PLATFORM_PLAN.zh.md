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
| 企业身份 provider | `datus_enterprise/auth_provider.py` | 当前重点是 `UserInfoBearerAuthProvider` 和 `SignedHeaderAuthProvider`。 |
| route dependency | `datus/api/enterprise/deps.py` | 模块权限、platform status、session/artifact/datasource helper 应集中在这里。 |
| route 暴露面 | `datus/api/enterprise/route_security_matrix.py` | 新增或修改 FastAPI route 必须同步分类并测试。 |
| service cache | `datus/api/services/datus_service_cache.py` | 企业模式 cache key 必须和本地兼容模式隔离。 |
| session owner | `datus/api/enterprise/defaults.py`、`datus/models/session_manager.py` | owner/index metadata 决定可见性；正文 store 不授予访问权。 |
| config projection | `datus_enterprise/projection.py` | 用户级 datasource/principal 限制只能进入请求级 `AgentConfig` clone。 |
| PostgreSQL metadata | `datus_enterprise/postgres_stores.py` | 试点/生产 metadata store 起点；当前不是完整 migration runner。 |
| PG session body | `datus_enterprise/postgres_session_store.py` | 可选正文/history/state backend，不替代 owner store，不迁移历史 `.db`。 |

## 核心链路

所有企业请求都按以下链路思考：

```text
Authenticate -> Build Context -> Authorize -> Project Config -> Execute -> Audit
```

分层含义：

| 层级 | 负责内容 | 典型控制点 |
| --- | --- | --- |
| 认证 | 谁在请求、是否来自企业身份域 | Bearer + userinfo、签名 header、后续 OIDC/JWKS |
| 模块 RBAC | 能不能进入某类 API/功能 | `module.chat`、`module.sql_executor`、`module.admin.users` |
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

- `/me` 只返回当前用户能力，不做管理操作。
- `/admin` 只管理当前企业上下文，使用 `module.admin.*`。
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
- 创建后默认 private：owner 和 `module.admin.artifacts` 管理员可见。
- 创建者自助分享只能使用脱敏用户/角色目录，不复用 admin 用户/角色详情接口。

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

每个 PG metadata/body store 独立持有 asyncpg pool。连接预算按：

```text
store 数量 * max_size * API 进程数 + 业务 datasource + 运维/监控余量
```

启用 `session_body_store` 后，新 session 正文/history/state 写 PG；历史 SQLite `.db` 不自动迁移。回滚方式是移除该配置并重启，新请求回本地 SQLite，但 PG 中已写正文不会自动回写。

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
| 3 模块 RBAC | `require_module()` 覆盖 route/subagent/admin/MCP/KB/config | 无权限 403；legacy enterprise disabled |
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
- chat/direct SQL/dashboard query/table/semantic metadata 都经过模块权限、datasource/table grant、request projection、SQL policy principal 和审计。
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
