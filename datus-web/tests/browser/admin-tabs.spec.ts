import { expect, test, type Page } from "@playwright/test"

function response(data: unknown) {
  return {
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ success: true, data }),
  }
}

async function mockAdminApi(page: Page): Promise<void> {
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url())

    if (url.pathname === "/api/v1/me") {
      await route.fulfill(response({
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
      await route.fulfill(response({ current_datasource: null, datasources: {} }))
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
