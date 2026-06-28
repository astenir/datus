import { computed, ref, shallowRef } from "vue";
import { toast } from "vue-sonner";

import { adminAuditApi } from "@/lib/api";
import type { AuditActionType, AuditLog, AuditLogExportFile, AuditLogSearchForm } from "@/types/admin";
import type { AdminAuditRouteState } from "@/features/workspace/route-state";

const defaultSearchForm = (): AuditLogSearchForm => ({
  user_id: "",
  action: "",
  resource_type: "",
  resource_id: "",
  decision: "",
});

function trimFilter(value: string): string | undefined {
  const trimmed = value.trim();
  return trimmed || undefined;
}

function downloadCsv(file: AuditLogExportFile): boolean {
  if (
    typeof document === "undefined"
    || typeof URL === "undefined"
    || typeof URL.createObjectURL !== "function"
  ) {
    return false;
  }

  const blob = new Blob([file.content], { type: file.contentType || "text/csv;charset=utf-8" });
  const href = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = href;
  anchor.download = file.filename || "audit-logs.csv";
  anchor.rel = "noopener";
  anchor.click();
  URL.revokeObjectURL(href);
  return true;
}

export function useAuditLogs() {
  const searchForm = ref<AuditLogSearchForm>(defaultSearchForm());

  const limit = shallowRef(50);
  const total = shallowRef(0);
  const logs = ref<AuditLog[]>([]);
  const loading = shallowRef(false);
  const exporting = shallowRef(false);
  const actionTypes = ref<AuditActionType[]>([]);
  const showDetail = shallowRef(false);
  const selectedLog = shallowRef<AuditLog | null>(null);

  const operatorCount = computed(() => new Set(logs.value.map((log) => log.user_id).filter(Boolean)).size);
  const targetCount = computed(() => new Set(logs.value.map((log) => log.resource_id).filter(Boolean)).size);
  const activeFilterCount = computed(() => Object.values(searchForm.value).filter((value) => value.trim()).length);
  const hasActiveFilters = computed(() => activeFilterCount.value > 0);
  const actionFilterValue = computed({
    get: () => searchForm.value.action || "__all__",
    set: (value: string) => {
      searchForm.value.action = value === "__all__" ? "" : value;
    },
  });
  const decisionFilterValue = computed({
    get: () => searchForm.value.decision || "__all__",
    set: (value: string) => {
      searchForm.value.decision = value === "__all__" ? "" : value;
    },
  });
  const limitValue = computed({
    get: () => String(limit.value),
    set: (value: string) => {
      const nextLimit = Number(value);
      if ([50, 100, 200, 500].includes(nextLimit)) {
        limit.value = nextLimit;
      }
    },
  });

  function currentParams() {
    return {
      limit: limit.value,
      userId: trimFilter(searchForm.value.user_id),
      action: trimFilter(searchForm.value.action),
      resourceType: trimFilter(searchForm.value.resource_type),
      resourceId: trimFilter(searchForm.value.resource_id),
      decision: trimFilter(searchForm.value.decision),
    };
  }

  function loadActionTypes() {
    actionTypes.value = [];
  }

  function applyRouteFilters(filters: AdminAuditRouteState): boolean {
    const nextForm: AuditLogSearchForm = {
      user_id: filters.userId ?? "",
      action: filters.action ?? "",
      resource_type: filters.resourceType ?? "",
      resource_id: filters.resourceId ?? "",
      decision: filters.decision ?? "",
    };
    const nextLimit = filters.limit;
    const changed = searchForm.value.user_id !== nextForm.user_id
      || searchForm.value.action !== nextForm.action
      || searchForm.value.resource_type !== nextForm.resource_type
      || searchForm.value.resource_id !== nextForm.resource_id
      || searchForm.value.decision !== nextForm.decision
      || limit.value !== nextLimit;

    if (changed) {
      searchForm.value = nextForm;
      limit.value = nextLimit;
    }

    return changed;
  }

  async function loadLogs() {
    loading.value = true;
    try {
      const result = await adminAuditApi.listLogs(currentParams());
      logs.value = result?.data ?? [];
      total.value = logs.value.length;
    } catch (err) {
      console.error("加载日志列表失败:", err);
      logs.value = [];
      total.value = 0;
      toast.error("加载审计日志失败");
    } finally {
      loading.value = false;
    }
  }

  function handleSearch() {
    void loadLogs();
  }

  function handleReset() {
    searchForm.value = defaultSearchForm();
    void loadLogs();
  }

  async function exportLogs() {
    exporting.value = true;
    try {
      const file = await adminAuditApi.exportLogs(currentParams());
      if (!downloadCsv(file)) {
        toast.error("当前环境不支持下载审计日志");
        return;
      }
      toast.success("审计日志已导出");
    } catch (err) {
      console.error("导出审计日志失败:", err);
      toast.error("导出审计日志失败");
    } finally {
      exporting.value = false;
    }
  }

  function viewDetail(log: AuditLog) {
    selectedLog.value = log;
    showDetail.value = true;
  }

  function getActionText(action: string) {
    const found = actionTypes.value.find((type) => type.value === action);
    return found?.label || action;
  }

  function getActionVariant(action: string): "default" | "secondary" | "destructive" | "outline" {
    if (action.includes("create") || action.includes("allow")) return "default";
    if (action.includes("delete") || action.includes("deny")) return "destructive";
    if (action.includes("update") || action.includes("assign") || action.includes("set")) return "default";
    return "secondary";
  }

  function formatLogKey(log: AuditLog, index: number) {
    return `${log.request_id ?? "request"}:${log.user_id ?? "system"}:${log.action}:${log.resource_type}:${log.resource_id ?? index}`;
  }

  return {
    searchForm,
    limit,
    total,
    logs,
    loading,
    exporting,
    actionTypes,
    showDetail,
    selectedLog,
    operatorCount,
    targetCount,
    activeFilterCount,
    hasActiveFilters,
    actionFilterValue,
    decisionFilterValue,
    limitValue,
    loadActionTypes,
    applyRouteFilters,
    loadLogs,
    handleSearch,
    handleReset,
    exportLogs,
    viewDetail,
    getActionText,
    getActionVariant,
    formatLogKey,
  };
}
