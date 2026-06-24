import { readFile, writeFile } from "node:fs/promises";

const GENERATED_TYPES_PATH = "src/types/openapi.ts";

const source = await readFile(GENERATED_TYPES_PATH, "utf8");
const withoutDocComments = source
  .replace(/\/\*\*[\s\S]*?\*\//g, "")
  .replace(/\n{3,}/g, "\n\n");

await writeFile(GENERATED_TYPES_PATH, withoutDocComments);
console.log(`Stripped generated OpenAPI comments from ${GENERATED_TYPES_PATH}`);
