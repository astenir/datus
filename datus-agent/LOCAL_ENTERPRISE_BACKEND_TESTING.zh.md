# 本地企业后端测试启动指南

本文只解决一件事：在本机快速启动企业模式后端，并验证 RBAC、datasource grant、session owner、audit 等企业链路是否能跑通。架构和上线门槛见 `ENTERPRISE_PLATFORM_PLAN.zh.md`。

## 最小启动清单

默认使用 `conf/agent.local-enterprise-pg.yml.example`，它是完整的本地企业 PG 配置，默认认证模式是 `SignedHeaderAuthProvider`。

```bash
cd datus-agent

# 1. 复制本地配置
cp conf/agent.local-enterprise-pg.yml.example conf/agent.local-enterprise-pg.yml

# 2. 准备环境变量
export DATUS_ENTERPRISE_PG_DSN="postgresql://datus:datus@127.0.0.1:5433/datus_enterprise"
export DATUS_ENTERPRISE_HEADER_SECRET="$(uv run python scripts/enterprise_local_api.py secret)"
export CCKS_FUND_DB_PASSWORD="datus"

# 3. 初始化企业 metadata
uv run python scripts/enterprise_local_pg_seed.py --datasource ccks_fund

# 4. 启动 Datus API
uv run datus-api \
  --config conf/agent.local-enterprise-pg.yml \
  --datasource ccks_fund \
  --port 8000 \
  --reload
```

另开终端验证：

```bash
cd datus-agent

uv run python scripts/enterprise_local_api.py request \
  --base-url http://127.0.0.1:8000 \
  --path /api/v1/me \
  --user alice

uv run python scripts/enterprise_local_api.py smoke \
  --base-url http://127.0.0.1:8000 \
  --datasource ccks_fund \
  --user alice
```

如果你只想测试前端 Bearer token 流程，请改用下文的 `UserInfoBearerAuthProvider`。

## 前置条件

需要：

- Python/uv 环境已可用。
- 本地 PostgreSQL 可访问，且存在 `datus_enterprise` metadata 库。
- 要测试 `ccks_fund` datasource 时，业务库也能通过配置访问。
- 可选：`DEEPSEEK_API_KEY` 和 `SILICONFLOW_API_KEY`，用于真实 chat/embedding 路径。

创建 metadata 库示例：

```bash
createdb -h 127.0.0.1 -p 5433 -U datus datus_enterprise
```

如果你的本地 PostgreSQL 用户、端口或密码不同，只改环境变量和 `conf/agent.local-enterprise-pg.yml` 的业务 datasource 段。不要把业务库 DSN 写进 `DATUS_ENTERPRISE_PG_DSN`；这个变量只给企业 metadata store 使用。

## 配置文件

本地配置默认包含：

- `agent.api.auth_provider`: `SignedHeaderAuthProvider`
- `agent.enterprise.*`: PostgreSQL-backed user、role、datasource grant、agent、session owner、session body、artifact ACL、audit、quota、secret stores
- `services.datasources.ccks_fund`: 本地业务 PostgreSQL 示例
- `sql_policy.enabled: false`: 基础 RBAC/grant smoke 默认不启用 SQL policy

常改字段：

```yaml
agent:
  home: ${DATUS_HOME:-~/.datus}
  project_root: ${DATUS_PROJECT_ROOT:-.}
  services:
    datasources:
      ccks_fund:
        host: 127.0.0.1
        port: "5433"
        username: datus
        password: ${CCKS_FUND_DB_PASSWORD:-datus}
        database: ccks_fund
        schema: public
```

本地文件 `conf/agent.local-enterprise-pg.yml` 不要提交。

## 方式一：SignedHeaderAuthProvider

适合模拟“企业网关已登录并向 Datus 注入签名身份 header”。

准备：

```bash
export DATUS_ENTERPRISE_HEADER_SECRET="$(uv run python scripts/enterprise_local_api.py secret)"
uv run python scripts/enterprise_local_pg_seed.py --datasource ccks_fund
```

启动：

```bash
uv run datus-api \
  --config conf/agent.local-enterprise-pg.yml \
  --datasource ccks_fund \
  --port 8000 \
  --reload
```

调用：

```bash
uv run python scripts/enterprise_local_api.py request \
  --base-url http://127.0.0.1:8000 \
  --path /api/v1/me \
  --user alice

uv run python scripts/enterprise_local_api.py request \
  --base-url http://127.0.0.1:8000 \
  --path /api/v1/catalog/list \
  --user alice
```

普通浏览器前端不能自己生成可信签名 header。前端联调一般建议用 `UserInfoBearerAuthProvider`。

## 方式二：UserInfoBearerAuthProvider

适合测试“浏览器发送 Bearer token，Datus 调企业 userinfo 获取身份”的 MVP 身份方案。

启动 mock userinfo：

```bash
uv run python scripts/enterprise_mock_userinfo.py --port 8010 --reload
export DATUS_ENTERPRISE_USERINFO_URL="http://127.0.0.1:8010/userinfo"
export DATUS_ENTERPRISE_PG_DSN="postgresql://datus:datus@127.0.0.1:5433/datus_enterprise"
export CCKS_FUND_DB_PASSWORD="datus"
```

