# datus-oracle

`datus-oracle` 是 Datus 的 Oracle Database 适配器。它基于 SQLAlchemy 和
`python-oracledb`，用于连接 Oracle 数据库、执行 SQL、读取 schema/table/view 元数据、
提取 DDL、读取样例数据，并作为通用 SQLAlchemy 迁移目标使用。

该适配器不使用 JDBC，因此不需要下载 JDBC jar。默认使用 `python-oracledb` Thin mode；
只有在显式配置 `thick_mode: true` 时，才需要准备 Oracle Client / Oracle Instant Client。

## 安装

```bash
pip install datus-oracle
```

在 monorepo 开发环境中，可在 `datus-db-adapters` workspace 下运行：

```bash
uv sync --dev
```

## 功能

- 通过 `SQLAlchemy` 和 `python-oracledb` 执行 SQL。
- 支持 Oracle service name 和 SID 两种连接方式。
- 支持 `python-oracledb` Thin mode 和 Thick mode。
- 支持 schema/user 元数据发现。
- 支持表、视图、物化视图列表读取。
- 支持列类型、主键、默认值、列注释等列级元数据读取。
- 支持通过 `DBMS_METADATA.GET_DDL` 提取对象 DDL。
- 支持使用 `FETCH FIRST n ROWS ONLY` 读取样例数据。

## 基础配置

最常见配置如下：

```yaml
database:
  type: oracle
  host: localhost
  port: 1521
  username: app
  password: secret
  database: FREEPDB1
  schema: APP
```

字段说明：

| 字段 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `type` | 是 | 无 | Datus 数据源类型，固定为 `oracle`。 |
| `host` | 否 | `127.0.0.1` | Oracle listener 地址。 |
| `port` | 否 | `1521` | Oracle listener 端口。 |
| `username` | 是 | 无 | Oracle 用户名。 |
| `password` | 否 | 空字符串 | Oracle 密码。 |
| `database` | 否 | `FREEPDB1` | `service_name` 的别名。 |
| `service_name` | 否 | `FREEPDB1` | Oracle service name。与 `sid` 互斥。 |
| `sid` | 否 | 无 | Oracle SID。与 `service_name` / `database` 互斥。 |
| `schema` / `schema_name` | 否 | 用户名大写 | 默认 Oracle schema/owner。 |
| `thick_mode` | 否 | `false` | 是否启用 `python-oracledb` Thick mode。 |
| `timeout_seconds` | 否 | `30` | 连接超时秒数。 |

`database` 在该适配器中会被当作 Oracle `service_name`。如果需要连接老式 SID，可改用
`sid`：

```yaml
database:
  type: oracle
  host: localhost
  port: 1521
  username: app
  password: secret
  sid: XE
  schema: APP
```

`service_name` / `database` 和 `sid` 不能同时配置。

## Thin Mode 与 Thick Mode

`python-oracledb` 默认运行在 Thin mode。Thin mode 直接由 Python driver 连接 Oracle
Database，不需要 Oracle Client libraries。对大多数 Oracle 12.1 及以上数据库，Thin mode
通常足够使用。

Thick mode 会加载 Oracle Client libraries，由 Oracle Client 处理网络连接和部分高级特性。
以下场景通常需要考虑 Thick mode：

- 需要连接较老的 Oracle Database 版本。
- 连接环境要求 Native Network Encryption、校验、部分高级认证或 Oracle Client 侧能力。
- 已有部署规范要求使用 Oracle Instant Client。
- 需要与原 `cx_Oracle` 厚客户端行为保持一致。

当前适配器的实现是：

```python
if config.thick_mode:
    import oracledb

    oracledb.init_oracle_client()
```

也就是说，配置 `thick_mode: true` 后，适配器会调用
`oracledb.init_oracle_client()`，但当前没有提供 `lib_dir` 配置项。因此 Oracle Client
library 必须能被当前进程通过系统动态库搜索路径找到。

