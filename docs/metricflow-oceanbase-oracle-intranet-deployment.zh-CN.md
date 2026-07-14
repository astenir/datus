# MetricFlow OceanBase Oracle 内网部署与验收

本文面向以下部署条件：

- 目标环境是可访问私有 PyPI 的企业内网；
- 使用 Datus monorepo 中尚未拆分发布的 MetricFlow OceanBase Oracle 源码链路；
- 目标 Python 为 3.12；
- 已有可访问的 OceanBase Oracle 模式租户；
- 先完成内网验收，再决定是否进入生产部署。

本文不覆盖完全断网 wheelhouse 制作，也不把当前实现描述为已通过生产验收。公开
OceanBase CE 镜像不能替代真实 Oracle 模式租户。

## 1. 部署结论

当前阶段推荐使用“完整 monorepo 源码 + 私有 PyPI + 锁定依赖”方式，不要只复制
`datus-agent/`，也不要手工逐个 `pip install`。

完整源码至少应包含：

```text
datus/
├── datus-agent/
├── datus-db-adapters/
│   ├── datus-db-core/
│   └── datus-oceanbase-oracle/
├── datus-semantic-adapter/
│   ├── datus-semantic-core/
│   └── datus-semantic-metricflow/
└── metricflow/
```

`datus-agent/pyproject.toml` 通过相对路径把这些源码安装到同一个虚拟环境。只复制
`datus-agent/` 会导致本地 source mapping 失效，运行时可能重新加载不含
`oceanbase-oracle` dialect 的旧版 MetricFlow。

## 2. 组件和依赖清单

### 2.1 Datus 源码包

`metricflow-oceanbase-oracle` extra 直接声明：

```text
datus-metricflow>=0.2.7
datus-semantic-metricflow>=0.2.8
datus-oceanbase-oracle>=0.1.0
```

完整 Datus 包链路为：

| 包 | 来源 | 作用 |
| --- | --- | --- |
| `datus-agent` | `datus-agent/` | datasource 选择、semantic adapter 加载、模型发布和 API |
| `datus-metricflow` | `metricflow/` | OceanBase Oracle engine、client、renderer、dry-run 和 SQL 参数转换 |
| `datus-semantic-core` | `datus-semantic-adapter/datus-semantic-core/` | semantic adapter 接口 |
| `datus-semantic-metricflow` | `datus-semantic-adapter/datus-semantic-metricflow/` | Datus 到 MetricFlow 的配置和查询适配 |
| `datus-db-core` | `datus-db-adapters/datus-db-core/` | 数据库 adapter 公共接口 |
| `datus-oceanbase-oracle` | `datus-db-adapters/datus-oceanbase-oracle/` | JDBC、连接池、元数据和参数化查询 |

这些包在当前部署模式下由 monorepo 本地源码构建，不要求先发布到私有 PyPI。

### 2.2 私有 PyPI 必须提供的内容

私有 PyPI 必须能提供 `datus-agent/uv.lock` 中的全部第三方依赖，不能只白名单以下几个
数据库包。关键依赖包括但不限于：

```text
DBUtils
JayDeBeApi
JPype1
pandas
pydantic
poetry-core
hatchling
setuptools
wheel
```

其中 `JPype1` 可能使用平台相关 wheel；私有镜像必须具备与目标 OS、CPU 架构和
Python 3.12 匹配的制品。`poetry-core` 用于构建 `datus-metricflow`，`hatchling`、
`setuptools` 和 `wheel` 用于构建其余本地项目。

### 2.3 非 Python 依赖

目标机还必须具备：

| 依赖 | 要求 |
| --- | --- |
| Python | CPython 3.12 |
| uv | 使用企业批准的 uv 可执行文件或私有 PyPI 制品 |
| Java | 与所选 OceanBase Connector/J 兼容的 JRE 或 JDK |
| Connector/J | 单独提供的 OceanBase JDBC jar，不包含在 Python wheel 中 |
| 网络 | 能访问私有 PyPI、OceanBase/ODP 地址和端口 |
| 数据库 | 真实 OceanBase Oracle 模式测试租户 |

