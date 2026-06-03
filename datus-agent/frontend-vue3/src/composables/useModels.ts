import { ref } from "vue";
import { modelsApi } from "@/lib/api";
import { useConnection } from "./useConnection";
import type { ModelInfo, SelectOption } from "@/types";

const models = ref<ModelInfo[]>([]);
const currentModel = ref("");
const modelOptions = ref<SelectOption[]>([]);

async function loadModels() {
  const { effectiveBase } = useConnection();
  const base = effectiveBase();
  try {
    const result = await modelsApi.list(base);
    if (result) {
      models.value = result.models ?? [];
      currentModel.value = result.current_model ?? "";
      modelOptions.value = models.value.map((m) => {
        const id = m.model ?? m.id;
        const value = m.provider ? `${m.provider}/${id}` : id;
        return { value, label: m.name ?? id };
      });
    }
  } catch {
    // silently fail
  }
}

export function useModels() {
  return {
    modelOptions,
    loadModels,
  };
}
