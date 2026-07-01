import { beforeEach, describe, expect, it, vi } from "vitest";

const getAgent = vi.fn();
const updateModels = vi.fn();
const updateDatasources = vi.fn();
const testModel = vi.fn();
const testDatasource = vi.fn();
const listModels = vi.fn();
const checkConnection = vi.fn();
const toastError = vi.fn();
const toastSuccess = vi.fn();

vi.mock("@/lib/api", () => ({
  configApi: {
    getAgent,
    updateModels,
    updateDatasources,
    testModel,
    testDatasource,
  },
  modelsApi: {
    list: listModels,
  },
}));

vi.mock("@/composables/useConnection", () => ({
  useConnection: () => ({
    effectiveBase: () => "http://api.test",
    checkConnection,
  }),
}));

vi.mock("vue-sonner", () => ({
  toast: {
    error: toastError,
    success: toastSuccess,
  },
}));

const agentConfig = {
  target: "openai/gpt-4.1",
  current_datasource: "fund",
  home: "/tmp/datus",
  models: {
    local: { type: "openai", model: "local-model" },
  },
  datasources: {
    fund: {
      type: "postgres",
      host: "db.internal",
      account: "",
      extra: { sslmode: "require" },
    },
  },
};

describe("useConfigurationManager", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getAgent.mockResolvedValue(agentConfig);
    listModels.mockResolvedValue({
      models: [{ provider: "openai", id: "gpt-4.1", model: "gpt-4.1", name: "GPT 4.1" }],
      providers: ["openai"],
      current_model: "openai/gpt-4.1",
      source: "cache",
    });
    updateModels.mockResolvedValue({});
    updateDatasources.mockResolvedValue({});
    testModel.mockResolvedValue({ ok: true, message: "model ok" });
    testDatasource.mockResolvedValue({ ok: true, message: "datasource ok" });
  });

  it("loads agent config and hydrates editable forms", async () => {
    const { useConfigurationManager } = await import("./useConfigurationManager");
    const manager = useConfigurationManager();

    await manager.loadConfiguration();

    expect(getAgent).toHaveBeenCalledWith("http://api.test");
    expect(listModels).toHaveBeenCalledWith("http://api.test");
    expect(manager.forms.value.target).toBe("openai/gpt-4.1");
    expect(manager.modelProbe.value).toMatchObject({ type: "openai", model: "gpt-4.1" });
    expect(manager.selectedDatasourceName.value).toBe("fund");
    expect(JSON.parse(manager.forms.value.datasourceProbeText)).toEqual({
      type: "postgres",
      host: "db.internal",
      sslmode: "require",
    });
  });

  it("saves full model desired state and can clear the target", async () => {
    const { useConfigurationManager } = await import("./useConfigurationManager");
    const manager = useConfigurationManager();
    await manager.loadConfiguration();
    manager.forms.value.target = "";
    manager.forms.value.modelsText = "{\"local\":{\"type\":\"openai\",\"model\":\"local-model\"}}";

    await manager.saveModels();

    expect(updateModels).toHaveBeenCalledWith("http://api.test", {
      local: { type: "openai", model: "local-model" },
    }, null);
    expect(checkConnection).toHaveBeenCalled();
    expect(toastSuccess).toHaveBeenCalledWith("模型配置已保存");
  });

  it("rejects non-object model entries before saving", async () => {
    const { useConfigurationManager } = await import("./useConfigurationManager");
    const manager = useConfigurationManager();
    manager.forms.value.modelsText = "{\"bad\":true}";

    await manager.saveModels();

    expect(updateModels).not.toHaveBeenCalled();
    expect(toastError).toHaveBeenCalledWith("models.bad 必须是 JSON 对象");
  });

  it("saves full datasource desired state", async () => {
    const { useConfigurationManager } = await import("./useConfigurationManager");
    const manager = useConfigurationManager();
    manager.forms.value.datasourcesText = "{\"fund\":{\"type\":\"postgres\",\"host\":\"db.internal\"}}";

    await manager.saveDatasources();

    expect(updateDatasources).toHaveBeenCalledWith("http://api.test", {
      fund: { type: "postgres", host: "db.internal" },
    });
    expect(checkConnection).toHaveBeenCalled();
  });

  it("tests model and datasource probes through config endpoints", async () => {
    const { useConfigurationManager } = await import("./useConfigurationManager");
    const manager = useConfigurationManager();
    manager.modelProbe.value = {
      type: "openai",
      model: "gpt-4.1",
      api_key: "",
      base_url: "",
    };
    manager.forms.value.datasourceProbeText = "{\"type\":\"postgres\",\"host\":\"db.internal\"}";

    await manager.testModelProbe();
    await manager.testDatasourceProbe();

    expect(testModel).toHaveBeenCalledWith("http://api.test", {
      type: "openai",
      model: "gpt-4.1",
      api_key: null,
      base_url: null,
    });
    expect(testDatasource).toHaveBeenCalledWith("http://api.test", {
      type: "postgres",
      host: "db.internal",
    });
    expect(manager.modelProbeResult.value).toEqual({ ok: true, message: "model ok" });
    expect(manager.datasourceProbeResult.value).toEqual({ ok: true, message: "datasource ok" });
  });
});

describe("configurationManagerInternals", () => {
  it("flattens datasource extra fields for probe requests", async () => {
    const { configurationManagerInternals } = await import("./useConfigurationManager");

    expect(configurationManagerInternals.datasourceProbeFromConfig({
      type: "postgres",
      host: "db.internal",
      extra: { sslmode: "require" },
    })).toEqual({
      type: "postgres",
      host: "db.internal",
      sslmode: "require",
    });
  });
});
