import { expect, test, type Page } from "@playwright/test"

function response(data: unknown) {
  return {
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ success: true, data }),
  }
}

interface ChatApiMockOptions {
  agentDelayMs?: number
}

async function mockChatApi(page: Page, options: ChatApiMockOptions = {}): Promise<void> {
  let userDefaultAgentId: string | null = null

  await page.route("**/api/v1/**", async (route) => {
    const request = route.request()
    const url = new URL(request.url())

    if (url.pathname === "/api/v1/me") {
      await route.fulfill(response({
        user_id: "chat-context-test-user",
        is_admin: false,
        permissions: [
          "module.chat",
          "module.config.view",
          "module.mcp.personal",
          "mcp.personal.list",
          "mcp.personal.use",
        ],
        features: {},
        views: { chat: true, configuration: true },
        datasource_grants: {
          warehouse: { effect: "allow" },
          lake: { effect: "allow" },
        },
      }))
      return
    }

    if (url.pathname === "/api/v1/config/agent") {
      await route.fulfill(response({
        current_datasource: "warehouse",
        datasources: {
          warehouse: { type: "postgres", display_name: "数据仓库" },
          lake: { type: "postgres", display_name: "湖仓分析库" },
        },
      }))
      return
    }

    if (url.pathname === "/api/v1/chat/sessions") {
      await route.fulfill(response({ sessions: [], total_count: 0 }))
      return
    }

    if (url.pathname === "/api/v1/agents") {
      if (options.agentDelayMs) {
        await new Promise<void>(resolve => setTimeout(resolve, options.agentDelayMs))
      }
      await route.fulfill(response([
        {
          agent_id: "analytics-agent",
          name: "数据分析 Agent",
          description: "浏览器测试 Agent",
          node_class: "agent",
          status: "published",
          source: "enterprise",
          personal_mcp_mode: "selectable",
        },
        {
          agent_id: "basic-agent",
          name: "基础 Agent",
          description: "不支持个人 MCP",
          node_class: "agent",
          status: "published",
          source: "enterprise",
          personal_mcp_mode: "disabled",
        },
        ...Array.from({ length: 24 }, (_, index) => ({
          agent_id: `extra-agent-${index + 1}`,
          name: `额外 Agent ${index + 1}`,
          description: "用于验证长列表滚动",
          node_class: "agent",
          status: "published",
          source: "enterprise",
          personal_mcp_mode: "selectable",
        })),
      ]))
      return
    }

    if (url.pathname === "/api/v1/me/mcp-servers/options") {
      await route.fulfill(response({
        enabled: true,
        allowed_hosts: ["mcp.example.com"],
        max_servers_per_user: 5,
        max_selected_per_session: 3,
      }))
      return
    }

    if (url.pathname === "/api/v1/me/mcp-servers") {
      await route.fulfill(response([
        {
          id: "personal-mcp-1",
          display_name: "我的指标 MCP",
          transport: "http",
          url: "https://mcp.example.com/metrics",
          auth_mode: "none",
          credential_configured: false,
          allowed_tools: [],
          blocked_tools: [],
          enabled: true,
          revision: 1,
        },
        {
          id: "personal-mcp-2",
          display_name: "我的报表 MCP",
          transport: "sse",
          url: "https://mcp.example.com/reports",
          auth_mode: "none",
          credential_configured: false,
          allowed_tools: [],
          blocked_tools: [],
          enabled: true,
          revision: 1,
        },
        {
          id: "personal-mcp-3",
          display_name: "我的知识 MCP",
          transport: "http",
          url: "https://mcp.example.com/knowledge",
          auth_mode: "none",
          credential_configured: false,
          allowed_tools: [],
          blocked_tools: [],
          enabled: true,
          revision: 1,
        },
      ]))
      return
    }

    if (url.pathname === "/api/v1/me/agent-preferences") {
      if (request.method() === "PUT") {
        const input = request.postDataJSON() as { default_agent_id?: string | null }
        userDefaultAgentId = input.default_agent_id ?? null
      }
      await route.fulfill(response({
        default_agent_id: userDefaultAgentId,
        user_default_agent_id: userDefaultAgentId,
        enterprise_default_agent_id: null,
        source: userDefaultAgentId ? "user" : "none",
      }))
      return
    }

    if (url.pathname === "/api/v1/models") {
      await route.fulfill(response({ models: [], providers: [], current_model: "", source: "browser-test" }))
      return
    }

    if (url.pathname === "/api/v1/me/model-credentials" || url.pathname === "/api/v1/me/model-preferences") {
      await route.fulfill(response(url.pathname.endsWith("credentials") ? [] : null))
      return
    }

    if (url.pathname === "/api/v1/catalog/status") {
      await route.fulfill(response({
        statuses: [
          { datasource_id: "warehouse", status: "connected", cached: true },
          { datasource_id: "lake", status: "connected", cached: true },
        ],
      }))
      return
    }

    if (url.pathname === "/api/v1/catalog/prewarm") {
      await route.fulfill(response({ datasource_id: url.searchParams.get("datasource_id") ?? "", status: "queued" }))
      return
    }

    if (url.pathname === "/api/v1/catalog/list") {
      await route.fulfill(response({
        databases: [
          { name: "analytics.sales", schema_name: "sales", tables: ["orders", "customers"] },
          { name: "analytics.finance", schema_name: "finance", tables: ["daily_revenue"] },
          { name: "reporting.public", schema_name: "public", tables: ["overview"] },
        ],
      }))
      return
    }

    await route.fulfill(response(null))
  })
}

