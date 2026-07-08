import type { ConnectionState } from "@/types";

export const APP_WORKSPACE_TITLE = "智能问数助手";
export const FALLBACK_USER_LABEL = "未登录用户";
export const FALLBACK_USERNAME_LABEL = "未配置账号";

export const CONNECTION_LABELS: Record<ConnectionState, string> = {
  idle: "未检测",
  checking: "检测中…",
  online: "已连接",
  offline: "未连接",
};
