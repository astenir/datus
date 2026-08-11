# Datus Enterprise 维护地图

`datus_enterprise` 是本下游仓库的企业扩展层。这里承载企业身份、授权、请求级配置投影、
企业 API、元数据存储、会话所有权、Artifact ACL、审计、Quota 和运行时策略等实现。

本文件只提供代码导航和放置规则。安全与产品契约以仓库根目录的
`ENTERPRISE_PLATFORM_PLAN.zh.md` 为准，开发检查项以
`ENTERPRISE_AI_DEVELOPMENT_GUIDE.zh.md` 为准，上游差异治理以仓库根目录的
`docs/upstream-diff-budget.zh-CN.md` 和 `docs/upstream-sync-manifest.yml` 为准。

## 包边界

企业能力当前跨两个包，但所有权不同：

- `datus/api/enterprise/`：上游核心侧的稳定扩展契约和安全接入面，包括 models、
  protocols、loader、FastAPI dependencies 和 route security matrix。
- `datus_enterprise/`：下游企业产品实现，包括 provider、policy、API、service 和具体
  metadata/session store。
- 上游 `datus/` 其他模块：只保留启动注册、请求上下文、配置投影、存储/执行扩展点和
  安全调用钩子；不要把企业策略重新写回共享 route 或 service 主体。

任何企业请求都必须保持以下链路：

```text
Authenticate -> Build Context -> Authorize -> Project Config -> Execute -> Audit
```

目录移动或模块拆分不能改变该顺序，也不能把 module RBAC、datasource grant、SQL
policy、session owner、Artifact ACL、Agent ACL、Quota 或 Audit 互相替代。

## 运行时和错误契约

### 企业 Loader 与配置投影

当前代码的 Loader 行为需要区分“代码兼容事实”和“生产维护规则”：

- `enterprise.enabled=false` 使用 local-compatible provider/store；
- `enterprise.enabled=true` 必须提供 authorization provider、audit sink 和 datasource
  grant store；
- 当前实现允许省略 `config_projector`，并回退到 `PassthroughConfigProjector`；它会 clone
  `AgentConfig`、设置当前 datasource/principal，但不会主动按 grant 缩小
  `services.datasources`；
- pilot/production 配置仍必须显式提供真实 `ConfigProjector`，不能把 passthrough fallback
  当成企业授权投影。是否允许某个本地兼容 profile 使用该 fallback，必须在部署配置中明确。

代码入口：`datus/api/enterprise/loader.py`、`datus/api/enterprise/defaults.py`、
`datus_enterprise/config_projection.py`。修改 loader、projector 或 grant store 时，必须
同步 `tests/unit_tests/api/enterprise/test_loader.py`、`test_config_projection.py` 和 route
security matrix tests。

### Chat/SSE 状态边界

Chat task、SSE event buffer、completed task 以及 Report/Dashboard edit session 当前由进程内
`ChatTaskManager` 持有；session metadata、body/history 和 terminal/tool sidecar 才进入
持久化 store。多 worker 或多 pod 部署必须使用 sticky chat/SSE/session routing，除非 task/event
状态已经外置。当前实现不能被描述为 stateless HA。

SSE cursor 是事件 ID 语义，不是数据库 offset；buffer 过期必须显式返回过期错误，不能静默
从头重放或删除 cursor。delta batching 必须在 terminal、tool、interaction、error 和 cancel
等协议边界前 flush。

### HTTP、Result 和 SSE 错误层

调用方必须按三层契约处理失败：

| 层 | 典型场景 | 调用方处理 |
| --- | --- | --- |
| HTTP 401/403/404/503 | Bearer 缺失、企业 membership、ACL、platform status、上游依赖 | 处理 HTTP status 和 `detail`，不要当作 `Result` 成功响应 |
| `Result(success=false, errorCode, errorMessage)` | 普通 API/service、catalog、MCP、SQL、artifact service 失败 | 调用 `errorCode`/`errorMessage`，不要只看 HTTP 200 |
| HTTP 200 + SSE `error` event | Chat pre-check、运行时 task、流式 tool/Agent 失败 | 消费 SSE event，保留 session/cursor/history 语义 |

新增 route 或 response 时，必须同时更新 Pydantic response model、route security matrix、
OpenAPI/前端类型和对应的错误边界测试。

### MCP 与 Artifact 的状态边界

- MCP 当前登录 Bearer 通过 request-scoped `MCPRequestCredentials` 传到连接边界，不得写入
  共享 `.mcp.json`、session history、cache 或日志；persisted static credential 的加密和轮换
  规则仍需由部署负责人确认；
