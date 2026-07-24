import { beforeEach, describe, expect, it, vi } from "vitest";

const getAgent = vi.fn();
const updateModels = vi.fn();
const updateDatasources = vi.fn();
const testModel = vi.fn();
const testSavedModel = vi.fn();
const testDatasource = vi.fn();
const testSavedDatasource = vi.fn();
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
    testSavedModel,
    testDatasource,
    testSavedDatasource,
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
  target: { custom: "local" },
  providers: {
    openai: { api_key: "********", base_url: "https://api.openai.com/v1", auth_type: "api_key" },
  },
  provider_options: [
    { value: "openai", label: "OpenAI", auth_type: "api_key", base_url: "https://api.openai.com/v1" },
  ],
  current_datasource: "fund",
  home: "/tmp/datus",
  models: {
    local: { type: "openai", model: "local-model" },
  },
  datasources: {
    fund: {
      type: "postgres",
      display_name: "分析库",
      host: "db.internal",
      password: "********",
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
    testSavedModel.mockResolvedValue({ ok: true, message: "saved model ok" });
    testDatasource.mockResolvedValue({ ok: true, message: "datasource ok" });
    testSavedDatasource.mockResolvedValue({ ok: true, message: "saved datasource ok" });
  });

  it("loads agent config and hydrates editable forms", async () => {
    const { useConfigurationManager } = await import("./useConfigurationManager");
    const manager = useConfigurationManager();

    await manager.loadConfiguration();

    expect(getAgent).toHaveBeenCalledWith("http://api.test");
    expect(listModels).toHaveBeenCalledWith("http://api.test");
    expect(manager.forms.value.target).toBe("custom/local");
    expect(manager.providerConfigs.value).toEqual(agentConfig.providers);
    expect(manager.selectedDatasourceName.value).toBe("fund");
    expect(JSON.parse(manager.forms.value.datasourceProbeText)).toEqual({
      type: "postgres",
      host: "db.internal",
      password: "",
      sslmode: "require",
    });
    expect(manager.datasourceProbeSecretFields.value).toEqual(["password"]);
  });

  it("saves full model desired state with a valid target", async () => {
    const { useConfigurationManager } = await import("./useConfigurationManager");
    const manager = useConfigurationManager();
    await manager.loadConfiguration();
    manager.replaceModelConfigs({ local: { type: "openai", model: "local-model" } });

    await manager.saveModels();

    expect(updateModels).toHaveBeenCalledWith("http://api.test", {
      models: {
        local: { type: "openai", model: "local-model" },
      },
      target: { custom: "local" },
    });
    expect(checkConnection).toHaveBeenCalled();
    expect(toastSuccess).toHaveBeenCalledWith("模型配置已保存");
  });

  it("saves the default model without replacing providers or custom models", async () => {
    const { useConfigurationManager } = await import("./useConfigurationManager");
    const manager = useConfigurationManager();
    await manager.loadConfiguration();
    manager.forms.value.target = "openai/gpt-4.1";

    await manager.saveTargetModel();

    expect(updateModels).toHaveBeenCalledWith("http://api.test", {
      target: { provider: "openai", model: "gpt-4.1" },
    });
    expect(toastSuccess).toHaveBeenCalledWith("默认模型已保存");
  });

  it("saves project provider credentials without replacing model configuration", async () => {
    const { useConfigurationManager } = await import("./useConfigurationManager");
    const manager = useConfigurationManager();
    await manager.loadConfiguration();
    manager.replaceProviderConfigs({
      openai: { api_key: "********", base_url: "https://api.openai.com/v1", auth_type: "api_key" },
      deepseek: { api_key: "new-key", base_url: "", auth_type: "api_key" },
    });

    await manager.saveProviders();

    expect(updateModels).toHaveBeenCalledWith("http://api.test", {
      providers: {
        openai: { api_key: "********", base_url: "https://api.openai.com/v1", auth_type: "api_key" },
        deepseek: { api_key: "new-key", base_url: "", auth_type: "api_key" },
      },
    });
    expect(checkConnection).toHaveBeenCalled();
    expect(toastSuccess).toHaveBeenCalledWith("Provider 凭据已保存");
  });

  it("rejects non-object model entries when applying advanced JSON", async () => {
    const { useConfigurationManager } = await import("./useConfigurationManager");
    const manager = useConfigurationManager();
    manager.forms.value.modelsText = "{\"bad\":true}";

    manager.applyModelsJson();

    expect(updateModels).not.toHaveBeenCalled();
    expect(toastError).toHaveBeenCalledWith("models.bad 必须是 JSON 对象");
  });

  it("selects the first remaining model when the target is removed", async () => {
    const { useConfigurationManager } = await import("./useConfigurationManager");
    const manager = useConfigurationManager();
    manager.forms.value.target = "custom/removed";

    manager.replaceModelConfigs({ local: { type: "openai", model: "local-model" } });

    expect(manager.forms.value.target).toBe("custom/local");
  });

  it("converts provider and custom target references to API payloads", async () => {
    const { configurationManagerInternals } = await import("./useConfigurationManager");

    expect(configurationManagerInternals.targetModelConfig("openrouter/openai/gpt-4o")).toEqual({
      provider: "openrouter",
      model: "openai/gpt-4o",
    });
    expect(configurationManagerInternals.targetModelConfig("custom/internal")).toEqual({ custom: "internal" });
    expect(configurationManagerInternals.targetModelRef({ provider: "deepseek", model: "deepseek-chat" })).toBe(
      "deepseek/deepseek-chat",
    );
  });

  it("saves full datasource desired state", async () => {
    const { useConfigurationManager } = await import("./useConfigurationManager");
    const manager = useConfigurationManager();
    manager.replaceDatasourceConfigs({ fund: { type: "postgres", host: "db.internal" } });

    await manager.saveDatasources();

    expect(updateDatasources).toHaveBeenCalledWith("http://api.test", {
      fund: { type: "postgres", host: "db.internal" },
    });
    expect(checkConnection).toHaveBeenCalled();
  });

  it("applies advanced JSON to the structured datasource state", async () => {
    const { useConfigurationManager } = await import("./useConfigurationManager");
    const manager = useConfigurationManager();
    manager.forms.value.datasourcesText = "{\"fund\":{\"type\":\"postgres\",\"display_name\":\"基金库\"}}";

    manager.applyDatasourcesJson();

    expect(manager.datasourceConfigs.value).toEqual({
      fund: { type: "postgres", display_name: "基金库" },
    });
    expect(toastSuccess).toHaveBeenCalledWith("数据源 JSON 已应用");
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

  it("does not expose failed probe details returned by providers", async () => {
    testModel.mockResolvedValueOnce({
      ok: false,
      message: "HTTP 401 from https://models.private/v1",
    });
    const { useConfigurationManager } = await import("./useConfigurationManager");
    const manager = useConfigurationManager();
    manager.modelProbe.value = {
      type: "openai",
      model: "gpt-4.1",
      api_key: "",
      base_url: "",
    };

    await manager.testModelProbe();

    expect(manager.modelProbeResult.value).toEqual({
      ok: false,
      message: "连接测试失败，请检查配置",
    });
    expect(JSON.stringify(manager.modelProbeResult.value)).not.toContain("models.private");
  });

  it("tests saved provider and custom model references without browser credentials", async () => {
    const { useConfigurationManager } = await import("./useConfigurationManager");
    const manager = useConfigurationManager();

    await manager.testProviderConfig("openai", "gpt-4.1");
    await manager.testCustomModel("local");

    expect(testSavedModel).toHaveBeenNthCalledWith(1, "http://api.test", {
      provider: "openai",
      model: "gpt-4.1",
    });
    expect(testSavedModel).toHaveBeenNthCalledWith(2, "http://api.test", { custom: "local" });
    expect(manager.savedModelProbeResults.value).toEqual({
      "provider:openai": { ok: true, message: "saved model ok" },
      "custom:local": { ok: true, message: "saved model ok" },
    });
  });

  it("tests a saved datasource reference without browser credentials", async () => {
    const { useConfigurationManager } = await import("./useConfigurationManager");
    const manager = useConfigurationManager();

    await manager.testSavedDatasource("fund");

    expect(testSavedDatasource).toHaveBeenCalledWith("http://api.test", "fund");
    expect(manager.savedDatasourceProbeResults.value).toEqual({
      fund: { ok: true, message: "saved datasource ok" },
    });
  });

  it("requires real secret values before testing a probe generated from redacted config", async () => {
    const { useConfigurationManager } = await import("./useConfigurationManager");
    const manager = useConfigurationManager();
    await manager.loadConfiguration();

    await manager.testDatasourceProbe();

    expect(testDatasource).not.toHaveBeenCalled();
    expect(manager.datasourceProbeResult.value).toEqual({
      ok: false,
      message: "请先填写真实密钥字段：password",
    });

    manager.forms.value.datasourceProbeText = JSON.stringify({
      type: "postgres",
      host: "db.internal",
      password: "real-secret",
      sslmode: "require",
    });

    await manager.testDatasourceProbe();

    expect(testDatasource).toHaveBeenCalledWith("http://api.test", {
      type: "postgres",
      host: "db.internal",
      password: "real-secret",
      sslmode: "require",
    });
  });

  it("blocks datasource probes that still contain redacted secrets", async () => {
    const { useConfigurationManager } = await import("./useConfigurationManager");
    const manager = useConfigurationManager();
    manager.forms.value.datasourceProbeText = "{\"type\":\"postgres\",\"host\":\"db.internal\",\"password\":\"********\"}";

    await manager.testDatasourceProbe();

    expect(testDatasource).not.toHaveBeenCalled();
    expect(manager.datasourceProbeResult.value).toEqual({
      ok: false,
      message: "请先填写真实密钥字段，不能使用脱敏值：password",
    });
    expect(toastError).toHaveBeenCalledWith("请先填写真实密钥字段，不能使用脱敏值：password");
  });
});

describe("configurationManagerInternals", () => {
  it("flattens datasource extra fields for probe requests", async () => {
    const { configurationManagerInternals } = await import("./useConfigurationManager");

    expect(configurationManagerInternals.datasourceProbeFromConfig({
      type: "postgres",
      host: "db.internal",
      password: "********",
      extra: { sslmode: "require" },
    })).toEqual({
      type: "postgres",
      host: "db.internal",
      password: "",
      sslmode: "require",
    });
  });

  it("detects redacted nested secret fields", async () => {
    const { configurationManagerInternals } = await import("./useConfigurationManager");

    expect(configurationManagerInternals.maskedProbeSecretFields({
      type: "postgres",
      extra: { client_secret: "********" },
    })).toEqual(["extra.client_secret"]);
  });

  it("maps redacted extra secret fields to flattened probe fields", async () => {
    const { configurationManagerInternals } = await import("./useConfigurationManager");

    expect(configurationManagerInternals.redactedDatasourceProbeFieldsFromConfig({
      type: "postgres",
      extra: { client_secret: "********" },
    })).toEqual(["client_secret"]);
  });
});
