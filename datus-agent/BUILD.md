# Datus Agent 构建与发布

本文说明源码构建、发布前验证和当前 GitHub Actions 发布流程。日常开发环境与测试规则见 [AGENTS.md](./AGENTS.md)，用户安装方式见 [README.md](./README.md)。

## 本地构建

```bash
uv sync --dev
uv run python -m build
uv run python -m twine check dist/*
```

也可以使用保留的 Makefile 封装：

```bash
make clean
make build
make check
make test
```

验证构建产物时使用临时虚拟环境，避免当前 editable source 掩盖缺包：

```bash
python -m venv /tmp/datus-release-smoke
/tmp/datus-release-smoke/bin/pip install dist/datus_agent-*.whl
/tmp/datus-release-smoke/bin/python -c "import datus; print(datus.__version__)"
```

## 版本事实来源

版本只在 `pyproject.toml` 的 `project.version` 中维护。`datus.__version__` 会从已安装 distribution metadata 或源码树的 `pyproject.toml` 读取，不需要再手工修改 `datus/__init__.py`。

版本采用 [Semantic Versioning](https://semver.org/)，预发布版本使用 Python 包版本格式，例如 `0.3.8rc1`。

## 正式发布流程

当前正式流程由两个手动 GitHub Actions workflow 负责，不再以本地 `.pypirc` + `make publish` 作为推荐发布路径。

### 1. 准备 release branch

运行 `.github/workflows/prepare-release.yml`，输入目标版本。workflow 会：

- 创建或更新 `release/<version>`；
- 通过 `ci/prepare_release.py` 更新版本和 adapter lower bounds；
- 同步 `uv.lock` 与 `requirements-test.txt`；
- 执行 release readiness 检查；
- 提交并推送 release metadata。

准备完成后，应在 release branch 上完成 CI、必要的候选版本验证和人工检查。

### 2. 发布并收尾

运行 `.github/workflows/publish-release.yml`，明确提供：

- `version`：必须与 `pyproject.toml` 一致；
- `ref`：待发布的 release branch、tag 或 SHA；
- `repository`：`testpypi` 或 `pypi`。

workflow 会校验 source/ref 状态，构建并检查 distributions，上传制品，发布到目标 package index，并按稳定版或预发布版规则完成 tag/release/metadata 收尾。

需要在 GitHub environment 中配置相应 token：

- `PYPI_API_TOKEN`
- `TEST_PYPI_API_TOKEN`

不要把 token 或 `.pypirc` 提交到仓库。

## 发布前检查

至少确认：

```bash
uv lock --locked
uv run ruff check .
uv run pytest
uv run python ci/check_release_readiness.py --expected-version <version>
git diff --check
```

跨 adapter、语义层或存储插件的版本变更还需要运行相应 cross-repo harness。若完整测试依赖外部数据库或私有服务，在 release 记录中写明实际运行环境和未覆盖项。

## 文档版本

`.github/workflows/deploy-docs.yml` 使用 `mike` 发布版本化文档：

- `main` 发布为 `dev`；
- `vX.Y.Z` tag 发布对应版本；
- 最新稳定版本更新 `latest` alias；
- 编辑链接指向实际构建 ref。

公开产品文档位于 `docs/`。monorepo 下游维护文档和企业说明不应混入公开文档版本流程。

## 本地上传命令的定位

Makefile 中仍保留 `upload-test`、`upload` 和 `publish`，用于维护脚本或应急验证；它们不是正式发布的首选入口。使用前必须确认目标仓库、凭据来源、版本唯一性和 GitHub 发布状态，避免绕过 readiness、tag 与 metadata 同步流程。
