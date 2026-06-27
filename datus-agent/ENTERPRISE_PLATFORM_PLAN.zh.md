# 企业内网平台化开发计划

本文是本下游 fork 后续从本地 agent/API 服务走向企业内网平台化能力的开发计划。目标产品形态是**单租户、多用户、RBAC + 数据权限的企业内网平台**，覆盖企业 SSO、员工会话隔离、模块 RBAC、数据源授权、执行安全、审计治理和高可用演进。文档放在项目根目录，作为本 fork 的产品化改造目标，不混入上游公开文档体系。

实现上不把 `tenant_id` 作为基础 metadata 维度。系统默认只有一个企业上下文，部门、项目组和数据域通过 role、permission、datasource grant、artifact ACL 表达。

本文已经按当前 checkout 的实现重新审查并整理。核心结论：

- 当前代码已有轻量身份上下文、按 `user_id` 的会话 scope、SQL policy principal 入口和工具级 permission profile，但它们还不是完整企业内网权限边界。
- 第一阶段必须先补齐硬边界：企业 SSO/认证、用户会话与运行中 task owner 校验、模块 RBAC、数据源投影、SQL policy 兜底和基础审计。
- `scoped_context`、前端隐藏、catalog 过滤、tool permission 都只能作为分层控制的一部分，不能单独声明为 RBAC、数据权限或员工隔离。
- 企业级能力应分阶段推进，先完成内部员工安全硬边界，再做审计、限流、状态外部化、审批流、列级权限、模型治理和高可用能力。

## 当前实现锚点

以下是当前项目中可复用或必须修改的代码位置。

| 现有能力 | 当前位置 | 现状判断 |
| --- | --- | --- |
| 请求上下文 | `datus/api/auth/context.py` | `AppContext` 只有 `user_id`、`project_id`、`config`、`principal`，还没有 roles、permissions、datasource grants。 |
| 默认认证 | `datus/api/auth/no_auth_provider.py` | `NoAuthProvider` 读取可选 `X-Datus-User-Id` 和 `X-Datus-Principal`，适合本地开源模式，不适合生产身份边界。 |
| 服务缓存 | `datus/api/deps.py`、`datus/api/services/datus_service_cache.py` | cache key 当前是 `project_id` 或 `default`，企业版需要加入固定企业 scope，避免部署模式或配置切换时污染 `DatusService`、`ChatTaskManager` 和 datasource config。 |
| 会话持久化 | `datus/models/session_manager.py` | `SessionManager(scope=...)` 支持 scope 子目录，当前 API 路径主要传 `ctx.user_id`，可作为企业版 `user_slug` scope 基础。 |
| 运行中任务 | `datus/api/services/chat_task_manager.py` | `ChatTask` 当前只记录 `session_id`、async task、node、events、status 等，没有 owner 字段。 |
| chat 路由 | `datus/api/routes/chat_routes.py` | `stream` 已传入 `ctx.user_id` 和 `ctx.principal`；`resume`、`stop`、`user_interaction`、`insert`、`tool_result` 当前缺少 owner 校验入口。 |
| SQL policy 预检查 | `datus/api/routes/chat_routes.py` | chat 入口已有 principal 必填字段预检查，但它只覆盖启用 SQL policy 的 chat 路径。 |
| SQL 执行工具 | `datus/tools/func_tool/database.py` | `DBFuncTool.read_query()` 有只读校验、scoped context 和 SQL policy principal 入口；写入/DDL 和直接 API SQL 路径仍需单独治理。 |
| 工具权限 | `datus/tools/permission/*` | 控制 agent 内部工具的 `allow` / `ask` / `deny`，不等价于业务模块 RBAC。 |
| 报表/仪表盘 | `datus/api/routes/report_routes.py`、`datus/api/routes/dashboard_routes.py` | 需要补 artifact ACL、模块权限、query datasource/table grant 和执行 principal。 |
| 数据源目录 | `datus/api/routes/database_routes.py`、`datus/api/services/database_service.py` | 当前按配置列 datasource/catalog/database/schema/table，缺少用户/角色授权过滤和执行兜底。 |

## 目标与非目标

### 目标

1. **企业内网身份边界**：企业 SSO 或网关认证构造稳定身份，生产模式禁用匿名或裸 header 冒充身份。
2. **用户会话隔离**：普通员工只能查看、恢复、停止、交互自己的会话；管理员只能在显式权限下管理企业内会话。
3. **模块 RBAC**：管理员可限制普通用户访问 chat、SQL 执行器、数据源目录、报表、仪表盘、KB、MCP、管理后台等模块。
4. **数据源授权**：用户只能看到和使用被授权的数据源及其 catalog/database/schema/table 范围，agent 执行时不能绕过。
5. **SQL 与产物兜底**：dashboard/report 保存的 SQL、chat 工具 SQL、直接 SQL API 都必须进入同一套 principal/policy/审计链路。
6. **低侵入维护**：尽量把企业能力放在下游扩展模块，通过 API dependency、AuthProvider、请求级 config projection 和服务缓存接线，减少对上游 agent 核心节点的大面积改动。

### 非目标

- 不把 `scoped_context` 包装成完整安全机制。它可以影响可见性、检索和部分工具校验，但硬边界仍要依赖后端授权、SQL policy 和数据库最小权限账号。
- 不让前端隐藏承担安全职责。前端只改善体验，后端必须独立拒绝未授权请求。
- 不让 token 里的 permissions 成为唯一权限来源。token 证明身份，服务端 RBAC store 决定当前有效权限。
- 不建设与企业内部员工数据服务无关的运营售卖能力。
- 不把部门、项目组、数据域建成独立产品主体；统一用组织属性、role、permission、datasource grant 和 workspace/project ACL 表达。
- 不在第一阶段一次性建设审批流、列级权限、SCIM、SAML、对象存储、外部任务队列等能力。

## 设计原则

### 分层授权

系统至少分为四层：

| 层级 | 负责内容 | 典型控制点 |
| --- | --- | --- |
| 认证 | 谁在请求，是否来自当前企业内部身份域 | 企业 SSO/JWT/OIDC、反向代理签名 header、API token |
| 模块 RBAC | 用户能不能进入某个 API 面或业务功能 | `module.report.view`、`module.dashboard.query`、`module.admin.users` |
| 资源授权 | 用户能访问哪些 datasource、artifact、KB、session | datasource grant、artifact ACL、session owner index |
| 执行策略 | SQL/LLM/MCP/文件系统真正执行时能不能过 | SQL policy、tool permission、数据库账号、quota、审计 |

模块 RBAC 不能替代 SQL policy。数据源目录过滤不能替代 SQL 执行校验。tool permission 不能替代业务模块权限。

### Fail closed

生产企业模式必须 fail closed：

- 缺少 `user_id`、角色、权限、数据源 grant 时默认拒绝。
- 缺少 SQL policy 必要 principal 字段时拒绝执行。
- 请求指定未授权 datasource/catalog/database/schema/table 时拒绝。
- 找不到资源和无权限时按接口策略返回统一错误，避免泄漏其他用户或企业资源是否存在。

`NoAuthProvider` 继续作为开源单机默认行为，但生产配置必须使用显式 auth provider，并禁用裸 `X-Datus-User-Id` 冒充式身份。

### 请求级投影

共享的 `DatusService.agent_config` 不能被用户请求直接修改。所有按用户/角色/数据源授权产生的限制都应写入请求级 clone：

1. 读取服务端 RBAC store。
2. 计算当前用户的模块权限和 datasource grants。
3. deep copy 当前 `AgentConfig`。
4. 删除未授权 datasource。
5. 注入 SQL policy principal。
6. 按模块权限收窄工具权限或隐藏工具。
7. 用 clone 启动本次 chat/task/query。

当前 `ChatTaskManager.start_chat()` 已经 deep copy `AgentConfig`，是 chat 请求投影的合适接入点。其他直接 query/report/dashboard 路径需要各自接入同样的投影或统一 execution service。

## 目标架构

建议新增下游扩展包，避免把企业逻辑散落进上游核心模块：

```text
datus_enterprise/
  auth_provider.py          # JWT/OIDC/反向代理身份解析，实现 AuthProvider
  context.py                # 企业上下文扩展类型和 helper
  rbac/
    models.py               # EnterpriseContext/User/Role/Permission/Grant/ACL 数据模型
    service.py              # can_access_module / allowed_datasources / owner checks
    store.py                # SQLite/Postgres 存储实现
  api/
    deps.py                 # require_module / require_datasource / require_session_owner
    admin_routes.py         # 用户、角色、权限、数据源授权管理 API
  config_projection.py      # 按请求过滤 AgentConfig.datasources 和 principal
  audit.py                  # 鉴权与资源访问审计
  quota.py                  # 后续限流/配额入口
```

