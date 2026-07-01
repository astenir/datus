import { writeFile } from "node:fs/promises";

const DEFAULT_API_TARGET = "http://localhost:8000";

function trimTrailingSlash(value) {
  return value.trim().replace(/\/+$/, "");
}

function openapiUrl() {
  const explicitUrl = process.env.DATUS_OPENAPI_URL?.trim();
  if (explicitUrl) return explicitUrl;

  const target = process.env.VITE_DATUS_API_TARGET
    || process.env.DATUS_API_TARGET
    || DEFAULT_API_TARGET;
  return `${trimTrailingSlash(target)}/openapi.json`;
}

function assertOpenApiDocument(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("OpenAPI response is not a JSON object");
  }
  if (typeof value.openapi !== "string" || !value.paths || typeof value.paths !== "object") {
    throw new Error("OpenAPI response is missing required openapi/paths fields");
  }
}

const url = openapiUrl();
const response = await fetch(url, { headers: { Accept: "application/json" } });

if (!response.ok) {
  throw new Error(`Failed to fetch OpenAPI from ${url}: HTTP ${response.status} ${response.statusText}`);
}

const document = await response.json();
assertOpenApiDocument(document);
await writeFile("openapi.json", `${JSON.stringify(document)}\n`);

console.log(`Synced OpenAPI schema from ${url}`);
