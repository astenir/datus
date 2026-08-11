import assert from "node:assert/strict";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { ESLint } from "eslint";

const projectRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const eslint = new ESLint({ cwd: projectRoot });

async function lintSource(source, filename) {
  const [result] = await eslint.lintText(source, { filePath: join(projectRoot, filename) });
  return result;
}

test("rejects direct fetch calls from project-owned production code", async () => {
  const result = await lintSource('void fetch("/api/v1/probe")\n', "src/composables/useArtifacts.ts");

  assert.equal(result.errorCount, 1, JSON.stringify(result.messages));
  assert.equal(result.messages[0]?.ruleId, "no-restricted-globals");
  assert.match(result.messages[0]?.message || "", /Route backend requests through src\/lib\/request\.ts/);
});

test("allows the canonical request wrapper to call fetch", async () => {
  const result = await lintSource(
    'export async function requestProbe() { return fetch("/api/v1/probe") }\n',
    "src/lib/request.ts",
  );

  assert.equal(result.errorCount, 0, JSON.stringify(result.messages));
});

test("allows tests to inspect or mock fetch", async () => {
  const result = await lintSource('void fetch("/api/v1/probe")\n', "src/lib/request.test.ts");

  assert.equal(result.errorCount, 0, JSON.stringify(result.messages));
});
