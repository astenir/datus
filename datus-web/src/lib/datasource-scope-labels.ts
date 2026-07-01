const maxInlineValues = 3;

const arrayScopeLabels: Record<string, string> = {
  catalogs: "Catalog",
  databases: "库",
  schemas: "Schema",
  tables: "表",
};

const ignoredScopeKeys = new Set([
  "effect",
  "enabled",
  "allow_catalog",
  "allow_sql",
  "allow_report",
  "allow_dashboard",
]);

export function formatDatasourceScope(scope: Record<string, unknown> | undefined): string {
  if (!scope || Object.keys(scope).length === 0) return "全量访问";

  const labels: string[] = [];

  for (const [key, label] of Object.entries(arrayScopeLabels)) {
    const values = stringArray(scope[key]);
    if (values.length > 0) {
      labels.push(`${label}: ${formatValueList(values)}`);
    }
  }

  if (labels.length > 0) return labels.join(" · ");

  const hasCustomKeys = Object.keys(scope).some((key) => !ignoredScopeKeys.has(key));
  return hasCustomKeys ? "自定义范围" : "全量访问";
}

function stringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string" && item.trim().length > 0);
}

function formatValueList(values: readonly string[]): string {
  if (values.includes("*")) return "全部";

  const visibleValues = values.slice(0, maxInlineValues);
  const suffix = values.length > maxInlineValues ? ` 等 ${values.length} 项` : "";
  return `${visibleValues.join("、")}${suffix}`;
}
