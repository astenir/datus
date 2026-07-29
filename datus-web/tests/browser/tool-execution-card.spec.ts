import { expect, test } from "@playwright/test"

test.beforeEach(async ({ page }) => {
  await page.goto("/tests/browser/fixtures/tool-execution-card.html")
  await expect(page.getByText("执行 SQL", { exact: true })).toBeVisible()
})

test("keeps user-facing summaries on the first level and technical data in details", async ({ page }) => {
  const cards = page.getByTestId("tool-execution-card")
  await expect(cards).toHaveCount(4)
  await expect(page.getByText("探索数据结构", { exact: true })).toBeVisible()
  await expect(page.getByText("创建执行队列", { exact: true })).toBeVisible()
  await expect(page.getByText("执行失败", { exact: true })).toBeVisible()
  await expect(page.getByText("任务内容格式无效，请检查后重试", { exact: true })).toBeVisible()
  await expect(page.getByText("生成报表", { exact: true })).toBeVisible()
  await expect(page.getByText("已中断", { exact: true })).toBeVisible()

  await expect(page.getByText("db_tools.execute_sql", { exact: true })).toBeHidden()
  await cards.nth(0).getByRole("button").first().click()
  await expect(page.getByText("db_tools.execute_sql", { exact: true })).toBeVisible()
  await expect(page.getByText("工具标识", { exact: true }).first()).toBeVisible()
})

test("uses a compact two-row header without a vertically floating leading icon", async ({ page }) => {
  const card = page.getByTestId("tool-execution-card").first()
  const trigger = card.getByTestId("tool-card-trigger")
  const primaryRow = card.getByTestId("tool-card-primary-row")
  const secondaryRow = card.getByTestId("tool-card-secondary-row")

  await expect(trigger).toBeVisible()
  await expect(primaryRow.getByText("执行 SQL", { exact: true })).toBeVisible()
  await expect(primaryRow.getByText("已完成", { exact: true })).toBeVisible()
  await expect(secondaryRow.getByText("select fund_id, position_value from fund_positions", { exact: true })).toBeVisible()
  await expect(secondaryRow.getByText("1.25 秒 · 2 行", { exact: true })).toBeVisible()

  const alignment = await card.evaluate((element) => {
    const triggerElement = element.querySelector<HTMLElement>('[data-testid="tool-card-trigger"]')
    const iconElement = element.querySelector<HTMLElement>('[data-testid="tool-card-leading-icon"]')
    const titleElement = element.querySelector<HTMLElement>('[data-testid="tool-card-title"]')
    if (!triggerElement || !iconElement || !titleElement) return null

    const triggerRect = triggerElement.getBoundingClientRect()
    const iconRect = iconElement.getBoundingClientRect()
    const titleRect = titleElement.getBoundingClientRect()
    return {
      height: triggerRect.height,
      centerDelta: Math.abs(
        iconRect.top + iconRect.height / 2 - (titleRect.top + titleRect.height / 2),
      ),
    }
  })

  expect(alignment).not.toBeNull()
  expect(alignment?.height).toBeLessThanOrEqual(64)
  expect(alignment?.centerDelta).toBeLessThanOrEqual(1)
})

test("shows sub-agent progress inside the parent task without duplicating completion events", async ({ page }) => {
  const taskCard = page.getByTestId("tool-execution-card").nth(1)
  await expect(taskCard.getByText("4 次工具调用 · 3.20 秒", { exact: true })).toBeVisible()

  await taskCard.getByRole("button").first().click()
  await expect(taskCard.getByText("子 Agent 执行过程", { exact: true })).toBeVisible()
  await expect(taskCard.getByText("列出数据表", { exact: true })).toBeVisible()
  await expect(page.getByText("仅用于完成事件", { exact: true })).toHaveCount(0)

  const childCard = taskCard.getByTestId("tool-execution-card")
  await expect(childCard.getByTestId("tool-card-inline-metadata")).toHaveText("0.80 秒 · 3 行")
  await expect(childCard.getByTestId("tool-card-secondary-row")).toHaveCount(0)

  const childTriggerHeight = await childCard.getByTestId("tool-card-trigger").evaluate(
    (element) => element.getBoundingClientRect().height,
  )
  expect(childTriggerHeight).toBeLessThanOrEqual(40)
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
