import { expect, test } from "@playwright/test"

test.beforeEach(async ({ page }) => {
  await page.goto("/tests/browser/fixtures/chat-panel-interaction.html")
  await expect(page.getByText("有什么我能帮你的吗？")).toBeVisible()
})

test("routes normal prompt submission through the workspace send action", async ({ page }) => {
  const messageInput = page.getByRole("textbox", { name: "消息内容" })

  await messageInput.fill("查询销售额")
  await messageInput.press("Enter")

  await expect(page.getByTestId("events")).toContainText("send:查询销售额")
})

test("routes streaming prompt submission to insert and keeps stop behavior", async ({ page }) => {
  const messageInput = page.getByRole("textbox", { name: "消息内容" })

  await page.getByTestId("enter-streaming").click()
  await messageInput.fill("补充当前任务")
  await messageInput.press("Enter")
  await expect(page.getByTestId("events")).toContainText("insert:补充当前任务")

  await page.getByRole("button", { name: "AI 正在生成，点击停止" }).click()
  await expect(page.getByTestId("events")).toContainText("stop")
})

test("keeps model, datasource, Agent, and personal MCP events connected", async ({ page }) => {
  await page.getByRole("button", { name: "选择 Model" }).click()
  await page.getByRole("option", { name: "GPT-4o" }).click()
  await expect(page.getByTestId("selected-model")).toHaveText("openai/gpt-4o")

  const contextTrigger = page.getByRole("button", { name: "选择数据上下文" })
  await contextTrigger.click()
  const contextDialog = page.getByRole("dialog", { name: "选择数据上下文" })
  await contextDialog.getByRole("button", { name: /湖仓分析库/ }).click()
  await expect(page.getByTestId("events")).toContainText("datasource:lake")
  await expect(page.getByTestId("events")).toContainText("catalog")
  await expect(page.getByTestId("selected-datasource")).toHaveText("lake")

  await page.keyboard.press("Escape")
  const settingsTrigger = page.getByRole("button", { name: "会话设置", exact: true })
  await settingsTrigger.click()
  await page.getByRole("menuitem", { name: /Agent/ }).first().click()
  await page.getByRole("menuitemradio", { name: "分析 Agent", exact: true }).click()
  await expect(page.getByTestId("selected-agent")).toHaveText("analytics-agent")

  await page.keyboard.press("Escape")
  await expect(settingsTrigger).toBeVisible()
  await settingsTrigger.click()
  const mcpSubmenuTrigger = page.locator('[data-slot="dropdown-menu-sub-trigger"]').filter({ hasText: "MCP" })
  await mcpSubmenuTrigger.click()
  await page.getByRole("menuitemcheckbox", { name: /指标 MCP/ }).click()
  await expect(page.getByTestId("events")).toContainText("mcp:personal-mcp-1")
})

test("submits the docked permission interaction through the panel coordinator", async ({ page }) => {
  await page.getByTestId("show-permission").click()

  const permissionDock = page.getByLabel("待处理工具权限请求")
  await expect(permissionDock).toBeVisible()
  await permissionDock.getByRole("button", { name: "允许" }).click()

  await expect(page.getByTestId("events")).toContainText(
    'interaction:permission-1:[["allow"]]',
  )
  await expect(permissionDock).toBeHidden()
})
