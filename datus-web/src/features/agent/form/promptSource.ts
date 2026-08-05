const PROMPT_SOURCE_LABELS: Readonly<Record<string, string>> = {
  builtin: "系统内置",
  builtin_fallback: "内置回退",
  enterprise: "企业自定义",
  runtime: "运行时配置",
  runtime_fallback: "运行时配置回退",
  user_override: "用户模板覆盖",
  user_override_fallback: "用户模板覆盖回退",
}

export function promptSourceLabel(source: string | null | undefined): string {
  const normalized = source?.trim()
  if (!normalized) return "-"
  return PROMPT_SOURCE_LABELS[normalized] ?? normalized
}