上游或通用代码只做必要接线：

- 扩展 `AppContext` 字段。
- `DatusServiceCache` 支持 enterprise-aware key，区分企业生产模式和本地兼容模式。
- `ChatTask` 增加 owner metadata。
- chat、database、dashboard、report、kb、mcp、config/admin 类 routes 增加 authorization dependency。
- chat 启动、dashboard/report query、direct SQL 统一走请求级 config projection 和 principal。
- 可选提供插件接口，让具体 RBAC store 和 admin API 留在下游。

## 扩展接口组织

扩展接口按请求安全决策链组织，而不是按页面或数据库表组织：

```text
Authenticate -> Build Context -> Authorize -> Project Config -> Execute -> Audit
```

主包只定义稳定 Protocol、默认 no-op 实现和 FastAPI dependency 接线；下游企业包实现具体 provider、store 和 admin API。route 不应直接依赖 `datus_enterprise` 的实现类。

### 接口分组

| 接口 | 职责 | 默认实现 | 企业实现 |
| --- | --- | --- | --- |
| `AuthProvider` | 认证请求并构造 `AppContext` | `NoAuthProvider` | MVP 支持两种最小企业接入：网关可改时用反向代理签名 header provider；网关不可改时由 Datus 用 Bearer access token 调企业用户信息接口 |
| `AuthorizationProvider` | 判断模块、资源、session、artifact 是否可访问 | 本地 allow | RBAC/ABAC/临时授权/审批状态 |
| `ConfigProjector` | 生成请求级 `AgentConfig` clone、过滤 datasource、注入 principal | 返回原配置 clone | datasource grant、tool deny、SQL policy principal |
| `SessionOwnerStore` | 记录和查询 session/task owner | 内存或 SQLite 兼容 | Postgres metadata |
| `ArtifactAclStore` | 查询 artifact ACL 和可见列表 | manifest 兼容 | Postgres artifact metadata |
| `AuditSink` | 写入 allow/deny、管理操作、SQL 决策审计 | no-op | Postgres/OpenTelemetry/SIEM |
| `QuotaLimiter` | 检查和提交 quota/usage | no-op | Redis/Postgres quota |

第一阶段最小接口集为 `AuthProvider`、`AuthorizationProvider`、`ConfigProjector`、`SessionOwnerStore`、`AuditSink`。`QuotaLimiter`、`ArtifactAclStore`、`SecretProvider`、外部 policy engine 可在后续阶段拆出。

当前第一阶段骨架实现状态：

- 主包 `datus/api/enterprise/` 定义稳定 dataclass、Protocol、默认 local-compatible 实现、动态 loader 和 `require_module()` dependency。
- 企业包 `datus_enterprise.auth_provider.SignedHeaderAuthProvider` 已提供生产反向代理签名 header 身份 provider 初版：网关完成 SSO/JWT/OIDC 校验后，用 HMAC-SHA256 签名 `user_id`、project、roles、permissions 和 principal 等 header，Datus 后端校验签名、时间戳和安全 ID 后构造 `AppContext`，不信任裸 `X-Datus-User-Id`。
- `AppContext` 已扩展 `roles`、`permissions`、`datasource_grants`、`is_admin` 字段；本地 `NoAuthProvider` 继续留空这些字段。
- `enterprise.enabled=true` 时，启动期必须配置生产 `api.auth_provider.class`，并显式配置 `enterprise.authorization_provider`、`enterprise.datasource_grant_store` 和 `enterprise.audit_sink`；缺失时 fail closed。`enterprise.config_projector` 的协议和 loader 已存在，但阶段 4 才接入 datasource grant/request-level projection 执行路径，阶段 1 未配置时使用 passthrough skeleton，避免把用户级 projection 缓存在 project 级 `DatusService` 中。
- 企业模式下 `DatusService` cache key 使用 `enterprise:{project_id}`，但传入服务内部的 `project_id` 保持不带 cache 前缀的项目标识，避免污染会话、日志和下游存储语义。
- `SessionOwnerStore` 协议已覆盖 owner 写入、查询、删除和按用户列出 session；默认提供进程内实现和 SQLite `session_owners` 骨架。chat 运行中 task、磁盘 session scope 和 session owner 校验已进入阶段 2 接线，长期多 worker 状态外部化仍需后续阶段推进。

### 核心协议形态

授权接口统一接收 action 和 resource：

```python
@dataclass(frozen=True)
class ResourceRef:
    type: str
    id: str | None = None
    project_id: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AccessDecision:
    allowed: bool
    reason: str | None = None
    code: str | None = None
    audit: dict[str, Any] = field(default_factory=dict)


class AuthorizationProvider(Protocol):
    async def check(self, ctx: AppContext, action: str, resource: ResourceRef) -> AccessDecision:
        ...

    async def allowed_datasources(self, ctx: AppContext) -> dict[str, Any]:
        ...
```

配置投影接口统一处理 datasource grant 和 principal：

```python
@dataclass(frozen=True)
class ProjectionInput:
    ctx: AppContext
    base_config: AgentConfig
    operation: str
    requested_datasource: str | None = None
    requested_catalog: str | None = None
    requested_database: str | None = None
    requested_schema: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProjectionResult:
    config: AgentConfig
    principal: dict[str, Any]
    datasource_grants: dict[str, Any]
    denied_reason: str | None = None


class ConfigProjector(Protocol):
    async def project(self, request: ProjectionInput) -> ProjectionResult:
        ...
```

审计接口统一记录安全决策：

```python
@dataclass(frozen=True)
class AuditEvent:
    user_id: str | None
    action: str
    resource_type: str
    resource_id: str | None
    decision: str
    reason: str | None = None
    request_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class AuditSink(Protocol):
    async def write(self, event: AuditEvent) -> None:
        ...
```

### 注册与配置

沿用当前 `api.auth_provider.class` 和 `agent.sql_policy.provider` 的动态加载风格：

```yaml
api:
  auth_provider:
    class: datus_enterprise.auth_provider:UserInfoBearerAuthProvider
    kwargs:
      userinfo_url: https://sso.example.internal/api/userinfo
      timeout_seconds: 3
      user_id_field: user_id
      email_field: email
      display_name_field: name

enterprise:
  authorization_provider:
    class: datus_enterprise.rbac.service:RbacAuthorizationProvider
  datasource_grant_store:
    class: datus.api.enterprise.defaults:SqliteEnterpriseDatasourceGrantStore
    kwargs:
      db_path: .datus/enterprise.db
  config_projector:
    class: datus_enterprise.projection:DatasourceGrantProjector
  audit_sink:
    class: datus_enterprise.audit:PostgresAuditSink
  quota_limiter:
    class: datus_enterprise.quota:RedisQuotaLimiter
```

生产企业模式下，缺失必要 provider 应 fail closed。本地 `NoAuthProvider` 模式继续使用默认 no-op 实现保持兼容。

### FastAPI 接入方式

route 只表达权限需求，不直接写 RBAC 规则：

```python
@router.get("/dashboards")
async def list_dashboards(
    svc: ServiceDep,
    ctx: Annotated[AppContext, Depends(require_module("module.dashboard.view"))],
):
    ...
```

资源级操作使用 helper：

```python
await require_session_access(ctx, session_id=request.session_id, action="stop")
await require_artifact_access(ctx, artifact_type="dashboard", slug=slug, action="query")
projection = await project_request_config(ctx, svc.agent_config, operation="dashboard.query", ...)
```

不要把 `ChatHooks.pre_chat()` 变成万能安全接口。它适合宿主系统做余额检查、业务预检和 usage 上报；核心授权、投影、审计必须走统一扩展接口。

## 请求上下文

目标上下文：

```python
@dataclass
class AppContext:
    user_id: str | None = None
    project_id: str | None = None
    roles: list[str] = field(default_factory=list)
    permissions: set[str] = field(default_factory=set)
    datasource_grants: dict[str, Any] = field(default_factory=dict)
    config: AgentConfig | None = None
    principal: dict[str, Any] = field(default_factory=dict)
    is_admin: bool = False
```

字段语义：

| 字段 | 语义 |
| --- | --- |
| `user_id` | 企业内员工身份。用于 session owner、审计、principal。 |
| `project_id` | Datus 项目/workspace 标识。可继续映射当前 `DatusService` project。 |
| `roles` | 用户在当前企业上下文下的角色。 |
| `permissions` | 角色权限和用户直接授权合并后的模块权限集合。 |
| `datasource_grants` | 当前用户可访问的数据源及细粒度范围。 |
| `config` | 认证 provider 或 dependency 预加载的请求配置。 |
| `principal` | 传给 SQL policy 的业务属性，包含身份、组织、部门、数据范围等。 |
| `is_admin` | 管理员快捷标识；实际授权仍以 permission 为准。 |

