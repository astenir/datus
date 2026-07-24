# 下游企业与前端契约补充

本文记录当前下游企业版和 Vue 前端依赖的补充契约。内容刻意放在独立下游文档中，避免继续扩大上游公开文档的 diff。

## 前端契约

前端集成约定见：

```text
docs/API/frontend_contract.md
```

该文档记录当前 Vue 前端使用的 OpenAPI 类型生成、`Result[T]` 响应包裹、SSE 处理和错误形态约定。它是下游前端维护文档，不作为上游 API 文档导航的一部分。

### 浏览器文件工具

上游 `v0.3.8` 在 `normal` 权限模式下默认把 `write_file`、`edit_file`、`delete_file` 代理给浏览器执行。当前下游 Vue 客户端只消费工具事件，不提供浏览器文件系统执行器，因此下游服务使用：

```yaml
agent:
  api:
    chat:
      web_filesystem_executor: server
```

这个兼容策略由 `DatusService` 装配，`ChatTaskManager` 的类级默认值仍保持上游的 `client`。这样直接复用上游客户端时可显式切回 `client`，下游前端也不会等待无法返回的代理执行结果。

## Chat 历史交互摘要

`interaction-summary` 只会在持久化历史 `GET /chat/history` 中返回，用于展示已经发生过的 `ask_user` 交互。这是只读 transcript 块：后端会刻意不返回 `interactionKey`，客户端也不应把它提交到 `POST /chat/user_interaction`。

示例：

```json
{
  "type": "interaction-summary",
  "payload": {
    "status": "answered",
    "actionType": "ask_user",
    "requests": [
      {
        "title": "County",
        "content": "Which county?",
        "contentType": "markdown",
        "options": [
          { "key": "1", "title": "Los Angeles" },
          { "key": "2", "title": "San Francisco" }
        ],
        "allowFreeText": true,
        "multiSelect": false
      }
    ],
    "answers": [{ "question": "Which county?", "answer": "Los Angeles" }]
  }
}
```

## 数据源多库枚举

下游 `DbConfig` 支持可选字段：

```yaml
agent:
  services:
    datasources:
      starrocks:
        type: starrocks
        host: ${STARROCKS_HOST}
        port: ${STARROCKS_PORT}
        username: ${STARROCKS_USER}
        password: ${STARROCKS_PASSWORD}
        database: ${STARROCKS_DATABASE}
        enumerate_databases: false
```

`enumerate_databases: true` 时，`catalog/list` 会枚举同一服务上可连接的所有数据库，而不是只返回配置中的 `database`。这用于企业目录浏览场景；它不授予权限，最终可见范围仍由企业数据源授权和 SQL policy 决定。

## KB 构建的数据源边界

下游 `POST /api/v1/kb/bootstrap` 要求显式传入 `datasource_id`。缺失、空白、不存在或未授权的数据源都会被拒绝，接口不会回退到服务端全局默认数据源；后端基于请求级配置副本执行，不能修改共享 `DatusService.agent_config`。

当 `semantic_model` 或 `metrics` 使用 success-story CSV 时，推荐按数据源隔离：

```text
{agent.home}/benchmark/{datasource}/{subagent}/success_story.csv
```

新格式 CSV 包含 `datasource_id` 列，且文件中只能有一个非空数据源；它必须与 KB 请求中的 `datasource_id` 一致。空值、混合数据源或不匹配返回 `422`。缺少该列的旧 CSV 暂时兼容，但后端会记录警告和审计事件。

## Success story 保存与迁移

前端保存 SQL success story 时，后端从该次 `execute_sql` / `read_query` 的规范会话历史中恢复真实数据源，不以页面 URL、当前选择或默认数据源决定目录。如果历史没有数据源，或开始/完成事件记录冲突，保存会失败关闭。

新版 CSV 格式为：

```csv
question,sql,datasource_id,source_id,session_id,session_link,subagent_name,timestamp
"Show revenue by category",SELECT ...,ccks_fund,ss_...,abc123...,http://localhost:8501?session=...,chat,2025-01-15T02:30:00Z
```

API 只返回相对于 benchmark 目录的 `storage_key`，例如 `ccks_fund/chat/success_story.csv`，不会暴露服务器绝对路径。旧文件不会被自动移动或删除；确认所有记录属于一个数据源后，可以显式复制迁移：

```bash
datus-agent migrate-success-stories \
  --source ~/.datus/benchmark/chat/success_story.csv \
  --datasource ccks_fund \
  --subagent chat
```

迁移按 `source_id` 去重，可以重复执行，并保留源文件；如果新版 CSV 已声明其他 `datasource_id`，迁移会被拒绝。

## Metadata embedding 样例限制

下游数据库 metadata embedding 支持两个防止超长样例进入 embedding provider 的配置：

```yaml
agent:
  storage:
    database:
      sample_cell_max_chars: 1000
      sample_max_chars: 8000
```

