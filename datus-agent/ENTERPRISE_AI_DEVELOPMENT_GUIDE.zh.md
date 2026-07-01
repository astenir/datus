# 企业内网平台化 AI 开发规范

本文是给 AI agent 和开发者的执行 checklist。总体产品与安全契约见 `ENTERPRISE_PLATFORM_PLAN.zh.md`；本地联调见 `LOCAL_ENTERPRISE_BACKEND_TESTING.zh.md`；通用 repo 规则见 `AGENTS.md`。

目标：每次企业相关改动都能明确阶段、边界、测试和剩余风险，避免把前端可见性、本地兼容逻辑或单节点 happy path 误说成生产安全边界。

## 开工前

企业相关任务开始前必须完成：

1. 阅读 `AGENTS.md`、`ENTERPRISE_PLATFORM_PLAN.zh.md` 和本文。
2. 声明本次任务属于哪个阶段：
   - 阶段 0：开关、兼容基线、fail-closed skeleton。
   - 阶段 1：认证、`AppContext`、RBAC 刷新、service cache。
   - 阶段 2：session/task owner。
   - 阶段 3：模块 RBAC。
   - 阶段 4：datasource grant 与 config projection。
   - 阶段 5：SQL policy、query/export、quota、audit 兜底。
   - 阶段 6：管理 API。
3. 写清楚非目标。不要把一个小切片扩成跨阶段重构。
4. 用 `rg` 找真实入口，不凭记忆改：

```bash
rg -n "AuthProvider|AuthorizationProvider|ConfigProjector|get_request_app_context|require_module" datus datus_enterprise tests
rg -n "chat/stream|sql/execute|dashboard/query|semantic_model|route_security_matrix" datus datus_enterprise tests
```

## 必守安全链

企业请求必须符合：

```text
Authenticate -> Build Context -> Authorize -> Project Config -> Execute -> Audit
```

实现时逐项确认：

- `AuthProvider` 只负责认证和构造身份上下文，不承担全部 RBAC、投影、审计和 quota。
- `AuthorizationProvider` / `require_module()` 负责模块和资源决策，不在 route 中散落角色名判断。
- `ConfigProjector` 生成请求级 `AgentConfig` clone，不修改共享 `DatusService.agent_config`。
- datasource grant、table scope、SQL policy principal、DB 最小权限账号共同约束执行。
- session/task/artifact 必须有 owner/ACL，body/HTML/slug 存在不授予访问权。
- 关键 allow/deny、执行、管理 mutation、platform status 拒绝写入审计。

## 禁止项

- 禁止用前端隐藏替代后端授权。
- 禁止信任裸 `X-Datus-User-Id` 作为生产身份。
- 禁止信任前端或 request body 传入的 roles、permissions、principal、datasource grants。
- 禁止把 `scoped_context`、catalog 过滤、tool permission 单独当作完整安全边界。
- 禁止把用户级权限状态写入共享 service/config/cache。
- 禁止绕过 route security matrix 新增企业暴露面。
- 禁止在企业模式下保留未接安全链的 legacy route。
- 禁止把本地 dev admin 开关用于真实员工试点或生产。
- 禁止把多 worker `--workers N` 描述成 chat/SSE/session 无状态 HA。
- 禁止把 secret、完整连接串、access token、userinfo 原文、敏感 prompt 或大结果集写入日志、session、trace、audit 或错误信息。

## 实现规则

### AuthProvider

- 网关不可改时默认用 `UserInfoBearerAuthProvider`：读取 Bearer token，调用企业 userinfo，映射稳定员工身份。
- 网关可改时可用 `SignedHeaderAuthProvider`：只信任签名 header，并确保后端不能绕过网关直连。
- userinfo/header 只证明“这个人是谁”。Datus 内部 RBAC store 才是模块权限、datasource grant、artifact ACL 的事实来源。
- 用户禁用、userinfo 失败、签名失败、provider 缺失必须 fail closed。

### AuthorizationProvider

- 所有模块、session、artifact、datasource 管理面都走统一 dependency/helper。
- admin 能力也使用显式 permission，例如 `module.admin.users`、`module.admin.audit.export`。
- 新增 permission key 时，同步 `ENTERPRISE_PLATFORM_PLAN.zh.md`、route matrix、测试 fixture 和 `/me` 返回。

### ConfigProjector

