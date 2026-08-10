import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { expect, test, type Frame, type Page } from "@playwright/test";

const rendererSource = readFileSync(fileURLToPath(new URL(
  "../../../datus-agent/datus/agent/node/visual_artifact/vendor/web_artifact_render_dist/index.umd.js",
  import.meta.url,
)), "utf8");
const rendererDataUrl = `data:text/javascript;base64,${Buffer.from(rendererSource).toString("base64")}`;

type BrowserQueryRequest = {
  requestId: string;
  dashboardSlug: string;
  querySlug: string;
  params: Record<string, unknown>;
  publishedVersion?: number;
};

type BrowserBridge = {
  ARTIFACT_QUERY_REQUEST: string;
  ARTIFACT_QUERY_RESULT: string;
  ARTIFACT_RENDER_ERROR: string;
  artifactRenderErrorFromMessage(
    event: MessageEvent<unknown>,
    expectedSource: Window | null,
  ): { message: string; stack: string | null } | null;
  withArtifactPreviewRuntime(html: string): string;
  handleArtifactPreviewMessage(
    event: MessageEvent<unknown>,
    expectedSource: Window | null,
    expectedDashboardSlug: string,
    query: (request: BrowserQueryRequest) => Promise<Record<string, unknown> | null>,
    signal: AbortSignal,
  ): Promise<boolean>;
};

type BrowserTestState = {
  outer: HTMLIFrameElement;
  queryCalls: BrowserQueryRequest[];
  renderErrors: Array<{ message: string; stack: string | null }>;
  outerHtml: string;
};

declare global {
  interface Window {
    __artifactPreviewBridge?: BrowserBridge;
    __artifactPreviewTest?: BrowserTestState;
  }
}

type PreviewScenario = {
  dashboardSlug?: string;
  expectedDashboardSlug?: string;
  failQuery?: boolean;
  renderError?: boolean;
  standaloneHttp?: boolean;
};

async function openFixture(page: Page) {
  await page.goto("/tests/browser/fixtures/artifact-preview.html");
  await page.addScriptTag({
    type: "module",
    content: `
      import * as bridge from "/src/lib/artifact-preview-bridge.ts";
      window.__artifactPreviewBridge = bridge;
    `,
  });
  await page.waitForFunction(() => Boolean(window.__artifactPreviewBridge));
}

async function launchPreview(page: Page, scenario: PreviewScenario = {}) {
  return page.evaluate(({ options, rendererUrl }) => {
    const bridge = window.__artifactPreviewBridge;
    if (!bridge) throw new Error("Artifact preview bridge was not loaded");

    const dashboardSlug = options.dashboardSlug ?? "fund-overview";
    const expectedDashboardSlug = options.expectedDashboardSlug ?? "fund-overview";
    const renderSource = options.renderError
      ? `
          import React from 'react';
          export default function App() {
            return React.createElement(undefined);
          }
        `
      : `
          import React from 'react';
          import { useDatusArtifact } from '@datus/web-artifact';
          export default function App() {
            const { useQuerySql } = useDatusArtifact();
            const { data, errorMessage } = useQuerySql('queries/total-nav', { trade_date: '2026-06-01' });
            const output = errorMessage ? 'ERROR:' + errorMessage : (data ? JSON.stringify(data) : 'pending');
            return React.createElement('pre', { id: 'query-result' }, output);
          }
        `;
    const detail = {
      slug: dashboardSlug,
      name: "Fund overview",
      published_version: 3,
      files: [{
        path: "render/app.jsx",
        content: renderSource,
      }],
    };
    const outerHtml = bridge.withArtifactPreviewRuntime(`<!doctype html>
      <html><head><meta charset="utf-8"></head><body><div id="root"></div>
      <script src="${rendererUrl}"><\/script>
      <script>
        window.DatusArtifact.initDashboard({
          rootId: "root",
          detail: ${JSON.stringify(detail).replace(/</g, "\\u003c")},
          queryEndpoint: "http://standalone.test/api/v1/dashboard/query",
          queryTransport: ${options.standaloneHttp ? "undefined" : "window.__DATUS_ARTIFACT_QUERY_TRANSPORT__"}
        });
      <\/script></body></html>`);
    const outer = document.createElement("iframe");
    const queryCalls: BrowserQueryRequest[] = [];
    const renderErrors: Array<{ message: string; stack: string | null }> = [];

    outer.dataset.testid = "outer-preview";
    outer.setAttribute("sandbox", "allow-scripts allow-downloads");
    outer.setAttribute("referrerpolicy", "no-referrer");

    window.addEventListener("message", (event) => {
      const renderError = bridge.artifactRenderErrorFromMessage(event, outer.contentWindow);
      if (renderError) {
        renderErrors.push(renderError);
        return;
      }

      void bridge.handleArtifactPreviewMessage(
        event,
        outer.contentWindow,
        expectedDashboardSlug,
        async (request) => {
          queryCalls.push(request);
          if (options.failQuery) throw new Error("query failed");
          return { row_count: 7, columns: ["total"], data: [{ total: 7 }] };
        },
        new AbortController().signal,
      );
    });

    outer.src = URL.createObjectURL(new Blob([outerHtml], { type: "text/html" }));
    document.querySelector("#test-root")?.replaceChildren(outer);
    window.__artifactPreviewTest = { outer, queryCalls, renderErrors, outerHtml };

    return {
      containsAuthorization: outerHtml.includes("Authorization"),
      containsBearer: outerHtml.includes("Bearer"),
      containsMutationObserver: outerHtml.includes("MutationObserver"),
    };
  }, { options: scenario, rendererUrl: rendererDataUrl });
}