test("navigates datasource context and keeps the composer usable on mobile", async ({ page }, testInfo) => {
  await mockChatApi(page)
  await page.goto("/chat")

  const contextTrigger = page.getByRole("button", { name: "选择数据上下文" })
  const moreSettingsTrigger = page.getByRole("button", { name: "会话设置", exact: true })
  await expect(contextTrigger).toBeVisible()
  await expect(moreSettingsTrigger).toBeVisible()

  const [settingsBox, contextBox] = await Promise.all([
    moreSettingsTrigger.boundingBox(),
    contextTrigger.boundingBox(),
  ])
  expect(settingsBox).not.toBeNull()
  expect(contextBox).not.toBeNull()
  expect(settingsBox!.x).toBeLessThan(contextBox!.x)

  await page.screenshot({ path: testInfo.outputPath("chat-context-desktop.png"), fullPage: true })

  await contextTrigger.click()
  const contextDialog = page.getByRole("dialog", { name: "选择数据上下文" })
  await expect(contextDialog.getByText("数据上下文 / 数据源", { exact: true })).toBeVisible()
  await expect(contextDialog.getByRole("button", { name: /数据仓库/ })).toBeVisible()
  await expect(contextDialog.getByRole("button", { name: /湖仓分析库/ })).toBeVisible()

  await contextDialog.getByRole("button", { name: /湖仓分析库/ }).click()
  await expect(contextDialog.getByText("数据上下文 / 数据范围", { exact: true })).toBeVisible()
  await expect(contextDialog.getByText("默认数据库", { exact: true })).toBeVisible()

  await contextDialog.getByRole("button", { name: /analytics/ }).click()
  await expect(contextDialog.getByText("默认 Schema", { exact: true })).toBeVisible()
  await expect(contextDialog.getByRole("button", { name: /sales/ })).toBeVisible()
  await contextDialog.getByRole("button", { name: /sales/ }).click()
  await expect(contextTrigger).toHaveAttribute("title", /湖仓分析库.*analytics.*sales/)

  await moreSettingsTrigger.click()
  await expect(page.getByRole("menuitem", { name: /Agent/ }).first()).toBeVisible()
  await page.getByRole("menuitem", { name: /Agent/ }).first().click()
  const agentSubmenu = page.locator('[data-slot="dropdown-menu-sub-content"]')
    .filter({ has: page.getByRole("menuitemradio", { name: /数据分析 Agent/ }) })
  const agentOptionList = agentSubmenu.locator("[data-agent-list]")
  await expect(agentSubmenu).toBeVisible()
  await expect(agentOptionList).toHaveCSS("overflow-y", "auto")
  expect(await agentOptionList.evaluate(element => element.scrollHeight > element.clientHeight)).toBe(true)
  await expect(page.getByText("选择本轮 Agent，或设置新会话默认值", { exact: true })).toHaveCount(0)
  const agentOption = page.getByRole("menuitemradio", { name: /数据分析 Agent/ })
  await expect(agentOption).toBeVisible()
  await agentOption.click()
  await expect(agentSubmenu).toBeVisible()

  const setDefaultAgentItem = page.getByRole("menuitem", { name: "设为默认 · 数据分析 Agent", exact: true })
  await expect(setDefaultAgentItem).toBeVisible()
  await setDefaultAgentItem.click()

  await moreSettingsTrigger.click()
  await page.getByRole("menuitem", { name: /Agent/ }).first().click()
  await expect(page.getByRole("menuitem", { name: "已是默认 · 数据分析 Agent", exact: true })).toBeDisabled()
  await page.keyboard.press("Escape")

  await moreSettingsTrigger.click()
  const mcpSubmenuTrigger = page.locator('[data-slot="dropdown-menu-sub-trigger"]').filter({ hasText: "MCP" })
  await expect(mcpSubmenuTrigger).toBeVisible()
  await mcpSubmenuTrigger.click()
  const firstMcp = page.getByRole("menuitemcheckbox", { name: /我的指标 MCP/ })
  const secondMcp = page.getByRole("menuitemcheckbox", { name: /我的报表 MCP/ })
  await expect(firstMcp).toBeVisible()
  await expect(page.getByText("HTTPS · https://mcp.example.com/metrics", { exact: true })).toHaveCount(0)
  await expect(page.getByText("最多选择 3 个；会话建立后不可切换。", { exact: true })).toHaveCount(0)
  await expect(page.getByRole("menuitem", { name: "刷新 MCP", exact: true })).toHaveCount(0)
  await expect(page.getByText("企业 MCP", { exact: true })).toHaveCount(0)
  await firstMcp.click()
  await expect(firstMcp).toHaveAttribute("aria-checked", "true")
  await secondMcp.click()
  await expect(secondMcp).toHaveAttribute("aria-checked", "true")
  await secondMcp.focus()
  await page.keyboard.press("Space")
  await expect(secondMcp).toHaveAttribute("aria-checked", "false")
  await expect(firstMcp).toBeVisible()
  await secondMcp.click()
  await expect(secondMcp).toHaveAttribute("aria-checked", "true")
  await expect(mcpSubmenuTrigger).toContainText("2/3")
  await page.keyboard.press("Escape")
  await expect(firstMcp).toBeHidden()

  await moreSettingsTrigger.click()
  await page.getByRole("menuitem", { name: /Agent/ }).first().click()
  await page.getByRole("menuitemradio", { name: /基础 Agent/ }).click()
  await expect(page.getByText("当前 Agent 不支持个人 MCP，已清除本次会话的个人 MCP 选择", { exact: true })).toBeVisible()

  await page.setViewportSize({ width: 390, height: 844 })
  await page.reload()
  await expect(page.getByRole("button", { name: "选择数据上下文" })).toBeVisible()
  await expect(page.getByRole("button", { name: "会话设置", exact: true })).toBeVisible()
  await expect.poll(async () => page.evaluate(() => document.body.scrollWidth)).toBeLessThanOrEqual(390)
  await page.screenshot({ path: testInfo.outputPath("chat-context-mobile.png"), fullPage: true })
})

