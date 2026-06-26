# Datus OceanBase Oracle Adapter

`datus-oceanbase-oracle` 是 Datus 的 OceanBase Oracle 模式数据库适配器。它通过
OceanBase Connector/J 连接 OceanBase Oracle 租户，适用于通过 Datus 执行 SQL、
读取元数据、提取 DDL、采样数据，以及作为数据迁移目标端使用。

> 注意：本适配器面向 OceanBase Oracle 模式租户。OceanBase MySQL 模式租户不能使用
> 该适配器。

## 功能

- 通过 `JayDeBeApi` 和 OceanBase Connector/J 建立 JDBC 连接。
- 支持 ODP/OBProxy 连接和 OBServer 直连两种模式。
- 支持 SQL 查询、DML、DDL 和批量语句执行。
- 支持 `csv`、`list`、`pandas`、`arrow` 等查询结果格式。
- 支持 schema、表、视图、物化视图、列、主键和列注释等元数据发现。
- 优先通过 `DBMS_METADATA.GET_DDL` 获取表和视图 DDL。
- 支持样例数据读取。
- 支持作为 `MigrationTargetMixin` 迁移目标，提供常见类型映射和 DDL 校验提示。

## 安装

```bash
pip install datus-oceanbase-oracle
```

在 monorepo 开发环境中，可在 `datus-db-adapters` workspace 下运行：

```bash
uv sync --dev
```

## 运行前准备

使用该适配器需要同时准备 Python 依赖、Java 运行时、OceanBase JDBC 驱动和
OceanBase 连接信息。

### 1. Java 运行时

`JayDeBeApi` 需要启动 JVM 加载 JDBC driver，因此运行 Datus 的机器或容器内需要可用的
Java 运行时。可以先检查：

```bash
java -version
```

### 2. OceanBase Connector/J jar

需要单独下载 OceanBase Connector/J，例如 `oceanbase-client-<version>.jar`，并在配置中
通过 `jar_path` 指定 jar 文件路径。

如果 Datus 运行在 Docker 容器内，`jar_path` 必须是容器内路径，而不是宿主机路径。例
如宿主机下载到：

```text
/home/user/jars/oceanbase-client.jar
```

容器内挂载为：

```text
/opt/datus/jars/oceanbase-client.jar
```

则 Datus 配置中应写：

```yaml
jar_path: /opt/datus/jars/oceanbase-client.jar
```

### 3. OceanBase 租户和账号

需要准备：

- 一个 OceanBase Oracle 模式租户。
- 可访问的连接地址和端口。
- 数据库账号和密码。
- 默认 Oracle schema，也就是业务对象所在的 owner/user schema。
- 读取业务表和元数据视图的权限。

ODP/OBProxy 常见用户名格式：

```text
user@tenant#cluster
```

OBServer 直连常见用户名格式：

```text
user@tenant
```

## 配置示例

### 通过 ODP/OBProxy 连接

ODP/OBProxy 通常使用端口 `2883`，用户名通常包含 tenant 和 cluster：

```yaml
database:
  type: oceanbase-oracle
  host: 172.22.32.50
  port: 2883
  connection_mode: odp
  database: DEV_TENANT01
  username: "npims_nl2sql@DEV_TENANT01#DEV_Cluster01"
  password: "your_password"
  schema: NPIMS
  jar_path: /opt/datus/jars/oceanbase-client.jar
```

上面的配置会生成类似下面的 JDBC URL：

```text
jdbc:oceanbase://172.22.32.50:2883/NPIMS?useSSL=false&useUnicode=true&characterEncoding=utf-8&connectTimeout=30000
```

连接建立后，适配器还会设置当前 schema：

```sql
ALTER SESSION SET CURRENT_SCHEMA = "NPIMS"
```

### 直连 OBServer

直连 OBServer 通常使用端口 `2881`。如果 `connection_mode` 设置为 `direct` 且未显式传入
`port`，适配器会默认使用 `2881`。

