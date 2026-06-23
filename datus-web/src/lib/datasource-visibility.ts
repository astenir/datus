export type DatasourceVisibilityOptions = {
  isAdmin: boolean;
  allowedDatasourceNames?: readonly string[] | null;
};

export function canAccessDatasource(name: string, options: DatasourceVisibilityOptions): boolean {
  const datasourceName = name.trim();
  if (!datasourceName) return false;
  if (options.isAdmin) return true;
  return new Set(options.allowedDatasourceNames ?? []).has(datasourceName);
}

export function visibleDatasourceEntries<T>(
  datasources: Record<string, T> | null | undefined,
  options: DatasourceVisibilityOptions
): [string, T][] {
  if (!datasources) return [];
  return Object.entries(datasources).filter(([name]) => canAccessDatasource(name, options));
}