test("keeps the session settings icon centered while Agent options load", async ({ page }) => {
  await mockChatApi(page, { agentDelayMs: 1200 })
  await page.goto("/chat")

  const settingsTrigger = page.getByRole("button", { name: "会话设置", exact: true })
  const loadingIcon = settingsTrigger.locator("svg.animate-spin")
  const loadingIconSlot = settingsTrigger.locator("[data-session-settings-icon]")
  await expect(loadingIcon).toBeVisible()
  const loadingButtonBox = await settingsTrigger.boundingBox()
  const loadingSlotBox = await loadingIconSlot.boundingBox()
  expect(loadingButtonBox).not.toBeNull()
  expect(loadingSlotBox).not.toBeNull()

  const plusIcon = settingsTrigger.locator("svg:not(.animate-spin)")
  const plusIconSlot = settingsTrigger.locator("[data-session-settings-icon]")
  await expect(plusIcon).toBeVisible()
  const plusButtonBox = await settingsTrigger.boundingBox()
  const plusSlotBox = await plusIconSlot.boundingBox()
  expect(plusButtonBox).not.toBeNull()
  expect(plusSlotBox).not.toBeNull()
  expect(Math.abs(loadingSlotBox!.x - loadingButtonBox!.x - (plusSlotBox!.x - plusButtonBox!.x))).toBeLessThanOrEqual(0.5)
  expect(Math.abs(loadingSlotBox!.y - loadingButtonBox!.y - (plusSlotBox!.y - plusButtonBox!.y))).toBeLessThanOrEqual(0.5)
  expect(loadingSlotBox!.width).toBe(plusSlotBox!.width)
  expect(loadingSlotBox!.height).toBe(plusSlotBox!.height)
})

