# Datus Monorepo

这个仓库用于统一维护 Datus 相关的四个子项目：

- `datus-agent/`：Datus Agent 后端、API、CLI、配置、测试和企业/下游扩展。
- `datus-db-adapters/`：数据库 adapter workspace，包括 PostgreSQL、MySQL、ClickHouse、Oracle 等适配器。
- `datus-storage-adapters/`：存储 adapter workspace，目前包含基础接口和 PostgreSQL 存储实现。
- `datus-web/`：Vue 3 + Vite 前端应用。

根目录只保留跨项目协调文件。具体开发、测试和启动方式以各子项目自己的 `README.md` / `AGENTS.md` 为准。

## 常用入口

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

### 前端

```bash
cd datus-web
npm install
npm test
npm run build
```

## 维护约定

- 不在根目录新增业务代码；业务代码放回对应子项目。
- 不提交真实密钥、token、数据库密码或本地私有配置。
- 不提交生成产物、虚拟环境、依赖目录、测试缓存或构建缓存。
- 子项目内已有规则优先级高于根目录说明。
