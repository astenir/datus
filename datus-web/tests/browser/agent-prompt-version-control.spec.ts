import { expect, test } from "@playwright/test";

test("creates the first enterprise version from the resolved builtin fallback", async ({ page }) => {
  await page.goto("/tests/browser/fixtures/agent-prompt-version-control.html?mode=fallback");

  await expect(page.getByText("内置回退")).toBeVisible();
  await expect(page.getByText("生效 v1.2")).toBeVisible();
  await page.getByRole("button", { name: "新建版本" }).click();

  const dialog = page.getByRole("dialog", { name: "新建提示词版本" });
  await expect(dialog).toBeVisible();
  await expect(page.getByLabel("提示词正文")).toHaveValue("Builtin fallback prompt body");
  await page.getByLabel("版本标识").fill("1.0-custom");
  await page.getByLabel("变更说明").fill("Create enterprise baseline");
  await page.getByRole("button", { name: "创建版本", exact: true }).click();

  await expect(page.getByTestId("last-event")).toContainText('"type":"create"');
  await expect(page.getByTestId("last-event")).toContainText('"based_on_version_id":null');
  await expect(page.getByTestId("last-event")).toContainText('"prompt_template":"Builtin fallback prompt body"');
});

test("previews and compares a version without activating it", async ({ page }) => {
  await page.goto("/tests/browser/fixtures/agent-prompt-version-control.html?mode=versions");

  await page.getByRole("combobox", { name: "选择提示词版本" }).click();
  await page.getByRole("option", { name: /v2\.0/ }).click();

  await expect(page.getByTestId("last-event")).toContainText('"type":"select"');
  await expect(page.getByTestId("last-event")).toContainText('"versionId":"version-2"');
  await expect(page.getByTestId("activation-count")).toHaveText("0");
  await expect(page.getByText("预览 v2.0")).toBeVisible();

  await page.getByRole("button", { name: "比较当前版本" }).click();
  const compareDialog = page.getByRole("dialog", { name: "比较提示词版本" });
  await expect(compareDialog).toBeVisible();
  await expect(page.getByLabel("当前 v1.0")).toHaveValue("Prompt body v1");
  await expect(page.getByLabel("预览 v2.0")).toHaveValue("Prompt body v2");
});

test("requires confirmation before activating a previewed version", async ({ page }) => {
  await page.goto("/tests/browser/fixtures/agent-prompt-version-control.html?mode=versions");
  await page.getByRole("combobox", { name: "选择提示词版本" }).click();
  await page.getByRole("option", { name: /v2\.0/ }).click();

  await page.getByRole("button", { name: "设为当前版本" }).click();
  const confirmDialog = page.getByRole("dialog", { name: "切换当前提示词版本" });
  await expect(confirmDialog).toContainText("正在执行的轮次不会被修改");
  await expect(page.getByTestId("activation-count")).toHaveText("0");
  await page.getByRole("button", { name: "确认切换" }).click();

  await expect(page.getByTestId("activation-count")).toHaveText("1");
  await expect(page.getByTestId("last-event")).toContainText('"type":"activate"');
  await expect(page.getByText("当前生效 v2.0")).toBeVisible();
});

test("keeps the create dialog usable on a mobile viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/tests/browser/fixtures/agent-prompt-version-control.html?mode=fallback");
  await page.getByRole("button", { name: "新建版本" }).click();

  const dialog = page.getByRole("dialog", { name: "新建提示词版本" });
  const dialogBox = await dialog.boundingBox();
  const promptBox = await page.getByLabel("提示词正文").boundingBox();

  expect(dialogBox).not.toBeNull();
  expect(promptBox).not.toBeNull();
  expect(dialogBox!.width).toBeLessThanOrEqual(390);
  expect(promptBox!.width).toBeGreaterThan(dialogBox!.width * 0.75);
});