> 重要：`python-oracledb` 的模式是进程级的。必须在创建任何 Oracle 连接或连接池之前启
> 用 Thick mode。一旦进程已经创建过连接，不能再在同一进程中从 Thin mode 切换到 Thick
> mode，反过来也一样。

## Thick Mode 环境准备

启用 Thick mode 时，需要在运行 Datus 的机器或容器中安装 Oracle Client libraries。常用
方式是安装 Oracle Instant Client。

推荐使用 Oracle Client 19 或更高版本。具体版本兼容性以 `python-oracledb` 官方文档和
Oracle 数据库版本为准。

### Linux

假设 Instant Client 解压到：

```text
/opt/oracle/instantclient_21_13
```

启动 Datus 前设置动态库路径：

```bash
export LD_LIBRARY_PATH=/opt/oracle/instantclient_21_13:${LD_LIBRARY_PATH}
```

然后在 Datus 配置中启用：

```yaml
database:
  type: oracle
  host: 127.0.0.1
  port: 1521
  username: app
  password: secret
  database: FREEPDB1
  schema: APP
  thick_mode: true
```

如果部署在 Docker 中，必须把 Instant Client 安装或挂载到容器内，并在容器启动时设置
`LD_LIBRARY_PATH`。例如：

```bash
docker run \
  -e LD_LIBRARY_PATH=/opt/oracle/instantclient_21_13 \
  -v /host/oracle/instantclient_21_13:/opt/oracle/instantclient_21_13:ro \
  your-datus-image
```

### macOS

可以安装 Oracle Instant Client 后，将库目录放到动态库可发现的位置。常见做法是设置：

```bash
export DYLD_LIBRARY_PATH=/path/to/instantclient:${DYLD_LIBRARY_PATH}
```

macOS 对动态库环境变量有安全限制。如果进程仍无法加载 Oracle Client，建议按 Oracle
Instant Client 官方安装说明配置库路径，或把客户端库放到系统可发现目录。

### Windows

将 Oracle Instant Client 目录加入 `PATH`，例如：

```powershell
$env:PATH = "C:\oracle\instantclient_21_13;$env:PATH"
```

然后启动 Datus，并在配置里设置：

```yaml
thick_mode: true
```

### 当前不支持 `lib_dir` 配置

`python-oracledb` 本身支持在代码中调用：

```python
oracledb.init_oracle_client(lib_dir="/path/to/instantclient")
```

但当前 `datus-oracle` 的配置模型只有 `thick_mode: true/false`，没有 `oracle_client_lib_dir`
或类似字段。因此目前不要在 YAML 中写 `lib_dir`，它会因为 `extra="forbid"` 被拒绝。

如果部署环境必须通过 `lib_dir` 指定 Oracle Client 路径，需要先扩展
`OracleConfig` 和 `OracleConnector` 的实现。

## Python 用法

Thin mode 示例：

```python
from datus_oracle import OracleConfig, OracleConnector

connector = OracleConnector(
    OracleConfig(
        host="localhost",
        port=1521,
        username="app",
        password="secret",
        service_name="FREEPDB1",
        schema="APP",
    )
)

try:
    result = connector.execute({"sql_query": "SELECT 1 FROM DUAL"}, result_format="list")
    print(result.sql_return)

    tables = connector.get_tables(schema_name="APP")
    print(tables)

    columns = connector.get_schema(schema_name="APP", table_name="CUSTOMERS")
    print(columns)
finally:
    connector.close()
```

Thick mode 示例：

```python
from datus_oracle import OracleConfig, OracleConnector

connector = OracleConnector(
    OracleConfig(
        host="localhost",
        port=1521,
        username="app",
        password="secret",
        service_name="FREEPDB1",
        schema="APP",
        thick_mode=True,
    )
)

try:
    print(connector.test_connection())
finally:
    connector.close()
```

## 权限建议

用于 Datus 问数和元数据浏览的账号建议至少具备：

