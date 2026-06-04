import { describe, expect, it } from "vitest";

import { displayValueForTool, sqlFromToolValue, summarizeValue, tableFromToolValue, toolResultStatus } from "./tool-display";

describe("displayValueForTool", () => {
  it("uses result as the primary rendered value for tool results", () => {
    expect(displayValueForTool("result", { success: 1, result: [{ name: "alpha" }] })).toEqual([{ name: "alpha" }]);
  });

  it("keeps full values for tool calls", () => {
    expect(displayValueForTool("call", { success: 1, result: "ignored" })).toEqual({ success: 1, result: "ignored" });
  });
});

describe("toolResultStatus", () => {
  it("treats numeric success flags distinctly", () => {
    expect(toolResultStatus({ success: 1 })).toBe("success");
    expect(toolResultStatus({ success: 0 })).toBe("error");
  });

  it("supports boolean success flags", () => {
    expect(toolResultStatus({ success: true })).toBe("success");
    expect(toolResultStatus({ success: false })).toBe("error");
  });
});

describe("tableFromToolValue", () => {
  it("turns an array of objects into table columns and rows", () => {
    expect(
      tableFromToolValue([
        { name: "alpha", count: 2 },
        { name: "beta", count: 5 }
      ])
    ).toEqual({
      columns: ["name", "count"],
      rows: [
        ["alpha", "2"],
        ["beta", "5"]
      ],
      sourceLabel: "2 rows"
    });
  });

  it("uses common result wrappers when tool output contains rows", () => {
    expect(tableFromToolValue({ rows: [{ id: 1, status: "ok" }] })).toEqual({
      columns: ["id", "status"],
      rows: [["1", "ok"]],
      sourceLabel: "1 row"
    });
  });

  it("turns plain objects into key value rows", () => {
    expect(tableFromToolValue({ query: "show funds", limit: 10 })).toEqual({
      columns: ["字段", "值"],
      rows: [
        ["query", "show funds"],
        ["limit", "10"]
      ],
      sourceLabel: "2 fields"
    });
  });

  it("turns column and row query results into a database table", () => {
    expect(
      tableFromToolValue({
        columns: ["fund_code", "nav"],
        rows: [
          ["000001", 1.23],
          ["000002", 2.34]
        ]
      })
    ).toEqual({
      columns: ["fund_code", "nav"],
      rows: [
        ["000001", "1.23"],
        ["000002", "2.34"]
      ],
      sourceLabel: "2 rows"
    });
  });

  it("turns compressed read query payloads into a database table", () => {
    expect(
      tableFromToolValue({
        original_rows: 2,
        original_columns: ["fund_code", "nav"],
        compressed_data: "fund_code,nav\n000001,1.23\n000002,2.34\n",
        is_compressed: false
      })
    ).toEqual({
      columns: ["fund_code", "nav"],
      rows: [
        ["000001", "1.23"],
        ["000002", "2.34"]
      ],
      sourceLabel: "2 rows"
    });
  });

  it("prefers CSV headers when original_columns is narrower than the data", () => {
    // Regression: backend may omit columns from original_columns (e.g. dropped "index")
    // but the CSV in compressed_data still contains them. The table must use CSV headers
    // so columns align correctly with data cells.
    expect(
      tableFromToolValue({
        original_rows: 5,
        original_columns: ["fundtypename"],
        is_compressed: false,
        compressed_data: "index,fundtypename\n0,QDII\n1,债券型\n2,混合型\n3,股票型\n4,货币型",
        removed_columns: [],
        compression_type: "none"
      })
    ).toEqual({
      columns: ["index", "fundtypename"],
      rows: [
        ["0", "QDII"],
        ["1", "债券型"],
        ["2", "混合型"],
        ["3", "股票型"],
        ["4", "货币型"]
      ],
      sourceLabel: "5 rows"
    });
  });

  it("uses compressed data inside semantic query result wrappers", () => {
    expect(
      tableFromToolValue({
        columns: ["date", "revenue"],
        data: {
          original_rows: 2,
          original_columns: ["date", "revenue"],
          compressed_data: "date,revenue\n2024-01-01,1000\n2024-01-02,1200\n",
          compression_type: "none"
        },
        metadata: { execution_time: 0.5 }
      })
    ).toEqual({
      columns: ["date", "revenue"],
      rows: [
        ["2024-01-01", "1000"],
        ["2024-01-02", "1200"]
      ],
      sourceLabel: "2 rows"
    });
  });

  it("supports singular column keys and column metadata objects", () => {
    expect(
      tableFromToolValue({
        column: [{ name: "cnt", type: "INTEGER" }],
        rows: [[3]]
      })
    ).toEqual({
      columns: ["cnt"],
      rows: [["3"]],
      sourceLabel: "1 row"
    });
  });

  it("turns describe_table column definitions into a schema table", () => {
    expect(
      tableFromToolValue({
        columns: [
          { name: "stage_id", type: "INTEGER", comment: "" },
          { name: "name", type: "VARCHAR", comment: "名称" }
        ],
        table: { name: "stage", description: "staging table" }
      })
    ).toEqual({
      columns: ["列名", "类型", "说明"],
      rows: [
        ["stage_id", "INTEGER", ""],
        ["name", "VARCHAR", "名称"]
      ],
      sourceLabel: "2 columns"
    });
  });

  it("can omit sql keys from key value tables", () => {
    expect(tableFromToolValue({ sql: "select 1", database: "fund" }, { omitKeys: ["sql"] })).toEqual({
      columns: ["字段", "值"],
      rows: [["database", "fund"]],
      sourceLabel: "1 field"
    });
  });

  it("returns null for scalar values", () => {
    expect(tableFromToolValue("plain text")).toBeNull();
  });
});

describe("sqlFromToolValue", () => {
  it("extracts sql text from common query fields", () => {
    expect(sqlFromToolValue({ query: "SELECT * FROM funds LIMIT 5" })).toBe("SELECT * FROM funds LIMIT 5");
    expect(sqlFromToolValue({ sql_query: "select count(*) from funds" })).toBe("select count(*) from funds");
  });

  it("ignores non-sql text", () => {
    expect(sqlFromToolValue({ query: "fund list" })).toBeNull();
  });
});

describe("summarizeValue", () => {
  it("formats arrays and objects into compact labels", () => {
    expect(summarizeValue([{ a: 1 }, { a: 2 }])).toBe("2 items");
    expect(summarizeValue({ a: 1, b: 2 })).toBe("2 fields");
    expect(summarizeValue("hello")).toBe("text");
    expect(summarizeValue(null)).toBe("empty");
  });
});