上下文中的 `user_id`、`project_id` 必须使用稳定、可审计的 ID。若用于文件路径 scope，需要先转换成安全 slug，不能直接拼接外部输入。

## 认证设计

### MVP：企业 access token + userinfo provider

如果企业网关/反向代理可改，推荐让网关完成 SSO/JWT/OIDC 校验，并使用 `datus_enterprise.auth_provider.SignedHeaderAuthProvider` 向 Datus 传递签名身份 header。

如果网关不可改，MVP 身份方案改为 Datus 自己校验 `Authorization: Bearer <access_token>`，用该 token 调企业用户信息接口，拿到稳定用户身份后构造 `AppContext`。建议新增 `datus_enterprise.auth_provider.UserInfoBearerAuthProvider`：

- 从 `Authorization: Bearer <access_token>` 读取 access token。
- 调用企业用户信息接口，例如 `/userinfo`、`/current-user` 或内部 IAM 用户详情接口。
- 从用户信息响应中映射 `user_id`、email、display name、department、employee id 等字段。
- 不直接信任请求体、前端传入的 roles、permissions 或 datasource grants。
- 从 Datus 自己的 RBAC store 重新加载用户状态、角色、权限、数据源授权。
- 用户被禁用、access token 无效、用户信息接口失败、生产认证接线缺失或系统处于停用维护状态时返回 401/403 或 fail closed。
- access token、用户信息接口响应原文和任何 secret 不得写入 session、trace、tool result、prompt、audit 明文字段或错误信息。

用户信息接口只负责“这个人是谁”。Datus 内部模块权限、数据源授权和 artifact ACL 仍由 Datus metadata store 决定，避免把企业 IAM 返回字段直接当作 Datus 授权事实。

网关可改时的签名 header 方案仍作为推荐部署形态之一：

- 网关负责读取和校验用户登录态、OIDC/JWT、企业 SSO 或其他内部身份凭证。
- 网关向 Datus 注入 `X-Datus-User-Id`、可选 `X-Datus-Project-Id`、roles、permissions、principal、email、display name 等 header。
- 网关必须用共享密钥对 method、path、timestamp 和身份 header 做 HMAC-SHA256 签名，并传入 `X-Datus-Timestamp` 和 `X-Datus-Signature`。
- Datus 后端校验签名、时间窗口和安全 ID 后构造 `AppContext`。

无论采用哪种方案，生产环境都必须保证裸 `X-Datus-User-Id`、未签名 roles、permissions、principal 一律不能作为生产身份依据。若使用网关签名 header 方案，还必须保证 Datus API 不能被公网或普通客户端绕过网关直连；推荐用内网安全组、mTLS、Ingress allowlist 或 sidecar 网络策略收口。

直接在 Datus 后端校验 JWT/JWKS、key rotation、issuer/audience/kid 校验和 JWKS cache 不进入 MVP，作为后续身份 provider 扩展。

### 生产部署形态

MVP 支持前两种形态，第三种作为后续扩展：

| 形态 | 说明 | 风险控制 |
| --- | --- | --- |
| Bearer access token + userinfo | Datus 从请求读取 access token，并调用企业用户信息接口换取用户身份 | access token 不落日志；用户信息接口失败时 fail closed；Datus RBAC store 仍是授权事实来源。 |
| 反向代理身份 | 网关完成 SSO 和 token 校验，Datus 只信任网关注入的签名 header | header 必须有 HMAC/签名或 mTLS 边界，禁止公网直接访问后端。 |
| OIDC/JWKS | Datus 后端直接校验 JWT/JWKS | 后续 provider；需要校验 issuer/audience/kid/exp，缓存 JWKS，处理 key rotation。 |

后续企业能力可增加 SAML、SCIM、服务账号/API token、MFA/IP allowlist、IdP group 到 Datus role 映射。

## Service Cache 隔离

当前 cache key 是：

```text
project_id 或 default
```

企业版目标 key：

```text
enterprise:{project_id}
```

建议封装成 helper，避免分散拼接：

```python
def service_cache_key(ctx: AppContext) -> str:
    project = require_safe_key(ctx.project_id or "default")
    return f"enterprise:{project}"
```

兼容策略：

- `NoAuthProvider` 模式继续使用当前 `default`/`project_id` 行为。
- 生产企业模式使用 `enterprise:{project_id}`，本地兼容模式继续使用当前 `default`/`project_id` 行为。
- `AuthProvider.on_evict()` 目前签名是 `project_id -> evict`，企业版需要按 enterprise key evict，避免配置刷新误伤其他运行模式。

验收断言：

- 企业生产模式和本地 `NoAuthProvider` 模式的 cache key 语义清晰，不互相污染。
- 企业配置更新只影响当前企业 scope 下的 service 实例。
- 有 active task 的 service 仍遵循当前延迟 shutdown 逻辑，但隔离在企业 key 内。

## API 组织

API 按调用者视角和权限边界组织，不按 RBAC 表或数据库表组织。普通业务 API 不携带企业上下文字段，企业上下文来自部署配置和认证后的 `AppContext`。

推荐总结构：

```text
/api/v1
  /me/*                 # 当前登录用户自己的身份、权限、可见能力
  /chat/*               # 普通运行时 chat 能力
  /datasources/*        # 当前用户可见的数据源目录
  /sql/*                # SQL 执行器能力
  /reports/*            # 报表访问、查询、导出
  /dashboards/*         # 仪表盘访问、查询、导出
  /kb/*                 # 知识库能力
  /mcp/*                # MCP 能力
  /admin/*              # 企业管理员 API
  /system/*             # 系统内部和部署运维 API，默认不开放给前端用户
  /internal/*           # worker/webhook/系统内部 API
```

### `/me`

`/me` 给前端初始化和菜单渲染使用，不做管理操作：

```text
GET /api/v1/me
GET /api/v1/me/permissions
GET /api/v1/me/datasource-grants
GET /api/v1/me/features
GET /api/v1/me/sessions
GET /api/v1/me/usage
```

返回当前用户在企业上下文下的 roles、permissions、features、datasource grants 摘要。前端隐藏菜单只依赖它做体验优化，不能替代后端授权。

当前已注册 `/api/v1/me`、`/api/v1/me/permissions`、`/api/v1/me/datasource-grants`、`/api/v1/me/features`、`/api/v1/me/sessions` 和 `/api/v1/me/usage`，只读取认证后 `AppContext`、当前用户 session scope 和当前用户 quota usage，不接受前端传入 roles、permissions 或 datasource grant。

### 普通运行时 API

运行时 API 使用当前 `AppContext` 的 `user_id/project_id`：

```text
POST   /api/v1/chat/stream
POST   /api/v1/chat/feedback
POST   /api/v1/chat/resume
POST   /api/v1/chat/stop
POST   /api/v1/chat/user_interaction
POST   /api/v1/chat/insert
POST   /api/v1/chat/tool_result
GET    /api/v1/chat/sessions
GET    /api/v1/chat/history
DELETE /api/v1/chat/sessions/{session_id}
POST   /api/v1/chat/sessions/{session_id}/compact
```

数据源目录使用产品语义命名。现有 `/api/v1/database/list` 可保留兼容层，新接口建议为：

```text
GET /api/v1/datasources
GET /api/v1/datasources/{datasource_id}/catalogs
GET /api/v1/datasources/{datasource_id}/databases
GET /api/v1/datasources/{datasource_id}/schemas
GET /api/v1/datasources/{datasource_id}/tables
GET /api/v1/datasources/{datasource_id}/tables/{table_id}
```

SQL 执行器独立于 CLI route：

```text
POST /api/v1/sql/execute
POST /api/v1/sql/stop
GET  /api/v1/sql/tasks/{task_id}
```

报表和仪表盘区分 view、query、export：

```text
GET  /api/v1/reports
GET  /api/v1/reports/{slug}
GET  /api/v1/reports/{slug}/html
POST /api/v1/reports/{slug}/query
POST /api/v1/reports/{slug}/export

GET  /api/v1/dashboards
GET  /api/v1/dashboards/{slug}
GET  /api/v1/dashboards/{slug}/html
POST /api/v1/dashboards/{slug}/query
POST /api/v1/dashboards/{slug}/export
```

`view` 权限只表示可看 list/detail/html，不自动包含实时查询或导出。

### `/admin`

`/admin` 只管理当前企业上下文：

