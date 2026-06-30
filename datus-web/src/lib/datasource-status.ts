import type { DatasourceConnectionStatus, DatasourceStatusItem } from "@/types";

export function datasourceStatusLabel(status?: DatasourceConnectionStatus): string {
  switch (status) {
    case "connecting":
      return "连接中";
    case "connected":
      return "已连接";
    case "failed":
      return "连接失败";
    case "timeout":
      return "连接超时";
    default:
      return "未知";
  }
}

export function datasourceStatusToneClass(status?: DatasourceConnectionStatus): string {
  switch (status) {
    case "connecting":
      return "border-blue-500/30 bg-blue-500/10 text-blue-700 dark:text-blue-300";
    case "connected":
      return "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300";
    case "failed":
      return "border-destructive/30 bg-destructive/10 text-destructive";
    case "timeout":
      return "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300";
    default:
      return "bg-muted text-muted-foreground";
  }
}

export function datasourceStatusDescription(status: DatasourceStatusItem | null | undefined): string {
  if (!status) return "状态未知，尚未获取到后端状态缓存";
  if (status.error_message) return status.error_message;
  if (typeof status.latency_ms === "number") {
    return `${datasourceStatusLabel(status.status)}，延迟 ${Math.round(status.latency_ms)} ms`;
  }
  if (status.last_checked) return `${datasourceStatusLabel(status.status)}，最后检查 ${status.last_checked}`;
  return datasourceStatusLabel(status.status);
}
