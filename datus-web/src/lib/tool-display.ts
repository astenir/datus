export type ToolTable = {
  columns: string[];
  rows: string[][];
  sourceLabel: string;
};

const tableKeys = ["rows", "data", "items", "records", "result", "results"];
export const sqlKeys = ["sql", "query", "sql_query", "sqlQuery", "statement", "command"];

type TableOptions = {
  omitKeys?: string[];
};

export type ToolResultStatus = "success" | "error" | "unknown";

export function displayValueForTool(mode: "call" | "result", value: unknown): unknown {
  if (mode !== "result" || !isPlainRecord(value)) return value;
  if ("result" in value) return value.result;
  if ("error" in value) return value.error;
  if ("message" in value) return value.message;
  return value;
}

export function toolResultStatus(value: unknown): ToolResultStatus {
  if (!isPlainRecord(value) || !("success" in value)) return "unknown";

  const success = value.success;
  if (success === true || success === 1 || success === "1" || success === "true") return "success";
  if (success === false || success === 0 || success === "0" || success === "false") return "error";
  return "unknown";
}

export function summarizeValue(value: unknown) {
  if (Array.isArray(value)) return `${value.length} 项`;
  if (value && typeof value === "object") return `${Object.keys(value as Record<string, unknown>).length} 个字段`;
  if (value === undefined || value === null || value === "") return "空";
  return "文本";
}

export function sqlFromToolValue(value: unknown): string | null {
  if (typeof value === "string") return looksLikeSql(value) ? value : null;

  if (isPlainRecord(value)) {
    for (const key of sqlKeys) {
      const candidate = value[key];
      if (typeof candidate === "string" && looksLikeSql(candidate)) return candidate;
    }
  }

  return null;
}

export function tableFromToolValue(value: unknown, options: TableOptions = {}): ToolTable | null {
  const columnDefinitionTable = tableFromColumnDefinitions(value);
  if (columnDefinitionTable) return columnDefinitionTable;

  const compressedTable = tableFromCompressedValue(value);
  if (compressedTable) return compressedTable;

  const columnTable = tableFromColumnsAndRows(value);
  if (columnTable) return columnTable;

  const rows = extractRows(value);

  if (rows && rows.length > 0) {
    const columns = uniqueColumns(rows);
    if (columns.length === 0) return null;

    return {
      columns,
      rows: rows.map((row) => columns.map((column) => formatCell(row[column]))),
      sourceLabel: `${rows.length} 行`
    };
  }

  if (isPlainRecord(value)) {
    const omitKeys = new Set(options.omitKeys ?? []);
    const entries = Object.entries(value).filter(([key]) => !omitKeys.has(key));
    if (entries.length === 0) return null;

    return {
      columns: ["字段", "值"],
      rows: entries.map(([key, entryValue]) => [key, formatCell(entryValue)]),
      sourceLabel: `${entries.length} 个字段`
    };
  }

  return null;
}

export function shouldShowChartRecommendation(toolName: string, table: ToolTable | null): boolean {
  if (!table || toolName.trim().toLowerCase() !== "read_query") return false;
  if (table.rows.length < 2 || table.columns.length < 2) return false;
  return table.columns.some((column, columnIndex) => isChartMeasureColumn(column, table.rows, columnIndex));
}

function tableFromColumnDefinitions(value: unknown): ToolTable | null {
  const columns = columnDefinitionRows(value);
  if (!columns || columns.length === 0) return null;

  const rowKeys = ["name", "type", "comment"];
  const extraKeys = uniqueColumns(columns).filter((key) => !rowKeys.includes(key));
  const keys = [...rowKeys, ...extraKeys];
  const labels: Record<string, string> = {
    name: "列名",
    type: "类型",
    comment: "说明"
  };

  return {
    columns: keys.map((key) => labels[key] ?? key),
    rows: columns.map((column) => keys.map((key) => formatCell(columnDefinitionValue(column, key)))),
    sourceLabel: `${columns.length} 列`
  };
}

