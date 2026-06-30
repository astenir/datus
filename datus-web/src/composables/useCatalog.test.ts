import { afterEach, describe, expect, it, vi } from "vitest";

describe("useCatalog", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.resetModules();
  });

  it("loads datasource status cache and records prewarm as connecting", async () => {
    const status = vi.fn().mockResolvedValue({
      statuses: [{
        datasource_id: "fund",
        status: "unknown",
        last_checked: null,
        latency_ms: null,
        error_message: null,
        cached: true,
      }],
    });
    const prewarm = vi.fn().mockResolvedValue({
      datasource_id: "fund",
      status: "queued",
    });

    vi.doMock("@/lib/api", () => ({
      catalogApi: {
        list: vi.fn(),
        status,
        prewarm,
      },
    }));
    vi.doMock("@/composables/useConnection", () => ({
      useConnection: () => ({
        effectiveBase: () => "",
      }),
    }));
    vi.doMock("@/lib/utils", () => ({
      handleError: vi.fn(),
    }));

    const { useCatalog } = await import("./useCatalog");
    const catalog = useCatalog();

    await expect(catalog.loadDatasourceStatuses("fund")).resolves.toBe(true);
    expect(catalog.datasourceStatuses.value.fund.status).toBe("unknown");

    await expect(catalog.prewarmDatasource("fund")).resolves.toBe(true);
    expect(prewarm).toHaveBeenCalledWith("", "fund");
    expect(catalog.datasourceStatuses.value.fund.status).toBe("connecting");
  });

  it("preserves the last good catalog when a refresh fails", async () => {
    const list = vi.fn()
      .mockResolvedValueOnce({
        databases: [{ name: "fund", schema_name: "public", tables: [] }],
      })
      .mockRejectedValueOnce(new Error("timeout"));

    vi.doMock("@/lib/api", () => ({
      catalogApi: {
        list,
        status: vi.fn(),
        prewarm: vi.fn(),
      },
    }));
    vi.doMock("@/composables/useConnection", () => ({
      useConnection: () => ({
        effectiveBase: () => "",
      }),
    }));
    vi.doMock("@/lib/utils", () => ({
      handleError: vi.fn(),
    }));

    const { useCatalog } = await import("./useCatalog");
    const catalog = useCatalog();

    await expect(catalog.loadCatalog(undefined, "fund")).resolves.toBe(true);
    expect(catalog.catalogEntries.value).toEqual([{ name: "fund", schema_name: "public", tables: [] }]);
    expect(catalog.databaseOptions.value).toEqual([{ value: "fund", label: "fund" }]);

    await expect(catalog.loadCatalog(undefined, "fund")).resolves.toBe(false);
    expect(catalog.catalogEntries.value).toEqual([{ name: "fund", schema_name: "public", tables: [] }]);
    expect(catalog.databaseOptions.value).toEqual([{ value: "fund", label: "fund" }]);
  });

  it("keeps catalog snapshots and selections per datasource", async () => {
    const list = vi.fn()
      .mockResolvedValueOnce({
        databases: [{ name: "fund", schema_name: "public", tables: [] }],
      })
      .mockResolvedValueOnce({
        databases: [{ name: "demo", schema_name: "main", tables: [] }],
      });

    vi.doMock("@/lib/api", () => ({
      catalogApi: {
        list,
        status: vi.fn(),
        prewarm: vi.fn(),
      },
    }));
    vi.doMock("@/composables/useConnection", () => ({
      useConnection: () => ({
        effectiveBase: () => "",
      }),
    }));
    vi.doMock("@/lib/utils", () => ({
      handleError: vi.fn(),
    }));

    const { useCatalog } = await import("./useCatalog");
    const catalog = useCatalog();

    await catalog.loadCatalog(undefined, "fund");
    catalog.setDatabase("fund");
    catalog.setSchema("public");

    catalog.selectCatalogDatasource("demo");
    expect(catalog.catalogEntries.value).toEqual([{ name: "fund", schema_name: "public", tables: [] }]);
    expect(catalog.database.value).toBe("fund");

    await catalog.loadCatalog(undefined, "demo");
    expect(catalog.database.value).toBe("");
    catalog.setDatabase("demo");
    catalog.setSchema("main");

    catalog.selectCatalogDatasource("fund");
    expect(catalog.catalogEntries.value).toEqual([{ name: "fund", schema_name: "public", tables: [] }]);
    expect(catalog.database.value).toBe("fund");
    expect(catalog.schema.value).toBe("public");
  });
});