```text
GET    /api/v1/admin/users
POST   /api/v1/admin/users
GET    /api/v1/admin/users/{user_id}
PUT    /api/v1/admin/users/{user_id}
POST   /api/v1/admin/users/{user_id}/disable
POST   /api/v1/admin/users/{user_id}/enable

GET    /api/v1/admin/roles
POST   /api/v1/admin/roles
GET    /api/v1/admin/roles/{role_id}
PUT    /api/v1/admin/roles/{role_id}
DELETE /api/v1/admin/roles/{role_id}
PUT    /api/v1/admin/roles/{role_id}/permissions
GET    /api/v1/admin/users/{user_id}/roles
PUT    /api/v1/admin/users/{user_id}/roles

GET    /api/v1/admin/datasource-grants
POST   /api/v1/admin/datasource-grants
GET    /api/v1/admin/datasource-grants/{grant_id}
PUT    /api/v1/admin/datasource-grants/{grant_id}
DELETE /api/v1/admin/datasource-grants/{grant_id}

GET    /api/v1/admin/artifacts
GET    /api/v1/admin/artifacts/{artifact_type}/{slug}/acl
PUT    /api/v1/admin/artifacts/{artifact_type}/{slug}/acl

GET    /api/v1/admin/sessions
GET    /api/v1/admin/sessions/{session_id}
POST   /api/v1/admin/sessions/{session_id}/stop
DELETE /api/v1/admin/sessions/{session_id}

GET    /api/v1/admin/audit-logs
GET    /api/v1/admin/audit-logs/export
GET    /api/v1/admin/quotas
PUT    /api/v1/admin/quotas
GET    /api/v1/admin/usage
```

每组管理 API 使用显式 permission，例如 `module.admin.users`、`module.admin.roles`、`module.admin.datasources`、`module.admin.sessions`、`module.admin.audit`、`module.admin.audit.export`。不要用一个硬编码超级用户绕过所有管理权限。

### `/system` 与 `/internal`

`/system` 不面向普通浏览器前端，只保留给系统内部和部署运维能力：

```text
GET  /api/v1/system/health
GET  /api/v1/system/status
GET  /api/v1/system/metrics
POST /api/v1/system/cache/evict
```

`/internal` 面向 worker、webhook 和系统内部调用，不给浏览器前端直接使用：

```text
POST /api/v1/internal/tasks/{task_id}/events
POST /api/v1/internal/tasks/{task_id}/complete
POST /api/v1/internal/audit/batch
POST /api/v1/internal/usage/batch
```

内部 API 使用独立认证方式，例如 mTLS、内部 service token 或网关策略，不复用普通用户 JWT。

### 响应与错误码

继续兼容当前 `Result[T]` 风格，但企业级错误码必须稳定：

```json
{
  "success": false,
  "errorCode": "DATASOURCE_FORBIDDEN",
  "errorMessage": "Forbidden",
  "requestId": "req_..."
}
```

建议错误码：

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

对可猜测资源，例如 `session_id` 和 artifact slug，可将不存在和无权限统一返回 `RESOURCE_NOT_FOUND`，避免泄漏存在性。

## RBAC 权限模型

权限使用稳定字符串，不直接绑定具体 URL：

```text
module.chat
module.sql_executor
module.datasource_catalog
module.report.view
module.report.query
module.dashboard.view
module.dashboard.query
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
module.system.status
```

内置角色建议：

| 角色 | 权限 |
| --- | --- |
| `enterprise_admin` | 当前企业部署内所有 `module.*` 和管理权限。 |
| `analyst` | chat、SQL 执行器、数据源目录、报表/仪表盘查看与查询。 |
| `viewer` | 报表/仪表盘查看。 |
| `developer` | chat、SQL 执行器、KB、MCP、非生产数据源。 |

权限匹配可支持 glob，例如 `module.dashboard.*`、`module.admin.*`。建议持久化时存储展开后的 permission key，同时保留 role template 方便 UI 展示和迁移。

通用 dependency：

```python
def require_module(permission: str):
    async def dep(ctx: AppContextDep):
        if not rbac.can_access_module(ctx, permission):
            raise HTTPException(status_code=403, detail="Forbidden")
        return ctx
    return dep
```

推荐接入点：

| 路由/能力 | 权限 |
| --- | --- |
| `POST /api/v1/chat/stream`、`POST /api/v1/chat/feedback` | `module.chat` |
| `POST /api/v1/cli/sql_execute`、SQL 执行器入口 | `module.sql_executor` |
| `GET /api/v1/database/list`、catalog/schema/table 类接口 | `module.datasource_catalog` |
| report list/html/detail | `module.report.view` |
| report query 或保存 SQL 实时查询 | `module.report.query` |
| dashboard list/html/detail | `module.dashboard.view` |
| `POST /api/v1/dashboard/query` | `module.dashboard.query` |
| KB 导入/查询/管理 | `module.kb` |
| MCP server/tool 管理与调用 | `module.mcp` |
| config datasource/model 修改 | `module.config.edit` 或 admin 权限 |
| 用户/角色/授权/审计 API | `module.admin.*` |

通过 subagent 间接生成 report/dashboard/SQL 的场景，必须在 subagent dispatch 前做模块权限判断，防止用户通过自然语言绕过模块入口。

## 数据源授权

数据源 grant 支持角色和用户两级授权。示例：

```json
{
  "datasource": "finance_dw",
  "catalogs": ["prod"],
  "databases": ["finance"],
  "schemas": ["public", "mart"],
  "tables": ["fnd_*", "dim_date"],
  "allow_catalog": true,
  "allow_sql": true,
  "effect": "allow"
}
```

合并规则：

1. 角色 grant 提供基础授权。
2. 用户 grant 对未授权数据源可增加直接授权；对已有 role grant 只能收窄或显式拒绝。
3. `deny` 优先级高于 `allow`。
4. 没有 grant 时默认不可见、不可用。
5. 管理员可以配置为默认全量，但仍建议通过显式 grant 表达，便于审计。

MVP 数据模型采用**每个主体和数据源一条 grant**：`(subject_type, subject_id, datasource_key)` 唯一，所有 catalog/database/schema/table 范围和 allow/deny 细节写入 `scope_json`。后续如果要支持多条 scoped grant，必须先更新本节规则和迁移脚本，不能让两种解释同时存在。

冲突与写入规则：

- admin API 对同一 `(subject_type, subject_id, datasource_key)` 使用 upsert，不插入重复 grant。
- role grants 先合并，user grants 后合并；当前单条 flattened grant 不能表达复杂 OR 条件，因此 role allow 合并保留已有 scope 维度、同维度 pattern 做并集，跨维度按执行层的 AND 语义保守生效。
- user grant 对没有 role grant 的 datasource 可作为直接授权加入；对已有 datasource grant 只做 scope 收窄或显式拒绝，不能扩大该 datasource 的有效授权。
- 显式 `deny` 永远优先于 `allow`。
- 宽范围 allow 与窄范围 deny 同时命中时，窄范围 deny 生效。
- 宽范围 deny 与窄范围 allow 同时命中时，除非 `scope_json` 明确支持例外白名单，否则 deny 生效。
- admin API 必须校验 `subject_type`、`subject_id`、`datasource_key` 存在性、`scope_json` schema 和 effect 合法值；无法确定语义的 grant 直接拒绝保存。

后端执行点：

- catalog/database/schema/table list 只返回授权范围。
- chat request 中的 `datasource` 必须在授权列表内。
- 请求级 `AgentConfig.services.datasources` clone 后只保留授权 datasource。
- SQL policy principal 写入 `allowed_datasources`、`allowed_tables`、`user_id`、部门、项目或数据域等字段。
- dashboard/report query 使用同一份 grant 和 principal。
- direct SQL API 不能绕过 datasource grant。

注意：表名 glob 只适合作为粗粒度授权表达。真正执行 SQL 时仍要依赖 SQL parser/policy 或数据库原生权限做兜底。

## 会话与运行中任务隔离

当前持久化会话已经可以通过 `SessionManager(scope=user_id)` 分目录。企业内网 MVP 继续使用用户 scope：

```text
~/.datus/sessions/{project}/{user_id}/{session_id}.db
```

运行中 task 必须记录 owner：

```python
class ChatTask:
    session_id: str
    user_id: str
    project_id: str
    asyncio_task: asyncio.Task
```

必须校验 owner 的接口：

- `POST /api/v1/chat/resume`
- `POST /api/v1/chat/stop`
- `POST /api/v1/chat/user_interaction`
- `POST /api/v1/chat/insert`
- `POST /api/v1/chat/tool_result`
- `GET /api/v1/chat/history`
- `DELETE /api/v1/chat/sessions/{session_id}`
- `POST /api/v1/chat/sessions/{session_id}/compact`

