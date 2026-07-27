const adminDateTimeFormatter = new Intl.DateTimeFormat("zh-CN", {
  timeZone: "Asia/Shanghai",
  hour12: false,
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
})

export function formatAdminDateTime(value: string | null | undefined): string {
  const text = value?.trim()
  if (!text) return "-"

  const isoValue = text.replace(/^(\d{4}-\d{2}-\d{2})\s/, "$1T")
  const dateValue = /(?:Z|[+-]\d{2}:?\d{2})$/.test(isoValue) ? isoValue : `${isoValue}Z`
  const date = new Date(dateValue)
  if (Number.isNaN(date.getTime())) return "-"

  return adminDateTimeFormatter.format(date)
}