- 不修改缓存里的 `DatusService.agent_config`。
- 未授权 datasource 从 clone 中删除。
- 请求 datasource/table 未授权时拒绝。
- principal 由服务端构造，不接受请求体覆盖。
- chat、catalog、direct SQL、dashboard query、table/semantic metadata 等路径应复用同一投影语义。

### Datasource Grant

- 按 `(subject_type, subject_id, datasource_key)` upsert，避免同主体同 datasource 多条语义冲突。
- role grants 先合并，user grants 后合并；deny 优先。
- user grant 不能扩大已有 role grant，只能直接授权未授权 datasource、收窄已有授权或显式拒绝。
- 保存前校验 subject、datasource key、scope schema、effect；无法解释时拒绝并审计。

### Session 与 Artifact

- list/history/delete/resume/feedback/control 路径都必须以 owner/ACL 为入口。
- `SessionBodyStore` 不替代 `SessionOwnerStore`；正文表存在不能补权。
- artifact `view` 不等于 query/export；实时查数和导出必须重新校验 ACL、模块权限、datasource grant、SQL policy、quota、audit。

### Platform Status

- 执行类请求和写入类 mutation 在 `DATUS_PLATFORM_STATUS != active` 时拒绝。
- gate 必须先于 `DatusService` 初始化和外部副作用执行。
- 拒绝写 `system.platform_status` 审计。
- 未识别状态 fail closed。

## Route Checklist

新增或修改 FastAPI route 时，必须回答：

- 这个 route 在 `enterprise.enabled=true` 下是否开放？
- 需要哪个 module permission？
- 是否涉及 session owner、artifact ACL、datasource grant、table scope、SQL policy、quota？
- 是否受 `readonly` / `maintenance` 限制？
- allow/deny/mutation 是否审计？
- 是否需要隐藏资源存在性？
- `datus/api/enterprise/route_security_matrix.py` 是否已更新？
- 测试是否证明矩阵和 `create_app()` 注册面一致？

如果暂时无法完整接安全链，企业模式下禁用并审计。

## 测试 Checklist

按风险选择最小但有效的测试组合：

- Auth：无 token、无效 token、userinfo/header 失败、禁用用户、dev admin 仅本地。
- RBAC：有权限 allow，无权限 deny，admin 权限拆分。
- Session：用户 A 不能 resume/stop/insert/delete/history 用户 B 的 session。
- Datasource：未授权 datasource/table 不出现在 list，也不能执行。
- Projection：请求级 clone 生效，原始 `DatusService.agent_config` 不变。
- SQL policy：principal 缺失 fail closed；direct SQL / dashboard query 不绕过。
- Artifact：slug 不存在和无权限不泄漏；view/query/export 权限分离。
- Platform status：拒绝路径不初始化 service、不写 metadata、不访问外部系统。
- Legacy：enterprise mode 下旧 route 禁用并审计。
- Store failure：PG/audit/quota/userinfo 不可用时稳定失败，不静默放行。
- Local compatibility：`enterprise.enabled=false` 和 `NoAuthProvider` 行为不被改坏。

真实 PG、真实 LLM、外部 userinfo、网络服务测试必须 gated，默认 CI 不依赖它们。

## 文档 Checklist

需要同步更新的情况：

- 改总体目标、API 分区、阶段、上线门槛：更新 `ENTERPRISE_PLATFORM_PLAN.zh.md`。
- 改 AI/开发执行标准：更新本文。
- 改本地启动或排错路径：更新 `LOCAL_ENTERPRISE_BACKEND_TESTING.zh.md`。
- 新增 route/permission/audit/quota/schema：更新 route matrix、计划文档和测试 fixture。
- 声称支持试点/生产/multi-worker/HA：写清楚部署拓扑、sticky session、状态外部化、连接数预算、备份恢复、观测来源。

## 完成说明模板

企业相关任务最终回复或提交说明应包含：

```text
阶段：
改动：
新增或保持的安全边界：
未覆盖路径及其企业模式行为：
测试：
未跑测试及原因：
运行级别：本地开发 / 单节点试点 / 粘性会话多 worker 试点 / HA
剩余风险：
```

不要因为“功能能跑”就写成生产可用；只有满足 `ENTERPRISE_PLATFORM_PLAN.zh.md` 的试点上线门槛，才能说可进入真实员工试点。
