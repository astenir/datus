"use strict";

// PR 标题门禁：强制 Conventional Commits 格式 `<type>(<scope>): <描述>`。
// 规则与根级 AGENTS.md 提交规范一致：type 来自允许列表，scope 可选（支持
// 逗号分隔的多 scope，如 `feat(web,agent)`），允许 `!` 表示破坏性变更，
// 冒号后必须跟随非空描述。纯函数实现，便于单测和 workflow 复用。

const TYPES = [
  "feat",
  "fix",
  "docs",
  "style",
  "refactor",
  "perf",
  "test",
  "build",
  "ci",
  "chore",
  "revert",
];

const TYPE_PATTERN = TYPES.join("|");
const TITLE_PATTERN = new RegExp(
  `^(${TYPE_PATTERN})(\\([a-z0-9][a-z0-9,-]*\\))?!?:\\s+\\S+.*$`,
);

// 失败时打在 PR 上的 label；带这些 label 的 PR 跳过检查（上游 datus-agent
// 同名机制，用于放行 meta/sync 类 PR）。
const FAILURE_LABEL = "title needs formatting";
const IGNORE_LABELS = new Set(["dont-check-PRs-with-this-label", "meta"]);

function checkPrTitle(title, labels) {
  const labelList = Array.isArray(labels) ? labels : [];
  const ignoredBy = labelList.filter((label) => IGNORE_LABELS.has(label));
  if (ignoredBy.length > 0) {
    return { ok: true, ignored: true, ignoredBy, reason: null };
  }

  if (typeof title !== "string" || title.trim() === "") {
    return {
      ok: false,
      ignored: false,
      ignoredBy: [],
      reason:
        "PR 标题为空，请按 Conventional Commits 规范填写：`<type>(<scope>): <描述>`",
    };
  }

  if (!TITLE_PATTERN.test(title.trim())) {
    return {
      ok: false,
      ignored: false,
      ignoredBy: [],
      reason:
        "PR 标题不符合 Conventional Commits 规范 `" +
        "<type>(<scope>): <描述>`。type 必须是 " +
        TYPES.join("/") +
        " 之一，scope 可选；例如 `feat(web): 新增数据源选择器`、" +
        "`fix(agent): 修复会话加载` 或 `chore(upstream): 升级依赖`。",
    };
  }

  return { ok: true, ignored: false, ignoredBy: [], reason: null };
}

module.exports = {
  checkPrTitle,
  FAILURE_LABEL,
  IGNORE_LABELS,
  TITLE_PATTERN,
  TYPES,
};
