# Datus 开发部署手册

本文面向本地开发、前后端联调和测试环境部署。它覆盖当前 monorepo 中两个主要运行面：

- 后端：`datus-agent`，FastAPI 服务，默认监听 `8000`。
- 前端：`datus-web`，Vue 3 + Vite 开发服务，默认监听 `5173`。

本文不替代生产上线方案。生产环境必须接入真实企业认证、密钥管理、备份恢复、监控告警和正式迁移流程；本地开发 token、mock userinfo、dev admin 开关都不能用于真实员工试点或生产。

下文命令默认从 monorepo 根目录执行；如果你在其他目录，请先 `cd /path/to/datus`。不要把个人用户名、机器目录或真实凭据写进提交的文档和配置。

## 1. 总体架构

本地联调时推荐使用 Bearer userinfo 模式：

```text
Browser
  |
  | http://localhost:5173
  v
datus-web Vite dev server
  |
  | proxy /api and /health
  v
datus-api http://127.0.0.1:8000
  |
  | Authorization: Bearer dev-alice-token
  v
mock userinfo http://127.0.0.1:8010/userinfo
  |
  v
PostgreSQL enterprise metadata + business datasource
```

默认端口：

| 服务 | 默认地址 | 说明 |
| --- | --- | --- |
| Datus API | `http://127.0.0.1:8000` | FastAPI 后端 |
| Mock userinfo | `http://127.0.0.1:8010` | 本地 Bearer token 到用户信息的模拟服务 |
| Datus Web | `http://localhost:5173` | Vite 前端开发服务 |
| PostgreSQL | `127.0.0.1:5433` | 本地 metadata / 业务库示例端口 |

## 2. 前置条件

### 2.1 基础工具

需要本机已安装：

- Python 3.12+
- `uv`
- Node.js 和 npm
- PostgreSQL，或可访问的本地 PostgreSQL 容器

建议先确认：

```bash
python --version
uv --version
node --version
npm --version
```

### 2.2 本地数据库

企业 metadata store 需要一个 PostgreSQL 库，例如：

```bash
createdb -h 127.0.0.1 -p 5433 -U datus datus_enterprise
```

如果要使用示例业务数据源 `ccks_fund`，还需要本地业务库可访问：

```text
host: 127.0.0.1
port: 5433
database: ccks_fund
user: datus
password: datus
schema: public
```

注意：`DATUS_ENTERPRISE_PG_DSN` 只给企业 metadata store 使用，不要把业务数据源 DSN 填进去。

## 3. 后端开发部署

### 3.1 安装后端依赖

```bash
cd datus-agent
uv sync --dev
```

### 3.2 准备本地配置

当前后端配置加载优先级是：

1. 显式传入的 `--config`
2. 当前工作目录下的 `./conf/agent.yml`
3. `~/.datus/conf/agent.yml`

推荐本地开发显式传入配置，避免运行目录变化导致加载错文件。

如果本机已有 `datus-agent/conf/agent.yml`，可以直接使用。该文件被 `datus-agent/.gitignore` 忽略，不应提交。

如果是干净环境，先复制模板：

```bash
cd datus-agent
cp conf/agent.local-enterprise-pg.yml.example conf/agent.yml
```

浏览器前端联调推荐使用 `UserInfoBearerAuthProvider`。如果复制出来的配置仍是 `SignedHeaderAuthProvider`，把 `agent.api.auth_provider` 改为：

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

同时确认配置里有：

```yaml
enterprise:
  enabled: true
```

以及本地业务数据源，例如：

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
      sslmode: prefer
      timeout_seconds: 30
      default: true
```

### 3.3 启动 mock userinfo

开第一个终端：

```bash
cd datus-agent
uv run python scripts/enterprise_mock_userinfo.py --port 8010 --reload
```

mock userinfo 内置的本地 token：

| Token | 用户 | 用途 |
| --- | --- | --- |
| `dev-alice-token` | `alice` | 推荐默认联调用用户 |
| `dev-bob-token` | `bob` | 权限差异测试 |
| `dev-charlie-token` | `charlie` | 未完整授权用户测试 |
| `disabled-token` | `disabled_user` | 禁用用户测试 |

### 3.4 初始化企业 metadata

开第二个终端：

```bash
cd datus-agent

export DATUS_ENTERPRISE_USERINFO_URL="http://127.0.0.1:8010/userinfo"
export DATUS_ENTERPRISE_PG_DSN="postgresql://datus:datus@127.0.0.1:5433/datus_enterprise"
export CCKS_FUND_DB_PASSWORD="datus"

uv run python scripts/enterprise_local_pg_seed.py --datasource ccks_fund
```

seed 会写入本地企业用户、角色、模块权限、数据源授权等测试 metadata。切换 datasource 或清理 metadata 库后需要重新 seed。

### 3.5 启动 Datus API

继续使用第二个终端：

```bash
uv run datus-api \
  --config conf/agent.yml \
  --datasource ccks_fund \
  --port 8000 \
  --reload
