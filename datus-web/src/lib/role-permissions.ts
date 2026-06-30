import { normalizeFeaturePermissionCode } from "@/lib/navigation";
import type { CatalogDatabase, RolePermissionRecord } from "@/types/admin";

export type RoleDatasourceTreeNode = {
  id: string;
  label: string;
  children?: RoleDatasourceTreeNode[];
};

type DatasourceGrant = {
  unrestricted: boolean;
  databases: Set<string>;
  schemas: Set<string>;
  tables: Set<string>;
};

export type DatasourceGrantScope = {
  databases?: string[];
  schemas?: string[];
  tables?: string[];
};

export function buildDatasourceTreeOptions(catalogDatabases: readonly CatalogDatabase[]): RoleDatasourceTreeNode[] {
  const datasourceMap = new Map<string, CatalogDatabase[]>();
  for (const db of catalogDatabases) {
    if (!datasourceMap.has(db.datasourceName)) {
      datasourceMap.set(db.datasourceName, []);
    }
    datasourceMap.get(db.datasourceName)!.push(db);
  }

  const result: RoleDatasourceTreeNode[] = [];
  datasourceMap.forEach((dbs, datasourceName) => {
    const datasourceNode: RoleDatasourceTreeNode = {
      id: `ds:${datasourceName}`,
      label: datasourceName,
      children: [],
    };

    const dbNameMap = new Map<string, CatalogDatabase[]>();
    for (const db of dbs) {
      if (!dbNameMap.has(db.name)) {
        dbNameMap.set(db.name, []);
      }
      dbNameMap.get(db.name)!.push(db);
    }

    dbNameMap.forEach((schemas, dbName) => {
      const dbNode: RoleDatasourceTreeNode = {
        id: `db:${datasourceName}:${dbName}`,
        label: dbName,
        children: [],
      };

      const schemaSet = new Set(schemas.map((schema) => schema.schemaName).filter(Boolean));
      if (schemaSet.size > 0) {
        const schemaMap = new Map<string, CatalogDatabase[]>();
        for (const schema of schemas) {
          const schemaName = schema.schemaName || "default";
          if (!schemaMap.has(schemaName)) {
            schemaMap.set(schemaName, []);
          }
          schemaMap.get(schemaName)!.push(schema);
        }

        schemaMap.forEach((tables, schemaName) => {
          const schemaNode: RoleDatasourceTreeNode = {
            id: `schema:${datasourceName}:${dbName}:${schemaName}`,
            label: schemaName,
            children: tables.flatMap((tableGroup) =>
              (tableGroup.tables || []).map((tableName) => ({
                id: `table:${datasourceName}:${tableGroup.name}:${schemaName}:${tableName}`,
                label: tableName,
              }))
            ),
          };
          dbNode.children!.push(schemaNode);
        });
      } else {
        const tables = schemas.flatMap((schema) =>
          (schema.tables || []).map((tableName) => ({
            id: `table:${datasourceName}:${schema.name}:${schema.schemaName || ""}:${tableName}`,
            label: tableName,
          }))
        );
        dbNode.children = tables.length > 0 ? tables : undefined;
      }

      datasourceNode.children!.push(dbNode);
    });

    result.push(datasourceNode);
  });

  return result;
}

export function featurePermissionCodes(permissions: readonly RolePermissionRecord[]): string[] {
  return Array.from(new Set(
    permissions
      .filter((permission) => permission.permission_type === "feature" && permission.permission_value === "allow")
      .map((permission) => normalizeFeaturePermissionCode(permission.resource_code))
  ));
}