如果 Datus 在容器中运行，Java 和 Connector/J 必须在容器内可见；配置中的 `jar_path`
也必须使用容器内路径。

## 3. 目录和账号建议

以下目录仅为推荐值，可按企业规范调整：

```text
/opt/datus/releases/<release-id>/   # 只读发布源码
/opt/datus/current                  # 指向当前发布的软链接
/etc/datus/agent.yml                # 非密钥运行配置
/etc/datus/oceanbase-oracle.env     # 数据库和私有服务密钥
/opt/datus/jars/oceanbase-client.jar
/var/lib/datus                      # Datus HOME 和运行数据
/var/log/datus                      # 服务日志（如未交给 journald）
```

建议使用独立的 `datus` 系统账号运行服务，并确保：

- 发布目录和 jar 对运行账号只读；
- `/var/lib/datus` 对运行账号可写；
- 环境变量文件权限为 `0600`；
- 不把数据库密码、PyPI token、模型 API key 写入 Git；
- 不以 root 身份长期运行 API。

## 4. 传入完整 monorepo

### 4.1 长期方案：内网 Git 镜像

把 `feature/metricflow-oceanbase-oracle` 推送到企业内网 Git 后，在目标机执行：

```bash
install -d -m 0755 /opt/datus/releases
cd /opt/datus/releases

git clone \
  --branch feature/metricflow-oceanbase-oracle \
  --single-branch \
  https://git.example.internal/data/datus.git \
  metricflow-oceanbase-oracle-<release-id>

cd metricflow-oceanbase-oracle-<release-id>
git status --short --branch
git rev-parse HEAD
```

正式交接时应记录准确 commit SHA，不要只记录可移动的分支名。

### 4.2 一次性测试：Git bundle

在能够访问当前仓库的交付机执行：

```bash
cd /path/to/datus

deploy/offline/package-intranet.sh \
  --branch feature/metricflow-oceanbase-oracle \
  --strict-clean \
  --skip-web
```

将 `dist/offline/datus-offline-*.tar.gz` 传入内网，然后执行：

```bash
cd /opt/datus/releases
tar -xzf /path/to/datus-offline-*.tar.gz
cd datus-offline-*

git clone source/datus-*.bundle ../metricflow-oceanbase-oracle-<release-id>
cd ../metricflow-oceanbase-oracle-<release-id>
git status --short --branch
git rev-parse HEAD
```

`package-intranet.sh` 当前包含 Git bundle、可选前端 dist 和配置模板，不包含 Python
wheel、Java 或 Connector/J。本场景可以从私有 PyPI 安装 Python 依赖，因此不需要离线
wheelhouse，但仍需单独传入 Connector/J。

上述命令用 `--skip-web` 是因为 MetricFlow 后端验收不依赖前端。需要同时交付 Web 时，
去掉该参数；前端构建和 Nginx 静态资源部署不改变本文的 Python、Java 和 JDBC 依赖链。

## 5. 配置私有 PyPI

以下示例假设私有索引为：

```text
https://pypi.example.internal/simple
```

先检查连通性和证书。未认证返回 `401` 也能证明网络和 TLS 已经连通：

```bash
curl --show-error --silent --output /dev/null --write-out '%{http_code}\n' \
  https://pypi.example.internal/simple/
```

如果私有 PyPI 使用企业 CA，应把 CA 安装到操作系统信任库，并让 uv 使用系统证书：

```bash
export UV_SYSTEM_CERTS=true
```

不要把 `--allow-insecure-host` 作为长期部署方案。

需要认证时，使用部署账号的只读凭据。可以交互式登录，避免把 token 放进命令历史：

```bash
uv auth login pypi.example.internal --username <readonly-user>
```

然后设置默认索引：

```bash
export UV_DEFAULT_INDEX='https://pypi.example.internal/simple'
export UV_SYSTEM_CERTS=true
```

### 5.1 处理锁文件中的源地址

当前受版本控制的 `datus-agent/uv.lock` 记录的是公开 PyPI 源地址。私有 PyPI 使用不同
URL 时，不能假设下面的组合一定会静默改写下载源：

