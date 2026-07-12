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

export async function handleArtifactPreviewMessage(
  event: ArtifactPreviewMessage,
  expectedSource: ArtifactPreviewMessageTarget | null,
  expectedDashboardSlug: string,
  query: ArtifactPreviewQueryHandler,
  signal: AbortSignal,
): Promise<boolean> {
  if (!expectedSource || event.source !== expectedSource) return false;

  const request = parseArtifactPreviewQueryRequest(event.data, expectedDashboardSlug);
  if (!request) return false;
  if (signal.aborted) return true;

  try {
    const result = await query(request, signal);
    if (signal.aborted) return true;
    if (!result) throw new Error("Dashboard query returned no data");

    expectedSource.postMessage({
      type: ARTIFACT_QUERY_RESULT,
      requestId: request.requestId,
      status: 200,
      payload: { success: true, data: result },
    }, "*");
  } catch (error) {
    if (signal.aborted) return true;
    console.error("Artifact preview query failed:", error);
    expectedSource.postMessage({
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

function previewQueryFetchBridgeSource(): string {
  return `(function () {
  var requestType = ${safeScriptString(ARTIFACT_QUERY_REQUEST)};
  var resultType = ${safeScriptString(ARTIFACT_QUERY_RESULT)};
  var queryPath = "/api/v1/dashboard/query";
  var timeoutMs = 30000;
  if (window.__datusPreviewBridgeInstalled || !window.fetch || !window.parent) return;
  window.__datusPreviewBridgeInstalled = true;
  var originalFetch = window.fetch.bind(window);
  var pending = new Map();
  var requestSequence = 0;

  function requestUrl(input) {
    if (typeof input === "string" || input instanceof URL) return String(input);
    if (input && typeof input.url === "string") return input.url;
    return "";
  }

  function requestMethod(input, init) {
    return String((init && init.method) || (input instanceof Request && input.method) || "GET").toUpperCase();
  }

  function isDashboardQuery(input) {
    var rawUrl = requestUrl(input).split("#", 1)[0].split("?", 1)[0].replace(/\\/+$/, "");
    return rawUrl === queryPath || rawUrl.endsWith(queryPath);
  }

  async function requestBody(input, init) {
    if (init && typeof init.body === "string") return JSON.parse(init.body);
    if (input instanceof Request) return JSON.parse(await input.clone().text());
    throw new Error("Dashboard query body must be JSON");
  }

  function nextRequestId() {
    requestSequence += 1;
    return Date.now().toString(36) + "-" + requestSequence.toString(36);
  }

  function disposeBridge(event) {
    if (event.persisted) return;
    pending.forEach(function (entry) {
      clearTimeout(entry.timeout);
      entry.reject(new DOMException("Artifact preview was closed", "AbortError"));
    });
    pending.clear();
  }

  window.addEventListener("message", function (event) {
    var message = event.data;
    if (event.source !== window.parent || !message || message.type !== resultType) return;
    var entry = pending.get(message.requestId);
    if (!entry) return;
    pending.delete(message.requestId);
    clearTimeout(entry.timeout);
    entry.resolve(new Response(JSON.stringify(message.payload), {
      status: message.status,
      headers: { "Content-Type": "application/json" }
    }));
  });

  window.fetch = async function (input, init) {
    if (requestMethod(input, init) !== "POST" || !isDashboardQuery(input)) {
      return originalFetch(input, init);
    }

    var body = await requestBody(input, init);
    var requestId = nextRequestId();
    return new Promise(function (resolve, reject) {
      var timeout = setTimeout(function () {
        pending.delete(requestId);
        reject(new Error("Dashboard query timed out"));
      }, timeoutMs);
      pending.set(requestId, { resolve: resolve, reject: reject, timeout: timeout });
      window.parent.postMessage({ type: requestType, requestId: requestId, body: body }, "*");
    });
  };
  window.addEventListener("pagehide", disposeBridge, { once: true });
})();`;
}

export function withArtifactPreviewRuntime(html: string): string {
  const childBridgeSource = previewQueryFetchBridgeSource();
  const script = `<script>
${childBridgeSource}
(function () {
  var requestType = ${safeScriptString(ARTIFACT_QUERY_REQUEST)};
  var resultType = ${safeScriptString(ARTIFACT_QUERY_RESULT)};
  var childBridgeSource = ${safeScriptString(childBridgeSource)};
  var bridgeMarker = "__datusPreviewBridgeInstalled";
  var relayTimeoutMs = 30000;
  var relaySequence = 0;
  var relays = new Map();

  function nextRelayId() {
    relaySequence += 1;
    return "relay-" + Date.now().toString(36) + "-" + relaySequence.toString(36);
  }

  function relayChildRequest(event, message) {
    if (!event.source || typeof event.source.postMessage !== "function") return;
    if (typeof message.requestId !== "string" || !message.requestId) return;

    var relayId = nextRelayId();
    var timeout = setTimeout(function () {
      relays.delete(relayId);
    }, relayTimeoutMs);
    relays.set(relayId, { source: event.source, requestId: message.requestId, timeout: timeout });
    window.parent.postMessage(Object.assign({}, message, { requestId: relayId }), "*");
  }

  function relayParentResult(message) {
    var relay = relays.get(message.requestId);
    if (!relay) return;
    relays.delete(message.requestId);
    clearTimeout(relay.timeout);
    relay.source.postMessage(Object.assign({}, message, { requestId: relay.requestId }), "*");
  }

  window.addEventListener("message", function (event) {
    var message = event.data;
    if (!message || typeof message !== "object") return;
    if (event.source === window.parent) {
      if (message.type === resultType) relayParentResult(message);
      return;
    }
    if (message.type === requestType) relayChildRequest(event, message);
  });

  function injectChildBridge(frame) {
    var srcdoc = frame.getAttribute("srcdoc");
    if (!srcdoc || srcdoc.indexOf(bridgeMarker) !== -1) return;

    var bridgeScript = "<script>" + childBridgeSource + "<" + "/script>\\n";
    var headEnd = srcdoc.toLowerCase().indexOf("</head>");
    var nextSrcdoc = headEnd === -1
      ? bridgeScript + srcdoc
      : srcdoc.slice(0, headEnd) + bridgeScript + srcdoc.slice(headEnd);
    frame.setAttribute("srcdoc", nextSrcdoc);
  }

  function inspectNode(node) {
    if (!(node instanceof Element)) return;
    if (node instanceof HTMLIFrameElement) injectChildBridge(node);
    node.querySelectorAll("iframe[srcdoc]").forEach(injectChildBridge);
  }

  var observer = new MutationObserver(function (mutations) {
    mutations.forEach(function (mutation) {
      if (mutation.type === "attributes") {
        inspectNode(mutation.target);
        return;
      }
      mutation.addedNodes.forEach(inspectNode);
    });
  });
  observer.observe(document.documentElement, {
    subtree: true,
    childList: true,
    attributes: true,
    attributeFilter: ["srcdoc"]
  });
  document.querySelectorAll("iframe[srcdoc]").forEach(injectChildBridge);
  window.addEventListener("pagehide", function (event) {
    if (event.persisted) return;
    observer.disconnect();
    relays.forEach(function (relay) {
      clearTimeout(relay.timeout);
    });
    relays.clear();
  }, { once: true });
})();
</script>`;

  return injectPreviewHeadScript(html, script);
}
