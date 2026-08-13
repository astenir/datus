"use strict";

// basedpyright 增量类型门禁：对比本次检查与 committed 基线的错误/警告总数。
// 存量错误不阻塞（基线内），新增错误必须为零（超过基线即失败）。
// 生成基线：uv run --with basedpyright==1.39.9 basedpyright --outputjson datus datus_enterprise
// 基线文件：datus-agent/ci/basedpyright-baseline.json（见 datus-agent/AGENTS.md）。

const fs = require("node:fs");

const USAGE = `usage: node check-basedpyright-baseline.cjs --report <json> --baseline <json> [--update-baseline]`;

function parseArguments(argv) {
  const args = { report: null, baseline: null, update: false };
  for (let index = 0; index < argv.length; index += 1) {
    switch (argv[index]) {
      case "--report":
        args.report = argv[++index];
        break;
      case "--baseline":
        args.baseline = argv[++index];
        break;
      case "--update-baseline":
        args.update = true;
        break;
      default:
        throw new Error(`unknown argument: ${argv[index]}`);
    }
  }
  if (!args.report || !args.baseline) {
    throw new Error(USAGE);
  }
  return args;
}

function loadJson(path) {
  return JSON.parse(fs.readFileSync(path, "utf8"));
}

function countByRule(diagnostics) {
  const counts = {};
  for (const diagnostic of diagnostics) {
    const rule = diagnostic.rule || "unknown";
    counts[rule] = (counts[rule] || 0) + 1;
  }
  return counts;
}

function compareBaseline(report, baseline) {
  const currentErrors = report.summary?.errorCount ?? 0;
  const currentWarnings = report.summary?.warningCount ?? 0;
  const baselineErrors = baseline.errorCount ?? baseline.summary?.errorCount ?? 0;
  const baselineWarnings = baseline.warningCount ?? baseline.summary?.warningCount ?? 0;

  const errorsIncreased = currentErrors > baselineErrors;
  const warningsIncreased = currentWarnings > baselineWarnings;
  const passed = !errorsIncreased && !warningsIncreased;

  const currentRules = countByRule(report.generalDiagnostics || []);
  const baselineRules = baseline.rules || {};
  const ruleDiff = [];
  for (const [rule, count] of Object.entries(currentRules)) {
    const delta = count - (baselineRules[rule] || 0);
    if (delta > 0) {
      ruleDiff.push(`+${delta} ${rule}`);
    }
  }

  return {
    passed,
    currentErrors,
    currentWarnings,
    baselineErrors,
    baselineWarnings,
    ruleDiff: ruleDiff.sort(),
  };
}

function buildBaseline(report, version) {
  return {
    basedpyrightVersion: version,
    pythonVersion: "3.12",
    generatedAt: new Date().toISOString(),
    filesAnalyzed: report.summary?.filesAnalyzed ?? null,
    errorCount: report.summary?.errorCount ?? 0,
    warningCount: report.summary?.warningCount ?? 0,
    rules: countByRule(report.generalDiagnostics || []),
  };
}

if (require.main === module) {
  const args = parseArguments(process.argv.slice(2));
  const report = loadJson(args.report);
  const baseline = loadJson(args.baseline);

  if (args.update) {
    const version = process.env.BASEDPYRIGHT_VERSION || "unknown";
    fs.writeFileSync(args.baseline, `${JSON.stringify(buildBaseline(report, version), null, 2)}\n`);
    console.log(`Baseline updated at ${args.baseline}`);
    process.exit(0);
  }

  const result = compareBaseline(report, baseline);
  if (result.passed) {
    console.log(
      `basedpyright baseline ok: ${result.currentErrors} errors, ${result.currentWarnings} warnings ` +
        `(baseline ${result.baselineErrors}/${result.baselineWarnings})`,
    );
    process.exit(0);
  }

  console.error(
    `basedpyright baseline exceeded: ${result.currentErrors} errors, ${result.currentWarnings} warnings ` +
      `(baseline ${result.baselineErrors}/${result.baselineWarnings})`,
  );
  console.error("新增错误规则:");
  for (const line of result.ruleDiff) {
    console.error(`  ${line}`);
  }
  console.error("存量错误不阻塞；请修复新增错误，或仅在有意收敛时更新基线。");
  process.exit(1);
}

module.exports = { buildBaseline, compareBaseline, countByRule, parseArguments };
