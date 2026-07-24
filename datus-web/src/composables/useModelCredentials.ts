import { computed, ref, shallowRef } from "vue";
import { toast } from "vue-sonner";

import { meApi } from "@/lib/api";
import { useModels } from "@/composables/useModels";
import type {
  ApiResponse,
  ModelCredentialSummary,
  ModelPreferenceSummary,
  ModelProbeResult,
  ModelProviderOption,
  UpdateModelPreferenceInput,
  UpsertModelCredentialInput,
} from "@/types/profile";

export interface ModelCredentialForm {
  provider: string;
  model: string;
  base_url: string;
  api_key: string;
  display_name: string;
  enabled: boolean;
}

export interface ModelCredentialTestState {
  ok: boolean;
  message: string;
}

export const CUSTOM_OPENAI_COMPATIBLE_PROVIDER = "custom_openai_compatible";
const MODEL_CONNECTION_FAILURE = "模型连接失败，请检查配置、凭据和网络后重试";

function resultData<T>(response: ApiResponse<T>, fallback: T): T {
  if (!response.success) {
    throw new Error(response.errorMessage || response.errorCode || "请求失败");
  }
  return response.data ?? fallback;
}

function defaultForm(provider = "", model = ""): ModelCredentialForm {
  return {
    provider,
    model,
    base_url: "",
    api_key: "",
    display_name: "",
    enabled: true,
  };
}

export function useModelCredentials() {
  const { loadModels } = useModels();
  const loading = shallowRef(false);
  const saving = shallowRef(false);
  const testingId = shallowRef<string | null>(null);
  const testResults = ref<Record<string, ModelCredentialTestState>>({});
  const error = shallowRef<string | null>(null);
  const providers = ref<ModelProviderOption[]>([]);
  const credentials = ref<ModelCredentialSummary[]>([]);
  const preference = ref<ModelPreferenceSummary | null>(null);
  const form = ref<ModelCredentialForm>(defaultForm());

  const enabledCredentials = computed(() => credentials.value.filter(item => item.enabled));
  const selectedProvider = computed(() => providers.value.find(item => item.provider === form.value.provider) ?? null);
  const catalogProviders = computed(() => providers.value.filter(item => item.custom !== true));
  const customProvider = computed(() => providers.value.find(item => item.custom === true) ?? null);
  const isCustomModel = computed(() =>
    form.value.provider === CUSTOM_OPENAI_COMPATIBLE_PROVIDER ||
    selectedProvider.value?.custom === true ||
    Boolean(form.value.base_url.trim()),
  );
  const modelOptions = computed(() => selectedProvider.value?.models ?? []);
  const defaultCredential = computed(() => {
    const id = preference.value?.default_credential_id;
    return credentials.value.find(item => item.id === id) ?? null;
  });
  const hasCredentials = computed(() => credentials.value.length > 0);

  async function load() {
    loading.value = true;
    error.value = null;
    try {
      const [providerResult, credentialResult, preferenceResult] = await Promise.all([
        meApi.modelProviders(),
        meApi.modelCredentials(),
        meApi.modelPreference(),
      ]);
      providers.value = resultData(providerResult, []);
      credentials.value = resultData(credentialResult, []);
      preference.value = resultData<ModelPreferenceSummary | null>(preferenceResult, null);
      ensureFormDefaults();
    } catch (err) {
      console.error("加载模型密钥失败:", err);
      error.value = "加载模型密钥失败";
      toast.error("加载模型密钥失败");
    } finally {
      loading.value = false;
    }
  }

  function startCreate() {
    const provider = catalogProviders.value[0] ?? customProvider.value ?? providers.value[0];
    form.value = defaultForm(provider?.provider ?? "", provider?.default_model ?? "");
  }

  function startEdit(credential: ModelCredentialSummary) {
    const provider = credential.base_url ? CUSTOM_OPENAI_COMPATIBLE_PROVIDER : credential.provider;
    form.value = {
      provider,
      model: credential.model,
      base_url: credential.base_url ?? "",
      api_key: "",
      display_name: credential.display_name ?? "",
      enabled: credential.enabled,
    };
  }

  async function saveCredential(id?: string) {
    saving.value = true;
    error.value = null;
    try {
      const payload = credentialPayload();
      const result = id
        ? await meApi.updateModelCredential(id, payload)
        : await meApi.createModelCredential(payload);
      resultData(result, null);
      toast.success(id ? "模型密钥已更新" : "模型密钥已添加");
      await load();
      await loadModels();
    } catch (err) {
      console.error("保存模型密钥失败:", err);
      error.value = "保存模型密钥失败";
      toast.error("保存模型密钥失败");
      throw err;
    } finally {
      saving.value = false;
    }
  }

  async function deleteCredential(id: string) {
    saving.value = true;
    error.value = null;
    try {
      await meApi.deleteModelCredential(id);
      toast.success("模型密钥已删除");
      await load();
      await loadModels();
    } catch (err) {
      console.error("删除模型密钥失败:", err);
      error.value = "删除模型密钥失败";
      toast.error("删除模型密钥失败");
    } finally {
      saving.value = false;
    }
  }

  async function testCredential(id: string): Promise<ModelProbeResult | null> {
    testingId.value = id;
    const credential = credentials.value.find(item => item.id === id);
    try {
      const result = resultData(await meApi.testModelCredential(id), { ok: false, message: "测试失败" });
      const message = result.ok ? "连接正常" : MODEL_CONNECTION_FAILURE;
      testResults.value = {
        ...testResults.value,
        [id]: { ok: result.ok, message },
      };
      if (result.ok) {
        toast.success("模型连接正常", {
          description: credential?.display_name || credential?.model,
        });
      } else {
        toast.error(message);
      }
      return result.ok ? result : { ...result, message };
    } catch (err) {
      console.error("测试模型密钥失败:", err);
      testResults.value = {
        ...testResults.value,
        [id]: { ok: false, message: MODEL_CONNECTION_FAILURE },
      };
      toast.error(MODEL_CONNECTION_FAILURE);
      return null;
    } finally {
      testingId.value = null;
    }
  }

  async function savePreference(input: UpdateModelPreferenceInput) {
    saving.value = true;
    error.value = null;
    try {
      const result = await meApi.updateModelPreference(input);
      preference.value = resultData<ModelPreferenceSummary | null>(result, null);
      toast.success("默认模型已更新");
      await loadModels();
    } catch (err) {
      console.error("保存默认模型失败:", err);
      error.value = "保存默认模型失败";
      toast.error("保存默认模型失败");
    } finally {
      saving.value = false;
    }
  }

  function ensureFormDefaults() {
    if (form.value.provider && form.value.model) return;
    const provider = providers.value[0];
    if (!provider) return;
    form.value = defaultForm(provider.provider, provider.default_model);
  }

  function credentialPayload(): UpsertModelCredentialInput {
    return {
      provider: form.value.provider,
      model: form.value.model,
      api_key: form.value.api_key,
      base_url: form.value.base_url.trim() || null,
      display_name: form.value.display_name || null,
      enabled: form.value.enabled,
    };
  }

  return {
    loading,
    saving,
    testingId,
    testResults,
    error,
    providers,
    credentials,
    preference,
    form,
    enabledCredentials,
    selectedProvider,
    catalogProviders,
    customProvider,
    isCustomModel,
    modelOptions,
    defaultCredential,
    hasCredentials,
    load,
    startCreate,
    startEdit,
    saveCredential,
    deleteCredential,
    testCredential,
    savePreference,
  };
}