export function datasourceNodeIdsFromPermissions(
  permissions: readonly RolePermissionRecord[],
  catalogDatabases: readonly CatalogDatabase[]
): string[] {
  const nodeIds: string[] = [];
  for (const permission of permissions.filter((item) => item.permission_type === "datasource")) {
    try {
      const value = JSON.parse(permission.permission_value || "{}") as {
        databases?: string[];
        schemas?: string[];
        tables?: string[];
      };
      const datasourceName = permission.resource_code;
      const databases = value.databases || [];
      const schemas = value.schemas || [];
      const tables = value.tables || [];

      for (const db of databases) {
        nodeIds.push(`db:${datasourceName}:${db}`);
      }
      for (const schema of schemas) {
        const { databaseName, schemaName } = parseGrantSchema(schema);
        const dbName = databaseName || findCatalogDbName(catalogDatabases, datasourceName, schemaName) || "";
        nodeIds.push(`schema:${datasourceName}:${dbName}:${schemaName}`);
      }
      for (const table of tables) {
        const { databaseName, schemaName, tableName } = parseGrantTable(table);
        const dbName = databaseName || findCatalogDbName(catalogDatabases, datasourceName, schemaName, tableName) || "";
        if (tableName) {
          nodeIds.push(`table:${datasourceName}:${dbName}:${schemaName}:${tableName}`);
        }
      }
    } catch {
      nodeIds.push(permission.resource_code);
    }
  }
  return nodeIds;
}

export function isStandardDatasourceGrantScope(scope: Record<string, unknown> | undefined): boolean {
  if (!scope || Object.keys(scope).length === 0) return true;

  return Object.entries(scope).every(([key, value]) =>
    (key === "databases" || key === "schemas" || key === "tables")
    && (value === undefined || isStringArray(value))
  );
}

export function datasourceNodeIdsFromScope(
  datasourceName: string,
  scope: Record<string, unknown> | undefined,
  catalogDatabases: readonly CatalogDatabase[]
): string[] {
  if (!scope || Object.keys(scope).length === 0) {
    return [`ds:${datasourceName}`];
  }

  const normalizedScope = normalizeDatasourceGrantScope(scope);
  return datasourceNodeIdsFromPermissions(
    [{
      permission_type: "datasource",
      resource_code: datasourceName,
      permission_value: JSON.stringify(normalizedScope),
    }],
    catalogDatabases,
  );
}

export function rolePermissionsFromSelections(
  roleType: string,
  selectedFeatures: readonly string[],
  selectedDatasourceNodes: readonly string[]
): RolePermissionRecord[] {
  if (roleType === "resource") {
    return selectedFeatures.map((feature) => ({
      permission_type: "feature",
      resource_code: feature,
      permission_value: "allow",
    }));
  }

  const grants = new Map<string, DatasourceGrant>();

  for (const nodeId of selectedDatasourceNodes) {
    const parts = nodeId.split(":");
    const kind = parts[0];
    const datasourceName = parts[1];
    if (!datasourceName) continue;

    const grant = ensureDatasourceGrant(grants, datasourceName);

    if (kind === "db") {
      const databaseName = parts[2];
      if (databaseName) grant.databases.add(databaseName);
    } else if (kind === "schema") {
      const databaseName = parts[2];
      const schemaName = parts[3];
      if (schemaName) grant.schemas.add(formatGrantSchema(databaseName, schemaName));
    } else if (kind === "table") {
      const databaseName = parts[2];
      const schemaName = parts[3];
      const tableName = parts[4];
      if (tableName) grant.tables.add(formatGrantTable(databaseName, schemaName, tableName));
    }
  }

  // 再处理数据源节点
  for (const nodeId of selectedDatasourceNodes) {
    const parts = nodeId.split(":");
    const kind = parts[0];
    const datasourceName = parts[1];
    if (!datasourceName) continue;

    const grant = grants.get(datasourceName);
    if (!grant) continue;

    if (kind === "ds") {
      // 只有当没有任何子节点时，才设置 unrestricted
      const hasChildren = grant.databases.size > 0 || grant.schemas.size > 0 || grant.tables.size > 0;
      if (!hasChildren) {
        grant.unrestricted = true;
      }
    }
  }

  const permissions: RolePermissionRecord[] = [];
  for (const [datasourceName, grant] of grants) {
    pruneBroaderDatasourceGrants(grant);
    const databases = grant.unrestricted ? [] : Array.from(grant.databases);
    const schemas = grant.unrestricted ? [] : Array.from(grant.schemas);
    const tables = grant.unrestricted ? [] : Array.from(grant.tables);
    if (grant.unrestricted || databases.length > 0 || schemas.length > 0 || tables.length > 0) {
      permissions.push({
        permission_type: "datasource",
        resource_code: datasourceName,
        permission_value: JSON.stringify({ databases, schemas, tables }),
      });
    }
  }
  return permissions;
}

