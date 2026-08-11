import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const schemaPath = join(projectRoot, "openapi.json");
const trackedTypesPath = join(projectRoot, "src/types/openapi.ts");
const generatorPath = join(projectRoot, "node_modules/openapi-typescript/bin/cli.js");
const normalizerPath = join(projectRoot, "scripts/strip-openapi-comments.mjs");
const tempDir = mkdtempSync(join(tmpdir(), "datus-openapi-types-"));
const generatedTypesPath = join(tempDir, "openapi.ts");

function runNodeScript(scriptPath, args) {
  const result = spawnSync(process.execPath, [scriptPath, ...args], {
    cwd: projectRoot,
    encoding: "utf8",
    stdio: "inherit",
  });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(`Command failed with exit code ${result.status}: ${scriptPath}`);
  }
}

function firstDifference(left, right) {
  const leftLines = left.split("\n");
  const rightLines = right.split("\n");
  const lineCount = Math.max(leftLines.length, rightLines.length);
  for (let index = 0; index < lineCount; index += 1) {
    if (leftLines[index] !== rightLines[index]) return index + 1;
  }
  return null;
}

try {
  runNodeScript(generatorPath, [schemaPath, "-o", generatedTypesPath]);
  runNodeScript(normalizerPath, [generatedTypesPath]);

  const expected = readFileSync(trackedTypesPath, "utf8");
  const actual = readFileSync(generatedTypesPath, "utf8");
  if (expected !== actual) {
    const line = firstDifference(expected, actual);
    throw new Error(
      `Generated OpenAPI types are stale (first difference at line ${line ?? "unknown"}). `
        + "Run npm run api:types after reviewing the OpenAPI source.",
    );
  }

  console.log("Generated OpenAPI types match openapi.json.");
} finally {
  rmSync(tempDir, { recursive: true, force: true });
}