把 `conf/agent.local-enterprise-pg.yml` 中的 `agent.api.auth_provider` 改成：

```yaml
api:
  auth_provider:
    class: datus_enterprise.auth_provider:UserInfoBearerAuthProvider
    kwargs:
      userinfo_url: ${DATUS_ENTERPRISE_USERINFO_URL}
      timeout_seconds: 3.0
      user_id_field: username
      external_user_id_field: userId
      email_field: email
      display_name_field: realname
      status_field: userStatus
      allowed_statuses: ["正常"]
      default_project_id: enterprise
      dev_admin_enabled: ${DATUS_DEV_ADMIN_AUTH:-false}
      dev_admin_require_basic_auth: ${DATUS_DEV_ADMIN_REQUIRE_BASIC_AUTH:-false}
      dev_admin_user_id: admin
      dev_admin_username: admin
      dev_admin_password: ${DATUS_DEV_ADMIN_PASSWORD:-admin}
      dev_admin_project_id: enterprise
```

重新 seed 并启动 API：

```bash
uv run python scripts/enterprise_local_pg_seed.py --datasource ccks_fund

uv run datus-api \
  --config conf/agent.local-enterprise-pg.yml \
  --datasource ccks_fund \
  --port 8000 \
  --reload
```

验证：

```bash
curl -i \
  -H "Authorization: Bearer dev-alice-token" \
  http://127.0.0.1:8000/api/v1/me

curl -i \
  -H "Authorization: Bearer dev-bob-token" \
  http://127.0.0.1:8000/api/v1/permissions/me
```

可用 mock token 通常包括：

```text
dev-alice-token
dev-bob-token
dev-charlie-token
disabled-token
```

如需本地“无 token 也进 admin”：

```bash
export DATUS_DEV_ADMIN_AUTH=true
# 可选：要求 Basic admin/admin
export DATUS_DEV_ADMIN_REQUIRE_BASIC_AUTH=true
```

该开关只允许本地开发使用。真实员工试点和生产必须关闭。

## 前端联调

Bearer userinfo 模式：

```bash
cd ../datus-web
VITE_DATUS_API_TARGET=http://127.0.0.1:8000 \
VITE_DEV_ACCESS_TOKEN=dev-alice-token \
npm run dev
```

如果要换用户：

```bash
VITE_DEV_ACCESS_TOKEN=dev-bob-token npm run dev
```

Signed header 模式不适合普通 Vite 浏览器前端直连，因为浏览器无法持有企业网关签名密钥。需要一个本地代理或改用 Bearer userinfo。

## 常见错误

| 错误 | 常见原因 | 处理 |
| --- | --- | --- |
| `database "datus_enterprise" does not exist` | metadata 库未创建或 DSN 指错 | 创建库，检查 `DATUS_ENTERPRISE_PG_DSN` |
| `AUTH_REQUIRED` | Bearer 模式没带 `Authorization`；signed 模式没带签名 header | Bearer 加 token；signed 用 `enterprise_local_api.py` |
| `AUTH_TOKEN_INVALID` | mock userinfo 不认识 token，或 userinfo URL 不通 | 确认 mock 进程和 `DATUS_ENTERPRISE_USERINFO_URL` |
| `AUTH_USERINFO_UNAVAILABLE` | Datus 访问 userinfo 超时/失败 | curl userinfo，检查端口和 env 是否被配置解析 |
| `AUTH_USER_DISABLED` | 使用了 disabled 用户或 metadata 中用户被禁用 | 换 token 或重新 seed/enable 用户 |
| `PERMISSION_DENIED` | 用户缺模块 permission | 检查 seed 的 role/permission，或用 admin 用户验证 |
| `DATASOURCE_ACCESS_DENIED` | 用户没有该 datasource grant | 重新 seed 或检查 grant metadata |
| `AUTH_SIGNATURE_INVALID` | 签名密钥不一致、时间戳过期、path/method 不匹配 | 重新导出 `DATUS_ENTERPRISE_HEADER_SECRET`，用脚本生成请求 |
| 端口 8000 被占用 | 旧 `datus-api --reload` 进程仍在 | `ss -tanp | rg ':8000'` 后停止旧进程 |
| 修改后端代码没生效 | 运行的是 daemon 或无 reload 进程 | 使用 `--reload` 或重启 API |

## 验证建议

基础 smoke：

```bash
curl -i http://127.0.0.1:8000/health
curl -i -H "Authorization: Bearer dev-alice-token" http://127.0.0.1:8000/api/v1/me
curl -i -H "Authorization: Bearer dev-alice-token" http://127.0.0.1:8000/api/v1/catalog/list
```

安全边界 smoke：

- Alice 能访问授权 datasource。
- Bob/Charlie 的权限与 grant 差异符合 seed。
- `disabled-token` 被拒绝。
- 未授权 datasource 返回 403 或稳定错误。
- 切到 `DATUS_PLATFORM_STATUS=readonly` 后，SQL/chat/admin mutation 在执行前拒绝。

测试命令：

```bash
uv run pytest tests/unit_tests/datus_enterprise/test_enterprise_mvp_smoke.py
uv run pytest tests/unit_tests/api/enterprise/test_route_security_matrix.py
```

真实 PostgreSQL integration 测试必须使用独立库或唯一前缀，并清理自己写入的数据。