export function datasourceScopeFromNodeIds(
  datasourceName: string,
  selectedDatasourceNodes: readonly string[]
): Record<string, unknown> {
  const permission = rolePermissionsFromSelections("datasource", [], selectedDatasourceNodes)
    .find((item) => item.resource_code === datasourceName);
  if (!permission) return {};

  const scope = parseDatasourceGrantScope(permission.permission_value);
  const hasSpecificScope =
    (scope.databases?.length ?? 0) > 0
    || (scope.schemas?.length ?? 0) > 0
    || (scope.tables?.length ?? 0) > 0;
  return hasSpecificScope ? scope : {};
}

function pruneBroaderDatasourceGrants(grant: DatasourceGrant) {
  for (const table of grant.tables) {
    const { databaseName, schemaName } = parseGrantTable(table);
    if (databaseName) grant.databases.delete(databaseName);
    if (schemaName) grant.schemas.delete(formatGrantSchema(databaseName, schemaName));
  }

  for (const schema of grant.schemas) {
    const { databaseName } = parseGrantSchema(schema);
    if (databaseName) grant.databases.delete(databaseName);
  }
}

export function parseGrantSchema(value: string): { databaseName: string; schemaName: string } {
  const parts = String(value || "").split(/[:.]/).filter(Boolean);
  if (parts.length >= 2) {
    return {
      databaseName: parts.at(-2) || "",
      schemaName: parts.at(-1) || "",
    };
  }
  return { databaseName: "", schemaName: parts[0] || "" };
}

export function parseGrantTable(value: string): { databaseName: string; schemaName: string; tableName: string } {
  const parts = String(value || "").split(/[:.]/).filter(Boolean);
  if (parts.length >= 3) {
    return {
      databaseName: parts.at(-3) || "",
      schemaName: parts.at(-2) || "",
      tableName: parts.at(-1) || "",
    };
  }
  if (parts.length >= 2) {
    return {
      databaseName: "",
      schemaName: parts.at(-2) || "",
      tableName: parts.at(-1) || "",
    };
  }
  return { databaseName: "", schemaName: "", tableName: parts[0] || "" };
}

function findCatalogDbName(
  catalogDatabases: readonly CatalogDatabase[],
  datasourceName: string,
  schemaName = "",
  tableName = ""
): string | null {
  const row = catalogDatabases.find((db) => {
    if (db.datasourceName !== datasourceName) return false;
    if (schemaName && (db.schemaName || "") !== schemaName) return false;
    if (tableName && !(db.tables || []).includes(tableName)) return false;
    return true;
  });
  return row?.name || null;
}

function formatGrantSchema(databaseName: string, schemaName: string): string {
  return databaseName ? `${databaseName}.${schemaName}` : schemaName;
}

function formatGrantTable(databaseName: string, schemaName: string, tableName: string): string {
  const schemaPath = formatGrantSchema(databaseName, schemaName);
  return schemaPath ? `${schemaPath}.${tableName}` : tableName;
}

function ensureDatasourceGrant(grants: Map<string, DatasourceGrant>, datasourceName: string): DatasourceGrant {
  const existing = grants.get(datasourceName);
  if (existing) return existing;
  const next = {
    unrestricted: false,
    databases: new Set<string>(),
    schemas: new Set<string>(),
    tables: new Set<string>(),
  };
  grants.set(datasourceName, next);
  return next;
}

function parseDatasourceGrantScope(value: string): DatasourceGrantScope {
  try {
    const parsed: unknown = JSON.parse(value);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
    return normalizeDatasourceGrantScope(parsed as Record<string, unknown>);
  } catch {
    return {};
  }
}

function normalizeDatasourceGrantScope(scope: Record<string, unknown>): DatasourceGrantScope {
  return {
    databases: stringArray(scope.databases),
    schemas: stringArray(scope.schemas),
    tables: stringArray(scope.tables),
  };
}

function stringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string" && item.trim().length > 0);
}

function isStringArray(value: unknown): boolean {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}
