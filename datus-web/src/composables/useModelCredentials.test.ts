import { beforeEach, describe, expect, it, vi } from "vitest";

const modelProviders = vi.fn();
const modelCredentials = vi.fn();
const modelPreference = vi.fn();
const createModelCredential = vi.fn();
const updateModelCredential = vi.fn();
const deleteModelCredential = vi.fn();
const testModelCredential = vi.fn();
const updateModelPreference = vi.fn();
const toastSuccess = vi.fn();
const toastError = vi.fn();

vi.mock("@/lib/api", () => ({
  meApi: {
    modelProviders,
    modelCredentials,
    modelPreference,
    createModelCredential,
    updateModelCredential,
    deleteModelCredential,
    testModelCredential,
    updateModelPreference,
  },
}));

vi.mock("vue-sonner", () => ({
  toast: {
    success: toastSuccess,
    error: toastError,
  },
}));

describe("useModelCredentials", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    modelProviders.mockResolvedValue({
      success: true,
      data: [{
        provider: "openai",
        label: "OpenAI",
        default_model: "gpt-4.1",
        models: ["gpt-4.1", "gpt-4.1-mini"],
        custom: false,
      }],
    });
    modelCredentials.mockResolvedValue({
      success: true,
      data: [{
        id: "cred-1",
        provider: "openai",
        model: "gpt-4.1",
        base_url: null,
        ref_hint: "***cret",
        display_name: "个人 OpenAI",
        enabled: true,
      }],
    });
    modelPreference.mockResolvedValue({
      success: true,
      data: {
        default_credential_id: "cred-1",
        default_model: "gpt-4.1",
      },
    });
    createModelCredential.mockResolvedValue({ success: true, data: null });
    updateModelCredential.mockResolvedValue({ success: true, data: null });
    deleteModelCredential.mockResolvedValue({ success: true, data: { deleted: true } });
    testModelCredential.mockResolvedValue({ success: true, data: { ok: true } });
    updateModelPreference.mockResolvedValue({
      success: true,
      data: {
        default_credential_id: "cred-1",
        default_model: "gpt-4.1",
      },
    });
  });

  it("loads providers, credentials, and preference without exposing raw keys", async () => {
    const { useModelCredentials } = await import("./useModelCredentials");
    const manager = useModelCredentials();

    await manager.load();

    expect(manager.providers.value[0].provider).toBe("openai");
    expect(manager.credentials.value[0].ref_hint).toBe("***cret");
    expect(manager.preference.value?.default_credential_id).toBe("cred-1");
    expect(manager.defaultCredential.value?.id).toBe("cred-1");
  });

  it("creates credentials through the me API and reloads state", async () => {
    const { useModelCredentials } = await import("./useModelCredentials");
    const manager = useModelCredentials();
    await manager.load();
    manager.form.value = {
      provider: "openai",
      model: "gpt-4.1",
      base_url: "",
      api_key: "sk-new-secret",
      display_name: "新的密钥",
      enabled: true,
    };

    await manager.saveCredential();

    expect(createModelCredential).toHaveBeenCalledWith({
      provider: "openai",
      model: "gpt-4.1",
      api_key: "sk-new-secret",
      base_url: null,
      display_name: "新的密钥",
      enabled: true,
    });
    expect(toastSuccess).toHaveBeenCalledWith("模型密钥已添加");
    expect(modelCredentials).toHaveBeenCalledTimes(2);
  });

  it("creates custom OpenAI-compatible credentials with a base URL", async () => {
    modelProviders.mockResolvedValueOnce({
      success: true,
      data: [{
        provider: "custom_openai_compatible",
        label: "自定义 OpenAI 兼容",
        default_model: "",
        models: [],
        custom: true,
        requires_base_url: true,
      }],
    });
    const { useModelCredentials, CUSTOM_OPENAI_COMPATIBLE_PROVIDER } = await import("./useModelCredentials");
    const manager = useModelCredentials();
    await manager.load();
    manager.form.value = {
      provider: CUSTOM_OPENAI_COMPATIBLE_PROVIDER,
      model: "Qwen3.5-397B",
      base_url: "https://models.corp/v1",
      api_key: "sk-local-secret",
      display_name: "自建模型",
      enabled: true,
    };

    await manager.saveCredential();

    expect(createModelCredential).toHaveBeenCalledWith({
      provider: "custom_openai_compatible",
      model: "Qwen3.5-397B",
      api_key: "sk-local-secret",
      base_url: "https://models.corp/v1",
      display_name: "自建模型",
      enabled: true,
    });
  });

  it("tests a credential and stores preference updates", async () => {
    const { useModelCredentials } = await import("./useModelCredentials");
    const manager = useModelCredentials();
    await manager.load();

    const probe = await manager.testCredential("cred-1");
    await manager.savePreference({
      default_credential_id: "cred-1",
      default_model: "gpt-4.1",
    });

    expect(probe).toEqual({ ok: true });
    expect(manager.testResults.value["cred-1"]).toEqual({
      ok: true,
      message: "连接正常",
    });
    expect(toastSuccess).toHaveBeenCalledWith("模型连接正常", {
      description: "个人 OpenAI",
    });
    expect(testModelCredential).toHaveBeenCalledWith("cred-1");
    expect(updateModelPreference).toHaveBeenCalledWith({
      default_credential_id: "cred-1",
      default_model: "gpt-4.1",
    });
  });

  it("keeps failed credential probe details for inline feedback", async () => {
    testModelCredential.mockResolvedValueOnce({
      success: true,
      data: { ok: false, message: "Invalid API key" },
    });
    const { useModelCredentials } = await import("./useModelCredentials");
    const manager = useModelCredentials();
    await manager.load();

    const probe = await manager.testCredential("cred-1");

    expect(probe).toEqual({ ok: false, message: "Invalid API key" });
    expect(manager.testResults.value["cred-1"]).toEqual({
      ok: false,
      message: "Invalid API key",
    });
    expect(toastError).toHaveBeenCalledWith("Invalid API key");
  });

  it("keeps request failures for inline feedback", async () => {
    testModelCredential.mockRejectedValueOnce(new Error("请求超时"));
    const { useModelCredentials } = await import("./useModelCredentials");
    const manager = useModelCredentials();
    await manager.load();

    const probe = await manager.testCredential("cred-1");

    expect(probe).toBeNull();
    expect(manager.testResults.value["cred-1"]).toEqual({
      ok: false,
      message: "请求超时",
    });
    expect(toastError).toHaveBeenCalledWith("请求超时");
  });
});