```text
UV_DEFAULT_INDEX=<private-index> uv sync --locked ...
```

切换默认索引会让 uv 重新校验解析结果，而 `--locked` 又禁止锁文件变化。正确做法是在
每个内网 release 中生成一份部署专用锁文件，再以 `--locked` 安装：

```bash
cd /opt/datus/releases/metricflow-oceanbase-oracle-<release-id>/datus-agent

cp uv.lock uv.lock.upstream

UV_DEFAULT_INDEX='https://pypi.example.internal/simple' \
UV_SYSTEM_CERTS=true \
uv lock

git diff -- uv.lock
```

`uv lock` 默认会复用已有锁文件中的版本偏好；不要添加 `--upgrade`。审查 diff 时：

- 私有 registry URL 变化是预期结果；
- 已锁定包的大规模版本变化不是预期结果；
- 如果版本变化，先检查私有镜像是否缺少原锁文件所需版本；
- 内网生成的锁文件应与 release 一起保留，便于复现和审计；
- `uv.lock.upstream` 只用于本机比对，不要作为项目源文件提交。

如果企业私有 PyPI 是对 `pypi.org` 和制品下载域名的透明代理，并且原锁文件 URL 在
内网已经被透明路由，则可以保留原 `uv.lock`，直接进入下一节。

## 6. 安装 Python 环境

### 6.1 验收环境

验收需要 pytest 等开发依赖：

```bash
cd /opt/datus/releases/metricflow-oceanbase-oracle-<release-id>/datus-agent

UV_DEFAULT_INDEX='https://pypi.example.internal/simple' \
UV_SYSTEM_CERTS=true \
uv sync --locked --dev --extra metricflow-oceanbase-oracle

UV_DEFAULT_INDEX='https://pypi.example.internal/simple' \
UV_SYSTEM_CERTS=true \
uv lock --check
```

### 6.2 仅运行环境

真实租户验收通过后，如果运行节点不需要 pytest，可以排除开发依赖：

```bash
UV_DEFAULT_INDEX='https://pypi.example.internal/simple' \
UV_SYSTEM_CERTS=true \
uv sync --locked --no-dev --extra metricflow-oceanbase-oracle
```

不要在同一个 release 虚拟环境里混用 `pip install`、全局 site-packages 和 `uv sync`。

## 7. 安装 Java 和 Connector/J

由 OceanBase 平台团队提供与服务端兼容的 Connector/J，并记录：

```text
OceanBase Server 版本
OceanBase Connector/J 版本
JRE/JDK 版本
连接模式：ODP 或直连 observer
目标地址和端口
```

放置并检查 jar：

```bash
install -d -m 0755 /opt/datus/jars
install -m 0444 /path/to/oceanbase-client.jar \
  /opt/datus/jars/oceanbase-client.jar

java -version
test -r /opt/datus/jars/oceanbase-client.jar
sha256sum /opt/datus/jars/oceanbase-client.jar
```

建议把 jar 的 SHA-256 写入本次发布记录。

## 8. 配置 OceanBase Oracle datasource

把下面片段合并到已经过验证的 `/etc/datus/agent.yml`，不要用它覆盖现有 provider、
认证、企业权限、存储和模型配置：

```yaml
agent:
  services:
    datasources:
      oceanbase_oracle:
        type: oceanbase-oracle
        host: ${OCEANBASE_ORACLE_HOST}
        port: ${OCEANBASE_ORACLE_PORT}
        username: ${OCEANBASE_ORACLE_USERNAME}
        password: ${OCEANBASE_ORACLE_PASSWORD}
        database: ${OCEANBASE_ORACLE_DATABASE}
        schema: ${OCEANBASE_ORACLE_SCHEMA}
        jar_path: ${OCEANBASE_ORACLE_JAR_PATH}
        connection_mode: odp
        connect_timeout_seconds: 30
        query_timeout_seconds: 60
        default: true

    semantic_layer:
      metricflow:
        default: true
```

环境文件 `/etc/datus/oceanbase-oracle.env` 示例：

