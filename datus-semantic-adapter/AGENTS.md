# Datus Semantic Adapters 维护指南

## 范围与事实来源

本文件覆盖 `datus-semantic-adapter/` uv workspace。包级 README、各包的
`pyproject.toml`、`datus-semantic-core` 源码和测试是实现事实来源；根目录
`AGENTS.md` 负责 monorepo 级协调。负责人：待确认。

workspace 当前包含：

- `datus-semantic-core/`：公共接口、基础模型和 `SemanticAdapterRegistry`；
- `datus-semantic-metricflow/`：Datus 到 MetricFlow 的配置、校验和查询适配；
- `datus-semantic-osi/`：OSI 语义模型适配；
- `datus-semantic-osi-engine/`：可选原生 Rust OSI Engine 适配，独立于 locked workspace 测试。

MetricFlow 源码来自 monorepo 的 `../metricflow` editable source。不要单独安装一份旧的
`datus-metricflow` 覆盖当前 checkout。

## 开发与验证

```bash
uv sync --locked --all-packages --all-extras
.venv/bin/python -m pytest --asyncio-mode=auto
(cd datus-semantic-osi-engine && ../.venv/bin/python -m pytest -q tests/unit --asyncio-mode=auto)
```

修改 MetricFlow integration 时，还应在 `metricflow/` 运行受影响的 SQL engine/client
tests。OSI engine 的真实 native binding 是可选依赖；workspace unit tests 使用隔离 fixture
时，不得把 fake binding 的通过结果描述为真实 Rust engine 验收。

## 运行时边界

`datus-agent` 应通过 `datus-semantic-core` 的接口和 `SemanticAdapterRegistry` 访问实现，
而不是在业务逻辑中直接 import MetricFlow/OSI adapter class。

- semantic adapter entry point group 为 `datus.semantic_adapters`；
- adapter 的 `service_type`、config model、metadata 和 capability 属于公共契约；
- MetricFlow/OSI 的 SQL、方言和 engine-specific 限制留在实现包；
- core 层不得为了某一个实现复制一套专用配置或查询协议；
- Registry discovery 是进程级初始化，测试必须避免跨用例共享注册状态。

## 新增或修改 adapter 的清单

1. 先在 core 中确认接口、模型和错误边界；必要时先补公共契约测试。
2. 在实现包中注册 `datus.semantic_adapters` entry point。
3. 同步所有实现、workspace source、包级 README 和兼容测试。
4. 覆盖配置解析、校验、能力发现、查询/SQL 生成和底层异常转换。
5. 说明是否需要外部数据库、MetricFlow source、OSI native engine 或特殊环境变量。
6. 修改公共模型时，检查 Agent semantic tools、Web API 类型和 MetricFlow integration 的调用方。

## 目录与兼容

- `datus-semantic-core/` 是公共边界；
- `datus-semantic-metricflow/`、`datus-semantic-osi/` 是实现包；
- `datus-semantic-osi-engine/` 的测试和 native wheel 生命周期独立；
- 当前未确认有生成代码目录；不得提交 `.venv/`、native build output、缓存或真实数据。

旧 `service_type`、entry point name、配置键和公共 Pydantic 字段必须视为兼容契约。实现
重命名时先保留兼容 alias 或迁移说明，再修改调用方；不要通过删除 adapter 检查来修复测试。

## 提交规则

遵循根仓库 Conventional Commits，例如：

```text
docs(semantic-adapter): 补充语义适配器维护边界
```
