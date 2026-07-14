# Datus Database Adapters

`datus-db-adapters` 是 Python 3.12 `uv` workspace。每个数据库 adapter 独立发布和安装；根 `pyproject.toml` 只用于源码开发，不是终端用户需要安装的聚合包。

## Workspace 结构

- `datus-db-core`：adapter 公共接口和注册能力。
- `datus-sqlalchemy`：关系型 adapter 共用的 SQLAlchemy 连接层。
- `datus-<database>`：数据库实现、包级配置说明和测试。
- `ci/`：required checks 与 workspace 级质量检查。

## 当前包

下表与根 `pyproject.toml` 的 `tool.uv.workspace.members` 保持一致。

| 包 | 实现方式 | 文档 |
| --- | --- | --- |
| `datus-db-core` | 公共接口 | [README](./datus-db-core/README.md) |
| `datus-sqlalchemy` | SQLAlchemy 公共层 | [README](./datus-sqlalchemy/README.md) |
| `datus-mysql` | SQLAlchemy / MySQL | [README](./datus-mysql/README.md) |
| `datus-postgresql` | SQLAlchemy / PostgreSQL | [README](./datus-postgresql/README.md) |
| `datus-starrocks` | MySQL 协议 | [README](./datus-starrocks/README.md) |
| `datus-snowflake` | Snowflake SDK | [README](./datus-snowflake/README.md) |
| `datus-clickzetta` | ClickZetta SDK | [README](./datus-clickzetta/README.md) |
| `datus-clickhouse` | ClickHouse | [README](./datus-clickhouse/README.md) |
| `datus-hive` | Hive | [README](./datus-hive/README.md) |
| `datus-redshift` | PostgreSQL 协议 / Redshift | [README](./datus-redshift/README.md) |
| `datus-spark` | Spark SQL | [README](./datus-spark/README.md) |
| `datus-trino` | Trino | [README](./datus-trino/README.md) |
| `datus-greenplum` | PostgreSQL 协议 / Greenplum | [README](./datus-greenplum/README.md) |
| `datus-oracle` | python-oracledb / SQLAlchemy | [README](./datus-oracle/README.md) |
| `datus-oceanbase-oracle` | JDBC / OceanBase Oracle 模式 | [README](./datus-oceanbase-oracle/README.md) |

## 安装

终端用户只安装需要的包，例如：

```bash
pip install datus-postgresql
pip install datus-oceanbase-oracle
```

具体配置键、可选依赖与数据库限制以包级 README 为准。

## 开发

```bash
uv sync --dev
uv run ruff check .
uv run pytest --import-mode=importlib datus-postgresql/tests/unit
```

集成测试通常依赖对应数据库容器或预置环境。先阅读 adapter 的 `tests/integration/README.md`；缺少服务或凭据时测试应明确跳过，不应在 import 阶段失败。

新增或修改 adapter 时至少检查：

- 配置校验和连接初始化；
- database/catalog/schema/table/view 元数据语义；
- identifier quoting、分页、sample rows 和 SQL 方言；
- 执行结果格式与错误包装；
- 包 entry point、workspace member 和 `known-first-party`；
- 包级 README 与单元/集成测试。

贡献流程与提交要求见 [CONTRIBUTING.md](./CONTRIBUTING.md)，面向自动化开发者的完整规则见 [AGENTS.md](./AGENTS.md)。
