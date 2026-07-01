import { computed, readonly, ref, shallowRef } from "vue";
import { modelsApi } from "@/lib/api";
import { handleError } from "@/lib/utils";
import { useConnection } from "./useConnection";
import type { ModelInfo, SelectOption } from "@/types";

const { effectiveBase } = useConnection();

const models = ref<ModelInfo[]>([]);
const modelOptions = ref<SelectOption[]>([]);
const currentModel = shallowRef("");
const isLoadingModels = shallowRef(false);

export function buildModelOption(model: ModelInfo): SelectOption {
  const id = model.provider === "custom" ? model.id : (model.model ?? model.id);
  const value = model.provider ? `${model.provider}/${id}` : id;
  return { value, label: model.name ?? id };
}

export function resolveModelDisplayName(value: string, options: readonly SelectOption[]) {
  if (!value) return "";
  return options.find((option) => option.value === value)?.label ?? value;
}

const defaultModelLabel = computed(() => resolveModelDisplayName(currentModel.value, modelOptions.value));

async function loadModels() {
  const base = effectiveBase();
  isLoadingModels.value = true;
  try {
    const result = await modelsApi.list(base);
    if (result) {
      models.value = result.models ?? [];
      modelOptions.value = models.value.map(buildModelOption);
      currentModel.value = result.current_model ?? "";
    }
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
