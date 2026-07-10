import type { SelectOption } from "@/types";
import type { AdminDatasource } from "@/types/admin";

export function datasourceDisplayName(config: Record<string, unknown> | undefined): string {
  const value = config?.display_name;
  return typeof value === "string" ? value.trim() : "";
}

export function datasourceLabel(name: string, config?: Record<string, unknown>): string {
  const displayName = datasourceDisplayName(config);
  return displayName ? `${displayName} (${name})` : name;
}

export function adminDatasourceLabel(datasource: AdminDatasource): string {
  const displayName = datasource.display_name?.trim();
  return displayName ? `${displayName} (${datasource.name})` : datasource.name;
}

export function selectedOptionLabel(value: string, options: readonly SelectOption[]): string {
  if (!value) return "";
  return options.find((option) => option.value === value)?.label ?? value;
}