```bash
OCEANBASE_ORACLE_HOST="ob.example.internal"
OCEANBASE_ORACLE_PORT="2883"
OCEANBASE_ORACLE_USERNAME="app@tenant#cluster"
OCEANBASE_ORACLE_PASSWORD="replace-with-secret"
OCEANBASE_ORACLE_DATABASE="tenant"
OCEANBASE_ORACLE_SCHEMA="APP"
OCEANBASE_ORACLE_JAR_PATH="/opt/datus/jars/oceanbase-client.jar"
OCEANBASE_ORACLE_METRICFLOW_RELATION="DATUS_MF_ORDERS_RO"
OCEANBASE_ORACLE_METRICFLOW_TIME_START="2025-01-01"
OCEANBASE_ORACLE_METRICFLOW_TIME_END="2025-01-31"
```

最后三个 `OCEANBASE_ORACLE_METRICFLOW_*` 变量只用于真实租户只读验收；正常 API 问数
使用 semantic model 自己配置的 `sql_table` 和维度列，不依赖这些测试变量。

设置权限：

```bash
chown root:datus /etc/datus/agent.yml
chown datus:datus /etc/datus/oceanbase-oracle.env
chmod 0640 /etc/datus/agent.yml
chmod 0600 /etc/datus/oceanbase-oracle.env
```

注意：

- 用户名或密码包含 `#` 时必须正确引用；
- `database` 对应 Oracle 模式 tenant；
- `schema` 对应 Oracle owner/schema，建议写大写；
- `connection_mode: odp` 时应填写实际 ODP 地址和端口；
- 如果改为直连 observer，必须同步调整地址、端口和实际支持的连接参数；
- `jar_path` 是 Datus 进程实际看到的路径。

即使显式传入 `--config /etc/datus/agent.yml`，Datus 仍会从进程工作目录读取
`./.datus/config.yml` 项目覆盖。它可以改写默认 datasource 或 semantic adapter。部署前
应检查服务的 `WorkingDirectory`，避免旧项目配置覆盖上述选择：

```bash
cd /opt/datus/releases/metricflow-oceanbase-oracle-<release-id>/datus-agent
test ! -f .datus/config.yml || sed -n '1,160p' .datus/config.yml
```

## 9. 分层验收

所有验收命令都从 release 的 `datus-agent/` 目录执行，并直接使用 `.venv/bin/python`，
避免验收时由 `uv run` 再次触发依赖同步。

### 9.1 环境和网络

```bash
python3.12 --version
uv --version
java -version
test -r /opt/datus/jars/oceanbase-client.jar
curl --show-error --silent --output /dev/null --write-out '%{http_code}\n' \
  https://pypi.example.internal/simple/
```

私有索引返回 `200` 或认证要求对应的 `401`，都说明网络和 TLS 已到达服务；Python 制品
认证和可下载性最终以第 6 节的 `uv sync` 成功为准。

按企业现有工具检查 OceanBase/ODP 端口，例如：

```bash
nc -vz ob.example.internal 2883
```

### 9.2 包加载路径

```bash
cd /opt/datus/releases/metricflow-oceanbase-oracle-<release-id>/datus-agent

.venv/bin/python -c "
import metricflow
import datus_oceanbase_oracle
import datus_semantic_core
import datus_semantic_metricflow
print('metricflow:', metricflow.__file__)
print('oceanbase:', datus_oceanbase_oracle.__file__)
print('semantic-core:', datus_semantic_core.__file__)
print('semantic-metricflow:', datus_semantic_metricflow.__file__)
"
```

输出应指向当前 release 的 monorepo 目录。若指向全局 site-packages、`/tmp` 或另一份旧
checkout，应先修复 Python 环境归属，再排查业务配置。

### 9.3 无真实数据库的初始化回归

```bash
HOME=/tmp/datus-test-home \
.venv/bin/python -m pytest \
  -p no:rerunfailures \
  tests/unit_tests/tools/func_tool/test_semantic_tools.py::TestRuntimeDbContext::test_metricflow_adapter_initializes_for_oceanbase_oracle \
  -q
```

该测试证明下面的初始化链路可用：

```text
Datus Agent
  -> datus-semantic-metricflow
  -> datus-metricflow
  -> oceanbase-oracle engine
```

