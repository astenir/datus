# Datus

通用数据智能平台 monorepo，整合 Agent 后端、Vue 3 前端、多数据库适配器与权限控制，支持自然语言数据问答、SQL 生成和可部署的数据应用。

<p align="center">
  <strong>Ask data questions. Generate trusted SQL. Ship governed data agents.</strong>
</p>

<p align="center">
  <a href="./datus-agent"><img src="https://img.shields.io/badge/Agent-Python-3776AB?logo=python&logoColor=white" alt="Python Agent"></a>
  <a href="./datus-web"><img src="https://img.shields.io/badge/Web-Vue%203-42B883?logo=vue.js&logoColor=white" alt="Vue 3 Web"></a>
  <a href="./datus-db-adapters"><img src="https://img.shields.io/badge/Adapters-Multi--Database-F97316" alt="Database Adapters"></a>
  <a href="./datus-agent"><img src="https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white" alt="FastAPI"></a>
  <a href="./LICENSE.md"><img src="https://img.shields.io/badge/License-Multi--license-blue" alt="Multi-license"></a>
</p>

![Datus architecture](./datus-agent/docs/assets/datus_architecture.svg)

## What You Can Build

- 自然语言数据问答和上下文增强的 SQL 生成。
- 面向团队和应用的数据工作区、权限控制和可部署 API。
- 可插拔的数据库、语义层和存储适配器。
- 面向数据工程师、分析师和业务应用的 Agent / Web / MCP 使用形态。

## Repository Layout

| Project | Purpose | Stack |
| --- | --- | --- |
| [`datus-agent`](./datus-agent) | Agent runtime、API、CLI、工作流引擎、知识库和权限能力 | Python, FastAPI |
| [`datus-web`](./datus-web) | 面向聊天、数据源、权限和管理流程的 Web 工作区 | Vue 3, Vite, TypeScript |
| [`datus-db-adapters`](./datus-db-adapters) | PostgreSQL、MySQL、ClickHouse、Oracle 等数据库适配器 | Python, uv |
| [`datus-storage-adapters`](./datus-storage-adapters) | 关系型和向量存储后端适配器 | Python, uv |
| [`datus-semantic-adapter`](./datus-semantic-adapter) | MetricFlow 等语义层的统一发现、校验和查询适配器 | Python, uv |
| [`metricflow`](./metricflow) | 指标模型编译、查询计划和数据库方言 SQL 渲染 | Python, Poetry |

根目录只保留跨项目协调文件。具体开发、测试和启动方式以各子项目自己的 `README.md` / `AGENTS.md` 为准。

## License

This monorepo contains components under different open-source licenses:

| Component | License |
| --- | --- |
| [`datus-agent`](./datus-agent) | Apache-2.0 |
| [`datus-db-adapters`](./datus-db-adapters) | Apache-2.0 |
| [`datus-storage-adapters`](./datus-storage-adapters) | Apache-2.0 |
| [`datus-semantic-adapter`](./datus-semantic-adapter) | Apache-2.0 |
| [`metricflow`](./metricflow) | AGPL-3.0-or-later |
| [`datus-web`](./datus-web) | MIT |

See [LICENSE.md](./LICENSE.md) and [ATTRIBUTION.md](./ATTRIBUTION.md) for the
full license and upstream attribution notes.

## 文档入口

- [文档导航](./docs/README.md)：按开发、企业能力、CI 和专项部署分类。
- [Agent 本地企业后端联调](./datus-agent/LOCAL_ENTERPRISE_BACKEND_TESTING.zh.md)：认证、RBAC、metadata seed 和 API smoke。
- [Web 开发与部署](./datus-web/README.md)：本地代理、Bearer token、子路径构建和质量检查。
- [MetricFlow OceanBase Oracle 内网部署与验收](./docs/metricflow-oceanbase-oracle-intranet-deployment.zh-CN.md)：专项源码部署和真实租户验收。

## Quick Start

也可以用 Docker Compose 启动一套本地企业联调环境：

```bash
cp .env.compose.example .env
docker compose up --build
```

启动后访问：

- Web 工作区：`http://localhost:5173`
- Datus API：`http://localhost:8000`
- Mock userinfo：`http://localhost:8010`
- PostgreSQL：`127.0.0.1:55433`

Compose 默认使用 `dev-alice-token`、mock userinfo、PostgreSQL metadata store 和示例 `ccks_fund` datasource，只适合本地体验和测试。`.env` 只保留常用运行参数：

- 大模型：先复制 `deploy/docker/agent/models.example.yml` 为 `deploy/docker/agent/models.yml`；`.env` 只用 `DATUS_TARGET_PROVIDER`、`DATUS_TARGET_MODEL` 或 `DATUS_TARGET` 选择默认模型，多个 provider、API key、私有 base_url 和自定义模型条目放在该 YAML 文件。
- 外接数据源：复制 `deploy/docker/agent/datasources.example.yml` 为 `deploy/docker/agent/datasources.yml`，在一个 YAML 文件里维护 datasource 清单；`.env` 中只用 `DATUS_DATASOURCE` 选择默认 datasource。
- 企业身份和权限：设置 `DATUS_ENTERPRISE_USERINFO_URL` 接真实 userinfo，设置 `DATUS_ENTERPRISE_PG_DSN` 接外部企业 metadata/RBAC PostgreSQL，并用 `DATUS_SEED_*` 控制本地 seed 的用户、角色、权限和 datasource grant。

真实部署仍需替换企业认证、密钥、备份、监控和上线配置。

也可以分别启动子项目：

```bash
git clone git@github.com:astenir/datus.git
cd datus

cd datus-agent
uv sync --dev
uv run datus-api --help

# 安装 monorepo 内 MetricFlow + OceanBase Oracle 语义链路
uv sync --dev --extra metricflow-oceanbase-oracle

cd ../datus-web
npm install
npm run dev
```

## Common Commands

### 后端

```bash
cd datus-agent
uv sync --dev
uv run ruff check .
uv run pytest
```

### 数据库适配器

```bash
cd datus-db-adapters
uv sync --dev
uv run ruff check .
uv run pytest --import-mode=importlib datus-postgresql/tests/unit
```

### 存储适配器

```bash
cd datus-storage-adapters
uv sync --dev
uv run ruff check .
uv run pytest
```

### 语义适配器与 MetricFlow

```bash
cd datus-agent
uv sync --dev --extra metricflow-oceanbase-oracle

cd ../datus-semantic-adapter
uv sync --locked --all-packages --all-extras
.venv/bin/python -m pytest --asyncio-mode=auto

cd ../metricflow
../datus-agent/.venv/bin/python -m pytest -p no:rerunfailures \
  metricflow/test/sql metricflow/test/sql_clients
```

### 前端

```bash
cd datus-web
npm install
npm test
npm run build
```

## Maintenance Notes

- 不在根目录新增业务代码；业务代码放回对应子项目。
- 不提交真实密钥、token、数据库密码或本地私有配置。
- 不提交生成产物、虚拟环境、依赖目录、测试缓存或构建缓存。
- 子项目内已有规则优先级高于根目录说明。
- 新文档先挂到 [`docs/README.md`](./docs/README.md)，同一流程只保留一个事实来源，其他位置使用链接。