```

开发期建议使用 `--reload`。不要在普通本地聊天和 SSE 联调中随意加 `--workers`；当前 chat task、SSE buffer 等状态仍有进程内边界，多 worker 或多实例需要网关层 sticky routing 才能保证连续性。

可选参数：

| 参数 | 说明 |
| --- | --- |
| `--host 0.0.0.0` | 默认绑定地址，局域网调试时可保留 |
| `--port 8000` | 后端端口 |
| `--reload` | 代码变更自动重载 |
| `--datasource ccks_fund` | 默认 datasource |
| `--debug` | 打开 debug 日志 |
| `--source web` | 默认启用 Web proxy tool source；仅在明确调试对应工具链时使用 |

### 3.6 后端 smoke 验证

健康检查：

```bash
curl -i http://127.0.0.1:8000/health
```

Bearer 认证：

```bash
curl -i \
  -H "Authorization: Bearer dev-alice-token" \
  http://127.0.0.1:8000/api/v1/me
```

权限接口：

```bash
curl -i \
  -H "Authorization: Bearer dev-alice-token" \
  http://127.0.0.1:8000/api/v1/permissions/me
```

数据目录：

```bash
curl -i \
  -H "Authorization: Bearer dev-alice-token" \
  http://127.0.0.1:8000/api/v1/catalog/list
```

如果要测试 signed header 模式，不要用浏览器直连。使用本地脚本生成签名请求：

```bash
cd datus-agent

export DATUS_ENTERPRISE_HEADER_SECRET="$(uv run python scripts/enterprise_local_api.py secret)"

uv run python scripts/enterprise_local_api.py request \
  --base-url http://127.0.0.1:8000 \
  --path /api/v1/me \
  --user alice
```

## 4. 前端开发部署

### 4.1 安装前端依赖

```bash
cd datus-web
npm install
```

### 4.2 配置后端地址和本地 token

前端 Vite dev server 会代理：

- `/api` -> `VITE_DATUS_API_TARGET`
- `/health` -> `VITE_DATUS_API_TARGET`

默认后端地址是：

```text
http://localhost:8000
```

推荐在本地 shell 中显式传入：

```bash
VITE_DATUS_API_TARGET=http://127.0.0.1:8000 \
VITE_DEV_ACCESS_TOKEN=dev-alice-token \
npm run dev
```

也可以写入 `datus-web/.env.local`：

```bash
VITE_DATUS_API_TARGET=http://127.0.0.1:8000
VITE_DEV_ACCESS_TOKEN=dev-alice-token
```

然后启动：

```bash
npm run dev
```

`.env.local` 只能存本地开发配置，不能提交真实 token、密码或生产地址。

### 4.3 访问前端

默认地址：

```text
http://localhost:5173
```

如果端口 `5173` 被占用，Vite 会自动尝试下一个可用端口，以终端输出为准。

### 4.4 前端 API smoke

接口联调或 API helper 变更后，运行：

```bash
cd datus-web

VITE_DATUS_API_TARGET=http://127.0.0.1:8000 \
DATUS_API_TOKEN=dev-alice-token \
npm run api:smoke
```

该脚本会：

1. 请求 `/api/v1/config/agent`
2. 读取当前 datasource
3. 调用 `/api/v1/config/datasources/test`
4. 输出脱敏后的 probe 形状和测试结果

### 4.5 API 契约同步

后端 OpenAPI 是前端 API 类型的来源。后端路由、请求体或响应结构变化后，运行：

```bash
cd datus-web

VITE_DATUS_API_TARGET=http://127.0.0.1:8000 \
npm run api:sync
```

如果 `openapi.json` 已经是目标契约，只重新生成类型：

```bash
npm run api:types
```

不要手工编辑 `src/types/openapi.ts`。

## 5. 日常联调流程

推荐按这个顺序启动：

1. 启动 PostgreSQL，确认 `datus_enterprise` 和业务库可访问。
2. 启动 mock userinfo。
3. export 后端环境变量。
4. seed 企业 metadata。
5. 启动 `datus-api --reload`。
6. 用 `curl /health` 和 `/api/v1/me` 验证后端。
7. 启动 `datus-web`。
8. 打开浏览器验证工作区、权限、数据目录、聊天和 SQL 执行路径。

完整命令示例：

```bash
# Terminal 1
cd datus-agent
uv run python scripts/enterprise_mock_userinfo.py --port 8010 --reload
```

```bash
# Terminal 2
cd datus-agent
export DATUS_ENTERPRISE_USERINFO_URL="http://127.0.0.1:8010/userinfo"
export DATUS_ENTERPRISE_PG_DSN="postgresql://datus:datus@127.0.0.1:5433/datus_enterprise"
export CCKS_FUND_DB_PASSWORD="datus"
uv run python scripts/enterprise_local_pg_seed.py --datasource ccks_fund
uv run datus-api --config conf/agent.yml --datasource ccks_fund --port 8000 --reload
```

```bash
# Terminal 3
cd datus-web
VITE_DATUS_API_TARGET=http://127.0.0.1:8000 \
VITE_DEV_ACCESS_TOKEN=dev-alice-token \
npm run dev
```

## 6. 切换联调用户

前端换用户时，重启 Vite 并替换 token：

```bash
VITE_DATUS_API_TARGET=http://127.0.0.1:8000 \
VITE_DEV_ACCESS_TOKEN=dev-bob-token \
npm run dev
```

后端 curl 验证同理：

```bash
curl -i \
  -H "Authorization: Bearer dev-bob-token" \
  http://127.0.0.1:8000/api/v1/me
