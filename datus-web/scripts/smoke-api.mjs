const DEFAULT_API_TARGET = "http://localhost:8000";
const SENSITIVE_KEY = /password|passwd|pwd|secret|token|key|credential/i;

function trimTrailingSlash(value) {
  return value.trim().replace(/\/+$/, "");
}

function apiTarget() {
  return trimTrailingSlash(
    process.env.VITE_DATUS_API_TARGET
    || process.env.DATUS_API_TARGET
    || DEFAULT_API_TARGET,
  );
}

async function requestJson(baseUrl, path, init) {
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...init?.headers,
    },
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} ${response.statusText}: ${text}`);
  }
  return payload;
}

function unwrapResult(payload) {
  if (payload && typeof payload === "object" && "success" in payload) {
    if (payload.success !== true) {
      throw new Error(String(payload.errorMessage || payload.errorCode || "Backend request failed"));
    }
    return payload.data ?? null;
  }
  return payload;
}

function isRecord(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function shouldIncludeDatasourceField(key, value) {
  if (value == null) return false;
  if (typeof value !== "string") return true;
  return value.trim() !== "" || key === "password";
}

function datasourceProbe(datasource) {
  if (!isRecord(datasource) || typeof datasource.type !== "string" || !datasource.type.trim()) {
    throw new Error("Current datasource is missing a testable string type");
  }

  const probe = { type: datasource.type };
  for (const [key, value] of Object.entries(datasource)) {
    if (key === "type" || key === "extra" || !shouldIncludeDatasourceField(key, value)) continue;
    probe[key] = value;
  }

  if (isRecord(datasource.extra)) {
    for (const [key, value] of Object.entries(datasource.extra)) {
      if (key in probe || !shouldIncludeDatasourceField(key, value)) continue;
      probe[key] = value;
    }
  }

  return probe;
}

function summarizePayload(value) {
  return Object.fromEntries(Object.entries(value).map(([key, item]) => {
    if (SENSITIVE_KEY.test(key)) return [key, "<redacted>"];
    if (Array.isArray(item)) return [key, `array(${item.length})`];
    if (item === null) return [key, "null"];
    return [key, typeof item];
  }));
}

const baseUrl = apiTarget();
const configPayload = await requestJson(baseUrl, "/api/v1/config/agent");
const config = unwrapResult(configPayload);

if (!isRecord(config)) {
  throw new Error("/api/v1/config/agent did not return a config object");
}

const datasourceName = typeof config.current_datasource === "string" ? config.current_datasource : "";
if (!datasourceName) {
  throw new Error("Config does not include current_datasource");
}

const datasource = isRecord(config.datasources) ? config.datasources[datasourceName] : null;
const probe = datasourceProbe(datasource);
const testPayload = await requestJson(baseUrl, "/api/v1/config/datasources/test", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(probe),
});
const testResult = unwrapResult(testPayload);

if (!isRecord(testResult) || typeof testResult.ok !== "boolean") {
  throw new Error("/api/v1/config/datasources/test did not return data.ok boolean");
}

console.log(JSON.stringify({
  baseUrl,
  currentDatasource: datasourceName,
  datasourceTest: testResult.ok ? "ok" : "failed",
  message: typeof testResult.message === "string" ? testResult.message : "",
  probeShape: summarizePayload(probe),
}, null, 2));
