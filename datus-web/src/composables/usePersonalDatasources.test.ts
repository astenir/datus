import { beforeEach, describe, expect, it, vi } from "vitest";

const datasourceProviders = vi.fn();
const personalDatasources = vi.fn();
const createPersonalDatasource = vi.fn();
const updatePersonalDatasource = vi.fn();
const deletePersonalDatasource = vi.fn();
const testPersonalDatasource = vi.fn();
const toastSuccess = vi.fn();
const toastError = vi.fn();

vi.mock("@/lib/api", () => ({
  meApi: {
    datasourceProviders,
    personalDatasources,
    createPersonalDatasource,
    updatePersonalDatasource,
    deletePersonalDatasource,
    testPersonalDatasource,
  },
}));

vi.mock("vue-sonner", () => ({
  toast: {
    success: toastSuccess,
    error: toastError,
  },
}));

describe("usePersonalDatasources", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    datasourceProviders.mockResolvedValue({
      success: true,
      data: {
        enabled: true,
        allowed_types: ["postgresql"],
        allowed_hosts: ["localhost"],
        default_ports: { postgresql: "5432" },
      },
    });
    personalDatasources.mockResolvedValue({
      success: true,
      data: [{
        id: "ds-1",
        datasource_key: "personal_ds-1",
        type: "postgresql",
        host: "localhost",
        port: "5432",
        username: "alice",
        password_hint: "***cret",
        database: "finance",
        enabled: true,
      }],
    });
    createPersonalDatasource.mockResolvedValue({ success: true, data: null });
    updatePersonalDatasource.mockResolvedValue({ success: true, data: null });
    deletePersonalDatasource.mockResolvedValue({ success: true, data: { deleted: true } });
    testPersonalDatasource.mockResolvedValue({ success: true, data: { ok: true } });
  });

  it("loads options and datasources without exposing raw passwords", async () => {
    const { usePersonalDatasources } = await import("./usePersonalDatasources");
    const manager = usePersonalDatasources();

    await manager.load();

    expect(manager.options.value.enabled).toBe(true);
    expect(manager.datasources.value[0].password_hint).toBe("***cret");
    expect(manager.form.value.type).toBe("postgresql");
    expect(manager.form.value.port).toBe("5432");
  });

  it("creates datasources through the me API and reloads state", async () => {
    const { usePersonalDatasources } = await import("./usePersonalDatasources");
    const manager = usePersonalDatasources();
    await manager.load();
    manager.form.value = {
      type: "postgresql",
      host: "localhost",
      port: "5432",
      username: "alice",
      password: "alice-db-secret",
      database: "finance",
      schema_name: "public",
      catalog_name: "",
      display_name: "个人分析库",
      enabled: true,
    };

    await manager.saveDatasource();

    expect(createPersonalDatasource).toHaveBeenCalledWith({
      type: "postgresql",
      host: "localhost",
      port: "5432",
      username: "alice",
      password: "alice-db-secret",
      database: "finance",
      schema_name: "public",
      catalog_name: null,
      display_name: "个人分析库",
      enabled: true,
    });
    expect(toastSuccess).toHaveBeenCalledWith("个人数据源已添加");
    expect(personalDatasources).toHaveBeenCalledTimes(2);
  });

  it("tests and deletes a personal datasource", async () => {
    const { usePersonalDatasources } = await import("./usePersonalDatasources");
    const manager = usePersonalDatasources();
    await manager.load();

    const probe = await manager.testDatasource("ds-1");
    await manager.deleteDatasource("ds-1");

    expect(probe).toEqual({ ok: true });
    expect(testPersonalDatasource).toHaveBeenCalledWith("ds-1");
    expect(deletePersonalDatasource).toHaveBeenCalledWith("ds-1");
  });
});