- 连接目标 Oracle service/SID 的权限。
- 对业务 schema 下目标表和视图的 `SELECT` 权限。
- 通过 `ALL_USERS`、`ALL_TABLES`、`ALL_VIEWS`、`ALL_MVIEWS`、`ALL_TAB_COLUMNS`、
  `ALL_CONSTRAINTS`、`ALL_CONS_COLUMNS`、`ALL_COL_COMMENTS` 查看可访问对象的权限。
- 如需完整 DDL，建议确保账号可以调用 `DBMS_METADATA.GET_DDL` 查看目标对象定义。

## 常见问题

### 什么时候需要 Thick Mode

默认先使用 Thin mode。如果 Thin mode 能正常连接并满足功能需求，不需要启用 Thick mode。
只有在数据库版本、网络加密、认证方式或部署规范要求 Oracle Client 时，再启用
`thick_mode: true`。

### `DPI-1047: Cannot locate a 64-bit Oracle Client library`

该错误通常表示 Thick mode 已启用，但进程找不到 Oracle Client library。检查：

- 是否已经安装 Oracle Instant Client。
- Datus 运行进程是否能看到对应动态库路径。
- Linux 下 `LD_LIBRARY_PATH` 是否在进程启动前设置。
- Windows 下 Instant Client 目录是否已加入 `PATH`。
- Python、操作系统和 Oracle Client 是否都是同一架构，例如都是 64-bit。
- 如果在 Docker 中运行，Instant Client 是否在容器内，而不是只存在于宿主机。

### `thick_mode: true` 仍然没有进入 Thick Mode

确认 Datus 进程中没有在此之前创建过 Oracle 连接。`python-oracledb` 的 Thin/Thick mode
不能在创建连接后切换。如果已经创建过连接，需要重启 Datus 进程，并确保首次 Oracle 连接
使用了 `thick_mode: true`。

### 连接成功但看不到表

优先检查 `schema` 是否是业务表实际所在的 Oracle schema/owner。默认情况下，如果未配置
`schema`，适配器会使用用户名的大写形式作为 schema。

例如：

```yaml
username: app
schema: REPORTING
```

表示连接用户是 `app`，但默认读取 `REPORTING` schema 下的对象。

### 使用 SID 连接

如果目标库使用 SID，不要同时配置 `database` / `service_name`：

```yaml
database:
  type: oracle
  host: localhost
  port: 1521
  username: app
  password: secret
  sid: XE
  schema: APP
```

## 测试

单元测试：

```bash
cd datus-db-adapters
uv run pytest datus-oracle/tests/unit -v
```

集成测试需要可访问的 Oracle 实例：

```bash
export DATUS_ORACLE_HOST=127.0.0.1
export DATUS_ORACLE_PORT=1521
export DATUS_ORACLE_USERNAME=app
export DATUS_ORACLE_PASSWORD=secret
export DATUS_ORACLE_SERVICE_NAME=FREEPDB1
export DATUS_ORACLE_SCHEMA=APP

uv run pytest datus-oracle/tests/integration -v
```

如果要在 Thick mode 下运行集成测试，先按上文配置 Oracle Client 环境，再在对应测试或
Datus 配置中启用 `thick_mode: true`。

## 已知限制

- 当前配置不支持传入 `oracledb.init_oracle_client(lib_dir=...)` 的 `lib_dir`。
- Thick mode 需要运行环境自行安装并暴露 Oracle Client libraries。
- 迁移目标能力目前继承自 SQLAlchemy 通用实现，不包含 Oracle 专属类型映射和 DDL 规则。
- DDL 获取依赖 `DBMS_METADATA.GET_DDL`；权限不足时只会返回不可用提示，不会完整重建
  DDL。

## 参考

- `python-oracledb` Thick mode 初始化文档：
  https://python-oracledb.readthedocs.io/en/latest/user_guide/initialization.html
- `python-oracledb` 安装与 Oracle Client 版本说明：
  https://python-oracledb.readthedocs.io/en/latest/user_guide/installation.html
- Thin mode 与 Thick mode 差异：
  https://python-oracledb.readthedocs.io/en/latest/user_guide/appendix_b.html