规则：

- 普通用户只能操作同 `user_id` 的 task/session。
- 管理员必须有 `module.admin.sessions` 才能管理企业内 task/session。
- 找不到或无权限时建议返回统一错误，避免暴露其他用户 session 是否存在。
- 多 worker 下运行中 task 仍在进程内，MVP 需要 sticky session；长期外部化 task metadata 和 event buffer。

建议新增 `session_owners` 索引表：

```text
user_id, project_id, session_id, agent_name, status, created_at, updated_at
```

磁盘 scope 是隔离机制，`session_owners` 是查询、审计和管理员操作索引。

## AgentConfig 投影

chat 请求投影流程：

1. `AuthProvider` 构造 `AppContext`。
2. `require_module("module.chat")` 校验模块权限。
3. 校验 `request.datasource` 是否在 datasource grants 内。
4. deep copy `DatusService.agent_config`。
5. 删除未授权 datasource。
6. 设置 `agent_config.current_datasource`。
7. 将 datasource/table grants 写入 `agent_config.principal`。
8. 将可见表范围写入 scoped context 或 SQL policy principal。
9. 按模块权限可选叠加 tool deny，例如无 SQL 权限时禁用 direct SQL 工具。
10. 用 clone 创建 node/task。

禁止事项：

- 禁止直接修改缓存里的共享 `DatusService.agent_config`。
- 禁止只过滤 catalog list，不过滤执行路径。
- 禁止让 request body 自带 `principal` 覆盖服务端 principal。
- 禁止把未脱敏 datasource secret 写入 principal、session、trace 或 LLM prompt。

## 与 PermissionConfig 的关系

现有 `datus/tools/permission` 保留为 agent 工具安全层：

- 控制 `db_tools.read_query`、`db_tools.execute_write`、`filesystem_tools.*`、`skills.*`、`mcp.*` 等工具。
- 决定工具是否展示给 LLM。
- 支持 `allow` / `ask` / `deny`。

新增 RBAC 是 API 和业务模块入口的前置授权，不替代 tool permission。

示例：

- 用户有 `module.sql_executor`，只表示可以进入 SQL 功能。
- 是否能执行写 SQL，仍取决于 `db_tools.execute_write` tool permission、SQL policy 和数据库账号权限。
- 用户无 `module.dashboard.query`，即使 dashboard HTML 可见，也不能调用 dashboard query API 实时查数。
- 用户有 `module.chat` 但无 datasource grant，chat 不应能选择或推理未授权 datasource。

## SQL 与数据安全

执行层应复用并加强 `DBFuncTool.read_query()` 的安全链路：

- 只读 SQL 类型校验。
- 禁止多语句。
- scoped context 表范围校验。
- SQL policy principal 校验。
- 连接器层执行。

新增要求：

- dashboard/report 保存的 SQL 模板执行时，也必须带同一份 principal。
- direct SQL API 必须接入 datasource grant、SQL policy 和审计。
- 数据源授权必须传入 SQL policy，而不是只做 catalog 过滤。
- 生产数据源使用最小权限数据库账号，优先只读账号。
- 需要行级隔离时，由 SQL policy 注入组织、部门、项目或数据域过滤条件，或使用数据库原生 RLS。
- SQL result 进入 LLM、trace、audit 前按策略脱敏或摘要化。

## 产物访问控制

报表和仪表盘产物建议在 manifest 或 metadata 表中增加 ACL：

```json
{
  "owner_user_id": "user_1",
  "visibility": "private",
  "allowed_roles": ["analyst"],
  "datasources": ["finance_dw"]
}
```

`visibility` 取值：

| 值 | 语义 |
| --- | --- |
| `private` | 仅 owner 和管理员可见。 |
| `role` | 指定角色可见。 |
| `enterprise` | 当前企业内有模块权限的用户可见。 |

访问规则：

- list 接口只返回当前用户可见产物。
- html/detail 接口必须二次校验 slug 权限。
- query 接口必须同时满足产物权限、模块 query 权限和 datasource/table grant。
- 产物不存在和无权限建议统一返回 404 或通用 403，避免泄漏 slug。
- 产物依赖的数据源授权变化后，需要重新评估 query 权限；仅历史静态 HTML 可见不代表实时查询仍可执行。

## Metadata 存储

MVP 可先用 SQLite，生产建议 Postgres。基础表不带 `tenant_id` 维度；企业上下文来自部署配置，不作为每张 metadata 表的分区字段。

```sql
CREATE TABLE users (
  id TEXT PRIMARY KEY,
  external_id TEXT,
  email TEXT,
  display_name TEXT,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (external_id)
);

CREATE TABLE roles (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  built_in INTEGER NOT NULL DEFAULT 0,
  UNIQUE (name)
);

CREATE TABLE user_roles (
  user_id TEXT NOT NULL,
  role_id TEXT NOT NULL,
  PRIMARY KEY (user_id, role_id)
);

CREATE TABLE role_permissions (
  role_id TEXT NOT NULL,
  permission_key TEXT NOT NULL,
  PRIMARY KEY (role_id, permission_key)
);

CREATE TABLE datasource_grants (
  id TEXT PRIMARY KEY,
  subject_type TEXT NOT NULL,
  subject_id TEXT NOT NULL,
  datasource_key TEXT NOT NULL,
  scope_json TEXT NOT NULL,
  effect TEXT NOT NULL DEFAULT 'allow',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE session_owners (
  user_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  session_id TEXT NOT NULL,
  agent_name TEXT,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (project_id, session_id)
);

CREATE TABLE artifact_acl (
  artifact_type TEXT NOT NULL,
  slug TEXT NOT NULL,
  owner_user_id TEXT NOT NULL,
  visibility TEXT NOT NULL,
  allowed_roles_json TEXT NOT NULL,
  datasource_keys_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (artifact_type, slug)
);

CREATE TABLE audit_logs (
  id TEXT PRIMARY KEY,
  user_id TEXT,
  actor_type TEXT NOT NULL DEFAULT 'user',
  request_id TEXT,
  action TEXT NOT NULL,
  resource_type TEXT NOT NULL,
  resource_id TEXT,
  decision TEXT NOT NULL,
  reason TEXT,
  metadata_json TEXT,
  created_at TEXT NOT NULL
);
```

建议索引：

```sql
CREATE INDEX idx_users_status ON users (status);
CREATE INDEX idx_grants_subject ON datasource_grants (subject_type, subject_id);
CREATE UNIQUE INDEX idx_grants_subject_datasource ON datasource_grants (subject_type, subject_id, datasource_key);
CREATE INDEX idx_sessions_user ON session_owners (project_id, user_id, updated_at);
CREATE INDEX idx_artifact_owner ON artifact_acl (artifact_type, owner_user_id);
CREATE INDEX idx_audit_time ON audit_logs (created_at);
```

## 开发阶段

### 阶段 0：开关与兼容基线

目标：

- 增加 `enterprise.enabled` 或等价配置。
- 保持 `NoAuthProvider` 本地默认行为兼容。
- 定义生产 provider fail closed 行为。
- 建立 RBAC store/service 的最小接口和测试 fixture。

验收：

- 未启用企业模式时，现有 chat/session/permission 测试不变。
- 启用生产 provider 且无 token 时返回 401。
- 启用生产 provider 且缺少 user 时返回 401/403。

运行语义：

- `enterprise.enabled=false`：保持开源/本地兼容行为，允许 `NoAuthProvider`，不要求 RBAC store、AuthorizationProvider、ConfigProjector 全量接线。
- `enterprise.enabled=true`：必须使用生产 auth provider；缺少 provider、provider 初始化失败或 token 缺失时 fail closed，不信任裸 `X-Datus-User-Id`。
- `enterprise.enabled=true`：RBAC store、AuthorizationProvider、ConfigProjector、AuditSink 至少要有可执行实现或显式 fail-closed stub，不能静默降级为 allow。
- 企业模式开关只决定运行安全链是否启用，不引入 `tenant_id` 维度，也不作为业务 API 参数传递。

### 阶段 1：认证、上下文与 service cache

目标：

- 实现生产 `AuthProvider`；网关不可改时 MVP 使用 Bearer access token + userinfo provider，网关可改时可使用反向代理签名 header provider，直接 OIDC/JWKS provider 后续补齐。
- 扩展 `AppContext`。
- 从 RBAC store 加载 roles、permissions、datasource grants。
- `DatusServiceCache` 使用 enterprise-aware key。
- 调整 eviction callback 支持 enterprise-aware cache key。

验收：

