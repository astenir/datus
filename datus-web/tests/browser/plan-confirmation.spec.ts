import { expect, test } from "@playwright/test"

test.beforeEach(async ({ page }) => {
  await page.goto("/tests/browser/fixtures/plan-confirmation.html")
  await expect(page.getByText("计划待确认")).toBeVisible()
})

test("renders the plan and submits each explicit decision", async ({ page }) => {
  await expect(page.getByText("基金持仓分析计划")).toBeVisible()
  await expect(page.getByRole("button", { name: "取消规划" })).toBeVisible()
  await expect(page.getByRole("button", { name: "确认并执行" })).toBeVisible()

  await page.getByRole("button", { name: "取消规划" }).click()
  await expect(page.getByTestId("submission")).toHaveText(
    '{"interactionKey":"plan-browser-1","answers":[["cancel"]]}',
  )

  await page.reload()
  await page.getByRole("textbox", { name: "修改意见" }).fill("先补充风险检查")
  await page.getByRole("button", { name: "提交修改意见" }).click()
  await expect(page.getByTestId("submission")).toHaveText(
    '{"interactionKey":"plan-browser-1","answers":[["先补充风险检查"]]}',
  )
})

test("stacks decision buttons on a narrow viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.reload()

  const cancel = page.getByRole("button", { name: "取消规划" })
  const revise = page.getByRole("button", { name: "提交修改意见" })
  const confirm = page.getByRole("button", { name: "确认并执行" })
  const cancelBox = await cancel.boundingBox()
  const reviseBox = await revise.boundingBox()
  const confirmBox = await confirm.boundingBox()

  expect(cancelBox).not.toBeNull()
  expect(reviseBox).not.toBeNull()
  expect(confirmBox).not.toBeNull()
  expect(cancelBox!.width).toBeGreaterThan(300)
  expect(reviseBox!.width).toBeGreaterThan(300)
  expect(confirmBox!.width).toBeGreaterThan(300)
  expect(cancelBox!.y).toBeLessThan(reviseBox!.y)
  expect(reviseBox!.y).toBeLessThan(confirmBox!.y)
})