async function previewFrames(page: Page): Promise<{ outer: Frame; inner: Frame }> {
  await expect.poll(() => page.frames().length, { timeout: 15_000 }).toBe(3);
  const outer = page.frames().find(frame => frame.parentFrame() === page.mainFrame());
  const inner = page.frames().find(frame => frame.parentFrame() === outer);
  if (!outer || !inner) throw new Error("Expected nested artifact preview frames");
  return { outer, inner };
}

test.beforeEach(async ({ page }) => {
  await openFixture(page);
});

test("runs a query through the renderer-native transport without credentials", async ({ page }) => {
  const preview = await launchPreview(page);
  const { inner } = await previewFrames(page);

  await expect(page.getByTestId("outer-preview")).toHaveAttribute("sandbox", "allow-scripts allow-downloads");
  await expect(page.getByTestId("outer-preview")).not.toHaveAttribute("sandbox", /allow-same-origin/);
  await expect(page.getByTestId("outer-preview")).toHaveAttribute("referrerpolicy", "no-referrer");
  await expect(inner.locator("body")).toBeVisible();
  await expect(inner.locator("#query-result")).toHaveText(JSON.stringify({
    row_count: 7,
    columns: ["total"],
    data: [{ total: 7 }],
  }));

  expect(preview).toEqual({
    containsAuthorization: false,
    containsBearer: false,
    containsMutationObserver: false,
  });
  await expect.poll(() => page.evaluate(() => window.__artifactPreviewTest?.queryCalls)).toEqual([{
    requestId: expect.not.stringMatching(/^relay-/),
    dashboardSlug: "fund-overview",
    querySlug: "total-nav",
    params: { trade_date: "2026-06-01" },
    publishedVersion: 3,
  }]);
});

test("rejects a renderer query for a different dashboard", async ({ page }) => {
  await launchPreview(page, { dashboardSlug: "another-dashboard" });
  await previewFrames(page);

  await page.waitForTimeout(100);
  expect(await page.evaluate(() => window.__artifactPreviewTest?.queryCalls)).toEqual([]);
});

test("returns a concise failure to the renderer-native provider", async ({ page }) => {
  await launchPreview(page, { failQuery: true });
  const { inner } = await previewFrames(page);

  await expect(inner.locator("#query-result")).toHaveText("ERROR:运行仪表盘查询失败");
});

test("forwards nested renderer failures to the host preview", async ({ page }) => {
  await launchPreview(page, { renderError: true });
  await previewFrames(page);

  await expect.poll(() => page.evaluate(() => window.__artifactPreviewTest?.renderErrors.length)).toBe(1);
  const errors = await page.evaluate(() => window.__artifactPreviewTest?.renderErrors);
  expect(errors?.[0]?.message).toContain("React error");
});

test("keeps the renderer HTTP provider as the standalone fallback", async ({ page }) => {
  const httpBodies: unknown[] = [];
  await page.route("http://standalone.test/api/v1/dashboard/query", async (route) => {
    const request = route.request();
    const headers = {
      "Access-Control-Allow-Headers": "content-type",
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Origin": "*",
      "Content-Type": "application/json",
    };
    if (request.method() === "OPTIONS") {
      await route.fulfill({ status: 204, headers });
      return;
    }
    httpBodies.push(request.postDataJSON());
    await route.fulfill({
      status: 200,
      headers,
      body: JSON.stringify({
        success: true,
        data: { row_count: 2, columns: ["total"], data: [{ total: 2 }] },
      }),
    });
  });

  await launchPreview(page, { standaloneHttp: true });
  const { inner } = await previewFrames(page);

  await expect(inner.locator("#query-result")).toHaveText(JSON.stringify({
    row_count: 2,
    columns: ["total"],
    data: [{ total: 2 }],
  }));
  expect(httpBodies).toEqual([{
    dashboard_slug: "fund-overview",
    query_slug: "total-nav",
    params: { trade_date: "2026-06-01" },
    published_version: 3,
  }]);
  expect(await page.evaluate(() => window.__artifactPreviewTest?.queryCalls)).toEqual([]);
});
