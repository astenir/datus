import { expect, test } from "@playwright/test"

test("keeps leading and metadata toolbar icons at the same visual size", async ({ page }) => {
  await page.goto("/tests/browser/fixtures/page-header-toolbar.html")

  const toolbar = page.getByRole("toolbar", { name: "页头工具栏尺寸测试" })
  await expect(toolbar).toBeVisible()
  await expect(toolbar.getByText("项目默认数据源")).toBeVisible()
  await expect(toolbar.getByText("平台模式")).toBeVisible()

  const iconSizes = await toolbar.locator("svg").evaluateAll((elements) =>
    elements.map((element) => {
      const styles = getComputedStyle(element)
      return { width: styles.width, height: styles.height }
    }),
  )

  expect(iconSizes).toEqual([
    { width: "16px", height: "16px" },
    { width: "16px", height: "16px" },
    { width: "16px", height: "16px" },
  ])
})
