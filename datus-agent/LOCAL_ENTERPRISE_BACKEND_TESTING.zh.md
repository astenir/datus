# 本地企业后端测试启动指南

本文用于在本地启动一套便于前端开发联调的 Datus 企业模式后端。目标是不用真实企业网关，也能测试：

- 企业认证入口。
- 用户、角色、权限和 datasource grant。
- PostgreSQL-backed enterprise metadata store。
- 业务 PostgreSQL datasource。
- `/api/v1/me`、catalog、SQL executor、chat 等前端常用 API。

本文只面向本下游 fork 的本地开发，不是生产部署文档。

## 架构说明

本地测试涉及两类 PostgreSQL：

| 名称 | 用途 | 示例 |
| --- | --- | --- |
| enterprise metadata PG | 存 Datus 企业平台元数据，例如用户、角色、权限、数据源授权、session owner、audit、quota | `datus_enterprise` |
| 业务 datasource PG | Datus 真正查询的业务库 | `ccks_fund` |

这两个库可以在同一个 PostgreSQL 实例里，也可以分开。`enterprise metadata PG` 不保存业务表数据。

本地企业模式有两种认证方式：

| 模式 | 适合场景 | 前端请求需要带什么 |
| --- | --- | --- |
| `SignedHeaderAuthProvider` | 模拟企业网关已经认证过用户，由网关注入签名身份 header | 本地代理补 `X-Datus-*` 签名 header |
| `UserInfoBearerAuthProvider` | 模拟 Datus 收到 access token 后自己调用企业 userinfo 接口 | 前端直接带 `Authorization: Bearer <token>` |

前端开发更推荐先用 `UserInfoBearerAuthProvider` 模式，因为浏览器只需要带 Bearer token，不需要本地代理计算 HMAC 签名。

## 前置条件

在仓库根目录执行以下命令：

```bash
cd datus-agent
uv sync
```

确认本地 PostgreSQL 可用，并准备好 enterprise metadata 数据库。以下示例假设 PostgreSQL 在 `127.0.0.1:5433`，用户名密码都是 `datus`：

```bash
psql "postgresql://datus:datus@127.0.0.1:5433/postgres" \
  -c "CREATE DATABASE datus_enterprise;"
```

如果数据库已存在，会报 `already exists`，可以忽略或换成你自己的库名。

配置环境变量：

```bash
export DATUS_ENTERPRISE_PG_DSN="postgresql://datus:datus@127.0.0.1:5433/datus_enterprise"
export CCKS_FUND_DB_PASSWORD="datus"
```

`DATUS_ENTERPRISE_PG_DSN` 指向 enterprise metadata PG。`CCKS_FUND_DB_PASSWORD` 是示例业务 datasource `ccks_fund` 的密码。

## 准备配置文件

从本地企业 PG 示例复制一份可修改配置：

```bash
cp conf/agent.local-enterprise-pg.yml.example conf/agent.local-enterprise-pg.yml
```

检查 `conf/agent.local-enterprise-pg.yml` 里的业务 datasource 配置，默认是：

```yaml
services:
  datasources:
    ccks_fund:
      type: postgresql
      host: 127.0.0.1
      port: "5433"
      username: datus
      password: ${CCKS_FUND_DB_PASSWORD:-datus}
      database: ccks_fund
      schema: public
```

如果你的业务 PG 地址、端口、库名或账号不同，只改这一段。不要把业务库 DSN 写到 `DATUS_ENTERPRISE_PG_DSN`。

## 初始化企业 metadata

执行 seed 脚本：

```bash
uv run python scripts/enterprise_local_pg_seed.py --datasource ccks_fund
```

默认会写入：

| 用户 | 默认 token 映射 | 角色 |
| --- | --- | --- |
| `alice` | `dev-alice-token` | 本地管理员 |
| `bob` | `dev-bob-token` | 普通读者/分析用户 |

默认管理员权限包含：

```text
module.*
module.admin.*
```

默认普通用户权限包含：

```text
module.chat
module.datasource_catalog
module.sql_executor
module.config.view
module.system.status
```

seed 脚本也会为角色写入 `ccks_fund` 的 datasource grant。如果你实际 datasource key 不是 `ccks_fund`，要改成对应值：

```bash
uv run python scripts/enterprise_local_pg_seed.py --datasource your_datasource_key
```

## 方式一：UserInfoBearerAuthProvider

这是推荐的本地前端联调方式。

### 启动 mock userinfo

打开一个终端：

```bash
uv run python scripts/enterprise_mock_userinfo.py --port 8010 --reload
```

mock userinfo 地址：

```text
http://127.0.0.1:8010/userinfo
```

查看可用 token：

```bash
curl -i http://127.0.0.1:8010/tokens
```

默认 token：

