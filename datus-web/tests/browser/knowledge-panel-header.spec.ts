import { expect, test } from "@playwright/test"

test("keeps shared panel card header typography and offsets aligned", async ({ page }, testInfo) => {
  await page.goto("/tests/browser/fixtures/knowledge-panel-header.html")

  const cards = page.locator('[data-slot="card"]')
  await expect(cards).toHaveCount(2)

  const metrics = await cards.evaluateAll((elements) => elements.map((card) => {
    const title = card.querySelector('[data-slot="card-title"]')
    const description = card.querySelector('[data-slot="card-description"]')
    const header = card.querySelector('[data-slot="card-header"]')
    const content = card.querySelector('[data-slot="card-content"]')
    if (!(title instanceof HTMLElement)) throw new Error("Knowledge card title was not rendered")
    if (!(description instanceof HTMLElement)) throw new Error("Knowledge card description was not rendered")
    if (!(header instanceof HTMLElement)) throw new Error("Knowledge card header was not rendered")
    if (!(content instanceof HTMLElement)) throw new Error("Knowledge card content was not rendered")

    const titleRow = title.parentElement
    if (!(titleRow instanceof HTMLElement)) throw new Error("Knowledge card title row was not rendered")

    const cardBox = card.getBoundingClientRect()
    const titleBox = title.getBoundingClientRect()
    const titleRowBox = titleRow.getBoundingClientRect()
    const descriptionBox = description.getBoundingClientRect()
    const headerBox = header.getBoundingClientRect()
    const contentBox = content.getBoundingClientRect()
    const styles = getComputedStyle(title)

    return {
      size: card.getAttribute("data-size"),
      titleOffsetLeft: titleBox.left - cardBox.left,
      titleOffsetTop: titleBox.top - cardBox.top,
      descriptionGap: descriptionBox.top - titleRowBox.bottom,
      contentGap: contentBox.top - headerBox.bottom,
      fontSize: styles.fontSize,
      fontWeight: styles.fontWeight,
    }
  }))

  expect(metrics.map((metric) => metric.size)).toEqual(["default", "default"])
  expect(metrics.map((metric) => metric.fontSize)).toEqual(["18px", "18px"])
  expect(metrics.map((metric) => metric.fontWeight)).toEqual(["500", "500"])
  expect(metrics.map((metric) => metric.descriptionGap)).toEqual([4, 4])
  expect(metrics.map((metric) => metric.contentGap)).toEqual([16, 16])
  expect(Math.abs(metrics[0].titleOffsetLeft - metrics[1].titleOffsetLeft)).toBeLessThan(1)
  expect(Math.abs(metrics[0].titleOffsetTop - metrics[1].titleOffsetTop)).toBeLessThan(1)

  await page.screenshot({ path: testInfo.outputPath("knowledge-panel-header-desktop.png"), fullPage: true })

  await page.setViewportSize({ width: 390, height: 844 })
  await page.reload()
  await expect(cards).toHaveCount(2)
  await expect.poll(async () => page.evaluate(() => document.body.scrollWidth)).toBeLessThanOrEqual(390)
  await page.screenshot({ path: testInfo.outputPath("knowledge-panel-header-mobile.png"), fullPage: true })
})
