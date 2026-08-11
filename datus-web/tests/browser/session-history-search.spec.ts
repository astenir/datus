import { expect, test } from "@playwright/test"

test.beforeEach(async ({ page }) => {
  await page.goto("/tests/browser/fixtures/session-history-search.html")
  await expect(page.getByRole("textbox", { name: "搜索会话" })).toBeVisible()
})

test("keeps the focused search ring inside the history layout boundary", async ({ page }) => {
  const searchInput = page.getByRole("textbox", { name: "搜索会话" })

  await searchInput.focus()

  const metrics = await page.evaluate(() => {
    const input = document.querySelector('[aria-label="搜索会话"]')
    const group = input?.closest('[data-slot="input-group"]')
    const parent = input?.closest('[data-slot="sidebar-group-content"]')

    if (!(group instanceof HTMLElement) || !(parent instanceof HTMLElement)) {
      throw new Error("Session history search layout was not rendered")
    }

    const groupBox = group.getBoundingClientRect()
    const parentBox = parent.getBoundingClientRect()

    return {
      activeElement: document.activeElement?.getAttribute("aria-label"),
      focusRing: getComputedStyle(group).boxShadow,
      leftInset: groupBox.left - parentBox.left,
      rightInset: parentBox.right - groupBox.right,
      parentOverflowX: getComputedStyle(parent).overflowX,
    }
  })

  expect(metrics.activeElement).toBe("搜索会话")
  expect(metrics.focusRing).not.toBe("none")
  expect(metrics.parentOverflowX).toBe("hidden")
  expect(metrics.leftInset).toBeGreaterThanOrEqual(3)
  expect(metrics.rightInset).toBeGreaterThanOrEqual(3)
})

test("filters sessions locally and keeps session selection events intact", async ({ page }) => {
  const searchInput = page.getByRole("textbox", { name: "搜索会话" })

  await searchInput.fill("利润")
  await expect(page.getByRole("button", { name: "查询利润率", exact: true })).toBeVisible()
  await expect(page.getByRole("button", { name: "查询销售额", exact: true })).toHaveCount(0)

  await searchInput.fill("")
  await page.getByRole("button", { name: "查询销售额", exact: true }).click()
  await expect(page.getByTestId("events")).toHaveText("open:session-sales")
})
