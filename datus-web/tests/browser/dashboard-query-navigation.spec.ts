import { expect, test, type Page } from "@playwright/test"

const dashboardSlug = "fund-overview"

function response(data: unknown) {
  return {
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ success: true, data }),
  }
}

function dashboardPreviewHtml(): string {
  const message = {
    type: "datus-artifact/query",
    requestId: "navigation-query",
    body: {
      dashboard_slug: dashboardSlug,
      query_slug: "total-nav",
      params: {},
    },
  }

  return `<!doctype html>
    <html>
      <body>
        <script>
          setTimeout(() => parent.postMessage(${JSON.stringify(message)}, "*"), 0)
        <\/script>
      </body>
    </html>`
}

async function mockWorkspaceApi(page: Page, queryResponse: Promise<void>): Promise<void> {
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url())

    if (url.pathname === "/api/v1/dashboard/query") {
      await queryResponse
      try {
        await route.fulfill(response({
          executed_at: "2026-08-09T00:00:00Z",
          datasource: "ccks_fund",
          row_count: 1,
          columns: [{ name: "total", type: "number" }],
          rows: [{ total: 10 }],
          sql: "select 10 as total",
        }))
      } catch {
        // Navigation aborts the request before the delayed response is released.
      }
      return
    }

    if (url.pathname === `/api/v1/dashboards/${dashboardSlug}/html`) {
      await route.fulfill({
        status: 200,
        contentType: "text/html",
        body: dashboardPreviewHtml(),
      })
      return
    }

    if (url.pathname === "/api/v1/me") {
      await route.fulfill(response({
        user_id: "dashboard-query-navigation-user",
        is_admin: false,
        permissions: [
          "module.chat",
          "module.dashboard.view",
          "module.dashboard.query",
        ],
        features: {
          chat: true,
          dashboard_view: true,
        },
        views: {
          artifacts: true,
          artifact_dashboards: true,
          profile: true,
        },
        datasource_grants: {
          ccks_fund: { effect: "allow" },
        },
      }))
      return
    }

    if (url.pathname === "/api/v1/me/permissions") {
      await route.fulfill(response([
        "module.chat",
        "module.dashboard.view",
        "module.dashboard.query",
      ]))
      return
    }

    if (url.pathname === "/api/v1/me/datasource-grants") {
      await route.fulfill(response({ ccks_fund: { effect: "allow" } }))
      return
    }

    if (url.pathname === "/api/v1/me/features") {
      await route.fulfill(response({ chat: true, dashboard_view: true }))
      return
    }

    if (url.pathname === "/api/v1/config/agent") {
      await route.fulfill(response({
        current_datasource: "ccks_fund",
        datasources: { ccks_fund: { type: "mock" } },
      }))
      return
    }

    if (url.pathname === "/api/v1/dashboards") {
      await route.fulfill(response([{
        slug: dashboardSlug,
        name: "Fund overview",
        description: "Dashboard query navigation test",
        owner_id: "dashboard-query-navigation-user",
        datasource: "ccks_fund",
        can_edit: false,
        can_manage_share: false,
      }]))
      return
    }

    if (url.pathname === "/api/v1/chat/sessions") {
      await route.fulfill(response({ sessions: [], total_count: 0 }))
      return
    }

    if (url.pathname === "/api/v1/agents") {
      await route.fulfill(response([]))
      return
    }

    if (url.pathname === "/api/v1/models") {
      await route.fulfill(response({ models: [], providers: [], current_model: null }))
      return
    }

    if (url.pathname === "/api/v1/me/model-credentials"
      || url.pathname === "/api/v1/me/model-preferences"
      || url.pathname === "/api/v1/me/agent-preferences") {
      await route.fulfill(response(url.pathname.endsWith("preferences") ? null : []))
      return
    }

    if (url.pathname === "/api/v1/me/mcp-servers/options") {
      await route.fulfill(response({ enabled: false }))
      return
    }

    if (url.pathname === "/api/v1/me/mcp-servers") {
      await route.fulfill(response([]))
      return
    }

    await route.fulfill(response(null))
  })
}

test("silently cancels a dashboard query when leaving the preview", async ({ page }) => {
  let releaseQuery: (() => void) | undefined
  const queryResponse = new Promise<void>((resolve) => {
    releaseQuery = resolve
  })
  const queryStarted = page.waitForRequest((request) => {
    const url = new URL(request.url())
    return url.pathname === "/api/v1/dashboard/query"
  })
  const queryFailures: string[] = []
  const previewErrors: string[] = []

  page.on("requestfailed", (request) => {
    const url = new URL(request.url())
    if (url.pathname === "/api/v1/dashboard/query") {
      queryFailures.push(request.failure()?.errorText ?? "unknown request failure")
    }
  })
  page.on("console", (message) => {
    if (message.type() === "error") previewErrors.push(message.text())
  })
  page.on("pageerror", (error) => previewErrors.push(error.message))

  await mockWorkspaceApi(page, queryResponse)
  await page.goto(`/artifacts/dashboards/${dashboardSlug}?datasource=ccks_fund`)
  await expect(page.locator('iframe[title="仪表盘预览"]')).toBeVisible()
  const queryRequest = await queryStarted
  expect(queryRequest.postDataJSON()).toEqual({
    dashboard_slug: dashboardSlug,
    query_slug: "total-nav",
    params: {},
  })

  await page.getByRole("button", { name: "个人设置", exact: true }).click()
  await expect(page).toHaveURL(/\/profile\?datasource=ccks_fund$/)
  await expect(page.getByRole("toolbar", { name: "个人设置页头工具栏" })).toBeVisible()

  releaseQuery?.()
  await expect.poll(() => queryFailures.length).toBeGreaterThan(0)
  expect(queryFailures).toEqual(expect.arrayContaining([expect.stringMatching(/aborted/i)]))
  expect(previewErrors.filter((message) => message.includes("Artifact preview query failed"))).toEqual([])
  expect(previewErrors.filter((message) => message.includes("运行仪表盘查询失败"))).toEqual([])
})