- Artifact 的 manifest/filesystem 与 ACL store 是两个边界；创建流程有 rollback，但 cleanup
  失败必须保留可定位的错误；view ACL 不授予 edit ACL；企业 edit 缺少 ACL store 时 fail closed；
- 以上状态都必须绑定当前 user/project/session，不得用前端 permission 或 body principal 替代
  后端授权。

### 矛盾验证后的维护事实

以下结论来自当前 tracked 源码和静态检查；“已确认”只表示代码边界已定位，不表示生产
部署已经满足该边界。

- `create_app()` 的 route projection 位于 `datus/api/service.py` 和
  `datus_enterprise/app_integration.py`；`datus/api/enterprise/route_security_matrix.py`
  当前有 201 个唯一 method/path key。`tests/unit_tests/api/enterprise/test_route_security_matrix.py`
  会把实际注册的 `APIRoute` 与 matrix 做集合相等断言。静态归一化比较没有差异；动态
  import 失败、可选依赖或部署配置造成的最终路由差异，仍需在目标环境运行该测试确认。
- `ChatTaskManager` 持有 process-local task、completed task、SSE buffer 和 artifact edit
  session；`DatusService` cache 至少按 project/config fingerprint 分组。Chat 启动时必须
  deep-copy `AgentConfig`，并把 user、principal、ACL store、workspace 和 datasource 限制
  写入 request-scoped clone。当前实现不能描述为 stateless HA，多 worker/pod 需要 sticky
  routing，除非这些状态已经外置。
- 企业 membership 校验位于 `datus_enterprise/services/request_context_policy.py`，会区分
  `AUTH_REQUIRED`、`USER_STATUS_UNAVAILABLE`、`ENTERPRISE_USER_NOT_PROVISIONED` 和
  `USER_DISABLED`。部分 route unit fixture 直接 override `get_request_app_context` 或
  `get_datus_service`，并使用默认的空 `InMemoryEnterpriseUserStore`；这类测试不能证明
  生产 membership 拒绝路径。dependency-level tests 仍然单独覆盖 active、未 provisioned
  和 disabled user。
- MCP 当前登录 Bearer 使用 request-scoped `MCPRequestCredentials`，连接时才投影到
  `Authorization`，不得写入共享配置。个人 MCP 的 allowed-host、HTTPS、公共地址和每次
  连接的 DNS/IP 检查已有代码约束；persisted static token 使用 `CredentialSecretCodec`
  保存。密钥来源、轮换、失效和部署 secret 生命周期仍需负责人确认。
- Artifact 创建顺序是 filesystem/manifest 后写 default private ACL；ACL 失败会尝试删除
  已创建目录并返回 cleanup error。进程崩溃、删除失败或并发 slug race 下的残留尚未被
  证明，当前 artifact tool unit tests 也没有覆盖完整的 ACL-failure cleanup 场景。
- 根目录的 `agent_registry.py`、`artifact_acl.py`、`auth_provider.py`、`*_stores.py` 和
  `*_session_store.py` 是兼容 re-export。它们仍被测试、脚本或部署 class path 消费；不能
  依据某次静态搜索没有找到 production import 就删除。单个 symbol 的动态调用方仍需
  运行/部署证据确认。

## 当前代码地图

