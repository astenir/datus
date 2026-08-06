import { expect, test } from "@playwright/test"

test("keeps profile identity context compact in the page header on desktop and mobile", async ({ page }, testInfo) => {
  await page.goto("/tests/browser/fixtures/profile-header-meta.html")

  const toolbar = page.getByRole("toolbar", { name: "个人设置页头工具栏" })
  await expect(toolbar).toBeVisible()
  await expect(toolbar).not.toContainText("个人设置")
  await expect(toolbar).toContainText("张三 · zhangsan")
  await expect(toolbar).toContainText("账号正常")
  await expect(toolbar).toContainText("角色 analyst、viewer +1")

  const desktopMetrics = await page.evaluate(() => ({
    bodyScrollWidth: document.body.scrollWidth,
    viewportWidth: window.innerWidth,
    toolbarHeight: document.querySelector('[role="toolbar"]')?.getBoundingClientRect().height ?? 0,
  }))
  expect(desktopMetrics.bodyScrollWidth).toBeLessThanOrEqual(desktopMetrics.viewportWidth)
  expect(desktopMetrics.toolbarHeight).toBeLessThan(100)
  await page.screenshot({ path: testInfo.outputPath("profile-header-meta-desktop.png"), fullPage: true })

  await page.setViewportSize({ width: 390, height: 844 })
  await page.reload()
  await expect(toolbar).toBeVisible()

  const mobileMetrics = await page.evaluate(() => ({
    bodyScrollWidth: document.body.scrollWidth,
    viewportWidth: window.innerWidth,
    toolbarWidth: document.querySelector('[role="toolbar"]')?.getBoundingClientRect().width ?? 0,
  }))
  expect(mobileMetrics.bodyScrollWidth).toBeLessThanOrEqual(mobileMetrics.viewportWidth)
  expect(mobileMetrics.toolbarWidth).toBeLessThanOrEqual(mobileMetrics.viewportWidth - 32)
  await page.screenshot({ path: testInfo.outputPath("profile-header-meta-mobile.png"), fullPage: true })
})
