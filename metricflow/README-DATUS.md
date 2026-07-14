# Datus MetricFlow Integration

本 fork 支持从 Datus datasource 配置构造 MetricFlow 连接，并保留原生 `~/.metricflow/config.yml` 模式。Datus Agent 的生产集成通过 `datus-semantic-metricflow` 调用本源码；`mf --datasource` 主要用于本地 CLI 验证。

## Monorepo 安装

从 `datus-agent/` 同步需要的本地源码依赖：

```bash
cd ../datus-agent
uv sync --dev --extra metricflow-oceanbase-oracle
```

`datus-agent/pyproject.toml` 的 `tool.uv.sources` 会把 `../metricflow` 和语义/数据库 adapter 以 editable path 安装到同一环境。不要单独安装一份旧 `datus-metricflow` 覆盖该源码。

## 两种配置模式

### Datus datasource

```bash
mf setup --datasource analytics
mf --datasource analytics list-metrics
mf --datasource analytics query --metrics revenue --dimensions metric_time
mf --datasource analytics health-checks
```

Datus 配置查找优先级：

1. 显式传给 CLI context 的 config path；
2. 当前工作目录的 `./conf/agent.yml`；
3. `~/.datus/conf/agent.yml`。

Datasource 位于：

```yaml
agent:
  services:
    datasources:
      analytics:
        type: postgresql
        host: 127.0.0.1
        port: "5432"
        username: datus
        password: ${ANALYTICS_DB_PASSWORD}
        database: analytics
        schema: public
```

CLI 的 semantic model 路径为 `<project_root>/subject/semantic_models/<datasource>/`。配置中的 `${VAR}` 和 `$VAR` 会从进程环境解析；真实密钥不要写入 YAML。

### 原生 MetricFlow

不传 `--datasource` 时读取 `~/.metricflow/config.yml`：

```yaml
dwh_dialect: duckdb
dwh_database: /path/to/duck.db
dwh_schema: main
model_path: ~/.metricflow/semantic_models
```

```bash
mf list-metrics
mf query --metrics revenue --dimensions metric_time
mf health-checks
```

## 当前 SQL client

`make_sql_client_from_config()` 当前可构造：

- DuckDB、SQLite；
- MySQL、PostgreSQL、Greenplum；
- StarRocks、ClickHouse、Trino；
- Snowflake；
- OceanBase Oracle。

具体 adapter 依赖和方言限制不由本 README 重复维护：

- 数据库 adapter：[datus-db-adapters](../datus-db-adapters/README.md)
- Datus 语义 adapter：[datus-semantic-metricflow](../datus-semantic-adapter/datus-semantic-metricflow/README.md)
- OceanBase Oracle 内网验收：[专项部署文档](../docs/metricflow-oceanbase-oracle-intranet-deployment.zh-CN.md)

OceanBase Oracle 需要 `datus-oceanbase-oracle`、Java 和 Connector/J，当前 production profile 是只读路径。Snowflake 支持 password 或 RSA key pair，二者只能配置一种。

## MCP server

```bash
mcp-metricflow serve --host 0.0.0.0 --port 8080
mcp-metricflow test
```

详细协议和 endpoint 说明见 [MCP-SERVER.md](./MCP-SERVER.md)。

## 验证

```bash
../datus-agent/.venv/bin/python -m pytest -p no:rerunfailures \
  metricflow/test/sql \
  metricflow/test/sql_clients
```

需要真实数据库的测试必须按测试 README 显式 opt in，不得把凭据写入测试或文档。
