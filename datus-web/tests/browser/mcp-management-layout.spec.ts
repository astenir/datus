import { expect, test, type Page } from "@playwright/test"

function response(data: unknown) {
  return {
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ success: true, data }),
  }
}

async function mockMcpApi(page: Page): Promise<void> {
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request()
    const url = new URL(request.url())

    if (url.pathname === "/api/v1/me") {
      await route.fulfill(response({
        user_id: "layout-test-user",
        is_admin: false,
        permissions: [
          "module.mcp",
          "module.mcp.personal",
          "mcp.server.list",
          "mcp.server.tools",
          "mcp.server.connectivity",
          "mcp.server.add",
          "mcp.server.edit",
          "mcp.server.remove",
          "mcp.personal.list",
          "mcp.personal.tools",
        ],
        features: {},
        views: { mcp: true },
        datasource_grants: {},
      }))
      return
    }

    if (url.pathname === "/api/v1/mcp/servers" && request.method() === "GET") {
      await route.fulfill(response({
        servers: [{
          name: "metrics-mcp",
          type: "sse",
          status: "启用",
          url: "https://mcp.example.com/metrics",
          auth: { mode: "none", credential_configured: false },
        }],
      }))
      return
    }

    if (url.pathname === "/api/v1/mcp/servers/metrics-mcp/tools") {
      await route.fulfill(response({
        tools: [{ name: "query_metrics", description: "查询指标" }],
      }))
      return
    }

    if (url.pathname === "/api/v1/me/mcp-servers/options") {
      await route.fulfill(response({
        enabled: true,
        allowed_hosts: ["mcp.example.com"],
        max_servers_per_user: 5,
        max_selected_per_session: 2,
      }))
      return
    }

    if (url.pathname === "/api/v1/me/mcp-servers") {
      await route.fulfill(response([{
        id: "personal-mcp-1",
        display_name: "我的指标 MCP",
        transport: "http",
        url: "https://mcp.example.com/personal",
        auth_mode: "none",
        credential_configured: false,
        allowed_tools: [],
        blocked_tools: [],
        enabled: true,
        revision: 1,
      }]))
      return
    }

    if (url.pathname === "/api/v1/me/mcp-servers/personal-mcp-1/tools") {
      await route.fulfill(response([{ name: "query_personal_metrics", description: "查询个人指标" }]))
      return
    }

    await route.fulfill(response(null))
  })
}

test("keeps MCP scope tabs in the management toolbar", async ({ page }, testInfo) => {
  await mockMcpApi(page)
  await page.goto("/mcp")

  const toolbar = page.getByRole("toolbar", { name: "MCP 管理页头工具栏" })
  await expect(toolbar).toBeVisible()
  const enterpriseTab = toolbar.getByRole("tab", { name: "企业 MCP", exact: true })
  const personalTab = toolbar.getByRole("tab", { name: "我的 MCP", exact: true })
  const refreshButton = toolbar.getByRole("button", { name: "刷新", exact: true })
  const addButton = toolbar.getByRole("button", { name: "添加", exact: true })

  await expect(enterpriseTab).toBeVisible()
  await expect(personalTab).toBeVisible()
  await expect(refreshButton).toBeVisible()
  await expect(addButton).toBeVisible()
  await expect(page.getByRole("banner").getByRole("button", { name: "企业 MCP", exact: true })).toHaveCount(0)

  const cardMetrics = await page.locator('[data-slot="card"]').evaluateAll((elements) => elements.map((card) => {
    const title = card.querySelector('[data-slot="card-title"]')
    if (!(title instanceof HTMLElement)) throw new Error("MCP card title was not rendered")

    const cardBox = card.getBoundingClientRect()
    const titleBox = title.getBoundingClientRect()
    const styles = getComputedStyle(title)

    return {
      title: title.textContent?.trim(),
      size: card.getAttribute("data-size"),
      titleOffsetLeft: titleBox.left - cardBox.left,
      titleOffsetTop: titleBox.top - cardBox.top,
      fontSize: styles.fontSize,
      fontWeight: styles.fontWeight,
    }
  }))

  expect(cardMetrics.map((metric) => metric.title)).toEqual(["MCP Server", "metrics-mcp"])
  expect(cardMetrics.map((metric) => metric.size)).toEqual(["default", "default"])
  expect(cardMetrics.map((metric) => metric.fontSize)).toEqual(["18px", "18px"])
  expect(cardMetrics.map((metric) => metric.fontWeight)).toEqual(["500", "500"])
  expect(Math.abs(cardMetrics[0].titleOffsetLeft - cardMetrics[1].titleOffsetLeft)).toBeLessThan(1)
  expect(Math.abs(cardMetrics[0].titleOffsetTop - cardMetrics[1].titleOffsetTop)).toBeLessThan(1)

  const boxes = await Promise.all([
    enterpriseTab.boundingBox(),
    refreshButton.boundingBox(),
    addButton.boundingBox(),
  ])
  expect(boxes.every(box => box !== null)).toBe(true)
  const yPositions = boxes.flatMap(box => box ? [box.y] : [])
  expect(Math.max(...yPositions) - Math.min(...yPositions)).toBeLessThan(8)

  const toolbarRadius = await toolbar.evaluate((element) => getComputedStyle(element).borderRadius)
  const cardRadius = await page.locator('[data-slot="card"]').first().evaluate((element) => getComputedStyle(element).borderRadius)
  expect(toolbarRadius).toBe(cardRadius)

  await page.screenshot({ path: testInfo.outputPath("mcp-toolbar-desktop.png"), fullPage: true })

  await personalTab.click()
  await expect(toolbar).toContainText("管理只在新会话开始前选择的个人 MCP Server。")
  await expect(page.getByRole("button", { name: /我的指标 MCP/ })).toBeVisible()

  await page.setViewportSize({ width: 390, height: 844 })
  await page.reload()
  await expect(page.getByRole("toolbar", { name: "MCP 管理页头工具栏" })).toBeVisible()
  const mobileServerButton = page.locator("button").filter({ hasText: "metrics-mcp" }).first()
  await expect(mobileServerButton).toBeVisible()
  await mobileServerButton.click()
  await expect(page.getByRole("heading", { name: "metrics-mcp", exact: true })).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath("mcp-toolbar-mobile.png"), fullPage: true })

  const dimensions = await page.evaluate(() => ({
    bodyScrollWidth: document.body.scrollWidth,
    viewportWidth: window.innerWidth,
  }))
  expect(dimensions.bodyScrollWidth).toBeLessThanOrEqual(dimensions.viewportWidth)
})
