import { beforeEach, describe, expect, it, vi } from "vitest";

const contextCommand = vi.fn();
const internalCommand = vi.fn();
const toastError = vi.fn();

vi.mock("@/lib/api", () => ({
  sqlApi: {
    contextCommand,
    internalCommand,
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

describe("useContextInspector", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    contextCommand.mockResolvedValue({
      context_type: "tables",
      database_name: "fund",
      result: {
        tables: [
          { table_name: "fund_nav", table_type: "table" },
          { name: "fund_profile", type: "view" },
        ],
        total_count: 2,
      },
    });
    internalCommand.mockResolvedValue({
      command: "databases",
      args: "",
      result: {
        command_output: "Available databases: fund",
        action_taken: "list_databases",
        context_changed: false,
        data: { databases: ["fund"] },
      },
    });
  });

  it("runs whitelisted context commands with workspace database and schema", async () => {
    const { useContextInspector } = await import("./useContextInspector");
    const inspector = useContextInspector();

    await inspector.runCommand("tables", {
      databaseName: "fund",
      schemaName: "public",
    });

    expect(contextCommand).toHaveBeenCalledWith("http://api.test", "tables", "", "fund", "public");
    expect(inspector.tableRows.value).toEqual([
      { name: "fund_nav", type: "table" },
      { name: "fund_profile", type: "view" },
    ]);
    expect(inspector.outputText.value).toBe("通过 context route 读取当前数据源可见表。");
  });

  it("runs read-only internal metadata commands and normalizes array payloads", async () => {
    const { useContextInspector } = await import("./useContextInspector");
    const inspector = useContextInspector();

    await inspector.runCommand("internal-databases");

    expect(internalCommand).toHaveBeenCalledWith("http://api.test", "databases", "");
    expect(inspector.tableRows.value).toEqual([{ name: "fund", type: "table" }]);
    expect(inspector.outputText.value).toBe("Available databases: fund");
  });

  it("surfaces backend errors without leaving the loading state stuck", async () => {
    contextCommand.mockRejectedValue(new Error("permission denied"));
    const { useContextInspector } = await import("./useContextInspector");
    const inspector = useContextInspector();

    await inspector.runCommand("catalogs");

    expect(inspector.isLoading.value).toBe(false);
    expect(inspector.error.value).toBe("permission denied");
    expect(toastError).toHaveBeenCalledWith("读取上下文失败");
  });
});

describe("contextInspectorInternals", () => {
  it("normalizes backend table objects and string lists", async () => {
    const { contextInspectorInternals } = await import("./useContextInspector");

    expect(contextInspectorInternals.tableRowsFromUnknown([
      "fund",
      { table_name: "fund_nav", table_type: "table" },
      { name: "fund_profile", type: "view" },
      { name: 1 },
    ])).toEqual([
      { name: "fund", type: "table" },
      { name: "fund_nav", type: "table" },
      { name: "fund_profile", type: "view" },
    ]);
  });
});
