import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SqlExecuteResult } from "@/types";

const execute = vi.fn();
const stopExecute = vi.fn();
const toastError = vi.fn();

vi.mock("@/lib/api", () => ({
  sqlApi: {
    execute,
    stopExecute,
  },
}));

vi.mock("@/composables/useConnection", () => ({
  useConnection: () => ({
    effectiveBase: () => "http://api.test",
  }),
}));

vi.mock("vue-sonner", () => ({
  toast: {
    error: toastError,
  },
}));

function sqlResult(overrides: Partial<SqlExecuteResult> = {}): SqlExecuteResult {
  return {
    execute_task_id: "task-1",
    sql_query: "select 1",
    row_count: 1,
    sql_return: '[{"name":"fund","count":2}]',
    result_format: "json",
    execution_time: 0.25,
    executed_at: "2026-06-29T00:00:00Z",
    ...overrides,
  };
}

describe("useSqlExecution", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    execute.mockResolvedValue(sqlResult());
    stopExecute.mockResolvedValue({ stopped: true });
  });

  it("executes SQL with workspace database context and normalizes table rows", async () => {
    const { useSqlExecution } = await import("./useSqlExecution");
    const execution = useSqlExecution();

    await execution.executeSql(" select 1 ", { databaseName: " fund " });

    expect(execute).toHaveBeenCalledWith("http://api.test", "select 1", {
      database_name: "fund",
      result_format: "json",
      execute_task_id: expect.stringMatching(/^frontend-sql-/),
    });
    expect(execution.rows.value).toEqual([{ name: "fund", count: 2 }]);
    expect(execution.columns.value).toEqual(["name", "count"]);
    expect(execution.displayRows.value).toEqual([["fund", "2"]]);
    expect(execution.running.value).toBe(false);
  });

  it("uses backend columns when an empty result still has headers", async () => {
    execute.mockResolvedValue(sqlResult({
      row_count: 0,
      sql_return: "[]",
      columns: ["fund_code", "nav"],
    }));
    const { useSqlExecution } = await import("./useSqlExecution");
    const execution = useSqlExecution();

    await execution.executeSql("select fund_code, nav from fund limit 0");

    expect(execution.columns.value).toEqual(["fund_code", "nav"]);
    expect(execution.displayRows.value).toEqual([]);
  });

  it("surfaces execution errors without leaving loading active", async () => {
    execute.mockRejectedValue(new Error("permission denied"));
    const { useSqlExecution } = await import("./useSqlExecution");
    const execution = useSqlExecution();

    await execution.executeSql("select * from forbidden");

    expect(execution.error.value).toBe("permission denied");
    expect(execution.running.value).toBe(false);
    expect(toastError).toHaveBeenCalledWith("SQL 执行失败");
  });

  it("stops an active SQL execution and ignores its late result", async () => {
    let resolveExecute: (result: SqlExecuteResult) => void = () => undefined;
    execute.mockReturnValue(new Promise<SqlExecuteResult>((resolve) => {
      resolveExecute = resolve;
    }));
    const { useSqlExecution } = await import("./useSqlExecution");
    const execution = useSqlExecution();

    const pending = execution.executeSql("select pg_sleep(10)");
    expect(execution.running.value).toBe(true);

    await execution.stopRunning();
    resolveExecute(sqlResult({ sql_return: '[{"late":true}]' }));
    await pending;

    expect(stopExecute).toHaveBeenCalledWith("http://api.test", expect.stringMatching(/^frontend-sql-/));
    expect(execution.result.value).toBeNull();
    expect(execution.running.value).toBe(false);
  });
});