| Token | userinfo 返回用户 | 用途 |
| --- | --- | --- |
| `dev-alice-token` | `alice` | 管理员视角 |
| `dev-bob-token` | `bob` | 普通用户视角 |
| `dev-charlie-token` | `charlie` | 认证成功但默认未 seed，适合测无权限 |
| `disabled-token` | `disabled_user`，`userStatus=停用` | 测禁用用户 |

验证 mock：

```bash
curl -i \
  -H "Authorization: Bearer dev-alice-token" \
  http://127.0.0.1:8010/userinfo
```

### 修改 Datus auth provider

编辑 `conf/agent.local-enterprise-pg.yml`，把 `agent.api.auth_provider` 改成：

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
```

设置 userinfo URL：

```bash
export DATUS_ENTERPRISE_USERINFO_URL="http://127.0.0.1:8010/userinfo"
```

### 启动 Datus API

打开另一个终端：

```bash
uv run datus-api \
  --config conf/agent.local-enterprise-pg.yml \
  --datasource ccks_fund \
  --port 8000 \
  --reload
```

API 地址：

```text
http://127.0.0.1:8000
```

### 可选：开启 dev admin 默认登录

只在本地开发需要跳过 mock userinfo / 前端 token 接线时启用：

```bash
export DATUS_DEV_ADMIN_AUTH=true
```

如果还希望浏览器或调试工具必须显式带 `admin/admin`，再打开 Basic 校验：

```bash
export DATUS_DEV_ADMIN_REQUIRE_BASIC_AUTH=true
```

此时请求可以不带 `Authorization`，默认进入 `admin`；如果启用了 Basic 校验，则使用：

```bash
curl -i \
  -u admin:admin \
  http://127.0.0.1:8000/api/v1/me
```

该开关由 `UserInfoBearerAuthProvider` 的 `dev_admin_enabled` 控制，默认关闭。开启后会给本地 `admin` 注入 `module.*`、`module.admin.*` 和所有已配置 datasource 的开发授权，只适合本地联调，不得用于真实企业试点或生产。

### 验证 Datus API

管理员视角：

```bash
curl -i \
  -H "Authorization: Bearer dev-alice-token" \
  http://127.0.0.1:8000/api/v1/me
```

普通用户视角：

```bash
curl -i \
  -H "Authorization: Bearer dev-bob-token" \
  http://127.0.0.1:8000/api/v1/me
```

数据源目录：

```bash
curl -i \
  -H "Authorization: Bearer dev-alice-token" \
  "http://127.0.0.1:8000/api/v1/catalog/list?datasource_id=ccks_fund"
```

SQL executor：

```bash
curl -i \
  -H "Authorization: Bearer dev-alice-token" \
  -H "Content-Type: application/json" \
  -d '{"database_name":"ccks_fund","sql_query":"SELECT 1","result_format":"json"}' \
  http://127.0.0.1:8000/api/v1/sql/execute
```

禁用用户：

```bash
curl -i \
  -H "Authorization: Bearer disabled-token" \
  http://127.0.0.1:8000/api/v1/me
```

预期被拒绝，错误应和 `AUTH_USER_DISABLED` 相关。

## 方式二：SignedHeaderAuthProvider

这个模式用于模拟“企业网关完成登录认证，然后向 Datus 注入签名身份 header”。

### 配置签名密钥

```bash
export DATUS_ENTERPRISE_HEADER_SECRET="$(uv run python scripts/enterprise_local_api.py secret)"
```

`conf/agent.local-enterprise-pg.yml.example` 默认就是 `SignedHeaderAuthProvider`，如果你没有改过 auth provider，可以直接启动 Datus API：

```bash
uv run datus-api \
  --config conf/agent.local-enterprise-pg.yml \
  --datasource ccks_fund \
  --port 8000 \
  --reload
```

### 使用本地签名工具调试

查看当前用户：

```bash
uv run python scripts/enterprise_local_api.py request \
  --base-url http://127.0.0.1:8000 \
  --path /api/v1/me \
  --user alice
```

catalog smoke：

```bash
uv run python scripts/enterprise_local_api.py smoke \
  --base-url http://127.0.0.1:8000 \
  --datasource ccks_fund \
  --print-curl
```

生成可复制的 curl：

```bash
uv run python scripts/enterprise_local_api.py curl \
  --base-url http://127.0.0.1:8000 \
  --path '/api/v1/catalog/list?datasource_id=ccks_fund' \
  --user alice
