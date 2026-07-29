const SESSION_STATUS_LABELS: Readonly<Record<string, string>> = {
  running: "运行中",
  completed: "已完成",
  error: "执行失败",
  cancelled: "已取消",
  persisted: "已保存会话记录",
}

const SESSION_STATUS_DESCRIPTIONS: Readonly<Record<string, string>> = {
  running: "当前任务正在运行。",
  completed: "任务已完成。",
  error: "任务执行失败。",
  cancelled: "任务已取消。",
  persisted: "会话记录已保存，可继续查看。",
}

export function adminSessionStatusLabel(status: string): string {
  const normalized = status.trim().toLowerCase()
  return SESSION_STATUS_LABELS[normalized] ?? status
}

export function adminSessionStatusDescription(status: string): string {
  const normalized = status.trim().toLowerCase()
  return SESSION_STATUS_DESCRIPTIONS[normalized] ?? "后端返回的会话运行状态。"
}

export function adminSessionBodyStateLabel(exists: boolean | null | undefined): string {
  if (exists === true) return "存在"
  if (exists === false) return "缺失"
  return "无法确认"
}

export function adminSessionRuntimeValueLabel(
  snapshotAvailable: boolean,
  value: string | number | null | undefined,
): string {
  if (!snapshotAvailable) return "—"
  if (value === null || value === undefined || value === "") return "—"
  return String(value)
}