test("opens session settings from desktop hover and keeps the menu alive across portals", async ({ page }) => {
  await mockChatApi(page)
  await page.goto("/chat")

  const settingsTrigger = page.getByRole("button", { name: "会话设置", exact: true })
  const agentTrigger = page.getByRole("menuitem", { name: /Agent/ }).first()
  const messageInput = page.getByRole("textbox", { name: "消息内容" })

  await settingsTrigger.hover()
  await page.mouse.move(5, 5)
  await page.waitForTimeout(200)
  await expect(agentTrigger).toBeHidden()

  await messageInput.focus()
  await settingsTrigger.hover()
  await expect(agentTrigger).toBeVisible()
  await expect(messageInput).toBeFocused()

  await agentTrigger.hover()
  await expect(agentTrigger).toBeVisible()
  await page.waitForTimeout(300)
  await expect(agentTrigger).toBeVisible()

  await agentTrigger.click()
  const agentSubmenu = page.locator('[data-slot="dropdown-menu-sub-content"]')
    .filter({ has: page.getByRole("menuitemradio", { name: /数据分析 Agent/ }) })
  await expect(agentSubmenu).toBeVisible()

  await agentSubmenu.hover()
  await page.waitForTimeout(300)
  await expect(agentSubmenu).toBeVisible()

  await page.mouse.move(5, 5)
  await expect(agentSubmenu).toBeHidden()
  await expect(agentTrigger).toBeHidden()
})

test("does not use touch hover and keeps keyboard opening available", async ({ page }) => {
  await mockChatApi(page)
  await page.goto("/chat")

  const settingsTrigger = page.getByRole("button", { name: "会话设置", exact: true })
  const agentTrigger = page.getByRole("menuitem", { name: /Agent/ }).first()

  await page.setViewportSize({ width: 390, height: 844 })
  await settingsTrigger.dispatchEvent("pointerenter", { pointerType: "touch" })
  await page.waitForTimeout(200)
  await expect(agentTrigger).toBeHidden()

  await settingsTrigger.focus()
  await page.keyboard.press("Enter")
  await expect(agentTrigger).toBeVisible()
  await page.keyboard.press("Escape")
  await expect(agentTrigger).toBeHidden()
})
