import { expect, test } from "@playwright/test"

test.beforeEach(async ({ page }) => {
  await page.goto("/tests/browser/fixtures/todo-queue.html")
  await expect(page.getByText("正在执行 2/3")).toBeVisible()
})

test("keeps live task progress in one dock above the composer", async ({ page }) => {
  const dock = page.getByTestId("todo-dock")

  await expect(dock.getByText("当前：输出数字 3")).toBeVisible()
  await expect(dock.getByRole("button", { name: "停止" })).toBeVisible()
  await expect(dock.getByText("执行第三步，输出数字 3。")).toBeHidden()

  await dock.getByRole("button", { name: "展开任务详情" }).click()
  await expect(dock.getByText("执行第三步，输出数字 3。")).toBeVisible()
})

test("renders one collapsible historical summary instead of update cards", async ({ page }) => {
  const summary = page.getByTestId("todo-summary")

  await expect(summary.getByText("已完成 3/3 个步骤")).toBeVisible()
  await expect(summary.getByText("输出数字 1")).toBeHidden()
  await summary.getByRole("button", { name: "展开已执行步骤" }).click()
  await expect(summary.getByText("输出数字 1")).toBeVisible()
  await expect(page.locator("body")).not.toContainText("任务状态已更新")
  await expect(page.locator("body")).not.toContainText("Successfully updated todo item")
})

test("keeps the queue within a narrow viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.reload()

  const dock = page.getByTestId("todo-dock")
  const box = await dock.boundingBox()

  expect(box).not.toBeNull()
  expect(box!.x).toBeGreaterThanOrEqual(0)
  expect(box!.x + box!.width).toBeLessThanOrEqual(390)
})