function columnDefinitionRows(value: unknown): Array<Record<string, unknown>> | null {
  if (isPlainRecord(value)) {
    const hasDataRows = ["rows", "data", "values", "records", "items", "result", "results"].some((key) => key in value);
    if (hasDataRows) return null;

    const columns = value.columns ?? value.column;
    if (isColumnDefinitionArray(columns)) return columns;
  }

  return null;
}

function columnDefinitionValue(column: Record<string, unknown>, key: string): unknown {
  if (key === "type") return column.type ?? column.data_type ?? column.column_type;
  if (key === "comment") return column.comment ?? column.description ?? column.desc;
  return column[key];
}

function isColumnDefinitionArray(value: unknown): value is Array<Record<string, unknown>> {
  return (
    isRecordArray(value) &&
    value.every((item) => typeof item.name === "string" && ("type" in item || "comment" in item || "data_type" in item || "column_type" in item))
  );
}

function tableFromColumnsAndRows(value: unknown): ToolTable | null {
  const source = findColumnsAndRows(value);
  if (!source) return null;

  const columns = normalizeColumns(source.columns);
  if (columns.length === 0) return null;

  const compressedRows = tableFromCompressedValue(source.rows, columns);
  if (compressedRows) return compressedRows;

  const rows = rowsFromValue(source.rows);
  if (!rows) return null;

  return {
    columns,
    rows: rows.map((row) => {
      if (Array.isArray(row)) return columns.map((_, index) => formatCell(row[index]));
      if (isPlainRecord(row)) return columns.map((column) => formatCell(row[column]));
      return [formatCell(row)];
    }),
    sourceLabel: `${rows.length} 行`
  };
}

function findColumnsAndRows(value: unknown): { columns: unknown[]; rows: unknown } | null {
  if (!isPlainRecord(value)) return null;

  const columns = value.columns ?? value.column ?? value.original_columns ?? value.fields;
  const rows = value.rows ?? value.data ?? value.values ?? value.records ?? value.items ?? value.result ?? value.results;
  if (Array.isArray(columns) && rows !== undefined) return { columns, rows };

  for (const key of tableKeys) {
    const nested = value[key];
    if (isPlainRecord(nested)) {
      const nestedTable = findColumnsAndRows(nested);
      if (nestedTable) return nestedTable;
    }
  }

  return null;
}

function tableFromCompressedValue(value: unknown, fallbackColumns: string[] = []): ToolTable | null {
  if (!isPlainRecord(value) || typeof value.compressed_data !== "string") return null;

  const parsed = parseCsv(value.compressed_data);
  const originalColumns = Array.isArray(value.original_columns) ? normalizeColumns(value.original_columns) : [];
  const csvHeaders = parsed.length > 0 ? parsed[0] : [];

  // Prefer CSV headers when original_columns is narrower than the actual data,
  // because original_columns may omit columns that still exist in compressed_data
  // (e.g. an "index" column). Fall back to original_columns / fallbackColumns only
  // when the CSV has no header row or is empty.
  let columns: string[];
  if (csvHeaders.length > 0 && (originalColumns.length === 0 || sameColumns(csvHeaders, originalColumns) || csvHeaders.length > originalColumns.length)) {
    columns = csvHeaders;
  } else if (originalColumns.length > 0) {
    columns = originalColumns;
  } else if (fallbackColumns.length > 0) {
    columns = fallbackColumns;
  } else {
    return null;
  }

  const dataRows = parsed.length > 0 && sameColumns(parsed[0], columns) ? parsed.slice(1) : parsed;
  const originalRows = typeof value.original_rows === "number" ? value.original_rows : dataRows.length;

  return {
    columns,
    rows: dataRows.map((row) => columns.map((_, index) => formatCell(row[index]))),
    sourceLabel:
      originalRows > dataRows.length
        ? `${dataRows.length}/${originalRows} 行`
        : `${dataRows.length} 行`
  };
}

