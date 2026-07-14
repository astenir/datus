# MetricFlow OceanBase Oracle 发布与验收

本文定义 OceanBase Oracle MetricFlow engine 的仓库边界、首版能力和发布顺序。该实现
横跨多个独立包，这些包以顶层项目纳入 Datus monorepo，但不应复制或 vendor 到
`datus-agent`。

面向可访问私有 PyPI 的企业内网安装、配置、systemd 启动和真实租户验收步骤，见
[MetricFlow OceanBase Oracle 内网部署与验收](../../../docs/metricflow-oceanbase-oracle-intranet-deployment.zh-CN.md)。

## 仓库边界

代码归属链路如下：

1. `datus-db-adapters/datus-oceanbase-oracle` 负责 JDBC 连接、连接池、元数据和参数化
   DataFrame 查询。
2. `Datus-ai/metricflow` 负责 `oceanbase-oracle` dialect、engine 能力声明、SQL renderer、
   参数转换、dry-run 和 SQL client。
3. `Datus-ai/datus-semantic-adapter` 负责 Datus semantic adapter，并把 datasource 配置
   传给 MetricFlow。
4. `datus-agent` 负责选择运行时 datasource、加载 semantic adapter，并且只在语义校验
   成功后发布模型。

monorepo 以顶层 `metricflow/` 和 `datus-semantic-adapter/` 项目保存源码及其上游历史，
并通过 Datus Agent 的本地 `tool.uv.sources` 映射安装。不要再创建嵌套源码仓库，也不要
把这些代码复制到 `datus-agent`。

## 首版能力边界

首个 profile 是只读实现，覆盖 adapter 初始化、语义校验、dry-run、真实指标读取、
`SUM`、`COUNT`、常见分组、Oracle 日/周/月/季度/年截断、时间偏移、Oracle 行数限制和
JDBC 参数绑定。

首版不覆盖由 MetricFlow 创建或删除 schema/table、DataFrame 写入、查询取消、
percentile 能力和通用写入型 MetricFlow workload。对应方法必须明确失败，不能静默宣称
支持。

## 源码开发安装

使用 Datus Agent 的虚拟环境。`metricflow-oceanbase-oracle` extra 会把完整依赖链映射到
monorepo 内的 editable source：

```bash
cd datus-agent
uv sync --dev --extra metricflow-oceanbase-oracle
```

不要把机器绝对路径写进发布元数据，也不要提交 editable install 产物。受版本控制的
`uv.lock` 使用相对 monorepo source，保证开发环境可以复现。

## 包发布顺序

必须按依赖方向发布。当前候选版本顺序是：

1. 发布 `datus-oceanbase-oracle` `0.1.0`，确认 wheel 能从目标包索引正常安装。
   Connector/J 仍由用户在运行环境提供，不打进 wheel。
2. 升级并发布 `datus-metricflow`（候选 `0.2.8`）。只有第 1 步的包能从索引解析后，
   才能增加可解析的 `oceanbase-oracle` optional extra；否则只记录独立安装要求。
3. 升级并发布 `datus-semantic-metricflow`（候选 `0.2.9`），最低依赖必须指向包含该
   engine 的 `datus-metricflow`。可以让 OceanBase extra 继续引用 MetricFlow extra，但
   不应强制其他数据库用户安装 JDBC adapter。
4. 所有制品都能从配置的包索引解析后，才更新 `datus-agent` 依赖约束和 `uv.lock`。

如果候选版本号被其他发布占用，应顺延版本号，但不能改变发布顺序。禁止先发布一个带有
不可解析传递依赖的 semantic adapter。

## 真实租户验收门禁

公开 OceanBase CE Docker 镜像不能替代 Oracle 模式租户。验收时需要现有真实租户和匹配
的 Connector/J：

```bash
ADAPTERS_METRICFLOW_OCEANBASE_ORACLE=1 \
OCEANBASE_ORACLE_HOST=ob.example.com \
OCEANBASE_ORACLE_PORT=2883 \
OCEANBASE_ORACLE_USERNAME='app@tenant#cluster' \
OCEANBASE_ORACLE_PASSWORD='...' \
OCEANBASE_ORACLE_DATABASE=tenant \
OCEANBASE_ORACLE_SCHEMA=APP \
OCEANBASE_ORACLE_JAR_PATH=/opt/datus/jars/oceanbase-client.jar \
OCEANBASE_ORACLE_METRICFLOW_RELATION=DATUS_MF_ORDERS_RO \
OCEANBASE_ORACLE_METRICFLOW_TIME_START=2025-01-01 \
OCEANBASE_ORACLE_METRICFLOW_TIME_END=2025-01-31 \
uv run pytest \
  tests/integration/adapters/test_semantic_metricflow_oceanbase_oracle.py -v
```

真实租户测试使用已有表或视图，只执行 `SELECT`。默认要求关系中存在 `ID`、`AMOUNT`、
`CREATED_AT` 三列；可分别通过 `OCEANBASE_ORACLE_METRICFLOW_ID_COLUMN`、
`OCEANBASE_ORACLE_METRICFLOW_AMOUNT_COLUMN` 和
`OCEANBASE_ORACLE_METRICFLOW_TIME_COLUMN` 覆盖。时间范围必须选择不会再变化的闭合历史
周期，测试会用参数化基准 SQL 计算期望值，并在结束时再次确认数据没有漂移。

运行账号只需登录和读取目标对象，不需要 `CREATE TABLE`、`DROP TABLE`、`INSERT`、
`UPDATE` 或 `DELETE` 权限。

本验收覆盖非累计指标、ratio、时间过滤和时间分组，不依赖 `mf_time_spine`。如果业务模型
使用 cumulative 或 offset metric，需要由数据所有者预置可读的 `MF_TIME_SPINE`；只读
client 在该对象不存在时会明确失败，不会自行创建。

标记 production-ready 前，真实环境至少要验证：

- 连接和当前 schema 初始化；
- semantic validation；
- 零行 dry-run；
- 只读基准 SQL 与 MetricFlow 结果一致；
- `SUM`、`COUNT` 真实指标查询；
- 时间过滤以及所有已声明时间粒度；
- 分组和行数限制；
- 如果仍声明对应能力，则验证 ratio cast、full outer join 和随机函数；
- 字符串、日期、重复命名参数、注释场景的参数绑定；
- 单元/客户端测试证明写入、取消和 percentile 接口按预期明确失败；真实只读租户验收不
  主动发送变更语句。

发布证据需要记录准确的 OceanBase 版本、Connector/J 版本、连接模式、测试命令和结果。
单元测试与 mock 测试是必要条件，但不能替代真实租户验收。
