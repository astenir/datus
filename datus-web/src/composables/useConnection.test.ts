import { afterEach, describe, expect, it, vi } from "vitest";

function installLocalStorage(value: string | null = null) {
  const storage = {
    getItem: vi.fn(() => value),
    setItem: vi.fn(),
  };
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: storage,
  });
  return storage;
}

describe("useConnection", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.resetModules();
    delete (globalThis as { localStorage?: unknown }).localStorage;
  });

  it("uses the injected chatbot origin when no local API base is configured", async () => {
    installLocalStorage("");
    vi.doMock("@/lib/injected-config", () => ({
      getInjectedApiOrigin: () => "https://embed.example.test/api/",
    }));

    const { useConnection } = await import("./useConnection");
    const { effectiveBase } = useConnection();

    expect(effectiveBase()).toBe("https://embed.example.test/api");
  });

  it("builds datasource options and tests the current datasource", async () => {
    installLocalStorage("");
    const getAgent = vi.fn().mockResolvedValue({
      current_datasource: "fund",
      datasources: {
        fund: {
          type: "postgres",
          host: "db.internal",
          account: "",
          extra: { sslmode: "require", timeout_seconds: 10 },
        },
        demo: { type: "sqlite", path: "/tmp/demo.db" },
      },
    });
    const testDatasource = vi.fn().mockResolvedValue({ ok: true, message: "SELECT 1 执行成功" });
    const switchDatasource = vi.fn();

    vi.doMock("@/lib/api", () => ({
      configApi: {
        getAgent,
        testDatasource,
        switchDatasource,
      },
    }));
    vi.doMock("@/lib/injected-config", () => ({
      getInjectedApiOrigin: () => "",
    }));

    const { useConnection } = await import("./useConnection");
    const connection = useConnection();

    await connection.checkConnection();
    const result = await connection.testDatasource();

    expect(connection.datasourceOptions.value).toEqual([
      { value: "fund", label: "fund" },
      { value: "demo", label: "demo" },
    ]);
    expect(result).toEqual({ ok: true, message: "SELECT 1 执行成功" });
    expect(testDatasource).toHaveBeenCalledWith("", {
      type: "postgres",
      host: "db.internal",
      sslmode: "require",
      timeout_seconds: 10,
    });
  });

  it("does not expose backend internal datasource test errors as status text", async () => {
    installLocalStorage("");
    const getAgent = vi.fn().mockResolvedValue({
      current_datasource: "fund",
      datasources: {
        fund: { type: "postgres", host: "db.internal" },
      },
    });
    const testDatasource = vi.fn().mockResolvedValue({
      ok: false,
      error: "dictionary update sequence element #0 has length 1; 2 is required",
    });
    const switchDatasource = vi.fn();

    vi.doMock("@/lib/api", () => ({
      configApi: {
        getAgent,
        testDatasource,
        switchDatasource,
      },
    }));
    vi.doMock("@/lib/injected-config", () => ({
      getInjectedApiOrigin: () => "",
    }));

    const { useConnection } = await import("./useConnection");
    const connection = useConnection();

    await connection.checkConnection();
    const result = await connection.testDatasource();

    expect(result).toEqual({ ok: false, message: "连接测试失败，请检查数据源配置" });
  });

  it("keeps readable datasource test failures from the backend", async () => {
    installLocalStorage("");
    const getAgent = vi.fn().mockResolvedValue({
      current_datasource: "fund",
      datasources: {
        fund: { type: "postgres", host: "db.internal" },
      },
    });
    const testDatasource = vi.fn().mockResolvedValue({
      ok: false,
      message: "password authentication failed",
    });
    const switchDatasource = vi.fn();

    vi.doMock("@/lib/api", () => ({
      configApi: {
        getAgent,
        testDatasource,
        switchDatasource,
      },
    }));
    vi.doMock("@/lib/injected-config", () => ({
      getInjectedApiOrigin: () => "",
    }));

    const { useConnection } = await import("./useConnection");
    const connection = useConnection();

    await connection.checkConnection();
    const result = await connection.testDatasource();

    expect(result).toEqual({ ok: false, message: "password authentication failed" });
  });

  it("switches datasource and refreshes the config summary", async () => {
    installLocalStorage("");
    const getAgent = vi.fn()
      .mockResolvedValueOnce({
        current_datasource: "fund",
        datasources: {
          fund: { type: "postgres" },
          demo: { type: "sqlite" },
        },
      })
      .mockResolvedValueOnce({
        current_datasource: "demo",
        datasources: {
          fund: { type: "postgres" },
          demo: { type: "sqlite" },
        },
      });
    const testDatasource = vi.fn();
    const switchDatasource = vi.fn().mockResolvedValue({ current_datasource: "demo" });

    vi.doMock("@/lib/api", () => ({
      configApi: {
        getAgent,
        testDatasource,
        switchDatasource,
      },
    }));
    vi.doMock("@/lib/injected-config", () => ({
      getInjectedApiOrigin: () => "",
    }));

    const { useConnection } = await import("./useConnection");
    const connection = useConnection();

    await connection.checkConnection();
    const changed = await connection.switchDatasource("demo");

    expect(changed).toBe(true);
    expect(switchDatasource).toHaveBeenCalledWith("", "demo");
    expect(getAgent).toHaveBeenCalledTimes(2);
    expect(connection.config.value?.current_datasource).toBe("demo");
  });
});
