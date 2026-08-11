import { expect, test, type Page } from "@playwright/test"

function response(data: unknown) {
  return {
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ success: true, data }),
  }
}

interface MockAdminApiOptions {
  agentConfig?: unknown
  datasources?: unknown
  grantSubjects?: unknown
  me?: unknown
  onGrantSubjectRequest?: (url: URL) => void
}

async function mockAdminApi(page: Page, options: MockAdminApiOptions = {}): Promise<void> {
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url())

    if (url.pathname === "/api/v1/me") {
      await route.fulfill(response(options.me ?? {
        user_id: "admin-tabs-test-user",
        is_admin: true,
        permissions: ["module.admin.*"],
        features: {},
        views: { admin: true, permissions: true },
        datasource_grants: {},
      }))
      return
    }

    if (url.pathname === "/api/v1/config/agent") {
      await route.fulfill(response(options.agentConfig ?? { current_datasource: null, datasources: {} }))
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

    if (url.pathname === "/api/v1/me/mcp-servers/options") {
      await route.fulfill(response({ enabled: false }))
      return
    }

    if (url.pathname === "/api/v1/me/mcp-servers") {
      await route.fulfill(response([]))
      return
    }

    if (url.pathname === "/api/v1/models") {
      await route.fulfill(response({ models: [], providers: [], current_model: null }))
      return
    }

    if (url.pathname === "/api/v1/me/model-credentials") {
      await route.fulfill(response([]))
      return
    }

    if (url.pathname === "/api/v1/me/model-preferences" || url.pathname === "/api/v1/me/agent-preferences") {
      await route.fulfill(response(null))
      return
    }

    if (url.pathname === "/api/v1/admin/audit-logs") {
      await route.fulfill(response({
        entries: [],
        limit: 20,
        before_id: null,
        next_before_id: null,
        has_more: false,
      }))
      return
    }

    if (url.pathname === "/api/v1/admin/datasource-grant-subjects") {
      options.onGrantSubjectRequest?.(url)
      await route.fulfill(response(options.grantSubjects ?? []))
      return
    }

    if (url.pathname === "/api/v1/admin/datasources") {
      await route.fulfill(response(options.datasources ?? []))
      return
    }

    if (url.pathname.startsWith("/api/v1/admin/")) {
      await route.fulfill(response([]))
      return
    }

    await route.fulfill(response(null))
  })
}

test("keeps only the active permission panel rendered when switching tabs", async ({ page }) => {
  await mockAdminApi(page)
  await page.goto("/admin")

  const toolbar = page.getByRole("toolbar", { name: "权限管理页头工具栏" })
  const managementTabs = page.locator('[data-slot="tabs"][data-orientation="horizontal"]').first()
  const visiblePanels = managementTabs.locator('[role="tabpanel"]:visible')

  await expect(toolbar).toBeVisible()
  await expect(managementTabs.getByRole("tab")).toHaveCount(8)
  await expect(visiblePanels).toHaveCount(1)
  await expect(visiblePanels).toContainText("用户")
  await expect(managementTabs.locator('[data-slot="card-title"]', { hasText: "用户" })).toBeVisible()
  await expect(managementTabs.locator('[data-slot="card-title"]', { hasText: "角色" })).toBeHidden()

  await managementTabs.getByRole("tab", { name: "角色", exact: true }).click()
  await expect(page).toHaveURL(/\/admin\?tab=roles(?:&|$)/)
  await expect(visiblePanels).toHaveCount(1)
  await expect(visiblePanels).toContainText("角色")
  await expect(managementTabs.locator('[data-slot="card-title"]', { hasText: "角色" })).toBeVisible()
  await expect(managementTabs.locator('[data-slot="card-title"]', { hasText: "用户" })).toBeHidden()

  await managementTabs.getByRole("tab", { name: "审计", exact: true }).click()
  await expect(page).toHaveURL(/\/admin\?tab=audit(?:&|$)/)
  await expect(visiblePanels).toHaveCount(1)
  await expect(visiblePanels).toContainText("审计")
  await expect(managementTabs.locator('[data-slot="card-title"]', { hasText: "审计" })).toBeVisible()
  await expect(managementTabs.locator('[data-slot="card-title"]', { hasText: "角色" })).toBeHidden()
})

test("leaves permission management without restoring an unauthorized default tab", async ({ page }) => {
  await mockAdminApi(page, {
    me: {
      user_id: "bob",
      is_admin: false,
      permissions: [
        "module.admin.audit",
        "module.admin.roles",
        "module.chat",
        "module.config.view",
        "module.dashboard.view",
        "module.report.view",
      ],
      features: {
        chat: true,
        config_view: true,
        dashboard_view: true,
        report_view: true,
      },
      views: {
        artifacts: true,
        artifact_dashboards: true,
        artifact_reports: true,
        configuration: true,
        permissions: true,
        profile: true,
      },
      datasource_grants: {
        ccks_fund: { effect: "allow" },
      },
    },
    agentConfig: {
      current_datasource: "ccks_fund",
      datasources: { ccks_fund: {} },
    },
  })

  await page.goto("/admin?datasource=ccks_fund&tab=roles")

  await page.getByRole("button", { name: "报表", exact: true }).click()
  await expect(page).toHaveURL(/\/artifacts\/reports\?datasource=ccks_fund(?:&|$)/)

  await page.goto("/admin?datasource=ccks_fund&tab=roles")

  await page.getByRole("button", { name: "配置", exact: true }).click()
  await expect(page).toHaveURL(/\/configuration\?datasource=ccks_fund(?:&|$)/)
})

test("searches grant subjects beyond the first user page and searches datasources", async ({ page }) => {
  const subjectRequests: string[] = []
  await mockAdminApi(page, {
    datasources: [
      { name: "fund", display_name: "Fund Warehouse", type: "postgres", is_default: true },
      { name: "risk", display_name: "Risk Warehouse", type: "postgres", is_default: false },
    ],
    grantSubjects: Array.from({ length: 25 }, (_, index) => ({
      subject_type: "user",
      subject_id: `user_${index}`,
      display_name: `User ${index}`,
      enabled: true,
    })),
    onGrantSubjectRequest: url => subjectRequests.push(url.search),
  })
  await page.goto("/admin?tab=grants")

  await page.getByRole("button", { name: "新增授权" }).click()
  const dialog = page.getByRole("dialog", { name: "新增数据授权" })
  await expect(dialog).toBeVisible()

  await dialog.getByRole("button", { name: "选择用户或角色" }).click()
  await page.getByPlaceholder("搜索用户或角色").fill("user_24")
  await expect.poll(() => subjectRequests.some(query => query.includes("search=user_24"))).toBe(true)
  await page.getByRole("option", { name: "User 24 (user_24)" }).click()
  await expect(dialog.getByRole("button", { name: "选择用户或角色" })).toContainText("User 24")

  await dialog.getByRole("button", { name: "选择数据源" }).click()
  await page.getByPlaceholder("搜索数据源").fill("risk")
  await page.getByRole("option", { name: "Risk Warehouse (risk)" }).click()
  await expect(dialog.getByRole("button", { name: "选择数据源" })).toContainText("Risk Warehouse")
})
