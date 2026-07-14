# Contributing to Datus Database Adapters

感谢参与 Datus 数据库适配器开发。本文只保留贡献者需要执行的流程；具体数据库行为与测试环境以对应包的 README 为准，仓库级实现规则以 [AGENTS.md](./AGENTS.md) 为准。

## 准备环境

要求 Python 3.12、`uv` 和 Git：

```bash
git clone https://github.com/Datus-ai/datus-db-adapters.git
cd datus-db-adapters
uv sync --dev
```

根 `pyproject.toml` 是开发 workspace。终端用户安装独立包，贡献者则在 workspace 环境中运行检查。

## 开发流程

1. 从 `main` 创建短生命周期分支。
2. 在对应 `datus-<adapter>/` 中完成最小改动。
3. 为修复添加能够复现问题的回归测试；为新行为覆盖配置、连接、元数据和执行路径。
4. 同步包级 README 中受影响的配置、环境变量或限制。
5. 先运行包级检查，再运行受影响的共享检查。

常用命令：

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest --import-mode=importlib datus-postgresql/tests/unit
```

集成测试需要数据库时，使用 adapter 自带的 `docker-compose.yml`、fixture 或环境变量说明。不得提交真实凭据；环境不可用时，在 PR 中写明未运行的测试和原因。

## 新增 adapter

新增包时保持现有布局，并同步以下位置：

```text
datus-<adapter>/
├── pyproject.toml
├── README.md
├── datus_<adapter>/
└── tests/
    ├── unit/
    └── integration/
```

- 根 `pyproject.toml` 的 `tool.uv.workspace.members`。
- Ruff/isort 的 `known-first-party`。
- adapter package 的 setuptools entry point。
- 根 [README](./README.md) 的当前包表。
- 必要的单元测试和可选集成测试说明。

不要假设 schema、catalog、identifier quoting、分页或 metadata SQL 能跨数据库复用。只有至少两个 adapter 需要同一行为且所有权明确时，才把逻辑上移到 `datus-sqlalchemy` 或 `datus-db-core`。

## 提交与 PR

本 monorepo 提交信息使用 Conventional Commits：

```text
<type>(<scope>): <中文描述>
```

示例：

```text
fix(postgresql): 修复跨库表结构查询
feat(oracle): 增加连接超时配置
docs(db-adapters): 同步适配器清单
```

上游仓库 PR 标题另受 CI 约束，必须以 `[BugFix]`、`[Enhancement]`、`[Feature]`、`[Refactor]`、`[UT]`、`[Doc]`、`[Tool]` 或 `[Others]` 开头。

PR 描述应包括：

- 受影响的 adapter 和行为；
- 兼容性或迁移影响；
- 已运行的精确测试命令与结果；
- 未运行的集成测试及原因。

不要提交 `.venv/`、缓存、数据库 volume、日志、覆盖率文件、构建产物或机器本地配置。
