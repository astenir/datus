import type { ConnectionState } from "@/types";

export const CONNECTION_LABELS: Record<ConnectionState, string> = {
  idle: "未检测",
  checking: "检测中…",
  online: "已连接",
  offline: "未连接",
};
