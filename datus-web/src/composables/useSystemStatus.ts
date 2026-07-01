import { computed, readonly, ref, shallowRef } from "vue";
import { toast } from "vue-sonner";

import { useConnection } from "@/composables/useConnection";
import { systemApi } from "@/lib/api";
import type { SystemStatusSummary } from "@/types";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function optionalString(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed || null;
}

function safeCount(value: unknown): number {
  if (typeof value !== "number" || !Number.isFinite(value)) return 0;
  return Math.max(0, Math.trunc(value));
}

export function normalizeSystemStatus(value: unknown): SystemStatusSummary | null {
  if (!isRecord(value)) return null;

  return {
    platform_status: optionalString(value.platform_status) ?? "unknown",
    enterprise_enabled: typeof value.enterprise_enabled === "boolean" ? value.enterprise_enabled : false,
    project_id: optionalString(value.project_id),
    current_datasource: optionalString(value.current_datasource),
    active_tasks: safeCount(value.active_tasks),
    known_tasks: safeCount(value.known_tasks),
  };
}

export function useSystemStatus() {
  const connection = useConnection();

  const loading = shallowRef(false);
  const error = shallowRef<string | null>(null);
  const status = ref<SystemStatusSummary | null>(null);

  const hasActiveTasks = computed(() => (status.value?.active_tasks ?? 0) > 0);
  const taskSummary = computed(() => {
    const active = status.value?.active_tasks ?? 0;
    const known = status.value?.known_tasks ?? 0;
    return `${active} / ${known}`;
  });

  async function loadStatus() {
    loading.value = true;
    error.value = null;
    try {
      const result = await systemApi.status(connection.effectiveBase());
      status.value = normalizeSystemStatus(result);
    } catch (err) {
      console.error("读取系统状态失败:", err);
      error.value = "读取系统状态失败";
      toast.error("读取系统状态失败");
    } finally {
      loading.value = false;
    }
  }

  return {
    loading: readonly(loading),
    error: readonly(error),
    status: readonly(status),
    hasActiveTasks,
    taskSummary,
    loadStatus,
  };
}
