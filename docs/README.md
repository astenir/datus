# Datus 文档导航

本目录只收纳跨子项目维护文档和无法归属单一组件的专项部署说明。组件的安装、配置和测试应写在对应子项目中；同一流程只保留一个事实来源，其他文档通过链接引用。

`datus-agent/docs/` 是上游公开产品文档；下游交接、差异治理和跨项目同步文档统一放在本目录。

## 开发入口

| 主题 | 文档 | 维护边界 |
| --- | --- | --- |
| Monorepo 总览 | [根 README](../README.md) | 组件边界、快速启动、常用命令 |
| Agent 开发规则 | [datus-agent/AGENTS.md](../datus-agent/AGENTS.md) | 后端结构、配置优先级、测试和安全约束 |
| Agent 本地企业联调 | [LOCAL_ENTERPRISE_BACKEND_TESTING.zh.md](../datus-agent/LOCAL_ENTERPRISE_BACKEND_TESTING.zh.md) | mock userinfo、Bearer/signed header、seed、API smoke |
| Web 开发与部署 | [datus-web/README.md](../datus-web/README.md) | Vite 代理、认证、子路径构建、测试 |
| 数据库适配器 | [datus-db-adapters/README.md](../datus-db-adapters/README.md) | 已注册 adapter、workspace 开发和包级文档 |
| 存储适配器 | [datus-storage-adapters/README.md](../datus-storage-adapters/README.md) | RDB/vector backend 与插件注册 |
| 语义适配器 | [datus-semantic-adapter/README.md](../datus-semantic-adapter/README.md) | core、MetricFlow 和 OSI 适配器 |
| MetricFlow | [metricflow/README-DATUS.md](../metricflow/README-DATUS.md) | Datus 配置集成和 CLI |

## 上游同步

| 文档 | 用途 |
| --- | --- |
| [统一上游同步清单](./upstream-sync-manifest.yml) | 上游地址、只读 remote、采用基线、待同步引用、版本锁文件和联动验证 |
| [Agent 上游差异预算](./upstream-diff-budget.zh-CN.md) | 当前 `datus-agent` 基线、差异分类、门禁和收敛流程 |

## 企业能力

| 文档 | 用途 |
| --- | --- |
| [企业平台架构契约](../datus-agent/ENTERPRISE_PLATFORM_PLAN.zh.md) | 产品目标、安全边界、阶段划分和上线门槛 |
| [企业 AI 开发规范](../datus-agent/ENTERPRISE_AI_DEVELOPMENT_GUIDE.zh.md) | 企业相关改动的执行清单和验证要求 |
| [本地企业后端测试](../datus-agent/LOCAL_ENTERPRISE_BACKEND_TESTING.zh.md) | 本地启动、认证切换、seed、smoke 和故障定位 |

三份文档职责不同：架构契约说明“不能破坏什么”，开发规范说明“改动时检查什么”，本地测试说明“如何运行和验证”。不要在其他 README 复制完整配置。

## 工程质量

| 文档 | 用途 |
| --- | --- |
| [CI 质量门禁维护指南](./ci-quality-gates.zh-CN.md) | 根 GitHub Actions、路径检测和 required status 契约 |
| [Web OpenAPI 实现映射](../datus-web/docs/openapi-implementation-map.md) | 后端 route 到前端 API、composable 和界面的实现状态 |

## 专项部署

| 文档 | 用途 |
| --- | --- |
| [MetricFlow OceanBase Oracle 内网部署与验收](./metricflow-oceanbase-oracle-intranet-deployment.zh-CN.md) | 私有 PyPI、完整 monorepo 源码安装、JDBC、真实租户验收和回退 |

该专项文档不是通用部署入口。普通本地开发优先使用根目录 Docker Compose，或分别按 Agent 与 Web 文档启动。

## 文档维护约定

- 命令、路径、端口、配置键和脚本名必须能在当前仓库中验证。
- 实现计划完成后删除计划稿；可复用的结论进入 README、架构契约或测试说明。
- 一次性测试结果不长期保存在源码树中；持续有效的能力由测试和 CI 证明。
- 包级用法放在包目录的 `README.md`，集成测试环境变量放在对应 `tests/integration/README.md`。
- 删除或移动文档时先更新仓库内链接，再运行链接与格式检查。
