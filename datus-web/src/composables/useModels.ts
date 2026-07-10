import { computed, readonly, ref, shallowRef } from "vue";
import { meApi, modelsApi } from "@/lib/api";
import { handleError } from "@/lib/utils";
import { useConnection } from "./useConnection";
import type { ModelInfo, SelectOption } from "@/types";
import type { ApiResponse, ModelCredentialSummary, ModelPreferenceSummary } from "@/types/profile";

const { effectiveBase } = useConnection();

const models = ref<ModelInfo[]>([]);
const modelOptions = ref<SelectOption[]>([]);
const currentModel = shallowRef("");
const personalCredentials = ref<ModelCredentialSummary[]>([]);
const personalPreference = shallowRef<ModelPreferenceSummary | null>(null);
const isLoadingModels = shallowRef(false);

const MODEL_CREDENTIAL_VALUE_PREFIX = "credential:";

export function buildModelOption(model: ModelInfo): SelectOption {
  const id = model.provider === "custom" ? model.id : (model.model ?? model.id);
  const value = model.provider ? `${model.provider}/${id}` : id;
  return { value, label: model.name ?? id };
}

export function buildPersonalModelOption(credential: ModelCredentialSummary): SelectOption {
  const name = credential.display_name?.trim() || credential.provider;
  return {
    value: `${MODEL_CREDENTIAL_VALUE_PREFIX}${credential.id}`,
    label: `${name} / ${credential.model}`,
    group: "我的模型",
  };
}

export function resolveModelDisplayName(value: string, options: readonly SelectOption[]) {
  if (!value) return "";
  return options.find((option) => option.value === value)?.label ?? value;
}

function resultData<T>(response: ApiResponse<T>, fallback: T): T {
  if (!response.success) {
    throw new Error(response.errorMessage || response.errorCode || "请求失败");
  }
  return response.data ?? fallback;
}

const defaultPersonalCredential = computed(() => {
  const enabled = personalCredentials.value.filter(item => item.enabled);
  const preferredId = personalPreference.value?.default_credential_id;
  return enabled.find(item => item.id === preferredId) ?? enabled[0] ?? null;
});
const defaultModelLabel = computed(() => {
  if (defaultPersonalCredential.value) {
    return `我的模型：${buildPersonalModelOption(defaultPersonalCredential.value).label}`;
  }
  return resolveModelDisplayName(currentModel.value, modelOptions.value);
});

async function loadModels() {
  const base = effectiveBase();
  isLoadingModels.value = true;
  try {
    const [catalogOutcome, credentialOutcome, preferenceOutcome] = await Promise.allSettled([
      modelsApi.list(base),
      meApi.modelCredentials(),
      meApi.modelPreference(),
    ]);
    if (catalogOutcome.status === "rejected") throw catalogOutcome.reason;
    const catalogResult = catalogOutcome.value;
    models.value = catalogResult?.models ?? [];
    personalCredentials.value = credentialOutcome.status === "fulfilled"
      ? resultData(credentialOutcome.value, [])
      : [];
    personalPreference.value = preferenceOutcome.status === "fulfilled"
      ? resultData<ModelPreferenceSummary | null>(preferenceOutcome.value, null)
      : null;
    modelOptions.value = [
      ...personalCredentials.value.filter(item => item.enabled).map(buildPersonalModelOption),
      ...models.value.map(buildModelOption),
    ];
    currentModel.value = catalogResult?.current_model ?? "";
  } catch (error) {
    handleError("加载模型列表失败", error);
  } finally {
    isLoadingModels.value = false;
  }
}

export function useModels() {
  return {
    modelOptions: readonly(modelOptions),
    defaultModelLabel,
    isLoadingModels: readonly(isLoadingModels),
    loadModels,
  };
}
