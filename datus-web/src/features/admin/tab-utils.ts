import type { AdminArtifact } from "@/types/admin"

export type EnabledStatusFilter = "all" | "enabled" | "disabled"
export type RoleTypeFilter = "all" | "built_in" | "custom"
export type GrantEffectFilter = "all" | "allow" | "deny"
export type SessionStateFilter = "all" | "running" | "stopped"
export type ArtifactTypeFilter = "all" | AdminArtifact["artifact_type"]

export function enabledFilterValue(filter: EnabledStatusFilter): boolean | undefined {
  if (filter === "enabled") return true
  if (filter === "disabled") return false
  return undefined
}

export function normalizedSearch(value: string): string | undefined {
  return value.trim() || undefined
}

export function searchKeyword(value: string): string {
  return value.trim().toLocaleLowerCase()
}

export function matchesKeyword(
  keyword: string,
  values: readonly (string | number | null | undefined)[],
): boolean {
  if (!keyword) return true
  return values
    .filter((value): value is string | number => value !== null && value !== undefined)
    .some((value) => String(value).toLocaleLowerCase().includes(keyword))
}

export function matchesEnabledStatus(filter: EnabledStatusFilter, enabled: boolean): boolean {
  if (filter === "enabled") return enabled
  if (filter === "disabled") return !enabled
  return true
}
