import { describe, expect, it } from "vitest";

import { displayValueForTool, shouldShowChartRecommendation, sqlFromToolValue, summarizeValue, tableFromToolValue, toolResultStatus } from "./tool-display";

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
      sourceLabel: "2 行"
    });
  });

  it("uses common result wrappers when tool output contains rows", () => {
    expect(tableFromToolValue({ rows: [{ id: 1, status: "ok" }] })).toEqual({
      columns: ["id", "status"],
      rows: [["1", "ok"]],
      sourceLabel: "1 行"
    });
  });

  it("turns plain objects into key value rows", () => {
    expect(tableFromToolValue({ query: "show funds", limit: 10 })).toEqual({
      columns: ["字段", "值"],
      rows: [
        ["query", "show funds"],
        ["limit", "10"]
      ],
      sourceLabel: "2 个字段"
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
      sourceLabel: "2 行"
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
      sourceLabel: "2 行"
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
      sourceLabel: "5 行"
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
      sourceLabel: "2 行"
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
      sourceLabel: "1 行"
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
      sourceLabel: "2 列"
    });
  });

  it("can omit sql keys from key value tables", () => {
    expect(tableFromToolValue({ sql: "select 1", database: "fund" }, { omitKeys: ["sql"] })).toEqual({
      columns: ["字段", "值"],
      rows: [["database", "fund"]],
      sourceLabel: "1 个字段"
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

  it("extracts sql text that starts with comments", () => {
    const sql = "-- 查找基金管理人\nSELECT DISTINCT investadvisorname FROM mf_fundarchives";
    expect(sqlFromToolValue({ sql })).toBe(sql);
  });

  it("ignores non-sql text", () => {
    expect(sqlFromToolValue({ query: "fund list" })).toBeNull();
  });
});

describe("shouldShowChartRecommendation", () => {
  it("shows chart recommendations for multi-row read_query tables with numeric values", () => {
    expect(shouldShowChartRecommendation("read_query", {
      columns: ["date", "revenue"],
      rows: [
        ["2024-01-01", "1000"],
        ["2024-01-02", "1200"],
      ],
      sourceLabel: "2 行",
    })).toBe(true);
  });

  it("hides chart recommendations for non-query tools and single-row tables", () => {
    const table = {
      columns: ["field", "type"],
      rows: [
        ["fund_code", "VARCHAR"],
        ["nav", "DECIMAL"],
      ],
      sourceLabel: "2 行",
    };

    expect(shouldShowChartRecommendation("describe_table", table)).toBe(false);
    expect(shouldShowChartRecommendation("read_query", {
      columns: ["investadvisorname"],
      rows: [["鹏华基金管理有限公司"]],
      sourceLabel: "1 行",
    })).toBe(false);
  });

  it("hides chart recommendations for text-only read_query tables", () => {
    expect(shouldShowChartRecommendation("read_query", {
      columns: ["fund_name", "manager_name"],
      rows: [
        ["基金 A", "张三"],
        ["基金 B", "李四"],
      ],
      sourceLabel: "2 行",
    })).toBe(false);
  });

  it("hides chart recommendations when numeric values are only identifiers", () => {
    expect(shouldShowChartRecommendation("read_query", {
      columns: ["基金代码", "产品编号", "fund_name"],
      rows: [
        ["000001", "1001", "基金 A"],
        ["000002", "1002", "基金 B"],
      ],
      sourceLabel: "2 行",
    })).toBe(false);
  });
});

describe("summarizeValue", () => {
  it("formats arrays and objects into compact labels", () => {
    expect(summarizeValue([{ a: 1 }, { a: 2 }])).toBe("2 项");
    expect(summarizeValue({ a: 1, b: 2 })).toBe("2 个字段");
    expect(summarizeValue("hello")).toBe("文本");
    expect(summarizeValue(null)).toBe("空");
  });
});