| 能力 | 主要入口 | 说明 |
| --- | --- | --- |
| 身份认证 | `auth/providers.py`、`auth/loader_policy.py` | Bearer userinfo、signed-header provider 与 fail-closed Loader 策略；根目录旧模块保留兼容导出 |
| 授权与审计 | `authorization.py`、`audit.py`、`quota.py` | 共享决策和稳定错误映射 |
| 请求配置投影 | `config_projection.py`、`projection.py` | 只写入请求级 `AgentConfig` clone |
| Agent | `agents/registry.py`、`agents/*_routes.py` | 目录、dispatch 和分域 API；根目录及 `api/agent_routes.py` 旧入口保留兼容聚合 |
| Artifact | `artifacts/acl.py`、`artifacts/*_routes.py` | ACL、Report/Dashboard 浏览、分享和管理；根目录及 `api/artifact_routes.py` 旧入口保留兼容聚合 |
| Admin Datasource/Role | `admin_datasources/`、`admin_roles/` | 管理端 Datasource Grant、默认数据源、Role 和用户角色绑定；旧 `api/admin_*_routes.py` 保留同模块兼容入口 |
| Admin Session/User | `admin_sessions/`、`admin_users/` | 管理端会话 owner/runtime 聚合与用户详情/保护性禁用；旧 `api/admin_*_routes.py` 保留同模块兼容入口 |
| 其余企业 API | `api/` | 尚未独立成领域包的权威 route 及兼容入口；注册映射见 `app_integration.py` |
| Chat/Session 运行时 | `services/chat_*`、`services/session_*` | 请求策略、task、历史和 sidecar 适配 |
| Chat 历史重建 | `services/chat_history_reconstruction.py` | 同步/异步历史、终态事件和嵌套 SubAgent 展开 |
| Success Story 来源 | `services/success_story_source.py` | 从可信会话历史解析成功 SQL、问题和 datasource |
| 执行策略 | `services/cli_sql_policy.py`、`services/database_tool_scope.py` | SQL 与 connector 执行边界 |
| 连接探测 | `services/connectivity_probe.py` | LLM 与 datasource 的同步一次性探测 |
| PostgreSQL metadata | `storage/postgres/` | 按 base/schema/records 和领域 Store 拆分；`postgres_stores.py` 保留兼容导出 |
| OceanBase metadata | `storage/oceanbase/` | 与 PostgreSQL 对称拆分；`oceanbase_stores.py` 保留兼容导出 |
| Store 共享规范 | `storage/common/normalization.py` | 仅共享数据库无关的输入规范化纯函数 |
| 本地 metadata | `storage/local/` | SQLite/InMemory 单节点实现；`datus/api/enterprise/defaults.py` 保留兼容导出 |
| Session body store | `storage/postgres/session.py`、`storage/oceanbase/session.py` | 稳定 Adapter 入口；正文/history/state 实现按 store/body/records/schema 拆分，不授予 owner 权限；根目录旧模块保留兼容导出 |

### 根目录保留规则

根目录不是第二套实现目录。这里仅保留以下三类文件：

- 包入口与组合根：`__init__.py`、`app_integration.py`、`README.md`。
- 跨多个领域的稳定安全边界：`audit.py`、`authorization.py`、`config_projection.py`、
  `model_policy.py`、`quota.py`、`projection.py`。这些模块保持身份、授权、投影、模型策略、
  Quota 和审计边界可直接定位，不为了减少根文件数量而合并。
- 已部署导入或 YAML 类路径的兼容入口：`agent_registry.py`、`artifact_acl.py`、
  `auth_provider.py`、`auth_loader_policy.py`、`oceanbase_common.py`、
  `*_session_store.py` 和 `*_stores.py`。这些文件只允许 re-export，不再写入业务实现。

`model_credentials.py`、`personal_datasources.py` 和 `workspace.py` 当前分别是一项独立的
用户资源能力；只有在各自增长出多个实现、策略或适配器时再建立领域目录，避免只为一份
实现增加空壳层级。`success_story_migration_cli.py` 是单一 CLI 注册入口，也保持在根目录。

`__pycache__/` 是 Python 运行时生成且被 Git 忽略的缓存，不属于源码结构；删除后仍会在
导入或测试时重建。

### Agent API 分域

- `agents/public_routes.py`：当前用户可见 Agent、工具和默认偏好。
- `agents/admin_support_routes.py`：工具、节点类型及脱敏 ACL 用户/角色目录。
- `agents/admin_routes.py`：管理列表、详情、默认值、CRUD 和状态变更。
- `agents/prompt_routes.py`：不可变 Prompt 版本的查询、创建和激活。
- `agents/policy_routes.py`：ACL、Tool/Runtime Policy 和默认用户。
- `agents/models.py`：上述 API 共享的 Pydantic 请求/响应模型。
- `agents/context.py`、`agents/helpers.py`：共享依赖和非路由辅助逻辑；route handler
  之间不互相调用。
- `api/agent_routes.py`：保持旧导入路径和统一 router 的兼容聚合层，不放新业务逻辑。

### Artifact API 分域

- `artifacts/browse_routes.py`：Report/Dashboard 列表、详情、HTML 和编辑会话入口。
- `artifacts/share_routes.py`：创建者 ACL 分享以及脱敏用户/角色目录。
- `artifacts/admin_routes.py`：管理员 Artifact 清单和完整 ACL 管理。
- `artifacts/models.py`、`artifacts/context.py`：共享 API 模型和 FastAPI 依赖。
- `artifacts/helpers.py`：上述分域共同使用的 Artifact 定位、ACL capability、审计及渲染
  辅助逻辑；route handler 之间不互相调用。
- `api/artifact_routes.py`：保持旧导入路径和统一 router 的兼容聚合层，不放新业务逻辑。

### Admin API 分域

- `admin_datasources/`：Datasource 清单、Catalog、Grant 和项目默认数据源；Grant 规范化、
  Subject 校验及审计辅助逻辑与 Pydantic 模型分离。