```

### 前端如何接 signed header 模式

前端浏览器不要保存 `DATUS_ENTERPRISE_HEADER_SECRET`，也不要自己计算 `X-Datus-Signature`。如果必须用 signed header 模式联调，应该由 Vite dev server、Node proxy、Nginx、Caddy 或 BFF 在服务端侧给 `/api/v1/*` 请求补签名 header。

生产环境也应由真实网关、Ingress、sidecar 或 BFF 做这个动作，不应由浏览器持有签名密钥。

## 前端开发建议

如果使用 `UserInfoBearerAuthProvider`，Vite 代理可以很简单：

```ts
import { defineConfig } from 'vite'

export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
```

前端请求示例：

```ts
const token = import.meta.env.VITE_DATUS_DEV_TOKEN ?? 'dev-alice-token'

const response = await fetch('/api/v1/me', {
  headers: {
    Authorization: `Bearer ${token}`,
  },
})
```

本地 `.env.development`：

```text
VITE_DATUS_DEV_TOKEN=dev-alice-token
```

常用前端初始化接口：

```text
GET /api/v1/me
GET /api/v1/me/features
GET /api/v1/me/permissions
GET /api/v1/me/datasource-grants
GET /api/v1/catalog/list?datasource_id=ccks_fund
```

SQL executor：

```text
POST /api/v1/sql/execute
POST /api/v1/sql/stop_execute
```

Chat：

```text
POST /api/v1/chat/stream
GET  /api/v1/chat/sessions
GET  /api/v1/chat/history
```

## 常见错误

### database "datus_enterprise" does not exist

含义：PostgreSQL 能连上，但 enterprise metadata 数据库还没创建。

处理：

```bash
psql "postgresql://datus:datus@127.0.0.1:5433/postgres" \
  -c "CREATE DATABASE datus_enterprise;"
```

### AUTH_REQUIRED

`UserInfoBearerAuthProvider` 模式下通常表示没有带 Bearer token：

```bash
curl -i \
  -H "Authorization: Bearer dev-alice-token" \
  http://127.0.0.1:8000/api/v1/me
```

`SignedHeaderAuthProvider` 模式下通常表示没有签名 header，需要用 `scripts/enterprise_local_api.py` 或本地代理补 header。

### AUTH_TOKEN_INVALID

含义：Datus 调 userinfo 时，mock userinfo 或真实 userinfo 拒绝了 token。

先验证 mock：

```bash
curl -i \
  -H "Authorization: Bearer dev-alice-token" \
  http://127.0.0.1:8010/userinfo
```

### AUTH_USER_DISABLED

含义：userinfo 返回的 `userStatus` 不在 `allowed_statuses` 中。默认只允许：

```yaml
allowed_statuses: ["正常"]
```

`disabled-token` 会触发这个路径。

### PERMISSION_DENIED

含义：认证通过，但 Datus 企业 metadata 中没有对应模块权限。

处理：

1. 确认 seed 已执行。
2. 确认 userinfo 返回的 `username` 和 seed 写入的用户一致。
3. 用 `dev-alice-token` 先测管理员视角。

### DATASOURCE_ACCESS_DENIED

含义：当前用户没有请求 datasource 的授权，或 seed 的 `--datasource` 和配置里的 datasource key 不一致。

处理：

```bash
uv run python scripts/enterprise_local_pg_seed.py --datasource ccks_fund
```

如果你的 datasource key 不是 `ccks_fund`，替换成实际 key。

### AUTH_SIGNATURE_INVALID

只适用于 `SignedHeaderAuthProvider`。通常是签名密钥不一致、请求 path 不一致，或签名过期。

处理：

1. 确认 Datus API 和签名脚本使用同一个 `DATUS_ENTERPRISE_HEADER_SECRET`。
2. 重新生成请求，默认签名时间窗口是 300 秒。
3. 优先使用 `scripts/enterprise_local_api.py` 生成请求，不要手写签名。

## 最小启动清单

推荐的本地前端开发启动顺序：

```bash
# 1. 准备配置
cp conf/agent.local-enterprise-pg.yml.example conf/agent.local-enterprise-pg.yml

# 2. 准备环境变量
export DATUS_ENTERPRISE_PG_DSN="postgresql://datus:datus@127.0.0.1:5433/datus_enterprise"
export DATUS_ENTERPRISE_USERINFO_URL="http://127.0.0.1:8010/userinfo"
export CCKS_FUND_DB_PASSWORD="datus"

# 3. 初始化企业 metadata
uv run python scripts/enterprise_local_pg_seed.py --datasource ccks_fund

# 4. 启动 mock userinfo，一个终端
uv run python scripts/enterprise_mock_userinfo.py --port 8010 --reload

# 5. 启动 Datus API，另一个终端
uv run datus-api \
  --config conf/agent.local-enterprise-pg.yml \
  --datasource ccks_fund \
  --port 8000 \
  --reload

# 6. 验证 API
curl -i \
  -H "Authorization: Bearer dev-alice-token" \
  http://127.0.0.1:8000/api/v1/me
```

注意第 5 步前，需要把 `conf/agent.local-enterprise-pg.yml` 的 `auth_provider` 改为 `UserInfoBearerAuthProvider`。如果不改，它仍会使用默认的 signed header 模式。
