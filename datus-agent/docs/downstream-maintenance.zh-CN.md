# 下游构建、发布与适配器维护

本文集中记录 monorepo 下游相对上游 `datus-agent` 的构建、发布和数据库适配器维护约定。公开入口 `README.md` 已与上游 release tag 保持一致；`BUILD.md` 因上游文件的尾随空格暂保留下游版本。下游特有信息不要继续写回这些上游原文件。

## 本地构建

```bash
uv sync --dev
uv run python -m build
uv run python -m twine check dist/*
```

也可以使用保留的 Makefile 封装：

```bash
make clean
make build
make check
make test
```

验证 wheel 时使用临时虚拟环境，避免当前 editable source 掩盖缺包：

```bash
python -m venv /tmp/datus-release-smoke
/tmp/datus-release-smoke/bin/pip install dist/datus_agent-*.whl
/tmp/datus-release-smoke/bin/python -c "import datus; print(datus.__version__)"
```

版本只在 `pyproject.toml` 的 `project.version` 中维护。`datus.__version__` 从已安装 distribution metadata 或源码树的 `pyproject.toml` 读取。

## 下游发布流程

正式发布由两个手动 GitHub Actions workflow 负责：

1. `.github/workflows/prepare-release.yml` 创建或更新 `release/<version>`，更新版本和 adapter lower bounds，同步 lock/test requirements，并执行 release readiness 检查。
2. `.github/workflows/publish-release.yml` 校验 ref 和版本，构建 distributions，发布到 TestPyPI 或 PyPI，并完成 tag、release 和 metadata 收尾。

发布环境需要配置对应的 `PYPI_API_TOKEN` 或 `TEST_PYPI_API_TOKEN`。不得提交 token、真实凭据或 `.pypirc`。

发布前至少运行：

```bash
uv lock --locked
uv run ruff check .
uv run pytest
uv run python ci/check_release_readiness.py --expected-version <version>
git diff --check
```

跨 adapter、语义层或存储插件的版本变化还要运行对应 cross-repo harness。若完整测试依赖外部数据库或私有服务，应在 release 记录中写明实际环境和未覆盖项。

## API 本地运行边界

当前服务入口为 `datus-api`：

```bash
uv run datus-api --host 127.0.0.1 --port 8000
uv run datus-api --host 127.0.0.1 --port 8000 --reload
```

`GET /health` 只表示进程存活，不创建数据库连接，也不探测 LLM。依赖诊断使用显式 datasource/model connectivity API。

Chat 的进程内 task、SSE 和 event buffer 仍要求多 worker/pod 使用粘性路由，除非这些运行态已经外部化。容量和缓冲区参数位于 `agent.api.chat`，包括：

```yaml
agent:
  api:
    chat:
      max_active_global: 32
      max_active_per_project: 16
      max_active_per_user: 4
      max_buffer_events: 5000
      max_buffer_bytes: 16777216
      completed_task_ttl_seconds: 300
      cleanup_interval_seconds: 60
```

## Monorepo 数据库适配器

上游 `v0.3.8` 的公开 README 保留当时的 adapter 列表。当前 monorepo 还维护和联调下列独立包：

| 数据库 | 类型 | 包 |
| --- | --- | --- |
| PostgreSQL | `postgresql` | `datus-postgresql` |
| MySQL | `mysql` | `datus-mysql` |
| Snowflake | `snowflake` | `datus-snowflake` |
| StarRocks | `starrocks` | `datus-starrocks` |
| ClickHouse | `clickhouse` | `datus-clickhouse` |
| ClickZetta | `clickzetta` | `datus-clickzetta` |
| Greenplum | `greenplum` | `datus-greenplum` |
| Hive | `hive` | `datus-hive` |
| Oracle Database | `oracle` | `datus-oracle` |
| OceanBase Oracle | `oceanbase-oracle` | `datus-oceanbase-oracle` |
| Redshift | `redshift` | `datus-redshift` |
| Spark | `spark` | `datus-spark` |
| Trino | `trino` | `datus-trino` |

源码位于相邻 `datus-db-adapters/` 工作区。`pyproject.toml` 的 `tool.uv.sources` 是 monorepo editable source 绑定；离线或独立部署不能只复制 `datus-agent` checkout，必须同时提供被引用的 adapter 源码或可安装制品。

## 差异治理

- 上游公开文档和默认示例优先恢复 release tag 内容。
- 下游部署、内网依赖、企业运行和 monorepo 说明放在新增文档、配置示例或 `datus_enterprise/` 中。
- 依赖和 package-data 的真实差异仍保留在 `pyproject.toml` / `uv.lock`，不通过文档迁移掩盖。
- 每次 release 合并或收敛后刷新 `docs/upstream-diff-budget.zh-CN.md`。
