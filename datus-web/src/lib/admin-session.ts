const SESSION_STATUS_LABELS: Readonly<Record<string, string>> = {
  running: "运行中",
  completed: "已完成",
  error: "执行失败",
  cancelled: "已取消",
  persisted: "仅保留记录",
}

const SESSION_STATUS_DESCRIPTIONS: Readonly<Record<string, string>> = {
  running: "当前 API 进程中正在运行。",
  completed: "当前 API 进程的断线恢复窗口内已完成。",
  error: "当前 API 进程的断线恢复窗口内执行失败。",
  cancelled: "当前 API 进程的断线恢复窗口内已取消。",
  persisted: "所有者索引仍存在，但当前 API 进程已无运行态快照。",
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