```yaml
database:
  type: oceanbase-oracle
  connection_mode: direct
  host: 172.22.32.50
  username: "npims_nl2sql@DEV_TENANT01"
  password: "your_password"
  schema: NPIMS
  jar_path: /opt/datus/jars/oceanbase-client.jar
```

### 从 JDBC URL 映射到 Datus 配置

假设已有 JDBC 连接串：

```text
jdbc:oceanbase://172.22.32.50:2883/NPIMS?useUnicode=true&characterEncoding=utf-8
```

可按下面方式映射：

| JDBC 部分 | Datus 配置 |
| --- | --- |
| `172.22.32.50` | `host: 172.22.32.50` |
| `2883` | `port: 2883` |
| `/NPIMS` | `schema: NPIMS` |
| `useUnicode=true` | 默认已包含，也可放入 `extra_jdbc_params` |
| `characterEncoding=utf-8` | 默认已包含，也可放入 `extra_jdbc_params` |

对应配置：

```yaml
database:
  type: oceanbase-oracle
  host: 172.22.32.50
  port: 2883
  connection_mode: odp
  database: DEV_TENANT01
  username: "npims_nl2sql@DEV_TENANT01#DEV_Cluster01"
  password: "your_password"
  schema: NPIMS
  jar_path: /opt/datus/jars/oceanbase-client.jar
```

如果密码或用户名中包含 `#`，必须使用引号包裹，否则 YAML 会把 `#` 后面的内容当作注释：

```yaml
username: "user@tenant#cluster"
password: "password_with_#_character"
```

## 配置字段

| 字段 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `type` | 是 | 无 | Datus 数据源类型，固定为 `oceanbase-oracle`。 |
| `host` | 否 | `127.0.0.1` | OceanBase、ODP 或 OBProxy 地址。 |
| `port` | 否 | `2883` | 连接端口。ODP/OBProxy 常用 `2883`，OBServer 直连常用 `2881`。 |
| `username` | 是 | 无 | 登录用户名。ODP 常用 `user@tenant#cluster`，直连常用 `user@tenant`。 |
| `password` | 否 | 空字符串 | 登录密码。包含 `#`、`:` 等特殊字符时建议加引号。 |
| `database` | 否 | 从用户名解析 | OceanBase tenant 名称。该字段不是 Oracle schema。 |
| `schema` / `schema_name` | 否 | 用户名前缀大写 | 默认 Oracle schema/owner。两者同时出现时优先 `schema_name`。 |
| `jar_path` | 是 | 无 | OceanBase Connector/J jar 文件路径。 |
| `driver_class` | 否 | `com.oceanbase.jdbc.Driver` | JDBC driver class。通常不需要修改。 |
| `connection_mode` | 否 | `odp` | 连接模式，可选 `odp` 或 `direct`。 |
| `use_ssl` | 否 | `false` | 是否在 JDBC URL 中设置 `useSSL=true`。 |
| `connect_timeout_seconds` | 否 | `30` | JDBC 连接超时秒数，会转换为毫秒写入 `connectTimeout`。 |
| `query_timeout_seconds` | 否 | `30` | 查询超时秒数，会设置为 `ob_query_timeout`，单位换算为微秒。 |
| `timeout_seconds` | 否 | `30` | Datus 通用超时字段，保留用于兼容。 |
| `pool_maxconnections` | 否 | `10` | 连接池最大连接数。 |
| `pool_mincached` | 否 | `2` | 连接池最小空闲连接数。 |
| `pool_maxcached` | 否 | `5` | 连接池最大空闲连接数。 |
| `pool_blocking` | 否 | `true` | 连接池耗尽时是否阻塞等待。 |
| `extra_jdbc_params` | 否 | `{}` | 额外 JDBC URL 参数。 |

## Python 用法

