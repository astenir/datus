const assert = require("node:assert/strict");
const test = require("node:test");

const {
  checkPrTitle,
  FAILURE_LABEL,
  IGNORE_LABELS,
  TYPES,
} = require("./check-pr-title.cjs");

test("accepts valid conventional commit titles", () => {
  for (const title of [
    "feat(web): 新增数据源选择器",
    "fix(agent): 修复会话加载",
    "docs: 补充维护规则",
    "style(web): 调整按钮间距",
    "refactor: 收口聊天工作区",
    "perf(agent): 缓存元数据清单",
    "test(web): 补充渲染器用例",
    "build(db-adapters): 更新锁文件",
    "ci(actions): 升级 checkout",
    "chore(sync): 同步本地企业变更",
    "revert: 回滚上一提交",
  ]) {
    assert.deepEqual(checkPrTitle(title), {
      ok: true,
      ignored: false,
      ignoredBy: [],
      reason: null,
    });
  }
});

test("accepts titles without scope and with multi-scope", () => {
  assert.equal(checkPrTitle("fix: 数据源目录缓存共享连接").ok, true);
  assert.equal(checkPrTitle("feat(web,agent): 个人 MCP 工具过滤").ok, true);
  assert.equal(checkPrTitle("chore(upstream): 升级 datus-agent 至 v0.3.9").ok, true);
});

test("accepts breaking change markers", () => {
  assert.equal(checkPrTitle("feat(web)!: 破坏性变更").ok, true);
  assert.equal(checkPrTitle("feat(web,agent)!: 多 scope 破坏性变更").ok, true);
  assert.equal(checkPrTitle("refactor!: 收口聊天工作区").ok, true);
});

test("rejects empty or non-string titles", () => {
  for (const title of ["", "   ", null, undefined, 42]) {
    const result = checkPrTitle(title);
    assert.equal(result.ok, false);
    assert.match(result.reason, /标题为空/);
  }
});

test("rejects unknown or non-lowercase types", () => {
  for (const title of [
    "update: 模糊提交",
    "wip: 调整代码",
    "bugfix: 修复问题",
    "FIX(web): 大写类型",
    "feat(Web): 大写 scope",
  ]) {
    assert.equal(checkPrTitle(title).ok, false);
  }
});

test("rejects malformed separators and empty descriptions", () => {
  for (const title of [
    "fix(web) 无冒号",
    "fix(web):新增数据源选择器",
    "fix:",
    "fix: ",
    "feat(web):",
    "feat(web): ",
    "新增数据源选择器",
    "feat(web)",
  ]) {
    assert.equal(checkPrTitle(title).ok, false);
  }
});

test("ignores PRs carrying an ignore label", () => {
  for (const label of IGNORE_LABELS) {
    const result = checkPrTitle("任意标题", [label]);
    assert.deepEqual(result, {
      ok: true,
      ignored: true,
      ignoredBy: [label],
      reason: null,
    });
  }
  const result = checkPrTitle("fix: 正常标题", ["enhancement", "meta"]);
  assert.equal(result.ok, true);
  assert.equal(result.ignored, true);
  assert.deepEqual(result.ignoredBy, ["meta"]);
});

test("tolerates missing or non-array labels", () => {
  assert.equal(checkPrTitle("fix: 正常标题").ok, true);
  assert.equal(checkPrTitle("fix: 正常标题", null).ok, true);
  assert.equal(checkPrTitle("fix: 正常标题", "meta").ok, true);
});

test("failure label is exported for workflow reuse", () => {
  assert.equal(FAILURE_LABEL, "title needs formatting");
  assert.ok(TYPES.includes("feat"));
  assert.ok(TYPES.includes("revert"));
});
