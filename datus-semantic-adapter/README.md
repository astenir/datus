# Datus Semantic Adapters

语义层 adapter workspace，为 Datus 提供统一的指标发现、配置校验和查询接口。

## 当前包

| 包 | 作用 | 文档 |
| --- | --- | --- |
| `datus-semantic-core` | 公共接口和基础模型 | 包内源码与测试 |
| `datus-semantic-metricflow` | Datus 到 MetricFlow 的配置、校验和查询适配 | [README](./datus-semantic-metricflow/README.md) |
| `datus-semantic-osi` | OSI 语义模型适配 | 包内源码与测试 |

该清单与根 `pyproject.toml` 的 `tool.uv.workspace.members` 保持一致。MetricFlow 源码在 monorepo 的 [`metricflow`](../metricflow/) 目录中，并通过 `tool.uv.sources` 以 editable path 接入。

## 开发

```bash
uv sync --locked --all-packages --all-extras
.venv/bin/python -m pytest --asyncio-mode=auto
```

运行 workspace 级测试前使用锁文件同步全部包。修改 MetricFlow 集成时，还应在 `metricflow/` 中运行受影响的 SQL engine/client 测试。

## 安装

终端用户安装具体实现包，例如：

```bash
pip install datus-semantic-metricflow
```

配置格式和后端限制以实现包 README 为准；公共接口变更必须同步所有实现与跨仓库兼容测试。
