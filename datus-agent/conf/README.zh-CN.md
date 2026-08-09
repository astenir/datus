# Datus Agent 配置文件说明

`conf/` 同时保存运行配置、可复制示例、企业配置片段和内置模型目录。它们不会全部被自动加载，也不能互相替代。

## 文件用途

| 文件 | 类型 | 用途 | 是否自动加载 |
| --- | --- | --- | --- |
| `agent.yml` | 本机完整配置 | 当前工作目录的实际运行配置；通常由示例复制后填写 | 未显式传 `--config` 时优先加载；已被 Git 忽略 |
| `agent.yml.example` | 完整示例 | 上游默认配置参考，覆盖面最完整 | 否；复制为 `agent.yml` 或通过 `--config` 指定副本 |
| `agent.downstream.zh-CN.yml.example` | 完整起步模板 | 下游中文化、本地开发和前端联调的精简推荐配置 | 否；复制后使用 |
| `agent.compose.yml` | 完整运行配置 | 仓库根目录 `docker-compose.yml` 和镜像默认命令使用的单进程企业联调配置 | 仅 Compose/镜像启动命令显式加载，不是普通 CLI 默认配置 |
| `agent.enterprise.mvp.yml.example` | 配置片段 | SQLite/in-memory 企业 metadata，适合本地单节点或小范围试点 | 否；把顶层 `api`、`enterprise` 合并到完整配置的 `agent:` 下 |
| `agent.enterprise.pg.yml.example` | 配置片段 | PostgreSQL 企业 metadata、会话和相关 store | 否；把顶层 `api`、`enterprise` 合并到完整配置的 `agent:` 下 |
| `agent.enterprise.ob.yml.example` | 配置片段 | OceanBase MySQL 企业 metadata、会话和相关 store | 否；把顶层 `enterprise` 合并到完整配置的 `agent:` 下 |
| `agent.local-enterprise-pg.yml.example` | 完整示例 | 无真实企业网关时，本地联调企业认证、授权和 PostgreSQL store | 否；复制为未跟踪的本地文件，再通过 `--config` 显式加载 |
| `auth_clients.yml.example` | 独立 legacy 示例 | 旧 `/auth/token` client-credentials 认证配置，不属于 `agent.yml` | 否；旧认证代码只读取 `{agent.home}/conf/auth_clients.yml` |
| `providers.yml` | 程序内置目录 | `datus init`、`/model` 和模型运行时使用的 provider/model 元数据，不保存用户凭据 | 由程序作为资源读取；不应复制成 `agent.yml` |

`providers.yml` 与包内的 `datus/conf/providers.yml` 必须保持字节级一致。增删 provider 或修改说明时应同步修改两份文件。

## 选择指南

- 普通本地开发：从 `agent.yml.example` 或 `agent.downstream.zh-CN.yml.example` 复制出 `agent.yml`。
- Docker Compose 联调：使用仓库根目录 `docker-compose.yml`，不要再把 `agent.compose.yml` 复制成默认配置。
- 单节点企业功能试验：在已有完整配置的 `agent:` 下合并 `agent.enterprise.mvp.yml.example`。
- 接近部署形态的企业 store：根据数据库选择 PostgreSQL 或 OceanBase 片段；这些片段不包含业务数据源、模型和全部运行路径，不能单独启动。
- 本地企业 PostgreSQL 端到端联调：按 `agent.local-enterprise-pg.yml.example` 文件头和 `../LOCAL_ENTERPRISE_BACKEND_TESTING.zh.md` 操作。

企业示例是能力接线和联调基线，不是可直接投产的安全配置。生产环境仍需配置真实身份源、密钥管理、最小权限、数据库迁移、备份恢复、审计、监控和容量；多 worker/pod 还需处理 chat/SSE 状态路由。

## 加载顺序

主配置按以下顺序选择，找到第一份后停止：

1. 命令行显式传入的 `--config <path>`；
2. 启动工作目录下的 `./conf/agent.yml`；
3. `~/.datus/conf/agent.yml`。

随后程序还会读取启动工作目录下的 `./.datus/config.yml`，覆盖项目级模型、默认数据源、`project_name` 等少量选择。它不是另一份完整 `agent.yml`。因此启动目录变化可能同时改变默认主配置、`.env` 和项目级覆盖文件；服务部署建议始终显式传 `--config`，并在需要稳定会话、索引或语义命名空间时显式设置 `agent.project_name`。

## `agent.yml`、环境变量与 `.env`

- YAML 保存配置结构和非敏感默认值；敏感值使用 `${ENV_NAME}` 引用，不要把真实密码、token 或 API key 提交到仓库。
- Datus 加载配置时会从当前工作目录查找 `.env`。系统环境中已经存在的同名变量优先，不会被 `.env` 默认覆盖。
- Docker Compose 从执行 Compose 命令的位置读取 `.env` 做变量替换，并且只有 `docker-compose.yml` 中声明或挂载的值才会进入容器。
- `.env` 只提供字符串变量，不会自动变成任意 `agent.*` 字段。例如要用环境变量控制项目名，YAML 中仍需写 `project_name: ${DATUS_PROJECT_NAME}`。
- `agent.compose.yml` 还通过 `DATUS_MODELS_FILE` 和 `DATUS_DATASOURCES_FILE` 合并容器挂载的模型凭据与业务数据源，避免把部署秘密写进仓库内的完整配置。

推荐做法是把稳定、可审查的结构写在 YAML，把随环境变化或敏感的值放在进程环境、未提交的 `.env`、容器 secret 或企业密钥系统中。

企业示例中的 `user_model_credential_store`、`user_datasource_store` 和
`user_mcp_server_store` 只在对应的用户模型、个人数据源或个人 MCP 功能开启时加载。
这些功能默认关闭时，可以直接从样例启动而不提供三类加密密钥；启用任一功能前，
必须先配置对应的 `DATUS_USER_MODEL_CREDENTIAL_SECRET`、
`DATUS_USER_DATASOURCE_SECRET` 或 `DATUS_USER_MCP_SECRET`，且每个密钥至少 32 个字符。

## Web 文件工具执行边界

当前下游 Vue 客户端不会在浏览器中执行 `write_file`、`edit_file`、`delete_file`。下游完整配置应显式保留：

```yaml
agent:
  api:
    chat:
      web_filesystem_executor: server
```

`ChatTaskManager` 自身的默认值是 `client`，与上游 `v0.3.8` 的浏览器代理契约一致；下游 `DatusService` 在未配置时使用兼容默认值 `server`。只有接入真正实现文件工具代理和结果回传的客户端后，才应改为 `client`。非法值会在服务构造时被拒绝，避免悄悄切换执行位置。

## 新增配置文件时

只有存在独立用途或独立启动入口时才新增文件。文件头至少说明：

1. 它是完整配置还是需要合并到 `agent:` 下的片段；
2. 由哪个命令加载，是否需要 `--config`；
3. 适用范围是本地开发、Compose、企业试点还是生产接线参考；
4. 必需环境变量和不得提交的敏感信息。