- 企业生产模式和本地兼容模式不共享 `DatusService`。
- 用户被禁用、生产认证接线缺失或系统处于停用维护状态后，新请求被拒绝。
- 角色变更后新请求读取最新权限。

### 阶段 2：会话与运行中任务隔离

目标：

- `ChatTask` 增加 `user_id` / `project_id`。
- `start_chat()` 写入 owner。
- `resume`、`stop`、`user_interaction`、`insert`、`tool_result` 校验 owner。
- session scope 使用 `user_id`。
- 增加 `session_owners` 记录。

当前接线状态：

- `ChatTask.owner_user_id` 记录 raw owner，`ChatTaskManager.start_chat()` 写入 `SessionOwnerStore`。
- API 磁盘 session 读写使用由 `user_id` 生成的安全 scope，避免把外部身份直接拼入路径。
- `chat/resume`、`chat/stop`、`chat/user_interaction`、`chat/insert`、`chat/tool_result`、`chat/history`、`chat/sessions/{session_id}` delete/compact 已接 owner 校验。
- 默认 SQLite `session_owners` 仍是单节点骨架；企业生产多 worker 应替换为 Postgres 等共享 metadata store，并继续满足 sticky session 或事件缓冲外部化要求。

验收：

- 用户 A 无法 resume/stop/insert 用户 B 的 session。
- 用户 A 无法向用户 B 的 interaction broker 或 tool channel 提交结果。
- 管理员只有具备 `module.admin.sessions` 时可管理企业内 session。
- 用户 scope 必须参与 owner 判断，避免 session owner 边界被简化成只看 `session_id`。

### 阶段 3：模块 RBAC

目标：

- 新增 `require_module()` dependency。
- 接入 chat、catalog、report、dashboard、KB、MCP、config/admin routes。
- subagent dispatch 前校验对应模块权限。

当前阶段 3 主包接线状态：

- `chat` route 已接入 `module.chat`，覆盖 stream、feedback、resume、stop、session list/history/delete/compact、user interaction、insert 和 tool result。
- chat subagent dispatch 前已按内置/自定义 subagent 类型叠加权限：`gen_sql` 使用 `module.sql_executor`，report 类 subagent 使用 `module.report.query`，dashboard 类 subagent 使用 `module.dashboard.query`。
- datasource catalog route 已接入 `module.datasource_catalog`，覆盖当前 `/api/v1/catalog/list`。
- 直接 SQL executor route 已接入 `module.sql_executor`，覆盖 `/api/v1/sql/execute` 和 `/api/v1/sql/stop_execute`。
- report route 已接入 `module.report.view`，覆盖当前 `/api/v1/report/detail`，并通过 enterprise artifact route 覆盖 `/api/v1/reports`、`/api/v1/reports/{slug}`、`/api/v1/reports/{slug}/html`。
- dashboard route 已接入 `module.dashboard.view` 和 `module.dashboard.query`，覆盖当前 `/api/v1/dashboard/detail`、`/api/v1/dashboard/query`，并通过 enterprise artifact route 覆盖 `/api/v1/dashboards`、`/api/v1/dashboards/{slug}`、`/api/v1/dashboards/{slug}/html`。
- config/model route 已接入 `module.config.view` 和 `module.config.edit`，覆盖 `/api/v1/config/agent`、`/api/v1/models`、配置更新接口和连接探测接口。
- KB route 已接入 `module.kb`，覆盖 KB bootstrap、platform docs bootstrap 和对应 cancel 接口。
- MCP route 已接入 `module.mcp`，覆盖 MCP server/tool/filter 的列表、管理和调用接口。
- 当前已注册的 datasource admin route `/api/v1/admin/datasources`、`/api/v1/admin/datasource-default` 和 `/api/v1/admin/datasource-grants` 已接入 `module.admin.datasources`，用于项目级数据源清单、默认数据源管理和 datasource grant metadata 管理。
- 当前已注册的 user/role admin route 已分别接入 `module.admin.users` 和 `module.admin.roles`，用于阶段 6 的用户状态、role metadata 和 role permission set 管理。
- admin sessions、artifacts ACL、audit query/export、quota metadata/usage 和 secret reference API 已进入阶段 6 接线；`/api/v1/system/status` 已使用 `module.system.status` 接入只读系统状态。当前已将 user-role metadata、role permission set 和 role/user datasource grants 在企业模式新请求中合并回 `AppContext.roles`、`AppContext.permissions`、`AppContext.datasource_grants` 和 `principal`，但长期生产仍应使用共享 metadata store。direct SQL 和 dashboard query 已复用请求级 projection、grant scope、SQL policy principal 与审计；`/api/v1/models` 和 chat stream/feedback 已支持服务端 `principal.model_policy` provider/model allowlist 初版，未授权模型不能在目录中展示，也不能启动 chat task；chat stream/feedback 已接入请求启动级 quota；admin audit export 已接入导出配额；report artifact 当前是预渲染静态 bundle，没有 agent-only live query endpoint。

验收：

- 无 `module.report.view` 不能访问 report list/html/detail。
- 无 `module.dashboard.query` 不能执行 dashboard query。
- 无 `module.datasource_catalog` 不能列 catalog/schema/table。
- 无 `module.chat` 不能启动 chat 或 feedback。
- 仅有 `module.chat` 不能通过 chat subagent dispatch 绕过 SQL executor/report query/dashboard query 权限。
- 无 `module.admin.datasources` 不能调用当前已注册的 datasource admin route。

### 阶段 4：数据源授权与 config projection

目标：

- 实现 role/user datasource grants。
- catalog list 过滤未授权 datasource/table。
- chat request.datasource 校验。
- 请求级 `AgentConfig` clone 只保留授权 datasource。
- grants 注入 principal。

当前接线状态：

- 已新增可配置的 `DatasourceGrantProjector`，支持按 `AppContext.datasource_grants` 生成请求级 `AgentConfig` clone、过滤未授权 datasource、选择授权默认 datasource，并向 principal 注入 `user_id`、`datasource`、`allowed_datasources` 和 `datasource_grants`。
- `/api/v1/chat/stream` 已通过统一 config projection 校验 `request.datasource`，未授权 datasource 以 SSE error 返回，并使用 projection clone 启动 chat task，避免污染缓存的 `DatusService.agent_config`。
- `/api/v1/catalog/list` 已接入 datasource-level projection：显式请求未授权 datasource 返回 403，未指定 datasource 时使用授权后的默认 datasource，并按 grant 中的 catalog/database/schema/table scope 裁剪返回的目录结果。
- `/api/v1/sql/execute` 已接入请求级 datasource projection 和执行前兜底：直接 SQL 使用投影后的 `AgentConfig` 执行，显式或默认 database 必须在 grant 范围内，手写 SQL 的 table/schema/database scope 会在执行前校验，并复用 SQL policy principal 进行 deny/rewrite。
- dashboard/report projection 和执行审计兜底仍未完成，继续按阶段 4/5/6 后续子阶段推进。

验收：

- 用户只能看到授权 datasource。
- 用户指定未授权 datasource 返回 403。
- LLM 工具列表、datasource prompt context、schema/RAG 检索不包含未授权 datasource。
- 直接 SQL API 和 chat prompt 都不能使用未授权 datasource。

### 阶段 5：SQL policy、产物查询与审计兜底

目标：

- 将 datasource/table grants 转成 SQL policy principal。
- dashboard query/report query/direct SQL 传入 principal。
- 未授权表查询被拒绝。
- 关键 allow/deny 写入 audit log。

验收：

- 手写 SQL 引用未授权表失败。
- dashboard 保存模板引用未授权表失败。
- SQL policy 缺失必要 principal 字段时拒绝执行。
- audit log 能查到拒绝原因和资源标识。

### 阶段 6：管理 API

目标：

- 用户管理。
- 角色管理。
- 权限管理。
- 数据源授权管理。
- 产物 ACL 管理。
- 审计日志查询。

当前接线状态：

