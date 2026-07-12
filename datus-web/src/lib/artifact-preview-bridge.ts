import type { SqlQueryResultEnvelope } from "@/types";

export const ARTIFACT_QUERY_REQUEST = "datus-artifact/query";
export const ARTIFACT_QUERY_RESULT = "datus-artifact/query-result";

const MAX_REQUEST_ID_LENGTH = 128;

export type ArtifactPreviewQueryRequest = {
  requestId: string;
  dashboardSlug: string;
  querySlug: string;
  params: Record<string, unknown>;
  publishedVersion?: number;
};

export type ArtifactPreviewQueryHandler = (
  request: ArtifactPreviewQueryRequest,
  signal: AbortSignal,
) => Promise<SqlQueryResultEnvelope | null>;

type ArtifactPreviewQueryResult = {
  type: typeof ARTIFACT_QUERY_RESULT;
  requestId: string;
  status: number;
  payload: {
    success: boolean;
    data?: SqlQueryResultEnvelope;
    errorMessage?: string;
  };
};

type ArtifactPreviewMessageTarget = {
  postMessage(message: ArtifactPreviewQueryResult, targetOrigin: string): void;
  readonly parent?: unknown;
};

type ArtifactPreviewMessage = {
  source: unknown;
  data: unknown;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function nonEmptyString(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed || null;
}

export function parseArtifactPreviewQueryRequest(
  value: unknown,
  expectedDashboardSlug: string,
): ArtifactPreviewQueryRequest | null {
  if (!isRecord(value) || value.type !== ARTIFACT_QUERY_REQUEST) return null;

  const requestId = nonEmptyString(value.requestId);
  if (!requestId || requestId.length > MAX_REQUEST_ID_LENGTH) return null;
  if (!isRecord(value.body)) return null;

  const body = value.body;
  const dashboardSlug = nonEmptyString(body.dashboard_slug);
  const querySlug = nonEmptyString(body.query_slug);
  if (!dashboardSlug || dashboardSlug !== expectedDashboardSlug.trim() || !querySlug) return null;
  if (!isRecord(body.params)) return null;

  const publishedVersion = body.published_version;
  if (publishedVersion !== undefined
    && publishedVersion !== null
    && (typeof publishedVersion !== "number" || !Number.isInteger(publishedVersion) || publishedVersion < 1)) {
    return null;
  }

  return {
    requestId,
    dashboardSlug,
    querySlug,
    params: body.params,
    ...(publishedVersion === undefined || publishedVersion === null ? {} : { publishedVersion }),
  };
}

function isPreviewMessageSource(
  source: unknown,
  expectedRoot: ArtifactPreviewMessageTarget,
): source is ArtifactPreviewMessageTarget {
  let current = source;
  for (let depth = 0; depth < 8; depth += 1) {
    if (current === expectedRoot) return true;
    if (!isRecord(current) && typeof current !== "function") return false;

    try {
      const parent = (current as ArtifactPreviewMessageTarget).parent;
      if (!parent || parent === current) return false;
      current = parent;
    } catch {
      return false;
    }
  }
  return false;
}

export async function handleArtifactPreviewMessage(
  event: ArtifactPreviewMessage,
  expectedSource: ArtifactPreviewMessageTarget | null,
  expectedDashboardSlug: string,
  query: ArtifactPreviewQueryHandler,
  signal: AbortSignal,
): Promise<boolean> {
  if (!expectedSource || !isPreviewMessageSource(event.source, expectedSource)) return false;

  const request = parseArtifactPreviewQueryRequest(event.data, expectedDashboardSlug);
  if (!request) return false;
  if (signal.aborted) return true;

  const responseTarget = event.source;
  try {
    const result = await query(request, signal);
    if (signal.aborted) return true;
    if (!result) throw new Error("Dashboard query returned no data");

    responseTarget.postMessage({
      type: ARTIFACT_QUERY_RESULT,
      requestId: request.requestId,
      status: 200,
      payload: { success: true, data: result },
    }, "*");
  } catch (error) {
    if (signal.aborted) return true;
    console.error("Artifact preview query failed:", error);
    responseTarget.postMessage({
      type: ARTIFACT_QUERY_RESULT,
      requestId: request.requestId,
      status: 502,
      payload: { success: false, errorMessage: "运行仪表盘查询失败" },
    }, "*");
  }

  return true;
}

function safeScriptString(value: string): string {
  return JSON.stringify(value).replace(/</g, "\\u003c");
}

function injectPreviewHeadScript(html: string, script: string): string {
  const marker = "</head>";
  const index = html.toLowerCase().indexOf(marker);
  if (index === -1) return `${script}\n${html}`;

  return `${html.slice(0, index)}${script}\n${html.slice(index)}`;
}

export function withArtifactPreviewRuntime(html: string): string {
  const script = `<script>
(function () {
  function installMemoryStorage(name) {
    try {
      void window[name];
      return;
    } catch {
      var values = new Map();
      var storage = {
        get length() { return values.size; },
        clear: function () { values.clear(); },
        getItem: function (key) {
          key = String(key);
          return values.has(key) ? values.get(key) : null;
        },
        key: function (index) { return Array.from(values.keys())[index] || null; },
        removeItem: function (key) { values.delete(String(key)); },
        setItem: function (key, value) { values.set(String(key), String(value)); }
      };
      Object.defineProperty(window, name, { configurable: true, value: storage });
    }
  }

  installMemoryStorage("localStorage");
  installMemoryStorage("sessionStorage");
  window.__DATUS_ARTIFACT_QUERY_TRANSPORT__ = Object.freeze({
    requestType: ${safeScriptString(ARTIFACT_QUERY_REQUEST)},
    resultType: ${safeScriptString(ARTIFACT_QUERY_RESULT)},
    timeoutMs: 30000
  });
})();
</script>`;

  return injectPreviewHeadScript(html, script);
}
