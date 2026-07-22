import { computed, readonly, ref, shallowRef } from "vue";
import { toast } from "vue-sonner";

import { useConnection } from "@/composables/useConnection";
import { tableApi } from "@/lib/api";
import { HttpError } from "@/lib/request";
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

interface SemanticWorkbenchOptions {
  currentDatasource?: () => string | null | undefined;
}

type TableLoadResource = "表结构" | "语义模型";

interface TableLoadFailure {
  resource: TableLoadResource;
  error: unknown;
}

function isAuthenticationFailure(error: unknown): boolean {
  return error instanceof HttpError && error.status === 401;
}

function isRequestTimeout(error: unknown): boolean {
  if (error instanceof Error) return error.name === "AbortError";
  if (typeof error !== "object" || error === null || !("name" in error)) return false;
  return (error as { name?: unknown }).name === "AbortError";
}

function tableLoadFailureMessage(failures: readonly TableLoadFailure[]): string | null {
  const visibleFailures = failures.filter(({ error }) => !isAuthenticationFailure(error));
  if (visibleFailures.length === 0) return null;

  if (visibleFailures.length > 1) {
    return visibleFailures.every(({ error }) => isRequestTimeout(error))
      ? "加载表结构和语义模型超时，请稍后重试"
      : "加载表结构和语义模型失败";
  }

  const [failure] = visibleFailures;
  if (!failure) return null;
  return isRequestTimeout(failure.error)
    ? `加载${failure.resource}超时，请稍后重试`
    : `加载${failure.resource}失败`;
}

export function useSemanticWorkbench(options: SemanticWorkbenchOptions = {}) {
  const connection = useConnection();

  const loadingTable = shallowRef(false);
  const validating = shallowRef(false);
  const savingSemantic = shallowRef(false);
  const tableName = shallowRef("");
  const tableDetail = ref<TableDetail | null>(null);
  const semanticYaml = shallowRef("");
  const validation = ref<SemanticModelValidation | null>(null);
  let tableLoadRequestId = 0;

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
    const requestId = ++tableLoadRequestId;
    const datasourceId = options.currentDatasource?.()?.trim() || undefined;
    try {
      const [detailResult, semanticResult] = await Promise.allSettled([
        tableApi.detail(connection.effectiveBase(), target, datasourceId),
        tableApi.getSemanticModel(connection.effectiveBase(), target, datasourceId),
      ]);
      if (requestId !== tableLoadRequestId) return;

      const failures: TableLoadFailure[] = [];
      if (detailResult.status === "fulfilled") {
        tableDetail.value = detailResult.value?.table ?? null;
      } else {
        tableDetail.value = null;
        failures.push({ resource: "表结构", error: detailResult.reason });
        console.error(`加载表结构失败 (${datasourceId ?? "default"}:${target}):`, detailResult.reason);
      }

      if (semanticResult.status === "fulfilled") {
        semanticYaml.value = semanticResult.value?.yaml ?? "";
      } else {
        semanticYaml.value = "";
        failures.push({ resource: "语义模型", error: semanticResult.reason });
        console.error(`加载语义模型失败 (${datasourceId ?? "default"}:${target}):`, semanticResult.reason);
      }

      const failureMessage = tableLoadFailureMessage(failures);
      if (failureMessage) toast.error(failureMessage);
    } finally {
      if (requestId === tableLoadRequestId) {
        loadingTable.value = false;
      }
    }
  }

  async function validateSemanticModel() {
    const target = tableName.value.trim();
    if (!target) {
      toast.error("请先加载表");
      return;
    }

    validating.value = true;
    const datasourceId = options.currentDatasource?.()?.trim() || undefined;
    try {
      validation.value = await tableApi.validateSemanticModel(
        connection.effectiveBase(),
        target,
        semanticYaml.value,
        datasourceId,
      );
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
    const datasourceId = options.currentDatasource?.()?.trim() || undefined;
    try {
      await tableApi.saveSemanticModel(connection.effectiveBase(), target, semanticYaml.value, datasourceId);
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