- 已新增 `EnterpriseUserStore` 协议，以及本地兼容的内存实现和单节点 SQLite `enterprise_users` 骨架；企业模式下可通过 `enterprise.user_store.class` 替换为生产 metadata store。
- 已注册 `/api/v1/admin/users`、`/api/v1/admin/users/{user_id}`、`/api/v1/admin/users/{user_id}/disable` 和 `/api/v1/admin/users/{user_id}/enable`，统一要求 `module.admin.users`，企业上下文只来自认证后的 `AppContext`，不从路径或请求体传入。
- 用户管理接口返回稳定 `Result` 错误码：`USER_ID_INVALID`、`RESOURCE_NOT_FOUND`、`USER_LIST_FAILED`、`USER_READ_FAILED`、`USER_UPSERT_FAILED`、`USER_UPDATE_FAILED`；管理 allow/deny 使用 `module.admin.users` 写入审计，metadata 只包含脱敏的新旧摘要。
- `enterprise.enabled=true` 的新请求会检查用户状态：缺少 `user_id` 返回 `AUTH_REQUIRED`，已存在且被禁用的用户返回 `USER_DISABLED`，用户状态存储不可用时返回 `USER_STATUS_UNAVAILABLE` 并审计 deny。未录入用户仍允许通过，以兼容已有 identity-only auth provider；若 role/grant metadata 读取失败或用户-role 绑定指向缺失 role，则 fail closed 并审计 deny。
- 已新增 `EnterpriseRoleStore` 协议，以及本地兼容的内存实现和单节点 SQLite `enterprise_roles` / `enterprise_role_permissions` / `enterprise_user_roles` 骨架；企业模式下可通过 `enterprise.role_store.class` 替换为生产 metadata store。
- 已注册 `/api/v1/admin/roles`、`/api/v1/admin/roles/{role_id}`、`/api/v1/admin/roles/{role_id}/permissions` 和 `/api/v1/admin/users/{user_id}/roles`，统一要求 `module.admin.roles`；role metadata、permission set 与用户-role 绑定会在后续新请求中自动合并进 `AppContext.roles` 和 `AppContext.permissions`，不会复用旧请求上下文。
- 角色管理接口返回稳定 `Result` 错误码：`ROLE_ID_INVALID`、`ROLE_NAME_INVALID`、`ROLE_PERMISSION_INVALID`、`USER_ID_INVALID`、`RESOURCE_NOT_FOUND`、`ROLE_LIST_FAILED`、`ROLE_READ_FAILED`、`ROLE_UPSERT_FAILED`、`ROLE_UPDATE_FAILED`、`ROLE_DELETE_FAILED`、`ROLE_DELETE_FORBIDDEN`、`ROLE_BINDINGS_READ_FAILED`、`USER_READ_FAILED`、`USER_ROLES_READ_FAILED`、`USER_ROLES_UPDATE_FAILED`；管理 allow/deny 使用 `module.admin.roles` 写入审计，metadata 只包含脱敏的新旧摘要。
- 已新增 `EnterpriseDatasourceGrantStore` 协议，以及本地兼容的内存实现和单节点 SQLite `enterprise_datasource_grants` 骨架；`enterprise.enabled=true` 时必须显式配置 `enterprise.datasource_grant_store.class`，避免管理 API 写入进程内临时授权状态。
- 已注册 `/api/v1/admin/datasource-grants` 和 `/api/v1/admin/datasource-grants/{subject_type}/{subject_id}/{datasource_key}`，统一要求 `module.admin.datasources`；当前切片管理 `user` / `role` datasource grant metadata，写入前校验 subject 和 datasource，使用 upsert 保证同一 `(subject_type, subject_id, datasource_key)` 只有一条 grant。role grant 先合并、user grant 后合并，任一 deny 都覆盖 allow；合并后的结果会在后续新请求中进入 `AppContext.datasource_grants` 和 `principal.datasource_grants`。
- 数据源授权管理接口返回稳定 `Result` 错误码：`DATASOURCE_GRANT_FILTER_INVALID`、`DATASOURCE_GRANT_ID_INVALID`、`DATASOURCE_GRANT_SUBJECT_INVALID`、`DATASOURCE_GRANT_DATASOURCE_INVALID`、`DATASOURCE_GRANT_EFFECT_INVALID`、`DATASOURCE_GRANT_SCOPE_INVALID`、`DATASOURCE_NOT_FOUND`、`RESOURCE_NOT_FOUND`、`USER_READ_FAILED`、`ROLE_READ_FAILED`、`DATASOURCE_GRANT_LIST_FAILED`、`DATASOURCE_GRANT_READ_FAILED`、`DATASOURCE_GRANT_UPSERT_FAILED`、`DATASOURCE_GRANT_DELETE_FAILED`；管理 allow/deny 使用 `module.admin.datasources` 写入审计，metadata 只包含脱敏的新旧摘要和 scope pattern，不记录 datasource 连接配置或 secret。
- 已新增 `EnterpriseQuotaStore` 协议，以及本地兼容的进程内 `InMemoryEnterpriseQuotaStore`；企业模式下可通过 `enterprise.quota_store.class` 替换为生产 quota/usage metadata store。当前已将直接 SQL 执行、dashboard 实时查询、chat stream、feedback 和 admin audit export 入口分别接入 `sql.execute`、`dashboard.query`、`chat.stream`、`chat.feedback` 和 `admin.audit.export` 配额消耗，缺少 quota store、quota 检查失败或超额都会在执行前返回稳定错误并写入 audit；chat provider/model allowlist 已有服务端 principal 初版，但 chat token、模型 token、report/dashboard export 和并发类配额仍按后续切片接入。
- 已注册 `/api/v1/admin/quotas` 和 `/api/v1/admin/usage`，统一要求 `module.admin.quotas`；quota upsert 校验 `subject_type`、`subject_id`、`resource`、`limit`、`window_seconds` 和 `enabled`，审计只写 quota 摘要，不记录执行结果或敏感配置。
- quota 管理接口返回稳定 `Result` 错误码：`QUOTA_FILTER_INVALID`、`QUOTA_STORE_UNAVAILABLE`、`QUOTA_LIST_FAILED`、`QUOTA_UPSERT_FAILED`、`USAGE_LIST_FAILED`、`QUOTA_SUBJECT_INVALID`、`QUOTA_RESOURCE_INVALID`、`QUOTA_LIMIT_INVALID`、`QUOTA_WINDOW_INVALID`、`QUOTA_ENABLED_INVALID`。
- 已新增单节点 `SqliteAuditSink`，实现 `AuditSink.write()` 和 admin audit 路由使用的 `query_events()`；企业 MVP 可用 SQLite 真实落审计，生产多 worker/HA 部署仍应替换为 Postgres、SIEM 或其他集中审计 sink。
- 已新增 `EnterpriseSecretStore` 协议，以及本地兼容的进程内 `InMemoryEnterpriseSecretStore`；企业模式下可通过 `enterprise.secret_store.class` 替换为生产 secret reference store。当前切片只管理 secret 引用 metadata，不保存 secret 明文，不把 secret reference 解析接入 datasource/model 配置路径。
- 已注册 `/api/v1/admin/secrets` 和 `/api/v1/admin/secrets/{name}`，统一要求 `module.admin.secrets`；secret upsert 只保存 `provider`、`reference`、描述和启用状态，响应与审计只返回 `ref_hint`，不回显完整 reference，更不接收或返回 secret value。
- secret 管理接口返回稳定 `Result` 错误码：`SECRET_FILTER_INVALID`、`SECRET_STORE_UNAVAILABLE`、`SECRET_LIST_FAILED`、`SECRET_NAME_INVALID`、`SECRET_PROVIDER_INVALID`、`SECRET_REFERENCE_INVALID`、`SECRET_DESCRIPTION_INVALID`、`SECRET_ENABLED_INVALID`、`SECRET_READ_FAILED`、`SECRET_UPSERT_FAILED`、`SECRET_DELETE_FAILED`、`RESOURCE_NOT_FOUND`。
- 企业 MVP 配置样例已放在 `conf/agent.enterprise.mvp.yml.example`，覆盖生产 `AuthProvider`、RBAC/role/user/datasource grant stores、request-level config projector、session owner store、SQLite audit sink 和单进程 quota store。
- `enterprise.enabled=true` 时，旧版 `/auth/token`、`/workflows/run` 和 `/workflows/feedback` 入口返回 `ENTERPRISE_LEGACY_API_DISABLED`，避免旧 client-credential workflow API 绕过 `/api/v1` 的企业身份、授权、投影和审计链路。

验收：

- 只有具备对应 `module.admin.*` 的用户可调用管理 API。
- 角色和授权变更后新请求立即生效。
- 授权变更、拒绝事件和管理操作写入 audit log。

管理变更语义：

- 禁用用户后，新请求、长任务续写、session resume 和实时 query 必须拒绝；历史 audit、session ownership 和产物记录不自动删除。
- 管理员可按权限停止被禁用用户的运行中任务，但不能通过删除用户绕过审计留痕。
- 删除 role 前必须确认没有 `user_roles` 绑定；如支持强制删除，必须同时清理 `user_roles` 和 `role_permissions` 并写 audit。
- 修改 role permission 或 datasource grant 后，新请求必须重新加载权限；不要依赖已缓存的旧 `AppContext` 跨请求复用。
- 撤销 datasource grant 后，catalog/list、chat config projection、dashboard/report/direct SQL 的新请求立即不可用；静态产物是否可见继续由 artifact ACL 决定，但实时 query 必须重新校验 grant。
- 修改 artifact ACL 后，list/detail/query/export 的新请求立即按新 ACL 判定。
- 所有 admin mutation 必须写入 actor、target resource、decision、旧值摘要、新值摘要和 request_id；摘要必须脱敏，不记录 secret、完整连接串或大结果集。

