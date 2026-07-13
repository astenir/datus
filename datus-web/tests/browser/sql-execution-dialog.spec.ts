import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("/tests/browser/fixtures/sql-execution-dialog.html");
  await expect(page.getByRole("dialog", { name: "执行 SQL" })).toBeVisible();
});

test("keeps datasource selection compact and renders execution results", async ({ page }) => {
  const datasource = page.getByRole("combobox", { name: "执行数据源" });
  const editor = page.getByRole("textbox", { name: "SQL" });
  const datasourceBox = await datasource.boundingBox();
  const editorBox = await editor.boundingBox();

  expect(datasourceBox).not.toBeNull();
  expect(editorBox).not.toBeNull();
  expect(datasourceBox!.width).toBeLessThan(editorBox!.width / 2);
  await expect(page.getByText("数据库：ccks_fund_pg")).toBeVisible();

  let requestBody: Record<string, unknown> | null = null;
  await page.route("**/api/v1/sql/execute", async (route) => {
    requestBody = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        data: {
          execute_task_id: "browser-test-sql",
          sql_query: "SELECT fund_code, fund_name FROM fund_nav_history",
          row_count: 2,
          sql_return: JSON.stringify([
            { fund_code: "000001", fund_name: "华夏成长" },
            { fund_code: "000002", fund_name: "华夏成长混合" },
          ]),
          result_format: "json",
          execution_time: 0.12,
          executed_at: "2026-07-13T10:00:00Z",
          columns: ["fund_code", "fund_name"],
        },
      }),
    });
  });

  await page.getByRole("button", { name: "执行", exact: true }).click();

  await expect.poll(() => requestBody).toMatchObject({
    datasource: "ccks_fund",
    database_name: "ccks_fund_pg",
    result_format: "json",
  });
  await expect(page.getByRole("heading", { name: "执行结果" })).toBeVisible();
  await expect(page.getByText("2 行 · 0.12s")).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "fund_code" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "华夏成长混合" })).toBeVisible();
});

test("stacks controls and actions on a narrow viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();

  const dialog = page.getByRole("dialog", { name: "执行 SQL" });
  const datasource = page.getByRole("combobox", { name: "执行数据源" });
  const executeButton = page.getByRole("button", { name: "执行", exact: true });
  const cancelButton = page.getByRole("button", { name: "取消" });
  const dialogBox = await dialog.boundingBox();
  const datasourceBox = await datasource.boundingBox();
  const executeBox = await executeButton.boundingBox();
  const cancelBox = await cancelButton.boundingBox();

  expect(dialogBox).not.toBeNull();
  expect(datasourceBox).not.toBeNull();
  expect(executeBox).not.toBeNull();
  expect(cancelBox).not.toBeNull();
  expect(datasourceBox!.width).toBeGreaterThan(dialogBox!.width * 0.7);
  expect(executeBox!.width).toBeGreaterThan(dialogBox!.width * 0.8);
  expect(cancelBox!.width).toBeGreaterThan(dialogBox!.width * 0.8);
});
