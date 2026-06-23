import { computed, ref, shallowRef } from "vue";

import { adminAuditApi } from "@/lib/api";
import type { AuditActionType, AuditLog, AuditLogSearchForm } from "@/types/admin";

export function useAuditLogs() {
  const searchForm = ref<AuditLogSearchForm>({
    start_date: "",
    end_date: "",
    action: "",
  });

  const page = shallowRef(1);
  const size = shallowRef(20);
  const total = shallowRef(0);
  const logs = ref<AuditLog[]>([]);
  const loading = shallowRef(false);
  const actionTypes = ref<AuditActionType[]>([]);
  const showDetail = shallowRef(false);
  const selectedLog = shallowRef<AuditLog | null>(null);

  const totalPages = computed(() => Math.ceil(total.value / size.value) || 1);
  const operatorCount = computed(() => new Set(logs.value.map((log) => log.operator_id).filter(Boolean)).size);
  const targetCount = computed(() => new Set(logs.value.map((log) => log.target_id).filter(Boolean)).size);
  const actionFilterValue = computed({
    get: () => searchForm.value.action || "__all__",
    set: (value: string) => {
      searchForm.value.action = value === "__all__" ? "" : value;
    },
  });

  async function loadActionTypes() {
    try {
      const result = await adminAuditApi.listActionTypes();
      actionTypes.value = result?.data || [];
    } catch (err) {
      console.error("加载操作类型失败:", err);
      actionTypes.value = [];
    }
  }

  async function loadLogs() {
    loading.value = true;
    try {
      const result = await adminAuditApi.listLogs({
        page: page.value,
        size: size.value,
        startDate: searchForm.value.start_date,
        endDate: searchForm.value.end_date,
        action: searchForm.value.action,
      });
      logs.value = result?.data?.logs || [];
      total.value = result?.data?.total || 0;
    } catch (err) {
      console.error("加载日志列表失败:", err);
      logs.value = [];
    } finally {
      loading.value = false;
    }
  }

  function handleSearch() {
    page.value = 1;
    loadLogs();
  }

  function handleReset() {
    searchForm.value = { start_date: "", end_date: "", action: "" };
    page.value = 1;
    loadLogs();
  }

  function goToPage(nextPage: number) {
    if (nextPage < 1 || nextPage > totalPages.value) return;
    page.value = nextPage;
    loadLogs();
  }

  function viewDetail(log: AuditLog) {
    selectedLog.value = log;
    showDetail.value = true;
  }

  function getActionText(action: string) {
    const found = actionTypes.value.find((type) => type.value === action);
    return found?.label || action;
  }

  function getActionVariant(action: string): "default" | "secondary" | "destructive" | "outline" | "success" {
    if (action.includes("create")) return "success";
    if (action.includes("delete")) return "destructive";
    if (action.includes("update") || action.includes("assign")) return "default";
    return "secondary";
  }

  function formatDateTime(dateStr: string) {
    // 如果时间字符串不包含时区信息，假定后端返回的是 UTC 时间
    // 添加 Z 后缀让 JavaScript 正确解析为 UTC 时间
    const normalizedDateStr = dateStr.endsWith("Z") ? dateStr : `${dateStr}Z`;
    return new Date(normalizedDateStr).toLocaleString("zh-CN", {
      hour12: false,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  }

  return {
    searchForm,
    page,
    size,
    total,
    logs,
    loading,
    actionTypes,
    showDetail,
    selectedLog,
    totalPages,
    operatorCount,
    targetCount,
    actionFilterValue,
    loadActionTypes,
    loadLogs,
    handleSearch,
    handleReset,
    goToPage,
    viewDetail,
    getActionText,
    getActionVariant,
    formatDateTime,
  };
}
