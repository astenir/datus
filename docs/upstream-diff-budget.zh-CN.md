# datus-agent 上游差异预算

本文是 `datus-agent` 相对正式上游 release tag 的当前差异治理快照。历史逐次收敛记录不再堆积在工作文档中；需要追溯某次迁移的具体行为、测试结果或数字变化时，使用 Git 提交历史和对应的 `ci/harness/upstream-modified-allowlist.yml` 记录。

## 当前基线

- 采样日期：2026-08-10
- 上游基线：`v0.3.9`
- 对比脚本：`datus-agent/ci/harness/report_upstream_diff.py`
- 机器可读分类清单：`datus-agent/ci/harness/upstream-modified-allowlist.yml`

从仓库根目录执行：

```bash
cd datus-agent
uv run python ci/harness/report_upstream_diff.py \
  --base v0.3.9 \
  --target upstream-agent/main
uv run python ci/harness/report_upstream_diff.py \
  --base v0.3.9 \
  --check
```

当前报告结果：

```text
503 files changed, 95635 insertions(+), 2549 deletions(-)
357 added
144 modified
2 deleted
```

`modified` 的分类为：

```text
94 production/package files
44 tests
2 docs
4 config/meta files
```

报告器只把 `modified` 计入上游差异门禁；新增的企业模块、下游测试、配置示例和部署资产单独统计，不与上游原文件修改混算。当前 allowlist 应返回：

```text
allowlist: ok (144 modified files)
```

数字是治理指标，不是业务改动数量。每次正式上游升级或低风险收敛后，都要重新生成报告并说明数字变化原因。

## 下游边界

上游原文件中的修改必须保持少量、稳定、可解释；企业逻辑优先归位到新增模块。以下安全边界不能因同步或收敛而放宽：

- 企业认证、用户启用状态和授权检查必须在服务初始化和业务执行前完成，并保持 fail closed。
- 认证上下文、RBAC、数据源 grant、SQL policy、session/task owner、Artifact ACL、workspace、审计和 quota 是独立边界，不能相互替代。
- 用户态数据源、模型凭据和授权状态只能投影到请求级 `AgentConfig` clone，不能写入共享 `DatusService.agent_config`。
- 数据库工具、迁移工具和企业 Web Chat 的只读/禁用策略必须在真实执行边界生效，不能只依赖前端或文档约定。
- 多 worker 或多 pod 的 Chat/SSE/session 仍依赖粘性路由，除非运行态已经外部化；不能把当前试点描述成无状态高可用。

## 分类与放置规则

| 分类 | 适用内容 | 首选归属 | 处理原则 |
| --- | --- | --- | --- |
| `core-hook` | 启动注册、请求上下文、配置投影、存储/执行扩展点、安全调用钩子 | 上游原文件的薄 hook | 保持调用时点和安全顺序稳定，避免把策略主体写回上游状态机 |
| `move-to-enterprise` | 企业 route/service 的策略主体 | `datus_enterprise/` | 迁移时同步 route security matrix、权限、审计、quota 和 focused tests |
| `upstreamable-fix` | 与企业模式无关的通用修复或扩展点 | 独立小提交，必要时贡献上游 | 与企业配置、模型和前端契约分开验证 |
| `docs-config-meta` | 文档、配置示例、构建、依赖、锁文件和仓库元数据 | 根 `docs/`、企业配置、对应 workspace | 优先恢复上游公开文档；依赖变化真实写入 `pyproject.toml`/锁文件 |
| `test-only` | 证明共享 hook 契约的上游测试修改 | 企业测试或新增 `*_downstream.py` | 企业语义优先迁移到下游测试；只有共享行为改变时保留上游测试修改 |

具体文件和当前分类以机器清单为准，不在本文复制完整路径列表：

```text
datus-agent/ci/harness/upstream-modified-allowlist.yml
```

## 标准同步流程

1. 从仓库根目录检查分支、工作区、remote 和基线；所有 upstream remote 保持只读，禁止向上游推送。
2. 正式 release tag 存在时，从 `upgrade/upstream-vX.Y.Z` 分支开始；不要例行把上游 `main` 合并到下游 `main`。
3. 刷新上游引用，记录每个项目的 observed SHA，并严格区分 observed ref 与 local adopted baseline。
4. 按 `docs/upstream-sync-manifest.yml` 检查耦合 workspace、package lower bound、editable source 和锁文件；Agent、数据库、存储、语义适配器与 MetricFlow 需要协同评估。
5. 先恢复或迁移文档、配置示例和纯下游测试等低风险差异，再处理 route/service 核心 hook；不要在同一提交中重排企业安全执行链。
6. 对每个保留的上游原文件修改更新 allowlist 分类，并写清保留理由和移除条件；已恢复上游的路径必须从 allowlist 删除。
7. 运行受影响 workspace 的 Ruff/锁文件检查和 focused tests，再运行 Agent、adapter、semantic、MetricFlow、Web 的联动检查；企业认证、授权、配置投影、SQL policy、session owner、Artifact ACL、审计和 quota 需要真实 smoke。
8. 更新本文件的当前数字、manifest 的 adopted/observed 状态和跳过项；通过 PR 交付受保护 `main`，合并后核对 ancestry、`origin/main` 对齐和工作区状态。

## 日常命令

```bash
# 仓库根目录
git fetch --all --tags --prune
git status --short --branch
git remote -v
git branch -vv

# datus-agent
cd datus-agent
uv run ruff check .
uv run python ci/harness/report_upstream_diff.py --base v0.3.9 --check
uv run pytest tests/unit_tests/api/enterprise tests/unit_tests/datus_enterprise
uv run pytest tests/unit_tests/api/enterprise/test_route_security_matrix.py
```

涉及配置示例时，对 `conf/*.yml*` 做 YAML 解析；涉及数据库、语义层、存储适配器或前端契约时，按根清单中的 `verification` 和 `dependency_propagation` 补跑相邻项目检查。无法运行的外部数据库、私有模型或真实内网 smoke 必须记录原因，不能用离线测试结果替代。

## 删除与归档规则

- 一次性迁移日志、旧基线数字和已完成的逐 hunk 说明放在 Git 历史，不继续追加到当前文档。
- 已被根级同步清单、企业平台契约、代码维护地图或包级 README 完整承接的重复文档可以删除；删除前先更新所有仓库内引用。
- 新的下游交接信息只进入根 `docs/` 的单一事实来源，组件 README 只保留链接和组件级用法。
