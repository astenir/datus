# MetricFlow OceanBase Oracle 发布与验收

本文定义 OceanBase Oracle MetricFlow engine 的仓库边界、首版能力和发布顺序。该实现
横跨多个独立包，不应把上游源码 vendor 到 `datus-agent`。

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

开发时把这些仓库放在同级目录，通过 editable install 串起来。不要把
`datus-semantic-adapter` 或 MetricFlow 克隆到 Datus 项目内部，也不要复制其源码到
`datus-agent`。

## 首版能力边界

首个 profile 是只读实现，覆盖 adapter 初始化、语义校验、dry-run、真实指标读取、
`SUM`、`COUNT`、常见分组、Oracle 日/周/月/季度/年截断、时间偏移、Oracle 行数限制和
JDBC 参数绑定。

首版不覆盖由 MetricFlow 创建或删除 schema/table、DataFrame 写入、查询取消、
percentile 能力和通用写入型 MetricFlow workload。对应方法必须明确失败，不能静默宣称
支持。

## 源码开发安装

使用同一个虚拟环境，并按依赖顺序 editable install。下面路径需按实际 checkout 布局
调整：

```bash
python -m pip install -e /path/to/datus/datus-db-adapters/datus-db-core
python -m pip install -e /path/to/datus/datus-db-adapters/datus-oceanbase-oracle
python -m pip install -e /path/to/metricflow
python -m pip install -e /path/to/datus-semantic-adapter/datus-semantic-core
python -m pip install -e /path/to/datus-semantic-adapter/datus-semantic-metricflow
```

不要把本地路径写进发布元数据，也不要提交 editable install 产物或在同级仓库中意外生成
的锁文件。

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
uv run pytest \
  tests/integration/adapters/test_semantic_metricflow_oceanbase_oracle.py -v
```

标记 production-ready 前，真实环境至少要验证：

- 连接和当前 schema 初始化；
- semantic validation；
- 零行 dry-run；
- `SUM`、`COUNT` 真实指标查询；
- 时间过滤以及所有已声明时间粒度；
- 分组和行数限制；
- 如果仍声明对应能力，则验证 ratio cast、full outer join 和随机函数；
- 字符串、日期、重复命名参数、注释场景的参数绑定；
- 写入、取消和 percentile 接口按预期明确失败。

发布证据需要记录准确的 OceanBase 版本、Connector/J 版本、连接模式、测试命令和结果。
单元测试与 mock 测试是必要条件，但不能替代真实租户验收。
