# Datus Storage Adapters

面向 [datus-agent](../datus-agent/) 的可插拔内部存储 workspace，提供关系型 metadata/task backend 与向量 backend。实现通过 setuptools entry points 注册，运行时不应直接依赖具体 adapter 类。

## 当前包

| 包 | 能力 | 文档 |
| --- | --- | --- |
| `datus-storage-base` | backend 接口、registry 与共享模型 | [README](./datus-storage-base/README.md) |
| `datus-storage-postgresql` | PostgreSQL RDB + pgvector | [README](./datus-storage-postgresql/README.md) |
| `datus-storage-oceanbase-mysql` | OceanBase MySQL 模式 RDB + vector | [README](./datus-storage-oceanbase-mysql/README.md) |

该清单与根 `pyproject.toml` 的 workspace members 和 `tool.uv.sources` 保持一致。

## 开发

```bash
uv sync --dev
uv run ruff check .
uv run pytest
```

PostgreSQL 和 OceanBase 集成测试需要相应数据库服务。优先运行被修改包的测试，再运行 workspace 检查；不要把本地 DSN、密码或容器数据提交到仓库。

## 新增 adapter

1. 新建 `datus-storage-<name>/` 包并添加包级 README。
2. 实现 `datus-storage-base` 中的 RDB 和/或 vector 接口。
3. 在包 `pyproject.toml` 中注册对应 entry point。
4. 同步根 `pyproject.toml` 的 workspace member、source 和依赖。
5. 更新上表，并为 registry discovery、核心行为和数据库集成增加测试。

业务 datasource adapter 属于 [`datus-db-adapters`](../datus-db-adapters/)，不应放进本 workspace。