## 测试计划

### 单元测试

- RBAC permission glob 匹配。
- 角色权限合并。
- 用户 grant 与角色 grant 合并。
- datasource grant deny 优先。
- datasource grant upsert 不产生重复语义。
- `can_access_session()` owner 判断。
- `can_access_artifact()` visibility 判断。
- user/project safe key 规范化。
- config projection 不修改原始 `DatusService.agent_config`。

### API 测试

- 无 token、生产认证/授权接线缺失、禁用用户。
- `enterprise.enabled=true` 但缺少生产 auth/RBAC/authorization 接线时 fail closed。
- 普通用户访问无权限模块返回 403。
- 用户 A 无法操作用户 B 运行中 task。
- catalog list 只返回授权 datasource。
- chat 指定未授权 datasource 失败。
- dashboard/report query 无权限时失败。
- admin API 非管理员失败。
- 禁用用户后新请求、resume 和实时 query 失败。
- 角色、permission、datasource grant、artifact ACL 变更后新请求立即按新规则生效。
- `tests/unit_tests/datus_enterprise/test_enterprise_mvp_smoke.py` 覆盖企业 MVP smoke：管理员写入 datasource grant，普通用户从服务端 store 刷新权限与授权，catalog 被 grant 裁剪，未授权 datasource 被拒绝，直接 SQL 使用投影后的 request-scoped config。
- `enterprise.enabled=true` 时旧版 `/auth/token` 和 `/workflows/run` 返回 `ENTERPRISE_LEGACY_API_DISABLED`。

### 回归测试

- 未启用企业 provider 时，`NoAuthProvider` 保持可用。
- 现有 `PermissionConfig` profile 行为不被 RBAC 改坏。
- 现有 `DBFuncTool.read_query()` 只读校验不被绕过。
- SQL policy principal 预检查仍覆盖 chat 路径。

### 安全测试

- 伪造 `session_id`。
- 伪造 `datasource`。
- 伪造企业上下文字段或 principal。
- artifact slug 路径穿越。
- dashboard query 引用未授权 SQL 模板。
- request body 试图覆盖 principal。
- 多 worker 下 SSE resume 跨 worker 行为与 sticky session 文档一致。

## 风险与决策

| 风险 | 建议 |
| --- | --- |
| 只做前端隐藏数据源会被 API 绕过 | 必须后端过滤 + 执行层 SQL policy。 |
| `session_id` 可猜测或泄露 | 运行中任务和磁盘会话都做 owner 校验。 |
| 多 worker 下 task 在进程内 | MVP 明确 sticky session；长期外部化 task/event store。 |
| 企业生产模式和本地/测试模式配置缓存串扰 | cache key 必须区分 enterprise 模式与本地兼容模式。 |
| admin 过度授权 | admin 也使用显式 permission，不用硬编码超级用户。 |
| SQL policy 只覆盖部分 read path | dashboard/report/direct SQL 路径都要接入同一执行层。 |
| datasource grant 只表达表级 | 先作为 MVP，列级权限和脱敏进入后续企业治理阶段。 |
| SQLite metadata 扩展受限 | MVP 可用 SQLite，企业试点建议直接 Postgres。 |

## 最小可交付 MVP

第一版不需要完整管理后台，建议最小范围：

1. Bearer access token + userinfo `AuthProvider`，或企业网关/反向代理签名 header `AuthProvider`。
2. `user_id/roles/permissions/datasource_grants` 上下文。
3. enterprise-aware `DatusServiceCache`。
4. 用户级 session scope 和运行中 chat task owner 校验。
5. 模块权限 dependency。
6. catalog list datasource 过滤。
7. chat 请求级 datasource 校验和 `AgentConfig` 投影。
8. SQL policy principal 注入。
9. 基础审计日志。

这一版完成后，应满足：

- 多用户会话彼此隔离。
- 普通用户不能访问被禁用的报表/仪表盘/SQL 执行器模块。
- 普通用户只能看到和使用授权数据源。
- 未授权数据源不能通过 agent prompt、direct API 或 dashboard/report query 绕过。

## 企业级后续能力

企业级目标不是“多几个权限表”，而是让 Datus 从本地 agent/API 服务升级为具备身份、资源、执行、成本、审计和运维边界的平台。建议按优先级推进。

### P1：运营硬边界

- 审计日志：登录、模块访问、数据源访问、SQL 执行、policy 改写、报表/仪表盘查询、授权变更、secret 操作、拒绝事件。
- 配额和限流：企业/用户/API token/模块/数据源/模型维度的请求数、token、并发、SQL 超时、返回行数。
- API token：scope、过期、轮换、撤销、最后使用时间，区分人类用户和机器调用方。
- Secret 管理：支持环境变量和外部 secret manager 引用，禁止 secret 进入 session、trace、tool result、prompt 和错误信息。
- 基础 admin API：用户、角色、授权、session、artifact、审计、quota、secret。

### P2：高可用与状态外部化

目标架构：

```text
Browser / Client
  -> API Gateway / Ingress
  -> Datus API Pods
  -> Redis: rate limit, task events, locks, short-lived cache
  -> Postgres: enterprise context, rbac, session index, audit, artifact metadata
  -> Object Storage: artifacts, exports, large traces
  -> Vector Store: enterprise/project/user/role-isolated KB indexes
  -> Data Sources
  -> LLM Providers
```

优先级：

1. `session_owners` 和 task metadata 入 Postgres。
2. 运行中 SSE event buffer 入 Redis Stream 或 Postgres event table。
3. rate limit 和 quota counter 入 Redis。
4. artifact 和导出文件进入对象存储。
5. 长任务进入 queue worker。

### P3：企业治理

- 身份集成：SAML、SCIM、IdP group 到 role 映射、MFA、IP allowlist、强制退出。
- 平台运行状态：active、maintenance、readonly，支持审计留存和生产 fail closed 策略。
- 数据治理：列级 allow/deny、敏感标签、动态脱敏、查询前检查和结果后处理。
- 策略引擎：内部 DSL、OPA/Rego 或数据库原生 RLS，支持 ABAC、dry-run、版本化和回滚。
- 审批流：临时访问数据源/敏感表/高风险 SQL/大结果导出/高成本模型，授权到期自动回收。
- 模型治理：企业/角色可用模型、外部 LLM 出境策略、私有 endpoint、成本与错误率统计、fallback。
- KB 治理：企业/项目/用户/角色 ACL，向量索引隔离，检索结果进入 LLM 前做 ACL 和脱敏。
- 报表/仪表盘发布治理：draft、pending_review、published、archived，版本、审批、回滚、导出审计。

### P4：企业版产品化

- Feature flag：dashboard、report、MCP、自定义数据源、私有模型、高级审计、审批流、列级权限、导出。
- 企业内配额：用户数、数据源数、并发会话、月 token、月 query、KB 文档数、artifact 数、审计 retention。
- API 版本化：稳定错误码、permission key 迁移、OpenAPI public/admin/internal 分组。
- 导入导出与迁移：企业配置、角色权限模板、数据源授权、artifact ACL、会话和产物迁移。
- 备份恢复：Postgres PITR、对象存储 versioning、全局配置恢复、单用户会话恢复、RPO/RTO。
- 可观测性与 SLO：API p95/p99、chat 首事件/首 token 延迟、SQL/dashboard query 耗时、LLM token、policy 拒绝率、企业/部门/用户维度成本。

## 企业内网 MVP 建议

如果目标是企业内部员工使用，建议企业内网 MVP 定义为：

1. 企业登录后返回 access token；Datus 用 access token 调用户信息接口获取身份，或在网关可改时由网关注入签名身份 header。
2. 用户、角色、权限、数据源 grant 存储。
3. 企业级 `DatusService` 隔离。
4. 用户级会话和运行中 task 隔离。
5. 模块 RBAC。
6. 数据源投影。
7. SQL policy 兜底。
8. Postgres 保存 RBAC metadata、session owner、artifact ACL、audit log。
9. Redis 保存限流计数和 SSE 事件缓冲。
10. 基础 admin API。
11. 基础 quota。
12. secret 引用和脱敏返回。

完成这一版后，系统可支撑企业内网单租户、多用户、RBAC + 数据权限试点。后续再逐步补齐审批、列级权限、模型治理、KB 治理和报表发布流。
