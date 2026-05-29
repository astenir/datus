# Fund 下游修改记录

本文记录 fund 版本相对上游 Datus 的下游专属改动，用于后续升级上游版本、排查冲突和判断哪些改动必须保留。

## 当前基线

- 上游基线：`v0.3.2`
- fund 当前提交：`9786a627`
- 最近整理日期：`2026-05-29`
- fund 仓库：`origin/main`，对应 `astenir/Datus-agent-fund`
- 上游仓库：`upstream`，对应 `Datus-ai/Datus-agent`

## 维护原则

- 本文件只记录 fund 相对上游额外保留的修改，不替代上游 release notes。
- 每次新增 fund 专属功能、配置、兼容补丁或维护约定时，都应补充一条记录。
- 升级上游 release/tag 前，先阅读本文的“升级关注点”，再做合并和测试。
- 如果某个 fund 改动后来被上游吸收，应在本文标记为“已上游化”，并在升级后移除本地重复实现。

## 修改记录

### 1. Datasource 数据库、Schema、表可见范围限制

- 提交：`9c5e0b94` (`[Feature] Restrict datasource database and schema visibility`)
- 类型：fund 专属功能
- 状态：当前保留
- 涉及文件：
  - `datus/tools/db_tools/db_manager.py`
  - `datus/tools/db_tools/restricted_connector.py`
  - `docs/configuration/datasources.md`
  - `tests/unit_tests/tools/db_tools/test_db_manager.py`

#### 背景

基金行业场景下，一个 datasource 的数据库账号可能拥有较宽的数据访问权限，但 Datus 不一定应该向 Agent 暴露全部 database、schema 或 table。需要在 Datus 配置层增加额外的可见范围限制，避免模型枚举或查询非目标业务表。

#### 实现摘要

- 新增 datasource 级配置字段：
  - `allowed_databases`
  - `allowed_schemas`
  - `allowed_tables`
- 在 `DBManager` 初始化连接后，如果 datasource 配置了上述字段，则用 `RestrictedSqlConnector` 包装底层 connector。
- `RestrictedSqlConnector` 会过滤元数据接口返回值，包括 database、schema、table、view 和 materialized view。
- SQL 执行前会解析查询引用的表，若引用白名单外对象，则返回失败结果，不调用底层 connector。
- 禁止通过该 datasource 直接查询常见元数据 schema：
  - `information_schema`
  - `pg_catalog`
- 对 `get_schema`、`get_sample_rows`、`get_tables_with_ddl`、`get_views_with_ddl` 等接口增加白名单校验。
- `allowed_*` 属于 Datus 内部配置，不会透传给底层数据库 adapter。

#### 配置示例

```yaml
services:
  datasources:
    ccks_pg:
      type: postgresql
      host: 127.0.0.1
      port: 5433
      username: datus
      password: datus
      database: ccks_fund
      schema: public
      allowed_databases:
        - ccks_fund
      allowed_schemas:
        - public
      allowed_tables:
        - public.mf_fundarchives
        - public.mf_netvalue
        - public.mf_fundmanagernew
```

#### 测试覆盖

相关单测在 `tests/unit_tests/tools/db_tools/test_db_manager.py`，主要覆盖：

- `get_connection` 可返回 `RestrictedSqlConnector`。
- database、schema、table 列表会按白名单过滤。
- 白名单内 SQL 查询正常透传到底层 connector。
- 白名单外 SQL 查询会被拒绝。
- 直接查询 `information_schema` 等元数据 schema 会被拒绝。
- datasource 内部白名单字段不会传给 adapter 配置。

#### 升级关注点

升级上游版本时，重点检查以下区域是否发生变化：

- `datus/tools/db_tools/db_manager.py`
- `BaseSqlConnector` / `ExecuteSQLResult` 接口
- `datus_db_core.connector_registry`
- `datus.utils.sql_utils.extract_table_names`
- datasource 配置解析和 `DbConfig.extra` 行为
- 上游是否已经提供类似 datasource/table allowlist 功能

建议升级后至少执行：

```bash
uv run pytest tests/unit_tests/tools/db_tools/test_db_manager.py
uv run ruff check datus/tools/db_tools tests/unit_tests/tools/db_tools/test_db_manager.py
```

### 2. 本地 Agent 协作说明

- 提交：`4f2fd33f` (`[Others] Restore agent instructions on development branches`)
- 提交：`9786a627` (`[Doc] Document fund downstream git workflow`)
- 类型：维护文档
- 状态：当前保留
- 涉及文件：
  - `AGENTS.md`
  - `.gitignore`

#### 背景

fund 仓库是上游 Datus 的下游版本，`origin/main` 不是干净的上游镜像。需要在仓库内明确本地开发、测试、提交、上游升级和工作树使用约定，避免后续误把 fund 分支当成普通 fork 同步。

#### 实现摘要

- 新增 `AGENTS.md`，记录项目结构、开发命令、测试规范、提交和 PR 规范。
- 在 `AGENTS.md` 中明确本地 Git 布局：
  - `/home/astenir/Code/oss/Datus-agent-fund`：fund 开发工作树，使用 `main`
  - `/home/astenir/Code/oss/Datus-agent`：干净上游参考工作树，使用 `upstream-main`
- 明确 fund 分支应跟随稳定上游 release tag 或 release branch，不建议直接跟随 raw `upstream/main`。
- `.gitignore` 增加 `.tmp/`，避免临时文件进入提交。

#### 升级关注点

- 上游升级时不要使用 GitHub 的 “Sync fork” 按钮直接覆盖 fund 历史。
- 推荐先基于上游 release/tag 创建升级分支，测试通过后再合并回 fund `main`。
- 如果 `AGENTS.md` 的命令、路径或分支约定变化，应同步更新本文和 `AGENTS.md`。

## 追加记录模板

新增 fund 专属改动时，可按以下模板追加：

```markdown
### N. 修改标题

- 提交：`<commit>`
- 类型：fund 专属功能 / 兼容补丁 / 维护文档 / 配置调整
- 状态：当前保留 / 已上游化 / 待移除
- 涉及文件：
  - `<path>`

#### 背景

说明为什么 fund 版本需要这个改动。

#### 实现摘要

说明做了什么，不需要逐行描述。

#### 测试覆盖

说明相关测试或人工验证方式。

#### 升级关注点

说明后续合并上游时需要重点检查的文件、接口或行为。
```
