import { expect, test } from "@playwright/test";

test("forwards a tooltip-wrapped artifact action click", async ({ page }) => {
  await page.goto("/tests/browser/fixtures/artifact-action.html");

  const action = page.getByRole("button", { name: "打开" });
  const clickCount = page.getByTestId("click-count");

  await expect(action).toBeVisible();
  await expect(clickCount).toHaveText("0");
  await action.click();
  await expect(clickCount).toHaveText("1");
});
