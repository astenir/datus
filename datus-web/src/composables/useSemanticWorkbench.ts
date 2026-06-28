import { computed, readonly, ref, shallowRef } from "vue";
import { toast } from "vue-sonner";

import { useConnection } from "@/composables/useConnection";
import { tableApi } from "@/lib/api";
import type { SemanticModelValidation, TableDetail } from "@/types";

function firstTableNameFromCatalogEntry(entry: Record<string, unknown>): string {
  const tables = Array.isArray(entry.tables) ? entry.tables : [];
  const first = tables[0];

  if (typeof first === "string") return first;
  if (typeof first === "object" && first !== null && "name" in first) {
    const name = (first as { name?: unknown }).name;
    return typeof name === "string" ? name : "";
  }

  return "";
}

export function useSemanticWorkbench() {
  const connection = useConnection();

  const loadingTable = shallowRef(false);
  const validating = shallowRef(false);
  const savingSemantic = shallowRef(false);
  const tableName = shallowRef("");
  const tableDetail = ref<TableDetail | null>(null);
  const semanticYaml = shallowRef("");
  const validation = ref<SemanticModelValidation | null>(null);

  const semanticInvalidMessages = computed(() => validation.value?.invalid_message ?? []);
  const canLoadTable = computed(() => tableName.value.trim().length > 0);

  async function loadTableDetails(name = tableName.value) {
    const target = name.trim();
    if (!target) {
      toast.error("请输入表名");
      return;
    }

    tableName.value = target;
    loadingTable.value = true;
    validation.value = null;
    try {
      const [detail, semantic] = await Promise.all([
        tableApi.detail(connection.effectiveBase(), target),
        tableApi.getSemanticModel(connection.effectiveBase(), target),
      ]);
      tableDetail.value = detail?.table ?? null;
      semanticYaml.value = semantic?.yaml ?? "";
    } catch (error) {
      console.error("加载语义模型失败:", error);
      toast.error("加载语义模型失败");
    } finally {
      loadingTable.value = false;
    }
  }

  async function validateSemanticModel() {
    const target = tableName.value.trim();
    if (!target) {
      toast.error("请先加载表");
      return;
    }

    validating.value = true;
    try {
      validation.value = await tableApi.validateSemanticModel(connection.effectiveBase(), target, semanticYaml.value);
      toast.success(validation.value?.valid ? "语义模型校验通过" : "语义模型校验未通过");
    } catch (error) {
      console.error("校验语义模型失败:", error);
      toast.error("校验语义模型失败");
    } finally {
      validating.value = false;
    }
  }

  async function saveSemanticModel() {
    const target = tableName.value.trim();
    if (!target) {
      toast.error("请先加载表");
      return;
    }

    savingSemantic.value = true;
    try {
      await tableApi.saveSemanticModel(connection.effectiveBase(), target, semanticYaml.value);
      toast.success("语义模型已保存");
      await loadTableDetails(target);
    } catch (error) {
      console.error("保存语义模型失败:", error);
      toast.error("保存语义模型失败");
    } finally {
      savingSemantic.value = false;
    }
  }

  function useCatalogTable(entry: Record<string, unknown>) {
    const name = firstTableNameFromCatalogEntry(entry);
    if (!name) {
      toast.error("该目录项没有可加载的表");
      return null;
    }
    void loadTableDetails(name);
    return name;
  }

  return {
    loadingTable: readonly(loadingTable),
    validating: readonly(validating),
    savingSemantic: readonly(savingSemantic),
    tableName,
    tableDetail: readonly(tableDetail),
    semanticYaml,
    validation: readonly(validation),
    semanticInvalidMessages,
    canLoadTable,
    loadTableDetails,
    validateSemanticModel,
    saveSemanticModel,
    useCatalogTable,
  };
}

export const semanticWorkbenchInternals = {
  firstTableNameFromCatalogEntry,
};
