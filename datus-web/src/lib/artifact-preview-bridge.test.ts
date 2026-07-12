import { describe, expect, it, vi } from "vitest";

import {
  ARTIFACT_QUERY_REQUEST,
  ARTIFACT_QUERY_RESULT,
  handleArtifactPreviewMessage,
  parseArtifactPreviewQueryRequest,
  withArtifactPreviewRuntime,
} from "./artifact-preview-bridge";

function queryMessage(overrides: Record<string, unknown> = {}) {
  return {
    type: ARTIFACT_QUERY_REQUEST,
    requestId: "request-1",
    body: {
      dashboard_slug: "fund-overview",
      query_slug: "total-nav",
      params: { trade_date: "2026-06-01" },
      ...overrides,
    },
  };
}

describe("artifact preview bridge", () => {
  it("injects a dashboard-query-only bridge without credentials", () => {
    const html = withArtifactPreviewRuntime("<!doctype html><html><head></head><body>preview</body></html>");

    expect(html).toContain(ARTIFACT_QUERY_REQUEST);
    expect(html).toContain(ARTIFACT_QUERY_RESULT);
    expect(html).toContain('var queryPath = "/api/v1/dashboard/query"');
    expect(html).toContain('requestMethod(input, init) !== "POST"');
    expect(html).toContain("return originalFetch(input, init)");
    expect(html).toContain("new MutationObserver");
    expect(html).toContain("relayChildRequest");
    expect(html).not.toContain("dev-alice-token");
    expect(html).not.toContain("Authorization");
  });

  it("injects the bridge even when the HTML has no head element", () => {
    const html = withArtifactPreviewRuntime("<main>preview</main>");

    expect(html).toContain(ARTIFACT_QUERY_REQUEST);
    expect(html).toContain("<main>preview</main>");
  });

  it("bridges dashboard POST requests and leaves unrelated fetches unchanged", async () => {
    const html = withArtifactPreviewRuntime("<html><head></head><body></body></html>");
    const script = html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
    expect(script).toBeTruthy();

    const originalResponse = new Response("unrelated");
    const originalFetch = vi.fn().mockResolvedValue(originalResponse);
    const parent = { postMessage: vi.fn() };
    const messageListeners: Array<(event: { source: unknown; data: unknown }) => void> = [];
    const pagehideListeners: Array<(event: { source: unknown; data: unknown }) => void> = [];
    const previewWindow = {
      parent,
      fetch: originalFetch,
      addEventListener: vi.fn((type: string, listener: (event: { source: unknown; data: unknown }) => void) => {
        if (type === "message") messageListeners.push(listener);
        if (type === "pagehide") pagehideListeners.push(listener);
      }),
    };
    class TestElement {
      querySelectorAll() {
        return [];
      }
    }
    class TestIFrameElement extends TestElement {
      private srcdoc: string;

      constructor(srcdoc: string) {
        super();
        this.srcdoc = srcdoc;
      }

      getAttribute(name: string) {
        return name === "srcdoc" ? this.srcdoc : null;
      }

      setAttribute(name: string, value: string) {
        if (name === "srcdoc") this.srcdoc = value;
      }
    }
    type ObserverCallback = (mutations: Array<{
      type: string;
      target: TestElement;
      addedNodes: TestElement[];
    }>) => void;
    const observer: { callback?: ObserverCallback } = {};
    const disconnectObserver = vi.fn();
    class TestMutationObserver {
      constructor(callback: ObserverCallback) {
        observer.callback = callback;
      }

      observe() {}
      disconnect() {
        disconnectObserver();
      }
    }
    const documentMock = {
      documentElement: new TestElement(),
      querySelectorAll: () => [],
    };
    const dispatchMessage = (event: { source: unknown; data: unknown }) => {
      messageListeners.forEach(listener => listener(event));
    };

    Function(
      "window",
      "Element",
      "HTMLIFrameElement",
      "MutationObserver",
      "document",
      script!,
    )(previewWindow, TestElement, TestIFrameElement, TestMutationObserver, documentMock);

    const generatedFrame = new TestIFrameElement("<html><head></head><body>artifact</body></html>");
    observer.callback?.([{
      type: "childList",
      target: documentMock.documentElement,
      addedNodes: [generatedFrame],
    }]);
    expect(generatedFrame.getAttribute("srcdoc")).toContain("__datusPreviewBridgeInstalled");

    await expect(previewWindow.fetch("https://assets.example.com/data.json")).resolves.toBe(originalResponse);
    const queryResponsePromise = previewWindow.fetch("/datus-api/api/v1/dashboard/query", {
      method: "POST",
      body: JSON.stringify({
        dashboard_slug: "fund-overview",
        query_slug: "total-nav",
        params: {},
      }),
    });
    await Promise.resolve();
    const requestMessage = parent.postMessage.mock.calls[0]?.[0];
    expect(requestMessage).toMatchObject({
      type: ARTIFACT_QUERY_REQUEST,
      body: {
        dashboard_slug: "fund-overview",
        query_slug: "total-nav",
        params: {},
      },
    });

    dispatchMessage({
      source: parent,
      data: {
        type: ARTIFACT_QUERY_RESULT,
        requestId: requestMessage.requestId,
        status: 200,
        payload: { success: true, data: { row_count: 1 } },
      },
    });

    const response = await queryResponsePromise;
    await expect(response.json()).resolves.toEqual({ success: true, data: { row_count: 1 } });
    expect(originalFetch).toHaveBeenCalledTimes(1);

    const child = { postMessage: vi.fn() };
    dispatchMessage({
      source: child,
      data: {
        type: ARTIFACT_QUERY_REQUEST,
        requestId: "child-request-1",
        body: {
          dashboard_slug: "fund-overview",
          query_slug: "total-nav",
          params: {},
        },
      },
    });
    const relayedRequest = parent.postMessage.mock.calls[1]?.[0];
    expect(relayedRequest.requestId).toMatch(/^relay-/);

    dispatchMessage({
      source: parent,
      data: {
        type: ARTIFACT_QUERY_RESULT,
        requestId: relayedRequest.requestId,
        status: 200,
        payload: { success: true, data: { row_count: 2 } },
      },
    });
    expect(child.postMessage).toHaveBeenCalledWith({
      type: ARTIFACT_QUERY_RESULT,
      requestId: "child-request-1",
      status: 200,
      payload: { success: true, data: { row_count: 2 } },
    }, "*");

    const abandonedQuery = previewWindow.fetch("/api/v1/dashboard/query", {
      method: "POST",
      body: JSON.stringify({
        dashboard_slug: "fund-overview",
        query_slug: "total-nav",
        params: {},
      }),
    });
    await Promise.resolve();
    pagehideListeners.forEach(listener => listener({ source: null, data: null }));

    await expect(abandonedQuery).rejects.toMatchObject({ name: "AbortError" });
    expect(disconnectObserver).toHaveBeenCalledOnce();
  });

  it("parses a valid request for the selected dashboard", () => {
    expect(parseArtifactPreviewQueryRequest(
      queryMessage({ published_version: 3 }),
      "fund-overview",
    )).toEqual({
      requestId: "request-1",
      dashboardSlug: "fund-overview",
      querySlug: "total-nav",
      params: { trade_date: "2026-06-01" },
      publishedVersion: 3,
    });
  });

  it("rejects requests outside the selected dashboard and malformed parameters", () => {
    expect(parseArtifactPreviewQueryRequest(queryMessage({ dashboard_slug: "other" }), "fund-overview")).toBeNull();
    expect(parseArtifactPreviewQueryRequest(queryMessage({ params: [] }), "fund-overview")).toBeNull();
    expect(parseArtifactPreviewQueryRequest(queryMessage({ params: "bad" }), "fund-overview")).toBeNull();
    expect(parseArtifactPreviewQueryRequest(queryMessage({ published_version: 0 }), "fund-overview")).toBeNull();
    expect(parseArtifactPreviewQueryRequest(queryMessage({ published_version: 1.5 }), "fund-overview")).toBeNull();
    expect(parseArtifactPreviewQueryRequest(queryMessage({ published_version: null }), "fund-overview")).toEqual({
      requestId: "request-1",
      dashboardSlug: "fund-overview",
      querySlug: "total-nav",
      params: { trade_date: "2026-06-01" },
    });
  });

  it("rejects missing and oversized request IDs", () => {
    expect(parseArtifactPreviewQueryRequest({ ...queryMessage(), requestId: "" }, "fund-overview")).toBeNull();
    expect(parseArtifactPreviewQueryRequest({ ...queryMessage(), requestId: "x".repeat(129) }, "fund-overview")).toBeNull();
  });

  it("ignores messages that did not come from the active preview iframe", async () => {
    const activeSource = { postMessage: vi.fn() };
    const query = vi.fn();
    const signal = new AbortController().signal;

    const handled = await handleArtifactPreviewMessage(
      { source: { postMessage: vi.fn() }, data: queryMessage() },
      activeSource,
      "fund-overview",
      query,
      signal,
    );

    expect(handled).toBe(false);
    expect(query).not.toHaveBeenCalled();
    expect(activeSource.postMessage).not.toHaveBeenCalled();
  });

  it("posts an API-compatible success envelope to the active preview", async () => {
    const activeSource = { postMessage: vi.fn() };
    const result = { columns: ["total"], data: [{ total: 10 }], row_count: 1 };
    const query = vi.fn().mockResolvedValue(result);
    const signal = new AbortController().signal;

    const handled = await handleArtifactPreviewMessage(
      { source: activeSource, data: queryMessage() },
      activeSource,
      "fund-overview",
      query,
      signal,
    );

    expect(handled).toBe(true);
    expect(query).toHaveBeenCalledWith({
      requestId: "request-1",
      dashboardSlug: "fund-overview",
      querySlug: "total-nav",
      params: { trade_date: "2026-06-01" },
    }, signal);
    expect(activeSource.postMessage).toHaveBeenCalledWith({
      type: ARTIFACT_QUERY_RESULT,
      requestId: "request-1",
      status: 200,
      payload: { success: true, data: result },
    }, "*");
  });

  it("posts a concise failure envelope when the authenticated query fails", async () => {
    const activeSource = { postMessage: vi.fn() };
    const signal = new AbortController().signal;

    await handleArtifactPreviewMessage(
      { source: activeSource, data: queryMessage() },
      activeSource,
      "fund-overview",
      vi.fn().mockRejectedValue(new Error("backend details")),
      signal,
    );

    expect(activeSource.postMessage).toHaveBeenCalledWith({
      type: ARTIFACT_QUERY_RESULT,
      requestId: "request-1",
      status: 502,
      payload: { success: false, errorMessage: "运行仪表盘查询失败" },
    }, "*");
  });

  it("does not post a stale result after the preview lifecycle is aborted", async () => {
    const activeSource = { postMessage: vi.fn() };
    const controller = new AbortController();
    const deferred: {
      resolve?: (value: {
        executed_at: string;
        datasource: string;
        row_count: number;
        columns: [];
      }) => void;
    } = {};
    const query = vi.fn(() => new Promise<{
      executed_at: string;
      datasource: string;
      row_count: number;
      columns: [];
    }>((resolve) => {
      deferred.resolve = resolve;
    }));

    const handling = handleArtifactPreviewMessage(
      { source: activeSource, data: queryMessage() },
      activeSource,
      "fund-overview",
      query,
      controller.signal,
    );
    controller.abort();
    deferred.resolve?.({
      executed_at: "2026-07-12T00:00:00Z",
      datasource: "fund",
      row_count: 1,
      columns: [],
    });

    await expect(handling).resolves.toBe(true);
    expect(activeSource.postMessage).not.toHaveBeenCalled();
  });
});
