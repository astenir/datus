import type { DeveloperViewType } from "@/types";

export const DEVELOPER_VIEW_FEATURES: Record<DeveloperViewType, string> = {
  chat: "chat",
  knowledge: "admin",
  mcp: "admin",
  sql: "sql_generation",
  dashboard: "dashboard",
  report: "report",
};

export const PRIMARY_DEVELOPER_VIEWS: DeveloperViewType[] = [
  "chat",
  "report",
  "dashboard",
];
export const SETTINGS_TOOL_DEVELOPER_VIEWS: DeveloperViewType[] = [
  "sql",
  "knowledge",
  "mcp",
];

export const ROLE_FEATURE_OPTIONS = [
  { value: DEVELOPER_VIEW_FEATURES.chat, label: "对话" },
  { value: DEVELOPER_VIEW_FEATURES.sql, label: "SQL生成" },
  { value: DEVELOPER_VIEW_FEATURES.report, label: "报表" },
  { value: DEVELOPER_VIEW_FEATURES.dashboard, label: "仪表盘" },
  { value: DEVELOPER_VIEW_FEATURES.knowledge, label: "管理" },
];

export function developerViewFeature(view: DeveloperViewType): string {
  return DEVELOPER_VIEW_FEATURES[view];
}

export function normalizeFeaturePermissionCode(code: string): string {
  if (code === "sql") return DEVELOPER_VIEW_FEATURES.sql;
  if (code === "knowledge" || code === "mcp") return DEVELOPER_VIEW_FEATURES.knowledge;
  return code;
}
