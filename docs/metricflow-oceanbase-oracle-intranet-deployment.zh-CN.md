# MetricFlow OceanBase Oracle 内网部署与验收

本文只覆盖“私有 PyPI + 完整 monorepo 源码 + 真实 OceanBase Oracle 模式租户”的内网交付。它不是通用 Datus 部署手册，也不覆盖完全断网 wheelhouse 制作。

当前实现是只读 profile。只有真实租户验收通过并保留版本、JDBC 与测试证据后，才能进入生产评估；公开 OceanBase CE 镜像不能替代 Oracle 模式租户。

## 1. 部署边界

必须交付完整 monorepo，不能只复制 `datus-agent/`。`datus-agent/pyproject.toml` 通过相对路径加载以下本地源码：

```text
datus-agent/
datus-db-adapters/
datus-semantic-adapter/
datus-storage-adapters/
metricflow/
```

推荐安装 `enterprise-intranet` extra，它包含当前内网基线中的 MetricFlow、OceanBase Oracle、标准 Oracle、MySQL、PostgreSQL 业务 adapter，以及 OceanBase MySQL/PostgreSQL 内部存储 backend。仅做语义链路测试时可使用较小的 `metricflow-oceanbase-oracle` extra。

业务 OceanBase Oracle datasource 与 Datus 内部 OceanBase MySQL storage 是两个独立插件和权限面：前者应使用只读业务账号，后者需要独立可写 tenant/database 和账号。

## 2. 环境要求

| 依赖 | 要求 |
| --- | --- |
| Python | CPython 3.12 |
| uv | 企业批准的版本 |
| 私有 PyPI | 能提供 `datus-agent/uv.lock` 所需全部第三方依赖和构建依赖 |
| Java | 与 Connector/J 和目标架构兼容的 JRE/JDK |
| Connector/J | 由 OceanBase 平台团队提供，单独记录版本和 SHA-256 |
| 数据库 | 可访问的真实 OceanBase Oracle 模式租户 |

建议目录：

```text
/opt/datus/releases/<release-id>/
/opt/datus/current
/etc/datus/agent.yml
/etc/datus/oceanbase-oracle.env
/opt/datus/jars/oceanbase-client.jar
/var/lib/datus
```

使用独立 `datus` 系统账号运行；release 与 jar 只读，运行数据可写，环境文件权限为 `0600`。不要以 root 长期运行 API。

## 3. 交付源码

长期方案是企业内网 Git 镜像，并固定 commit SHA。一次性交付可在外网交付机运行：

```bash
deploy/offline/package-intranet.sh \
  --branch feature/metricflow-oceanbase-oracle \
  --strict-clean \
  --skip-web
```

内网解包并克隆 bundle：

```bash
tar -xzf datus-offline-*.tar.gz
cd datus-offline-*
git clone source/datus-*.bundle ../datus-<release-id>
cd ../datus-<release-id>
git rev-parse HEAD
git status --short --branch
```

`package-intranet.sh` 包含已提交 Git 历史和配置模板，不包含 Python wheelhouse、真实密钥或 Connector/J。

## 4. 私有 PyPI 与 Python 环境

先让操作系统信任企业 CA，再配置 uv：

```bash
export UV_DEFAULT_INDEX='https://pypi.example.internal/simple'
export UV_SYSTEM_CERTS=true
uv auth login pypi.example.internal --username <readonly-user>
```

受版本控制的 `uv.lock` 记录公开索引。私有索引 URL 不同且不是透明代理时，为每个 release 生成部署专用锁文件；不要使用 `--upgrade`：

```bash
cd /opt/datus/releases/<release-id>/datus-agent
cp uv.lock uv.lock.upstream
uv lock
git diff -- uv.lock
```

审查时只接受 registry URL 等预期变化。大规模版本漂移通常说明私有镜像缺少原锁文件版本，应先补齐制品。

验收环境：

```bash
uv sync --locked --dev --extra enterprise-intranet
uv lock --check
```

运行环境：

```bash
uv sync --locked --no-dev --extra enterprise-intranet
```

不要在同一 release venv 中混用全局 site-packages、临时 `pip install` 和 `uv sync`。

## 5. Java 与 Connector/J

```bash
install -d -m 0755 /opt/datus/jars
install -m 0444 /path/to/oceanbase-client.jar \
  /opt/datus/jars/oceanbase-client.jar
java -version
test -r /opt/datus/jars/oceanbase-client.jar
sha256sum /opt/datus/jars/oceanbase-client.jar
```

记录 OceanBase Server、Connector/J、Java 版本，连接模式（ODP 或 observer）以及目标地址和端口。容器部署时，Java、jar 和配置路径必须在容器内可见。

## 6. Datasource 配置

把 datasource 片段合并到已经过验证的配置，不要覆盖现有 provider、认证、企业权限、模型或内部存储配置：

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

`/etc/datus/oceanbase-oracle.env` 示例：

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

最后三个变量只用于真实租户验收。用户名或密码包含 `#` 时必须正确引用；`schema` 建议使用实际 Oracle owner 的大写形式。

