export interface QuotaResourceOption {
  value: string;
  label: string;
  description: string;
}

export const quotaResourceOptions = [
  {
    value: "chat.stream",
    label: "普通对话",
    description: "限制普通聊天流请求次数。",
  },
  {
    value: "chat.feedback",
    label: "反馈对话",
    description: "限制反馈 agent 请求次数。",
  },
  {
    value: "sql.execute",
    label: "SQL 执行",
    description: "限制直接 SQL 执行次数。",
  },
  {
    value: "dashboard.query",
    label: "仪表盘查询",
    description: "限制仪表盘实时查询次数。",
  },
  {
    value: "admin.audit.export",
    label: "审计导出",
    description: "限制审计日志 CSV 导出次数。",
  },
] as const satisfies readonly QuotaResourceOption[];

export function quotaResourceOptionFor(value: string): QuotaResourceOption | null {
  return quotaResourceOptions.find((option) => option.value === value) ?? null;
}
