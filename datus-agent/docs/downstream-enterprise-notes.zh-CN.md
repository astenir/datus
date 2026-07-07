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
