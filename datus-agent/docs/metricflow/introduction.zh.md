# Datus-MetricFlow 介绍

> 说明：本项目基于 [dbt-labs/metricflow](https://github.com/dbt-labs/metricflow) 0.140.0 分支继续演进，感谢 dbt Labs 团队对原始项目的出色贡献。

## 什么是 MetricFlow？

MetricFlow 是一层语义层，用于以代码方式组织与管理“业务指标”的定义。它能根据指标定义自动生成简洁、可复用且一致的 SQL，让全组织范围内的指标口径统一。

借助 MetricFlow 你可以：

- 将业务指标用标准化方式“一次定义，多处复用”
- 按不同维度（时间、地域、品类等）一致地查询这些指标
- 获取针对数据仓库优化生成的 SQL

## 关键特性

### 指标管理

- **集中式定义**：使用简洁 YAML 在统一位置维护指标
- **多种指标类型**：简单指标、比率、表达式、累计指标
- **维度分析**：按任意维度拆分（时间、地理、品类等）

### 智能查询生成

- **自动 SQL 生成**：将指标请求转换为优化 SQL 查询
- **多跳联接**：处理事实表与维表之间的复杂联接
- **时间粒度**：按日/周/月等多粒度聚合

### 集成与灵活性

- **多数据仓库**：适配多种数据平台
- **API 集成**：可与下游工具进行扩展集成
- **版本控制**：像代码一样用 Git 管理指标定义

## 支持的系统

### 数据仓库
当前支持：

- **DuckDB**、**SQLite** — 适合本地开发和 Demo 的嵌入式数据库
- **MySQL**、**PostgreSQL**、**Greenplum** — 关系型与分析型数据库
- **ClickHouse**、**StarRocks**、**Trino** — 分析引擎
- **Snowflake** — 云数据仓库
- **OceanBase Oracle** — 只读预览能力；依赖 `datus-oceanbase-oracle`、Java、
  OceanBase Connector/J，并且正式投产前必须在真实 Oracle 模式租户上完成验收

MetricFlow 不会只根据“是否存在 Python driver 或 SQLAlchemy dialect”来判断数据库是否
可用。每种 engine 都要显式注册 client、SQL renderer、数据类型、时间函数、行数限制、
参数绑定和能力开关。因此，未注册的数据源方言会在 adapter 初始化阶段直接失败，避免到
查询阶段才生成错误 SQL。

OceanBase Oracle 的首个 profile 支持语义校验、dry-run、只读指标查询、常见聚合与分组，
以及日/周/月/季度/年的时间截断；暂不支持由 MetricFlow 创建或删除 schema/table、查询取消
和 percentile 能力。

## datus-metricflow 的增强
在 0.140.0 的基础上，我们提供了：

- **Python 3.12 支持**
- **新增数据库适配**：提供 Datus 专用 SQL client 和 renderer，包括 OceanBase Oracle 只读预览 profile
- **与 Datus 集成**：统一配置、无缝协作
- **独立安装包**：可作为依赖单独使用

## 安装
确保系统已安装 Python 3.12，然后执行：
```bash
pip install datus-metricflow
```

## 下一步

1. **定义指标**：在语义模型目录编写 YAML，或使用 subagent 定义业务指标
2. **查询指标**：使用 `mf query` 或结合 Datus Agent 进行查询
3. **工具集成**：通过 MCP 服务器将 MetricFlow 接入 LLM 应用