它不连接真实 JDBC 数据库，不能替代下一节。

### 9.4 真实 Oracle 模式租户验收

先把测试凭据加载到当前 shell。不要把真实密码复制进 shell history；推荐从权限为
`0600` 的临时环境文件加载：

```bash
set -a
. /etc/datus/oceanbase-oracle.env
set +a
```

执行：

```bash
ADAPTERS_METRICFLOW_OCEANBASE_ORACLE=1 \
.venv/bin/python -m pytest \
  -p no:rerunfailures \
  tests/integration/adapters/test_semantic_metricflow_oceanbase_oracle.py \
  -v
```

该测试只读取已有表或视图，不创建、修改或删除数据库对象。目标关系默认需要以下列：

```text
ID
AMOUNT
CREATED_AT
```

如果实际列名不同，通过以下环境变量覆盖：

```text
OCEANBASE_ORACLE_METRICFLOW_ID_COLUMN
OCEANBASE_ORACLE_METRICFLOW_AMOUNT_COLUMN
OCEANBASE_ORACLE_METRICFLOW_TIME_COLUMN
```

schema、关系和列名必须是标准的非引号 Oracle 标识符。验收时间范围必须是不会再变化的
闭合历史周期，且至少包含一行有效数据。测试先执行参数化只读基准 SQL 计算
`SUM(AMOUNT)` 和 `COUNT(ID)`，再与 MetricFlow 结果比较；模块结束时重新执行基准 SQL，
若数据发生变化会明确失败。

测试账号只需要登录和目标表/视图的对象级 `SELECT` 权限，不需要 `CREATE TABLE`、
`DROP TABLE`、`INSERT`、`UPDATE` 或 `DELETE`。它验证：

- semantic validation；
- 零行 dry-run；
- 参数化只读基准 SQL 与 MetricFlow 结果一致；
- Oracle 行数限制 SQL；
- `SUM`、`COUNT` 和 ratio metric；
- 时间过滤；
- 日、周、月、季度、年分组；
- JDBC 参数绑定；
- 真实指标结果读取。

这套验收使用非累计指标，不依赖 `MF_TIME_SPINE`。如果实际 semantic model 使用
cumulative 或 offset metric，需要由数据所有者预置 `MF_TIME_SPINE` 并向 Datus 账号
授予 `SELECT`；只读 client 在对象不存在时会明确失败，不会尝试自动建表。

### 9.5 配置加载和 API smoke

先在前台启动，确认完整配置可以初始化：

```bash
set -a
. /etc/datus/oceanbase-oracle.env
set +a

HOME=/var/lib/datus \
.venv/bin/datus-api \
  --config /etc/datus/agent.yml \
  --host 127.0.0.1 \
  --port 8000 \
  --workers 1
```

另开终端检查：

```bash
curl --fail http://127.0.0.1:8000/health
```

然后通过实际的语义模型创建/发布入口验证原始问题已消失。日志中不应再出现：

```text
Semantic adapter unavailable
Only DuckDB, MySQL, PostgreSQL ... dialects are supported
Got dialect 'oceanbase-oracle'
```

## 10. systemd 示例

真实租户验收和前台 smoke 都通过后，可以创建：

```text
/etc/systemd/system/datus-api.service
```

示例：

```ini
[Unit]
Description=Datus API with MetricFlow OceanBase Oracle
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=datus
Group=datus
WorkingDirectory=/opt/datus/current/datus-agent
Environment=HOME=/var/lib/datus
Environment=UV_SYSTEM_CERTS=true
EnvironmentFile=/etc/datus/oceanbase-oracle.env
# 按现有部署保留模型、认证等其他 EnvironmentFile
ExecStart=/opt/datus/current/datus-agent/.venv/bin/datus-api --config /etc/datus/agent.yml --host 127.0.0.1 --port 8000 --workers 1
Restart=on-failure
RestartSec=5
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
```

启用：

```bash
ln -sfn \
  /opt/datus/releases/metricflow-oceanbase-oracle-<release-id> \
  /opt/datus/current

systemctl daemon-reload
systemctl enable --now datus-api
systemctl status datus-api
journalctl -u datus-api -n 200 --no-pager
```

