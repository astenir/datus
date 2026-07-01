import { beforeEach, describe, expect, it, vi } from "vitest";

const tableDetail = vi.fn();
const getSemanticModel = vi.fn();
const validateSemanticModel = vi.fn();
const saveSemanticModel = vi.fn();
const toastError = vi.fn();
const toastSuccess = vi.fn();

vi.mock("@/lib/api", () => ({
  tableApi: {
    detail: tableDetail,
    getSemanticModel,
    validateSemanticModel,
    saveSemanticModel,
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
    success: toastSuccess,
  },
}));

describe("useSemanticWorkbench", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    tableDetail.mockResolvedValue({
      table: {
        name: "fund_nav",
        rows: 100,
        columns: [{ name: "fund_id", type: "varchar", nullable: false, pk: true }],
        indexes: [],
      },
    });
    getSemanticModel.mockResolvedValue({ yaml: "table: fund_nav" });
    validateSemanticModel.mockResolvedValue({ valid: true, invalid_message: null });
    saveSemanticModel.mockResolvedValue({});
  });

  it("loads table detail and semantic YAML", async () => {
    const { useSemanticWorkbench } = await import("./useSemanticWorkbench");
    const workbench = useSemanticWorkbench();
    workbench.tableName.value = " fund_nav ";

    await workbench.loadTableDetails();

    expect(tableDetail).toHaveBeenCalledWith("http://api.test", "fund_nav");
    expect(getSemanticModel).toHaveBeenCalledWith("http://api.test", "fund_nav");
    expect(workbench.tableName.value).toBe("fund_nav");
    expect(workbench.tableDetail.value?.name).toBe("fund_nav");
    expect(workbench.semanticYaml.value).toBe("table: fund_nav");
  });

  it("rejects empty table names before loading", async () => {
    const { useSemanticWorkbench } = await import("./useSemanticWorkbench");
    const workbench = useSemanticWorkbench();
    workbench.tableName.value = " ";

    await workbench.loadTableDetails();

    expect(tableDetail).not.toHaveBeenCalled();
    expect(getSemanticModel).not.toHaveBeenCalled();
    expect(toastError).toHaveBeenCalledWith("请输入表名");
  });

  it("validates and saves table semantic YAML", async () => {
    const { useSemanticWorkbench } = await import("./useSemanticWorkbench");
    const workbench = useSemanticWorkbench();
    workbench.tableName.value = "fund_nav";

    await workbench.loadTableDetails();
    workbench.semanticYaml.value = "table: fund_nav\ncolumns: []";
    await workbench.validateSemanticModel();
    await workbench.saveSemanticModel();

    expect(validateSemanticModel).toHaveBeenCalledWith("http://api.test", "fund_nav", "table: fund_nav\ncolumns: []");
    expect(saveSemanticModel).toHaveBeenCalledWith("http://api.test", "fund_nav", "table: fund_nav\ncolumns: []");
    expect(tableDetail).toHaveBeenCalledTimes(2);
    expect(toastSuccess).toHaveBeenCalledWith("语义模型已保存");
  });

  it("rejects validate and save before a table is loaded", async () => {
    const { useSemanticWorkbench } = await import("./useSemanticWorkbench");
    const workbench = useSemanticWorkbench();

    await workbench.validateSemanticModel();
    await workbench.saveSemanticModel();

    expect(validateSemanticModel).not.toHaveBeenCalled();
    expect(saveSemanticModel).not.toHaveBeenCalled();
    expect(toastError).toHaveBeenCalledWith("请先加载表");
  });

  it("loads the first table from a catalog entry", async () => {
    const { useSemanticWorkbench } = await import("./useSemanticWorkbench");
    const workbench = useSemanticWorkbench();

    const tableName = workbench.useCatalogTable({
      database_name: "fund",
      schema_name: "public",
      tables: [{ name: "fund_nav" }, { name: "fund_profile" }],
    });

    expect(tableName).toBe("fund_nav");
    expect(tableDetail).toHaveBeenCalledWith("http://api.test", "fund_nav");
  });

  it("reports catalog entries without usable tables", async () => {
    const { useSemanticWorkbench } = await import("./useSemanticWorkbench");
    const workbench = useSemanticWorkbench();

    const tableName = workbench.useCatalogTable({ database_name: "fund", tables: [] });

    expect(tableName).toBeNull();
    expect(tableDetail).not.toHaveBeenCalled();
    expect(toastError).toHaveBeenCalledWith("该目录项没有可加载的表");
  });
});

describe("semanticWorkbenchInternals", () => {
  it("finds the first string or object table name from catalog entries", async () => {
    const { semanticWorkbenchInternals } = await import("./useSemanticWorkbench");

    expect(semanticWorkbenchInternals.firstTableNameFromCatalogEntry({
      tables: ["fund_nav"],
    })).toBe("fund_nav");
    expect(semanticWorkbenchInternals.firstTableNameFromCatalogEntry({
      tables: [{ name: "fund_profile" }],
    })).toBe("fund_profile");
    expect(semanticWorkbenchInternals.firstTableNameFromCatalogEntry({
      tables: [{ name: 1 }],
    })).toBe("");
  });
});