function rowsFromValue(value: unknown): unknown[] | null {
  if (Array.isArray(value)) return value;
  if (typeof value === "string") return parseCsv(value);
  return null;
}

function extractRows(value: unknown): Array<Record<string, unknown>> | null {
  if (isRecordArray(value)) return value;

  if (value && typeof value === "object" && !Array.isArray(value)) {
    const record = value as Record<string, unknown>;
    for (const key of tableKeys) {
      const nested = record[key];
      if (isRecordArray(nested)) return nested;
    }
  }

  return null;
}

function isRecordArray(value: unknown): value is Array<Record<string, unknown>> {
  return Array.isArray(value) && value.length > 0 && value.every((item) => Boolean(item) && typeof item === "object" && !Array.isArray(item));
}

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function uniqueColumns(rows: Array<Record<string, unknown>>) {
  const columns = new Set<string>();
  for (const row of rows.slice(0, 20)) {
    for (const key of Object.keys(row)) columns.add(key);
  }
  return Array.from(columns);
}

function normalizeColumns(columns: unknown[]) {
  return columns.map((column, index) => {
    if (isPlainRecord(column)) {
      const name = column.name ?? column.column_name ?? column.column ?? column.field ?? column.key ?? column.label;
      if (name !== undefined && name !== null && String(name).trim()) return String(name);
    }
    const label = String(column).trim();
    return label || `column_${index + 1}`;
  });
}

function formatCell(value: unknown): string {
  if (value === undefined || value === null) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

function isNumericCell(value: string | undefined) {
  if (!value) return false;
  const normalized = value.replace(/,/g, "").trim();
  return normalized !== "" && Number.isFinite(Number(normalized));
}

function isChartMeasureColumn(column: string, rows: string[][], columnIndex: number) {
  if (isLikelyIdentifierColumn(column)) return false;
  return rows.some((row) => isNumericCell(row[columnIndex]));
}

function isLikelyIdentifierColumn(column: string) {
  const normalized = column.trim().toLowerCase();
  if (!normalized) return false;
  return /(^|[_\s-])(id|uuid|guid|code|key|index|idx|no|number)([_\s-]|$)|(id|code)$|代码|编号|编码|序号|索引/.test(normalized);
}

function looksLikeSql(value: string) {
  let candidate = value.trimStart();

  for (;;) {
    if (candidate.startsWith("--")) {
      const nextLine = candidate.indexOf("\n");
      candidate = nextLine >= 0 ? candidate.slice(nextLine + 1).trimStart() : "";
      continue;
    }

    if (candidate.startsWith("/*")) {
      const commentEnd = candidate.indexOf("*/");
      candidate = commentEnd >= 0 ? candidate.slice(commentEnd + 2).trimStart() : "";
      continue;
    }

    break;
  }

  return /^(with|select|insert|update|delete|create|drop|alter|explain|describe|show)\b/i.test(candidate);
}

function parseCsv(value: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let quoted = false;

  for (let index = 0; index < value.length; index += 1) {
    const char = value[index];
    const next = value[index + 1];

    if (char === '"' && quoted && next === '"') {
      cell += '"';
      index += 1;
      continue;
    }

    if (char === '"') {
      quoted = !quoted;
      continue;
    }

    if (char === "," && !quoted) {
      row.push(cell);
      cell = "";
      continue;
    }

    if ((char === "\n" || char === "\r") && !quoted) {
      if (char === "\r" && next === "\n") index += 1;
      row.push(cell);
      if (row.some((item) => item !== "")) rows.push(row);
      row = [];
      cell = "";
      continue;
    }

    cell += char;
  }

  row.push(cell);
  if (row.some((item) => item !== "")) rows.push(row);
  return rows;
}

function sameColumns(left: string[], right: string[]) {
  if (left.length !== right.length) return false;
  return left.every((column, index) => column === right[index]);
}