```python
from datus_oceanbase_oracle import OceanBaseOracleConnector

connector = OceanBaseOracleConnector(
    {
        "host": "172.22.32.50",
        "port": 2883,
        "connection_mode": "odp",
        "database": "DEV_TENANT01",
        "username": "npims_nl2sql@DEV_TENANT01#DEV_Cluster01",
        "password": "your_password",
        "schema": "NPIMS",
        "jar_path": "/opt/datus/jars/oceanbase-client.jar",
    }
)

try:
    print(connector.test_connection())

    result = connector.execute_query("SELECT 1 FROM DUAL", result_format="list")
    print(result.sql_return)

    tables = connector.get_tables(schema_name="NPIMS")
    print(tables)
finally:
    connector.close()
```

## 权限建议

用于 Datus 问数和元数据浏览的账号建议至少具备：

- 连接目标 OceanBase Oracle 租户的权限。
- 对业务 schema 下目标表和视图的 `SELECT` 权限。
- 通过 `ALL_USERS`、`ALL_TABLES`、`ALL_VIEWS`、`ALL_MVIEWS`、`ALL_TAB_COLUMNS`、
  `ALL_CONSTRAINTS`、`ALL_CONS_COLUMNS`、`ALL_COL_COMMENTS` 查看可访问对象的权限。
- 如需完整 DDL，建议确保账号可以调用 `DBMS_METADATA.GET_DDL` 查看目标对象定义。

如果 `DBMS_METADATA.GET_DDL` 不可用，适配器会尝试根据列信息重建基础表结构，但该
fallback 不会完整覆盖索引、外键、check 约束、复杂 view 定义等对象信息。

## 常见问题

### 连接成功但看不到表

优先检查 `schema` 是否为业务表实际所在的 Oracle schema/owner。JDBC URL 中的 `/NPIMS`
在当前适配器中会映射为：

```yaml
schema: NPIMS
```

如果业务表实际属于 `NPIMS_NL2SQL`，则应配置为：

```yaml
schema: NPIMS_NL2SQL
```

### YAML 中的用户名或密码包含 `#`

必须加引号：

```yaml
username: "user@tenant#cluster"
password: "aaAA11##"
```

不加引号时，YAML 会把 `#` 后面的内容当作注释，导致 Datus 实际读取到的用户名或密码不
完整。

### 找不到 JDBC driver

检查：

- `jar_path` 是否存在。
- Datus 进程是否有读取该文件的权限。
- 如果运行在 Docker 容器中，`jar_path` 是否是容器内路径。
- Java 是否可用：`java -version`。

### ODP 和直连如何选择

优先使用业务环境提供的标准连接入口。如果给出的用户名形如 `user@tenant#cluster`，通常
使用 ODP/OBProxy：

```yaml
connection_mode: odp
port: 2883
```

如果给出的用户名形如 `user@tenant`，并且连接地址是 OBServer，则通常使用直连：

```yaml
connection_mode: direct
port: 2881
```

### 需要显式配置 `extra_jdbc_params` 吗

通常不需要。适配器默认会加入：

```text
useSSL=false
useUnicode=true
characterEncoding=utf-8
connectTimeout=<connect_timeout_seconds * 1000>
```

只有在需要追加环境特定 JDBC 参数时，才需要配置：

```yaml
extra_jdbc_params:
  someParam: someValue
```

## 测试

当前仓库提供单元测试，单元测试不需要真实 OceanBase 实例：

```bash
cd datus-db-adapters
uv run pytest datus-oceanbase-oracle/tests/unit -v
```

当前适配器暂未提供集成测试夹具。连接真实 OceanBase Oracle 租户时，建议先用上面的
Python smoke test 或 Datus 数据源连接测试验证：

```sql
SELECT 1 FROM DUAL
```

## 已知限制

- 该适配器依赖 OceanBase Connector/J jar，需要手动下载并配置 `jar_path`。
- 该适配器依赖 Java 运行时。
- 目前没有随仓库提供可自动运行的 OceanBase Oracle 集成测试。
- `database` 字段在该适配器中表示 OceanBase tenant；Oracle schema 应使用 `schema` 或
  `schema_name`。
- DDL fallback 只重建基础表结构，不保证覆盖所有数据库对象和约束细节。
