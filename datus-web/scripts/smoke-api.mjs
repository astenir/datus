const DEFAULT_API_TARGET = "http://localhost:8000";
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

function authHeaders() {
  const token = process.env.DATUS_API_TOKEN || process.env.DATUS_BEARER_TOKEN || "";
  if (!token.trim()) return {};
  return {
    Authorization: token.trim().toLowerCase().startsWith("bearer ")
      ? token.trim()
      : `Bearer ${token.trim()}`,
  };
}

async function requestJson(baseUrl, path, init) {
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...authHeaders(),
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

const testPayload = await requestJson(baseUrl, "/api/v1/config/datasources/test-saved", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ name: datasourceName }),
});
const testResult = unwrapResult(testPayload);

if (!isRecord(testResult) || typeof testResult.ok !== "boolean") {
  throw new Error("/api/v1/config/datasources/test-saved did not return data.ok boolean");
}
if (!testResult.ok) {
  throw new Error(
    typeof testResult.message === "string" && testResult.message
      ? testResult.message
      : `Saved datasource ${datasourceName} failed its connection test`,
  );
}

console.log(JSON.stringify({
  baseUrl,
  currentDatasource: datasourceName,
  datasourceTest: "ok",
  message: typeof testResult.message === "string" ? testResult.message : "",
}, null, 2));
