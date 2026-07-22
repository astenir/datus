import { beforeEach, describe, expect, it, vi } from "vitest";

const tableDetail = vi.fn();
const getSemanticModel = vi.fn();
const validateSemanticModel = vi.fn();
const saveSemanticModel = vi.fn();
const toastError = vi.fn();
const toastSuccess = vi.fn();

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

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
    const workbench = useSemanticWorkbench({ currentDatasource: () => "oceanbase_data" });
    workbench.tableName.value = " fund_nav ";

    await workbench.loadTableDetails();

    expect(tableDetail).toHaveBeenCalledWith("http://api.test", "fund_nav", "oceanbase_data");
    expect(getSemanticModel).toHaveBeenCalledWith("http://api.test", "fund_nav", "oceanbase_data");
    expect(workbench.tableName.value).toBe("fund_nav");
    expect(workbench.tableDetail.value?.name).toBe("fund_nav");
    expect(workbench.semanticYaml.value).toBe("table: fund_nav");
  });

  it("ignores an older successful load after a newer table finishes", async () => {
    const firstDetail = deferred<{ table: { name: string } }>();
    const firstSemantic = deferred<{ yaml: string }>();
    tableDetail
      .mockImplementationOnce(() => firstDetail.promise)
      .mockResolvedValueOnce({ table: { name: "CURRENT_VIEW" } });
    getSemanticModel
      .mockImplementationOnce(() => firstSemantic.promise)
      .mockResolvedValueOnce({ yaml: "table: CURRENT_VIEW" });

    const { useSemanticWorkbench } = await import("./useSemanticWorkbench");
    const workbench = useSemanticWorkbench();
    const firstLoad = workbench.loadTableDetails("STALE_VIEW");
    const currentLoad = workbench.loadTableDetails("CURRENT_VIEW");

    await currentLoad;
    firstDetail.resolve({ table: { name: "STALE_VIEW" } });
    firstSemantic.resolve({ yaml: "table: STALE_VIEW" });
    await firstLoad;

    expect(workbench.tableName.value).toBe("CURRENT_VIEW");
    expect(workbench.tableDetail.value?.name).toBe("CURRENT_VIEW");
    expect(workbench.semanticYaml.value).toBe("table: CURRENT_VIEW");
    expect(workbench.loadingTable.value).toBe(false);
  });

  it("does not report an error from an older table load", async () => {
    const firstDetail = deferred<{ table: { name: string } }>();
    tableDetail
      .mockImplementationOnce(() => firstDetail.promise)
      .mockResolvedValueOnce({ table: { name: "CURRENT_VIEW" } });
    getSemanticModel
      .mockResolvedValueOnce({ yaml: "table: STALE_VIEW" })
      .mockResolvedValueOnce({ yaml: "table: CURRENT_VIEW" });

    const { useSemanticWorkbench } = await import("./useSemanticWorkbench");
    const workbench = useSemanticWorkbench();
    const firstLoad = workbench.loadTableDetails("STALE_VIEW");
    const currentLoad = workbench.loadTableDetails("CURRENT_VIEW");

    await currentLoad;
    firstDetail.reject(new Error("stale request failed"));
    await firstLoad;

    expect(workbench.tableName.value).toBe("CURRENT_VIEW");
    expect(workbench.tableDetail.value?.name).toBe("CURRENT_VIEW");
    expect(workbench.semanticYaml.value).toBe("table: CURRENT_VIEW");
    expect(toastError).not.toHaveBeenCalled();
    expect(workbench.loadingTable.value).toBe(false);
  });

  it("keeps semantic YAML when table structure loading fails", async () => {
    tableDetail.mockRejectedValueOnce(new Error("table detail failed"));

    const { useSemanticWorkbench } = await import("./useSemanticWorkbench");
    const workbench = useSemanticWorkbench();

    await workbench.loadTableDetails("fund_nav");

    expect(workbench.tableDetail.value).toBeNull();
    expect(workbench.semanticYaml.value).toBe("table: fund_nav");
    expect(toastError).toHaveBeenCalledWith("加载表结构失败");
  });

  it("keeps table structure when semantic model loading fails", async () => {
    getSemanticModel.mockRejectedValueOnce(new Error("semantic model failed"));

    const { useSemanticWorkbench } = await import("./useSemanticWorkbench");
    const workbench = useSemanticWorkbench();

    await workbench.loadTableDetails("fund_nav");

    expect(workbench.tableDetail.value?.name).toBe("fund_nav");
    expect(workbench.semanticYaml.value).toBe("");
    expect(toastError).toHaveBeenCalledWith("加载语义模型失败");
  });

  it("reports timeouts separately from other semantic model failures", async () => {
    getSemanticModel.mockRejectedValueOnce(new DOMException("Aborted", "AbortError"));

    const { useSemanticWorkbench } = await import("./useSemanticWorkbench");
    const workbench = useSemanticWorkbench();

    await workbench.loadTableDetails("fund_nav");

    expect(workbench.tableDetail.value?.name).toBe("fund_nav");
    expect(workbench.semanticYaml.value).toBe("");
    expect(toastError).toHaveBeenCalledWith("加载语义模型超时，请稍后重试");
  });

  it("combines failures when both table resources fail", async () => {
    tableDetail.mockRejectedValueOnce(new Error("table detail failed"));
    getSemanticModel.mockRejectedValueOnce(new Error("semantic model failed"));

    const { useSemanticWorkbench } = await import("./useSemanticWorkbench");
    const workbench = useSemanticWorkbench();

    await workbench.loadTableDetails("fund_nav");

    expect(workbench.tableDetail.value).toBeNull();
    expect(workbench.semanticYaml.value).toBe("");
    expect(toastError).toHaveBeenCalledTimes(1);
    expect(toastError).toHaveBeenCalledWith("加载表结构和语义模型失败");
  });

  it("leaves 401 feedback to the global authentication handler", async () => {
    const { HttpError } = await import("@/lib/request");
    tableDetail.mockRejectedValueOnce(new HttpError(401, "Unauthorized"));
    getSemanticModel.mockRejectedValueOnce(new HttpError(401, "Unauthorized"));

    const { useSemanticWorkbench } = await import("./useSemanticWorkbench");
    const workbench = useSemanticWorkbench();

    await workbench.loadTableDetails("fund_nav");

    expect(workbench.tableDetail.value).toBeNull();
    expect(workbench.semanticYaml.value).toBe("");
    expect(toastError).not.toHaveBeenCalled();
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
    let datasource = "oceanbase_data";
    const workbench = useSemanticWorkbench({ currentDatasource: () => datasource });
    workbench.tableName.value = "fund_nav";

    await workbench.loadTableDetails();
    workbench.semanticYaml.value = "table: fund_nav\ncolumns: []";
    await workbench.validateSemanticModel();
    await workbench.saveSemanticModel();

    expect(validateSemanticModel).toHaveBeenCalledWith(
      "http://api.test",
      "fund_nav",
      "table: fund_nav\ncolumns: []",
      "oceanbase_data",
    );
    datasource = "oracle_data";
    workbench.semanticYaml.value = "table: fund_nav\ncolumns: []";
    await workbench.validateSemanticModel();
    expect(validateSemanticModel).toHaveBeenLastCalledWith(
      "http://api.test",
      "fund_nav",
      "table: fund_nav\ncolumns: []",
      "oracle_data",
    );
    expect(saveSemanticModel).toHaveBeenCalledWith(
      "http://api.test",
      "fund_nav",
      "table: fund_nav\ncolumns: []",
      "oceanbase_data",
    );
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
    expect(tableDetail).toHaveBeenCalledWith("http://api.test", "fund_nav", undefined);
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