生产入口建议放在 Nginx/Traefik 等反向代理之后，并由代理终止 TLS。当前聊天任务和 SSE
状态尚未完全外置，多 worker 或多实例部署需要粘性会话；首轮内网验收保持
`--workers 1`。

## 11. 发布切换和回退

后续版本验收通过后再切换 `/opt/datus/current`：

```bash
ln -sfn \
  /opt/datus/releases/metricflow-oceanbase-oracle-<release-id> \
  /opt/datus/current

systemctl restart datus-api
curl --fail http://127.0.0.1:8000/health
```

回退时把软链接指回上一个已验证 release，重新启动服务。数据库 nightly 创建的是专用
测试表，不应成为发布切换或回退的一部分。

## 12. 常见故障

### 12.1 仍提示 dialect 不支持

优先运行第 9.2 节的包加载路径检查。最常见原因是进程使用了旧版 MetricFlow、全局
Python 或另一份 checkout，而不是当前 release 的 `.venv`。

### 12.2 `No module named datus_oceanbase_oracle`

确认安装命令包含：

```text
--extra metricflow-oceanbase-oracle
```

并确认执行的是当前 release 下的 `.venv/bin/python`。

### 12.3 `No module named jpype` 或 JVM 启动失败

确认 `JPype1` 已从私有 PyPI 安装，Java 可被运行账号执行，并且 JRE/JDK 架构与 Python
进程一致。

### 12.4 Connector/J jar 不存在

检查 `jar_path` 是运行进程或容器内部路径，而不是交付机、宿主机或另一台机器上的路径。

### 12.5 `uv sync --locked` 提示锁文件需要更新

通常是私有索引 URL 与受版本控制的锁文件源地址不同。按第 5.1 节生成部署专用锁文件，
检查版本没有意外漂移后再执行 `uv sync --locked`。

### 12.6 私有 PyPI 缺包

不要通过临时访问公网绕过。先让制品管理员补齐原 `uv.lock` 所需版本以及
`poetry-core`、`hatchling`、`setuptools`、`wheel` 等构建依赖，再重新生成内网锁文件。

### 12.7 连接成功但 semantic validation 失败

依次检查：

1. 当前 datasource 是否确实是 `oceanbase_oracle`；
2. 工作目录的 `.datus/config.yml` 是否覆盖了 datasource 或 semantic adapter；
3. schema/owner 是否正确且大小写符合实际；
4. 运行账号是否能读 jar；
5. Connector/J 与 OceanBase 版本是否匹配；
6. 语义模型中的表名、列名和时间维度是否存在；
7. 日志中的最终 JDBC/SQL 错误，而不只看最外层 `validate_semantic` 文案。

## 13. 验收记录模板

每次内网验收至少记录：

```text
Datus commit SHA:
受版本控制的 uv.lock SHA-256:
内网 uv.lock SHA-256:
Python 版本:
uv 版本:
操作系统和 CPU 架构:
OceanBase Server 版本:
OceanBase Connector/J 版本和 SHA-256:
Java 版本:
连接模式和端口:
测试 tenant/schema:
只读验收 relation:
只读验收时间窗口:
运行账号对象授权:
初始化回归结果:
真实租户 nightly 结果:
API health 结果:
验收时间:
验收人:
```

只有真实 Oracle 模式租户 nightly 通过，并保留上述证据后，才能继续评估
production-ready。当前首版仍是只读 profile，不支持由 MetricFlow 创建/删除业务
schema/table、通用 DataFrame 写入、查询取消或 percentile workload。

## 14. 相关文档

- [MetricFlow OceanBase Oracle 发布与验收](../datus-agent/docs/develop/metricflow_oceanbase_oracle.zh.md)
- [MetricFlow 语义适配器](../datus-agent/docs/adapters/metricflow_semantic_adapter.zh.md)
- [语义层配置](../datus-agent/docs/configuration/semantic_layer.zh.md)
- [Datus API 部署](../datus-agent/docs/API/deployment.zh.md)
- [内网交付脚本](../deploy/offline/package-intranet.sh)