```

如果权限结果与预期不一致，先重跑 seed，再检查对应用户、角色、模块权限和 datasource grant。

## 7. 端口、进程和重启

查看端口占用：

```bash
ss -tanp | rg ':8000|:8010|:5173'
```

停止前台进程：

```text
Ctrl+C
```

如果使用 daemon 模式启动后端，可用：

```bash
uv run datus-api --config conf/agent.yml --action status
uv run datus-api --config conf/agent.yml --action stop
uv run datus-api --config conf/agent.yml --action restart
```

开发期不建议 daemon + reload 混用；当前 CLI 明确禁止 `--daemon` 和 `--reload` 同时使用。

## 8. 测试和构建

后端常用检查：

```bash
cd datus-agent
uv run ruff check .
uv run pytest
```

前端常用检查：

```bash
cd datus-web
npm test
npm run build
npm run lint:typography
```

接口相关变更额外运行：

```bash
cd datus-web
VITE_DATUS_API_TARGET=http://127.0.0.1:8000 npm run api:sync
VITE_DATUS_API_TARGET=http://127.0.0.1:8000 DATUS_API_TOKEN=dev-alice-token npm run api:smoke
```

## 9. 常见问题

| 现象 | 常见原因 | 处理 |
| --- | --- | --- |
| `AUTH_REQUIRED` | 请求没有 Bearer token；或 signed header 模式缺签名 header | 前端设置 `VITE_DEV_ACCESS_TOKEN`；curl 加 `Authorization`；signed 模式用脚本 |
| `AUTH_TOKEN_INVALID` | mock userinfo 不认识 token；userinfo 服务没启动 | 确认 token 是 `dev-alice-token` 等内置 token；检查 `8010` |
| `AUTH_USERINFO_UNAVAILABLE` | 后端访问不到 userinfo URL | 确认 API 终端 export 了 `DATUS_ENTERPRISE_USERINFO_URL` |
| `AUTH_USER_DISABLED` | 使用了 `disabled-token` 或用户状态停用 | 换 token 或修 metadata |
| `PERMISSION_DENIED` | 用户缺模块权限 | 重跑 seed；检查角色权限 |
| `DATASOURCE_ACCESS_DENIED` | 用户没有 datasource grant | 重跑 seed；检查 datasource grant |
| `database "datus_enterprise" does not exist` | metadata 库不存在或 DSN 指错 | 创建库；检查 `DATUS_ENTERPRISE_PG_DSN` |
| 前端显示离线 | 后端没启动；API base 错；浏览器存了旧 API 地址 | 访问 `/health`；检查 `VITE_DATUS_API_TARGET`；清理页面里的 API 地址 |
| 修改后端代码没生效 | 后端不是 reload 进程或跑错配置 | 使用 `--reload`；确认 `--config` 路径 |
| 端口占用 | 旧进程未停止 | 用 `ss -tanp` 找进程并停止 |
| 前端请求 403/401 但 curl 正常 | Vite 没带 token，或页面 API base 指向别处 | 重启 Vite；确认 `VITE_DEV_ACCESS_TOKEN` 和当前 API base |

## 10. 测试环境部署注意事项

测试环境可以复用本地启动结构，但必须收紧这些边界：

- 不使用 `dev-alice-token`、`dev-bob-token` 等本地 token。
- 不开启 `DATUS_DEV_ADMIN_AUTH`。
- 不让浏览器持有 signed header secret。
- `DATUS_CORS_ORIGINS` 不要使用无约束通配，按实际前端 origin 配置。
- 真实 userinfo / 网关 / BFF 必须由服务端负责身份换取或签名注入。
- `DATUS_ENTERPRISE_PG_DSN`、业务库密码、模型 API key 通过部署平台 secret 注入，不写入 Git。
- 多实例部署必须明确 sticky routing，除非 chat task、SSE buffer、tool result channel 等状态已经外部化。
- 企业 metadata PostgreSQL 需要备份、恢复、迁移和连接池预算。
- OpenAPI 契约变更要同步 `datus-web/openapi.json` 和 `src/types/openapi.ts`。

## 11. 配置和提交规范

不要提交：

- `datus-agent/conf/agent.yml`
- `datus-web/.env.local`
- 真实 token、密码、API key、DSN
- `node_modules/`
- `.venv/`
- `dist/`
- 测试缓存和构建产物

提交信息遵循 monorepo 规范：

```text
<type>(<scope>): <中文描述>
```

示例：

```text
docs(deploy): 补充开发部署手册
```