- `admin_roles/`：Role CRUD、权限集和用户角色绑定；保留“操作者只能授予自身拥有权限”及
  内置角色/已绑定角色删除保护。
- `admin_sessions/`：Session owner 分页、runtime task 合并、详情重建、停止和删除；Session
  body 是否存在不替代 owner 授权元数据。
- `admin_users/`：用户 CRUD、启停、角色和 Datasource Grant 聚合；保留禁止停用当前用户与
  Enterprise Admin 的保护。
- 各域的 `models.py` 只放请求/响应模型，`helpers.py` 放非路由聚合、校验和审计辅助逻辑，
  `routes.py` 保持认证依赖、Platform Status、执行与审计顺序。
- `api/admin_datasource_routes.py`、`api/admin_role_routes.py`、
  `api/admin_session_routes.py`、`api/admin_user_routes.py` 是旧导入路径的兼容别名，不再放
  新业务逻辑。

## 新代码放置规则

- 新企业 route 放在对应的 `datus_enterprise/<domain>/routes.py`；尚未形成领域包的能力可先
  放在 `datus_enterprise/api/`。新增或修改路由时同步
  `datus/api/enterprise/route_security_matrix.py` 和对应测试。
- 可被多个 route 复用的业务操作放在 `datus_enterprise/services/`；route 之间不要导入
  私有函数。
- 身份、授权、SQL、Agent、Artifact 和 workspace 等安全策略保持独立模块，不在 route
  内散落角色名或前端提交的权限判断。
- 新 metadata backend 实现同一 `datus/api/enterprise/protocols.py` 契约；数据库方言、
  连接池和事务逻辑留在各 adapter 内，不建立隐藏 SQL 差异的通用 ORM。
- 多个数据库实现共享的数据规范化可以提取到纯函数模块；SQL、DDL 和驱动异常处理不得
  为了复用而混在一起。
- 不在共享 `DatusService.agent_config` 写入用户级状态；datasource、principal、tool 和
  workspace 限制都进入请求级 clone。
- 保留稳定旧导入路径作为阶段性 re-export 后再迁移调用方，避免一次目录移动扩大升级
  冲突和部署风险。

## 变更检查表

新增或修改企业能力时至少确认：

1. 身份和 `AppContext` 是否只来自服务端可信边界。
2. module permission 与资源 ACL/grant 是否分别校验。
3. platform status、SQL/tool policy、Quota 是否在外部执行和写入前完成。
4. allow/deny 是否写入正确的 Audit action，失败策略是否仍为 fail closed。
5. route security matrix、Protocol、loader/config 和所有启用的 store 是否同步。
6. 聚焦测试是否覆盖允许、拒绝、provider/store 不可用及本地非企业兼容路径。
7. 是否只修改当前职责所需文件，并保持上游核心 hook 足够薄。

## 渐进式收敛顺序

当前结构按以下顺序渐进收敛，不进行一次性全包搬迁：

1. 提取 route 间共享服务，消除私有 Route-to-Route 导入。
2. 分别拆分 PostgreSQL、OceanBase metadata Store，并保留兼容 re-export。
3. 提取数据库实现共享的 record/scope normalization 纯函数。
4. 按 Prompt、ACL/Policy、管理 CRUD 拆分 Agent route。
5. 按浏览、分享、管理拆分 Artifact route。
6. 从 Chat mixin 提取 history reconstruction 和 Success Story source。
7. 将 `datus/api/enterprise/defaults.py` 中 SQLite/InMemory Store 下沉到
   `storage/local/`，只保留核心 local authorization/projector 和兼容导出。
8. 将 PostgreSQL/OceanBase Session Body Store 和 OceanBase 连接公共层下沉到对应
   `storage/` adapter；再按 `session_store.py`、`session_body.py`、`session_records.py`、
   `session_schema.py` 拆开数据库访问、会话适配、记录转换和 Schema，根目录保留 YAML
   类路径兼容导出。
9. 将 Agent registry 与 Artifact ACL 实现归入 `agents/`、`artifacts/`，根目录保留
   下游调用兼容导出。
10. 将生产认证 Provider 与 fail-closed Loader 策略归入 `auth/`，并保持旧配置类路径。
11. 将 Datasource、Role、Session、User 管理 API 按 `models/helpers/routes` 归入对应
    `admin_*` 领域目录，旧 `api/admin_*_routes.py` 保持模块身份兼容。

每一步都应在迁移前后运行同一组聚焦测试，并保持 route、错误码、审计和安全拒绝顺序
不变。