显式 `--config` 不会阻止项目级 `./.datus/config.yml` 覆盖默认 datasource。部署前检查 systemd `WorkingDirectory` 及其中的项目配置。

## 7. 分层验收

所有命令从 release 的 `datus-agent/` 执行，并直接使用 `.venv/bin/python`，避免 `uv run` 在验收时重新同步环境。

### 7.1 包与 entry point

```bash
.venv/bin/python -c "
from importlib import metadata
import metricflow, datus_oceanbase_oracle, datus_semantic_metricflow
from datus.storage.rdb import RdbRegistry
from datus.storage.vector import VectorRegistry
print(metricflow.__file__)
print(datus_oceanbase_oracle.__file__)
print(datus_semantic_metricflow.__file__)
print(sorted(ep.name for ep in metadata.entry_points(group='datus.adapters')))
print(RdbRegistry.registered_types())
print(VectorRegistry.registered_types())
"
```

模块路径必须指向当前 release。`enterprise-intranet` profile 的 database adapters 应包含 `mysql`、`oceanbase-oracle`、`oracle`、`postgresql`；RDB/vector backend 应包含 `oceanbase-mysql` 和 `postgresql`。

### 7.2 无数据库初始化回归

```bash
HOME=/tmp/datus-test-home \
.venv/bin/python -m pytest -p no:rerunfailures \
  tests/unit_tests/tools/func_tool/test_semantic_tools.py::TestRuntimeDbContext::test_metricflow_adapter_initializes_for_oceanbase_oracle \
  -q
```

该测试只证明 Datus → semantic adapter → MetricFlow → engine 初始化链路，不能替代真实 JDBC 验收。

### 7.3 真实租户只读验收

```bash
set -a
. /etc/datus/oceanbase-oracle.env
set +a

ADAPTERS_METRICFLOW_OCEANBASE_ORACLE=1 \
.venv/bin/python -m pytest -p no:rerunfailures \
  tests/integration/adapters/test_semantic_metricflow_oceanbase_oracle.py \
  -v
```

目标 relation 必须在一个不会变化的闭合历史时间窗内有数据，默认列为 `ID`、`AMOUNT`、`CREATED_AT`。列名不同时设置：

```text
OCEANBASE_ORACLE_METRICFLOW_ID_COLUMN
OCEANBASE_ORACLE_METRICFLOW_AMOUNT_COLUMN
OCEANBASE_ORACLE_METRICFLOW_TIME_COLUMN
```

验收只需要登录与目标对象 `SELECT` 权限，不执行 DDL/DML。测试会比较参数化基准 SQL 与 MetricFlow 的 `SUM`、`COUNT`、ratio、时间过滤和时间粒度结果，并在结束时复查基准数据未变化。

非累计指标不需要 `MF_TIME_SPINE`；cumulative/offset 指标仍要求数据所有者预置并授权可读的 `MF_TIME_SPINE`，只读 client 不会自动创建。

### 7.4 API smoke

```bash
HOME=/var/lib/datus \
.venv/bin/datus-api \
  --config /etc/datus/agent.yml \
  --host 127.0.0.1 \
  --port 8000 \
  --workers 1

curl --fail http://127.0.0.1:8000/health
```

首轮验收保持单 worker。当前 chat task 与 SSE 状态尚未完全外置，多实例需要粘性路由。

## 8. 切换、回退与故障定位

验收通过后使用 release 软链接切换：

```bash
ln -sfn /opt/datus/releases/<release-id> /opt/datus/current
systemctl restart datus-api
curl --fail http://127.0.0.1:8000/health
```

回退时把软链接指回上一个已验证 release 并重启。配置和运行数据必须位于 release 外，避免随代码切换丢失。

常见问题按以下顺序定位：

| 现象 | 首要检查 |
| --- | --- |
| dialect 不支持 | Python/MetricFlow 是否来自当前 release |
| `No module named datus_oceanbase_oracle` | 是否安装 `metricflow-oceanbase-oracle` 或 `enterprise-intranet` extra |
| `No module named jpype` / JVM 失败 | `JPype1`、Java 架构、运行账号 PATH |
| jar 不存在 | `jar_path` 是否为进程/容器内可读路径 |
| `uv sync --locked` 要求更新 | 私有索引 URL 与 lock source 是否不同 |
| storage backend 未注册 | 是否安装 `enterprise-intranet`，并检查 RDB/vector entry point |
| 连接成功但 semantic validation 失败 | datasource 选择、`.datus/config.yml` 覆盖、schema、列名、JDBC 最内层错误 |

## 9. 验收记录

每次至少保留：

```text
Datus commit SHA
受版本控制和内网 uv.lock SHA-256
Python / uv / OS / CPU 架构
OceanBase Server / Connector/J / Java 版本
Connector/J SHA-256
连接模式、端口、tenant、schema
只读 relation、列映射、时间窗口和对象授权
初始化回归、真实租户测试、API health 结果
验收时间和验收人
```

更细的测试变量和契约以 [`datus-agent/tests/integration/adapters/README.md`](../datus-agent/tests/integration/adapters/README.md) 为准；产品侧语义配置见 `datus-agent/docs/` 中的 MetricFlow 文档。
