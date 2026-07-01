import { readFile, writeFile } from "node:fs/promises";

const GENERATED_TYPES_PATH = "src/types/openapi.ts";

const source = await readFile(GENERATED_TYPES_PATH, "utf8");
const withoutDocComments = source
  .replace(/\/\*\*[\s\S]*?\*\//g, "")
  .replace(/\n{3,}/g, "\n\n");
const normalized = withoutDocComments
  .split("\n")
  .map((line) => line.trimEnd())
  .join("\n");

await writeFile(GENERATED_TYPES_PATH, normalized);
console.log(`Normalized generated OpenAPI types at ${GENERATED_TYPES_PATH}`);
