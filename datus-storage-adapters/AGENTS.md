# Datus Storage Adapters 维护指南

## 范围与事实来源

本文件覆盖 `datus-storage-adapters/` workspace。包级 README、各包的
`pyproject.toml`、`datus-storage-base` 源码和测试是实现事实来源；根目录
`AGENTS.md` 负责 monorepo 级协调。负责人：待确认。

当前 workspace 包：

- `datus-storage-base/`：RDB/vector 抽象、共享模型和 Registry；
- `datus-storage-postgresql/`：PostgreSQL RDB 与 pgvector backend；
- `datus-storage-oceanbase-mysql/`：OceanBase MySQL 模式 RDB 与 vector backend。

workspace 成员和 source 必须与 `pyproject.toml` 保持一致。新增 package 时先确认它属于
内部 metadata/session/vector storage，而不是业务 datasource；业务 datasource adapter 放在
`datus-db-adapters/`。

## 开发与验证

使用 Python 3.12 和 uv：

```bash
uv sync --dev
uv run ruff check .
uv run pytest
```

PostgreSQL 和 OceanBase integration tests 需要外部数据库服务。先运行被修改包的 unit
tests，再运行 workspace 检查；无法提供外部服务时应明确记录跳过的测试，不要把本地 DSN、
密码、容器数据或测试缓存提交到仓库。

## 运行时边界

`datus-agent` 运行时只应依赖 `datus-storage-base` 的接口/模型和 Registry，不应在业务
逻辑中直接 import `datus-storage-postgresql` 或 `datus-storage-oceanbase-mysql` 的具体类。

- RDB backend 通过 `datus_storage_base.rdb.registry.RdbRegistry` 创建；entry point group 为
  `datus.storage.rdb`；
- vector backend 通过 `datus_storage_base.vector.registry.VectorRegistry` 创建；entry point
  group 为 `datus.storage.vector`；
- Registry 的 discovery 是进程级初始化，新增 adapter 必须覆盖 entry point、重复注册、
  缺依赖和测试隔离行为；
- backend 的连接池、事务、SQL 方言和驱动异常留在具体 adapter 内，不向 base 层泄漏。

不要把业务 datasource connector 和内部 metadata/session backend 混在同一 workspace；两者
的权限、生命周期和外部依赖不同。

## 新增或修改 adapter 的清单

1. 在 `datus-storage-base` 中确认已有接口是否足够；不要先为单个实现增加空泛抽象。
2. 在新包中实现 RDB 和/或 vector backend，并补包级 README。
3. 在包 `pyproject.toml` 注册正确的 entry point。
4. 同步 workspace members、workspace sources 和依赖。
5. 增加 Registry discovery、backend lifecycle、错误处理和代表性数据库集成测试。
6. 检查连接初始化、关闭、事务边界和敏感配置日志；禁止打印 DSN 密码或 token。
7. 若修改 base interface，必须同步所有实现、Agent 调用方和兼容测试。

## 目录与生成物

- `datus-storage-base/` 是公共契约，不放具体数据库 SQL；
- 具体 backend 源码放在对应包目录，测试放在包内 `tests/`；
- integration 测试和容器脚本是测试/运维辅助，不是 Agent 运行入口；
- 当前未确认有需要手工维护的生成代码目录；不要提交 `.venv/`、数据库 volume、日志、
  coverage 或 build output。

## 提交与兼容

遵循根仓库 Conventional Commits，例如：

```text
docs(storage-adapters): 补充存储适配器维护边界
```

旧 import path、entry point name、backend type name 和 base model 字段属于兼容契约。移动
实现时先保留 re-export 或 adapter alias，再迁移调用方；不要用测试预期变化掩盖兼容破坏。
