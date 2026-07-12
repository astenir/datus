import { expect, test, type Frame, type Page } from "@playwright/test";

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
  directMessage?: boolean;
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
  return page.evaluate((options) => {
    const bridge = window.__artifactPreviewBridge;
    if (!bridge) throw new Error("Artifact preview bridge was not loaded");

    const dashboardSlug = options.dashboardSlug ?? "fund-overview";
    const expectedDashboardSlug = options.expectedDashboardSlug ?? "fund-overview";
    const requestBody = {
      dashboard_slug: dashboardSlug,
      query_slug: "total-nav",
      params: { trade_date: "2026-06-01" },
      published_version: 3,
    };
    const innerAction = options.directMessage
      ? `window.parent.postMessage({
          type: ${JSON.stringify(bridge.ARTIFACT_QUERY_REQUEST)},
          requestId: "inner-request",
          body: ${JSON.stringify(requestBody)}
        }, "*");
        document.body.textContent = "message-sent";`
      : `fetch("/api/v1/dashboard/query", {
          method: "POST",
          body: JSON.stringify(${JSON.stringify(requestBody)})
        }).then(function (response) {
          return response.json().then(function (payload) {
            document.body.textContent = JSON.stringify({ status: response.status, payload: payload });
          });
        }).catch(function (error) {
          document.body.textContent = "ERROR:" + error.message;
        });`;
    const innerHtml = `<html><head></head><body>pending<script>${innerAction}<\/script></body></html>`;
    const serializedInnerHtml = JSON.stringify(innerHtml).replace(/</g, "\\u003c");
    const outerBodyScript = `<script>
      var frame = document.createElement("iframe");
      frame.setAttribute("sandbox", "allow-scripts");
      frame.setAttribute("srcdoc", ${serializedInnerHtml});
      document.body.appendChild(frame);
    <\/script>`;
    const outerHtml = bridge.withArtifactPreviewRuntime(
      `<html><head></head><body>${outerBodyScript}</body></html>`,
    );
    const outer = document.createElement("iframe");
    const queryCalls: BrowserQueryRequest[] = [];

    outer.dataset.testid = "outer-preview";
    outer.setAttribute("sandbox", "allow-scripts allow-downloads");
    outer.setAttribute("referrerpolicy", "no-referrer");

    window.addEventListener("message", (event) => {
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
    window.__artifactPreviewTest = { outer, queryCalls, outerHtml };

    return {
      containsAuthorization: outerHtml.includes("Authorization"),
      containsBearer: outerHtml.includes("Bearer"),
    };
  }, scenario);
}

async function previewFrames(page: Page): Promise<{ outer: Frame; inner: Frame }> {
  await expect.poll(() => page.frames().length).toBe(3);
  const outer = page.frames().find(frame => frame.parentFrame() === page.mainFrame());
  const inner = page.frames().find(frame => frame.parentFrame() === outer);
  if (!outer || !inner) throw new Error("Expected nested artifact preview frames");
  return { outer, inner };
}

test.beforeEach(async ({ page }) => {
  await openFixture(page);
});

test("runs a dashboard query through nested sandbox frames without credentials", async ({ page }) => {
  const preview = await launchPreview(page);
  const { outer, inner } = await previewFrames(page);

  await expect(page.getByTestId("outer-preview")).toHaveAttribute("sandbox", "allow-scripts allow-downloads");
  await expect(page.getByTestId("outer-preview")).not.toHaveAttribute("sandbox", /allow-same-origin/);
  await expect(page.getByTestId("outer-preview")).toHaveAttribute("referrerpolicy", "no-referrer");
  await expect(outer.locator("iframe")).toHaveAttribute("sandbox", "allow-scripts");
  await expect(inner.locator("body")).toHaveText(JSON.stringify({
    status: 200,
    payload: {
      success: true,
      data: { row_count: 7, columns: ["total"], data: [{ total: 7 }] },
    },
  }));

  expect(preview).toEqual({ containsAuthorization: false, containsBearer: false });
  await expect.poll(() => page.evaluate(() => window.__artifactPreviewTest?.queryCalls)).toEqual([{
    requestId: expect.stringMatching(/^relay-/),
    dashboardSlug: "fund-overview",
    querySlug: "total-nav",
    params: { trade_date: "2026-06-01" },
    publishedVersion: 3,
  }]);
});

test("rejects a nested query for a different dashboard", async ({ page }) => {
  await launchPreview(page, { dashboardSlug: "another-dashboard", directMessage: true });
  const { inner } = await previewFrames(page);

  await expect(inner.locator("body")).toHaveText("message-sent");
  await page.waitForTimeout(100);
  expect(await page.evaluate(() => window.__artifactPreviewTest?.queryCalls)).toEqual([]);
});

test("returns a concise failure response to the nested renderer", async ({ page }) => {
  await launchPreview(page, { failQuery: true });
  const { inner } = await previewFrames(page);

  await expect(inner.locator("body")).toHaveText(JSON.stringify({
    status: 502,
    payload: { success: false, errorMessage: "运行仪表盘查询失败" },
  }));
});
