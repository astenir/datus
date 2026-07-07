# 下游企业与前端契约补充

本文记录当前下游企业版和 Vue 前端依赖的补充契约。内容刻意放在独立下游文档中，避免继续扩大上游公开文档的 diff。

## 前端契约

前端集成约定见：

```text
docs/API/frontend_contract.md
```

该文档记录当前 Vue 前端使用的 OpenAPI 类型生成、`Result[T]` 响应包裹、SSE 处理和错误形态约定。它是下游前端维护文档，不作为上游 API 文档导航的一部分。

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
