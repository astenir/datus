import type { SelectOption } from "@/types"

export const WILDCARD_DATASOURCE_GRANT = "*"

export function mergeSelectOptions(...groups: readonly SelectOption[][]): SelectOption[] {
  const seen = new Set<string>();
  const options: SelectOption[] = [];
  for (const group of groups) {
    for (const option of group) {
      if (!option.value || seen.has(option.value)) continue;
      seen.add(option.value);
      options.push(option);
    }
  }
  return options;
}

export function datasourceGrantAllowsCatalog(grant: unknown): boolean {
  if (grant === true) return true;
  if (!isRecord(grant)) return false;
  const effect = typeof grant.effect === "string" ? grant.effect.trim().toLowerCase() : "allow";
  return effect === "allow" && grant.allow_catalog !== false;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
