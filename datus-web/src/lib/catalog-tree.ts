import type { CatalogRecord } from "@/types";
import { databaseNameFromCatalog } from "@/lib/chat";

export type CatalogSchemaRow = {
  key: string;
  database: string;
  schema: string;
  type: string;
  tableCount: number;
};

export type CatalogTableRow = {
  key: string;
  database: string;
  schema: string;
  table: string;
  tableType: string;
  rowsLabel: string;
  columnsLabel: string;
  fullName: string;
};

export type CatalogTreeSchemaNode = {
  key: string;
  path: string;
  name: string;
  tables: CatalogTableRow[];
};

export type CatalogTreeDatabaseNode = {
  key: string;
  path: string;
  name: string;
  schemas: CatalogTreeSchemaNode[];
};

export type CatalogTreeData = {
  databases: CatalogTreeDatabaseNode[];
  expandedPaths: Set<string>;
};

function stringField(value: unknown) {
  return typeof value === "string" ? value.trim() : "";
}

function numberLabel(value: unknown) {
  return typeof value === "number" ? value.toLocaleString("zh-CN") : "-";
}

function tableNameFromItem(item: unknown) {
  if (typeof item === "string") return item.trim();
  if (typeof item !== "object" || item === null) return "";

  const record = item as Record<string, unknown>;
  return stringField(record.name ?? record.table_name);
}

function tableTypeFromItem(item: unknown) {
  if (typeof item !== "object" || item === null) return "";
  return stringField((item as Record<string, unknown>).table_type);
}

function tableRowsLabelFromItem(item: unknown) {
  if (typeof item !== "object" || item === null) return "-";
  return numberLabel((item as Record<string, unknown>).row_count);
}

function tableColumnsLabelFromItem(item: unknown) {
  if (typeof item !== "object" || item === null) return "-";
  return numberLabel((item as Record<string, unknown>).columns_count);
}

export function fullTableName(database: string, schema: string, table: string) {
  if (table.includes(".")) return table;
  return [database, schema, table].filter(Boolean).join(".");
}

export function catalogTableRowsForEntry(entry: CatalogRecord): CatalogTableRow[] {
  const tables = Array.isArray(entry.tables) ? entry.tables : [];
  const database = databaseNameFromCatalog(entry);
  const schema = stringField(entry.schema_name ?? entry.schema ?? entry.catalog_name);
  return tables.map((item, index) => {
    const table = tableNameFromItem(item);
    const fullName = fullTableName(database, schema, table);
    return {
      key: [database, schema, table, String(index)].join(":"),
      database,
      schema,
      table,
      tableType: tableTypeFromItem(item),
      rowsLabel: tableRowsLabelFromItem(item),
      columnsLabel: tableColumnsLabelFromItem(item),
      fullName,
    };
  }).filter((row) => row.table && row.fullName);
}

export function catalogTableRows(entries: readonly CatalogRecord[]): CatalogTableRow[] {
  return entries.flatMap(catalogTableRowsForEntry);
}

export function catalogSchemaRows(entries: readonly CatalogRecord[]): CatalogSchemaRow[] {
  return entries.map((entry) => {
    const database = databaseNameFromCatalog(entry);
    const schema = stringField(entry.schema_name ?? entry.schema ?? entry.catalog_name);
    return {
      key: [database, schema, stringField(entry.type)].join(":"),
      database,
      schema,
      type: stringField(entry.type),
      tableCount: catalogTableRowsForEntry(entry).length,
    };
  });
}

export function buildCatalogTree(entries: readonly CatalogRecord[]): CatalogTreeData {
  const databases = new Map<string, CatalogTreeDatabaseNode>();
  const expandedPaths = new Set<string>();

  for (const entry of entries) {
    const rows = catalogTableRowsForEntry(entry);
    const databaseName = databaseNameFromCatalog(entry) || "默认数据库";
    const schemaName = stringField(entry.schema_name ?? entry.schema ?? entry.catalog_name) || "默认 schema";
    const databasePath = `database:${databaseName}`;
    const schemaPath = `${databasePath}:schema:${schemaName}`;

    let databaseNode = databases.get(databasePath);
    if (!databaseNode) {
      databaseNode = {
        key: databasePath,
        path: databasePath,
        name: databaseName,
        schemas: [],
      };
      databases.set(databasePath, databaseNode);
    }

    databaseNode.schemas.push({
      key: schemaPath,
      path: schemaPath,
      name: schemaName,
      tables: rows,
    });
    expandedPaths.add(databasePath);
    expandedPaths.add(schemaPath);
  }

  return {
    databases: Array.from(databases.values()),
    expandedPaths,
  };
}
