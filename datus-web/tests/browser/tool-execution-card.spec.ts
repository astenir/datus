import { expect, test } from "@playwright/test"

test.beforeEach(async ({ page }) => {
  await page.goto("/tests/browser/fixtures/tool-execution-card.html")
  await expect(page.getByText("执行 SQL", { exact: true })).toBeVisible()
})

test("keeps user-facing summaries on the first level and technical data in details", async ({ page }) => {
  const cards = page.getByTestId("tool-execution-card")
  await expect(cards).toHaveCount(3)
  await expect(page.getByText("探索数据结构", { exact: true })).toBeVisible()
  await expect(page.getByText("创建执行队列", { exact: true })).toBeVisible()
  await expect(page.getByText("执行失败", { exact: true })).toBeVisible()
  await expect(page.getByText("任务内容格式无效，请检查后重试", { exact: true })).toBeVisible()

  await expect(page.getByText("db_tools.execute_sql", { exact: true })).toBeHidden()
  await cards.nth(0).getByRole("button").first().click()
  await expect(page.getByText("db_tools.execute_sql", { exact: true })).toBeVisible()
  await expect(page.getByText("工具标识", { exact: true }).first()).toBeVisible()
})

test("shows sub-agent progress inside the parent task without duplicating completion events", async ({ page }) => {
  const taskCard = page.getByTestId("tool-execution-card").nth(1)
  await expect(taskCard.getByText("4 次工具调用 · 3.20 秒", { exact: true })).toBeVisible()

  await taskCard.getByRole("button").first().click()
  await expect(taskCard.getByText("子 Agent 执行过程", { exact: true })).toBeVisible()
  await expect(taskCard.getByText("列出数据表", { exact: true })).toBeVisible()
  await expect(page.getByText("仅用于完成事件", { exact: true })).toHaveCount(0)
})

test("uses the same status vocabulary for interaction history and artifacts", async ({ page }) => {
  const interaction = page.getByTestId("interaction-summary")
  await expect(interaction.getByText("补充信息", { exact: true })).toBeVisible()
  await expect(interaction.getByText("已回答", { exact: true })).toBeVisible()
  await expect(page.getByText("ask_user", { exact: true })).toHaveCount(0)

  await expect(page.getByText("基金持仓分析报告", { exact: true })).toBeVisible()
  await expect(page.getByText("已生成", { exact: true })).toBeVisible()
  await expect(page.getByText("报表 · 新建", { exact: true })).toBeVisible()
})

test("does not overflow a narrow conversation viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.reload()

  await page.getByTestId("tool-execution-card").nth(1).getByRole("button").first().click()
  const dimensions = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }))

  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth)
})
