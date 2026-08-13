const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const {
  buildBaseline,
  compareBaseline,
  countByRule,
  parseArguments,
} = require("./check-basedpyright-baseline.cjs");

function reportWith(errorCount, warningCount, rules) {
  const generalDiagnostics = [];
  for (const [rule, count] of Object.entries(rules)) {
    for (let index = 0; index < count; index += 1) {
      generalDiagnostics.push({ rule, severity: "error", message: "x" });
    }
  }
  return { summary: { errorCount, warningCount, filesAnalyzed: 10 }, generalDiagnostics };
}

const BASELINE = { errorCount: 10, warningCount: 2, rules: { reportOptionalMemberAccess: 5 } };

test("parseArguments reads report, baseline and update flag", () => {
  const args = parseArguments([
    "--report",
    "r.json",
    "--baseline",
    "b.json",
    "--update-baseline",
  ]);
  assert.deepEqual(args, { report: "r.json", baseline: "b.json", update: true });
});

test("parseArguments rejects unknown and missing arguments", () => {
  assert.throws(() => parseArguments(["--nope"]), /unknown argument/);
  assert.throws(() => parseArguments(["--report", "r.json"]), /usage:/);
});

test("passes when errors and warnings stay within baseline", () => {
  const result = compareBaseline(reportWith(10, 2, { reportOptionalMemberAccess: 5 }), BASELINE);
  assert.equal(result.passed, true);
  assert.deepEqual(result.ruleDiff, []);
});

test("passes when errors decrease (existing fixes are allowed)", () => {
  const result = compareBaseline(reportWith(8, 1, {}), BASELINE);
  assert.equal(result.passed, true);
  assert.deepEqual(result.ruleDiff, []);
});

test("fails when errors exceed baseline and reports per-rule deltas", () => {
  const result = compareBaseline(
    reportWith(12, 2, { reportOptionalMemberAccess: 5, reportArgumentType: 2 }),
    BASELINE,
  );
  assert.equal(result.passed, false);
  assert.equal(result.currentErrors, 12);
  assert.equal(result.baselineErrors, 10);
  assert.deepEqual(result.ruleDiff, ["+2 reportArgumentType"]);
});

test("fails when warnings exceed baseline", () => {
  const result = compareBaseline(reportWith(10, 3, {}), BASELINE);
  assert.equal(result.passed, false);
  assert.equal(result.currentWarnings, 3);
});

test("countByRule groups diagnostics and tolerates missing rule", () => {
  assert.deepEqual(
    countByRule([{ rule: "a" }, { rule: "a" }, { rule: "b" }, { message: "no rule" }]),
    { a: 2, b: 1, unknown: 1 },
  );
});

test("buildBaseline captures summary and rules without diagnostics payload", () => {
  const baseline = buildBaseline(reportWith(7, 1, { a: 3 }), "1.39.9");
  assert.equal(baseline.basedpyrightVersion, "1.39.9");
  assert.equal(baseline.errorCount, 7);
  assert.equal(baseline.warningCount, 1);
  assert.deepEqual(baseline.rules, { a: 3 });
  assert.equal(baseline.generalDiagnostics, undefined);
});

test("update-baseline rewrites the baseline file", () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "baseline-test-"));
  const baselinePath = path.join(directory, "baseline.json");
  fs.writeFileSync(baselinePath, JSON.stringify(BASELINE));
  const reportPath = path.join(directory, "report.json");
  fs.writeFileSync(reportPath, JSON.stringify(reportWith(7, 1, { a: 3 })));

  const { execFileSync } = require("node:child_process");
  execFileSync(
    process.execPath,
    [
      path.resolve(__dirname, "check-basedpyright-baseline.cjs"),
      "--report",
      reportPath,
      "--baseline",
      baselinePath,
      "--update-baseline",
    ],
    { env: { ...process.env, BASEDPYRIGHT_VERSION: "1.39.9" } },
  );

  const updated = JSON.parse(fs.readFileSync(baselinePath, "utf8"));
  assert.equal(updated.errorCount, 7);
  assert.equal(updated.basedpyrightVersion, "1.39.9");
  assert.deepEqual(updated.rules, { a: 3 });
});
