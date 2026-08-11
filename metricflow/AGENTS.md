# Datus MetricFlow 维护指南

## 范围与事实来源

本文件覆盖 monorepo 内的 MetricFlow fork。`README-DATUS.md`、`pyproject.toml`、
`metricflow/` 与 `mcp_metricflow/` 源码、SQL/client tests 是事实来源；根目录
`AGENTS.md` 负责 monorepo 级协调。负责人：待确认。

MetricFlow 使用 Poetry package，当前包名为 `datus-metricflow`，许可证为
AGPL-3.0-or-later。Datus Agent 通过 `datus-semantic-metricflow` 和 editable source
调用本目录；不要在同一开发环境中用旧发布包覆盖当前源码。

## 两种配置模式

### Datus datasource 模式

通过 `mf --datasource <name>` 使用 Datus `agent.services.datasources` 配置。配置文件查找
优先级为：

1. 显式传给 CLI context 的 config path；
2. 当前工作目录的 `./conf/agent.yml`；
3. `~/.datus/conf/agent.yml`。

Datasource、`${VAR}`/`$VAR` 环境变量和 semantic model 路径必须按
`README-DATUS.md` 的实际规则验证。真实密码、token 和 DSN 不得写入 YAML 或 README。

### Native MetricFlow 模式

不传 `--datasource` 时读取 `~/.metricflow/config.yml`。native 模式和 Datus datasource
模式的配置、生命周期和故障边界不同；不要把一个模式下的路径或默认值复制到另一个模式。

## 运行入口与验证

公开命令：

```text
mf
mcp-metricflow
```

常用验证：

```bash
../datus-agent/.venv/bin/python -m pytest -p no:rerunfailures \
  metricflow/test/sql \
  metricflow/test/sql_clients
```

真实数据库测试必须按测试 README 显式 opt in；没有外部服务或凭据时应清楚报告未验证范围。
MCP server 的 `mcp-metricflow serve` 与 `mcp-metricflow test` 是独立运行入口，不应被普通
SQL unit test 代替。

## SQL client 与方言边界

当前 README 列出的 client 包括 DuckDB、SQLite、MySQL、PostgreSQL、Greenplum、StarRocks、
ClickHouse、Trino、Snowflake 和 OceanBase Oracle。具体驱动依赖和限制以 DB adapter 与
semantic adapter 文档为准。

- 不把 Trino 自动等同于 native PrestoDB；PrestoDB 支持需单独确认；
- 不假设 catalog、database、schema、identifier quoting、分页和 metadata table name 可移植；
- SQL 生成/改写失败要保留方言上下文和底层错误，不要用 generic normalization 掩盖实现差异；
- OceanBase Oracle 等需要额外 Java/JDBC/driver 的路径必须单独记录外部依赖和只读边界。

## 修改清单

1. 修改 Datus datasource 配置解析时，同时检查 `datus-semantic-metricflow` 和 Agent 的调用方。
2. 修改 SQL client 或 dialect 时，补对应 engine/client unit test，并确认是否需要真实数据库 smoke。
3. 修改公共 semantic model、metric query 或 response 时，同步 semantic adapter、Agent API 和 Web generated types。
4. 修改 MCP endpoint、tool schema 或 auth 时，分别验证 native MetricFlow MCP 和 Datus enterprise MCP 的边界。
5. 保留原生 `~/.metricflow/config.yml` 兼容模式，除非迁移方案已由人确认。

## 目录、上游和发布

- `metricflow/`：指标模型、planner、SQL engine/client 与测试；
- `mcp_metricflow/`：MetricFlow MCP server/client surface；
- `metricflow/test/`：SQL engine/client tests；
- Poetry metadata、lockfile、上游差异和许可证边界属于发布契约；
- 当前未确认有额外生成代码目录；不要提交 `.venv/`、`dist/`、build output、缓存或数据库文件。

上游同步或大规模目录重组必须先核对 `docs/upstream-sync-manifest.yml` 和
`docs/upstream-diff-budget.zh-CN.md`，保留 Datus datasource、native mode、MCP 和方言兼容入口。

## 提交规则

遵循根仓库 Conventional Commits，例如：

```text
docs(metricflow): 补充 Datus 集成维护边界
```
