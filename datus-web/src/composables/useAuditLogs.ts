import { computed, ref, shallowRef } from "vue";
import { toast } from "vue-sonner";

import { adminAuditApi } from "@/lib/api";
import { defaultAuditLogLimit, isAuditLogLimitOption } from "@/lib/audit-log-pagination";
import type {
  AuditActionType,
  AuditLog,
  AuditLogExportFile,
  AuditLogListResponse,
  AuditLogPage,
  AuditLogSearchForm,
} from "@/types/admin";
import type { AdminAuditRouteState } from "@/features/workspace/route-state";

const defaultSearchForm = (): AuditLogSearchForm => ({
  user_id: "",
  action: "",
  resource_type: "",
  resource_id: "",
  decision: "",
  request_id: "",
  created_after: "",
  created_before: "",
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

  const limit = shallowRef<number>(defaultAuditLogLimit);
  const beforeId = shallowRef<number | null>(null);
  const previousBeforeIds = ref<Array<number | null>>([]);
  const nextBeforeId = shallowRef<number | null>(null);
  const hasMore = shallowRef(false);
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
  const currentPage = computed(() => previousBeforeIds.value.length + 1);
  const hasPreviousPage = computed(() => previousBeforeIds.value.length > 0);
  const lastLogId = computed(() => {
    const lastLog = logs.value[logs.value.length - 1];
    return lastLog?.id ?? null;
  });
  const nextPageBeforeId = computed(() => nextBeforeId.value ?? lastLogId.value);
  const hasNextPage = computed(() => hasMore.value && nextPageBeforeId.value != null);
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
      if (isAuditLogLimitOption(nextLimit)) {
        limit.value = nextLimit;
        resetPagination();
      }
    },
  });

  function currentParams() {
    return {
      limit: limit.value,
      beforeId: beforeId.value ?? undefined,
      userId: trimFilter(searchForm.value.user_id),
      action: trimFilter(searchForm.value.action),
      resourceType: trimFilter(searchForm.value.resource_type),
      resourceId: trimFilter(searchForm.value.resource_id),
      decision: trimFilter(searchForm.value.decision),
      requestId: trimFilter(searchForm.value.request_id),
      createdAfter: trimFilter(searchForm.value.created_after),
      createdBefore: trimFilter(searchForm.value.created_before),
    };
  }

  function loadActionTypes() {
    actionTypes.value = [];
  }

  function normalizePage(data: AuditLogListResponse | null | undefined): AuditLogPage {
    if (Array.isArray(data)) {
      const lastEntry = data[data.length - 1];
      const inferredNextBeforeId = lastEntry?.id ?? null;
      const inferredHasMore = data.length >= limit.value && inferredNextBeforeId != null;
      return {
        entries: data,
        limit: limit.value,
        before_id: beforeId.value,
        next_before_id: inferredHasMore ? inferredNextBeforeId : null,
        has_more: inferredHasMore,
      };
    }

    return {
      entries: data?.entries ?? [],
      limit: data?.limit ?? limit.value,
      before_id: data?.before_id ?? beforeId.value,
      next_before_id: data?.next_before_id ?? null,
      has_more: data?.has_more ?? false,
    };
  }

  function resetPagination() {
    beforeId.value = null;
    previousBeforeIds.value = [];
    nextBeforeId.value = null;
    hasMore.value = false;
  }

  function applyRouteFilters(filters: AdminAuditRouteState): boolean {
    const nextForm: AuditLogSearchForm = {
      user_id: filters.userId ?? "",
      action: filters.action ?? "",
      resource_type: filters.resourceType ?? "",
      resource_id: filters.resourceId ?? "",
      decision: filters.decision ?? "",
      request_id: filters.requestId ?? "",
      created_after: filters.createdAfter ?? "",
      created_before: filters.createdBefore ?? "",
    };
    const nextLimit = filters.limit;
    const nextBeforeId = filters.beforeId;
    const changed = searchForm.value.user_id !== nextForm.user_id
      || searchForm.value.action !== nextForm.action
      || searchForm.value.resource_type !== nextForm.resource_type
      || searchForm.value.resource_id !== nextForm.resource_id
      || searchForm.value.decision !== nextForm.decision
      || searchForm.value.request_id !== nextForm.request_id
      || searchForm.value.created_after !== nextForm.created_after
      || searchForm.value.created_before !== nextForm.created_before
      || limit.value !== nextLimit
      || beforeId.value !== nextBeforeId;

    const filtersChanged = searchForm.value.user_id !== nextForm.user_id
      || searchForm.value.action !== nextForm.action
      || searchForm.value.resource_type !== nextForm.resource_type
      || searchForm.value.resource_id !== nextForm.resource_id
      || searchForm.value.decision !== nextForm.decision
      || searchForm.value.request_id !== nextForm.request_id
      || searchForm.value.created_after !== nextForm.created_after
      || searchForm.value.created_before !== nextForm.created_before
      || limit.value !== nextLimit;

    if (changed) {
      searchForm.value = nextForm;
      limit.value = nextLimit;
      beforeId.value = nextBeforeId;
      if (filtersChanged) {
        previousBeforeIds.value = [];
      }
    }

    return changed;
  }

  async function loadLogs() {
    loading.value = true;
    try {
      const result = await adminAuditApi.listLogs(currentParams());
      const page = normalizePage(result?.data);
      logs.value = page.entries;
      total.value = logs.value.length;
      beforeId.value = page.before_id ?? null;
      nextBeforeId.value = page.next_before_id ?? null;
      hasMore.value = page.has_more;
    } catch (err) {
      console.error("加载日志列表失败:", err);
      logs.value = [];
      total.value = 0;
      nextBeforeId.value = null;
      hasMore.value = false;
      toast.error("加载审计日志失败");
    } finally {
      loading.value = false;
    }
  }

  function handleSearch() {
    resetPagination();
    void loadLogs();
  }

  function handleReset() {
    searchForm.value = defaultSearchForm();
    resetPagination();
    void loadLogs();
  }

  function prepareNextPage(): number | null {
    if (!hasNextPage.value) return null;
    previousBeforeIds.value = [...previousBeforeIds.value, beforeId.value];
    return nextPageBeforeId.value;
  }

  function preparePreviousPage(): number | null {
    if (!hasPreviousPage.value) return null;
    const previousIds = [...previousBeforeIds.value];
    const previous = previousIds.pop() ?? null;
    previousBeforeIds.value = previousIds;
    return previous;
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
    if (log.id != null) return `audit-log:${log.id}`;
    return `${log.request_id ?? "request"}:${log.user_id ?? "system"}:${log.action}:${log.resource_type}:${log.resource_id ?? index}`;
  }

  return {
    searchForm,
    limit,
    beforeId,
    nextBeforeId,
    hasMore,
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
    currentPage,
    hasPreviousPage,
    hasNextPage,
    actionFilterValue,
    decisionFilterValue,
    limitValue,
    loadActionTypes,
    applyRouteFilters,
    loadLogs,
    handleSearch,
    handleReset,
    resetPagination,
    prepareNextPage,
    preparePreviousPage,
    exportLogs,
    viewDetail,
    getActionText,
    getActionVariant,
    formatLogKey,
  };
}