- `sample_cell_max_chars`：单个样例单元格的最大字符数；超长内容会被替换为长度标记。
- `sample_max_chars`：单张表完整样例序列化后的最大字符数，默认 `8000`。

## MetricFlow 与 OceanBase Oracle

当前 monorepo 的 MetricFlow 扩展支持 DuckDB、SQLite、MySQL、PostgreSQL、Greenplum、ClickHouse、StarRocks、Trino、Snowflake，以及只读预览的 OceanBase Oracle。引擎支持不只取决于 Python driver 或 SQLAlchemy dialect；还需要显式注册 SQL client、renderer、数据类型、时间函数、行数限制、参数绑定和 capability profile。

OceanBase Oracle 的首个 profile 支持语义校验、dry-run、只读指标查询、常见聚合与分组，以及日/周/月/季度/年时间截断；不支持 MetricFlow 管理的 schema/table 写入、查询取消和 percentile。连接示例、跨仓库归属、依赖发布顺序和真实 Oracle 模式租户验收见：

- `datus_enterprise/docs/metricflow_oceanbase_oracle.md`
- `datus_enterprise/docs/metricflow_oceanbase_oracle.zh.md`

## 普通用户自配模型与数据源

企业模式允许把两类普通用户自助配置放在“当前用户”边界内，而不是写入共享 `agent.services` 或 admin grant metadata：

- BYOK 模型密钥：接口前缀为 `/api/v1/me/model-*`。API key 只存加密 blob，列表和详情只返回尾号提示；聊天执行时把当前用户选中的 credential 投影到请求级 `AgentConfig` clone，不修改共享 `DatusService.agent_config`。
- 自建模型端点：普通用户可在后端允许时添加 OpenAI 兼容 `base_url` 和任意模型名；服务端统一按 `provider: openai` 写入请求级配置，并通过 `enterprise.user_model_credentials.custom_openai_compatible.allowed_base_urls` 做白名单校验。
- 个人数据源：接口前缀为 `/api/v1/me/datasource*`。数据源默认私有，仅当前用户可见；执行时生成 `personal_<id>` datasource key，并在请求级 projection 中临时加入当前用户配置和本地 allow grant，不进入企业公共 datasource grant。

运行配置要点：

- `enterprise.user_model_credentials.custom_openai_compatible.enabled` 默认应保持 `false`。开启前必须把 `allowed_base_urls` 收窄到企业内模型网关或本地试点地址，不要允许任意公网 URL；网络层也应限制 API 进程到模型网关的出站访问。
- `enterprise.user_datasources.enabled` 默认应保持 `false`。开启前必须收窄 `allowed_hosts`，不要用 `*` 作为生产配置；网络层也应限制 API 进程到业务数据库的出站访问。
- `DATUS_USER_MODEL_CREDENTIAL_SECRET` 与 `DATUS_USER_DATASOURCE_SECRET` 至少 32 字符，并需要纳入备份恢复 runbook。丢失后，历史加密 blob 无法解密。
- PG/OceanBase metadata store 会创建 `user_model_credentials`、`user_model_preferences`、`user_datasources` 表；SQLite store 只适合单节点试点。
- 密钥和密码明文只在服务端 store 读出后用于请求级执行或连通性测试，不返回给前端，不写入审计。个人数据源 CRUD/probe 审计 action 为 `me.datasource`，metadata 只记录脱敏后的连接摘要。
- 当前 MVP 只支持数据库连接型个人数据源；文件上传、共享给他人、升级为企业公共数据源、审批流和更强 DNS/IP/CIDR 出站策略都属于后续能力。

## OceanBase MySQL 存储后端

OceanBase MySQL 模式可以安装 `datus-storage-oceanbase-mysql` 并作为 RDB 和/或 vector 后端使用。RDB 后端存结构化 metadata；vector 后端把 embedding 写入 OceanBase `VECTOR(N)` 列，并使用 OceanBase 向量距离函数做近邻检索。

示例：

```yaml
storage:
  isolation: logical
  rdb:
    type: oceanbase-mysql
    host: ${OB_HOST:-127.0.0.1}
    port: ${OB_PORT:-2881}
    user: ${OB_USER}
    password: ${OB_PASSWORD}
    database: datus_storage
    pool_max_size: 5

  vector:
    type: oceanbase-mysql
    host: ${OB_HOST:-127.0.0.1}
    port: ${OB_PORT:-2881}
    user: ${OB_USER}
    password: ${OB_PASSWORD}
    database: datus_storage
    pool_max_size: 5
```

`logical` 隔离会把所有项目存到配置的 OceanBase database，并在表内增加 Datus 内部 namespace 列。`physical` 隔离会按 `<project>__<store>` 创建项目/存储级 OceanBase database；配置用户需要具备创建 database 的权限。

OceanBase vector 表需要数据库版本支持 `VECTOR` 列和向量索引。适配器会创建 heap-organized vector 表，并通过 OceanBase `CREATE VECTOR INDEX` 支持 HNSW 向量索引。
