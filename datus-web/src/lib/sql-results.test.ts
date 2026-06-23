import { describe, expect, it } from "vitest";

import { displaySqlCellValue, parseSqlReturnRows } from "./sql-results";

describe("parseSqlReturnRows", () => {
  it("parses JSON row arrays", () => {
    expect(parseSqlReturnRows('[{"name":"fund","count":2}]')).toEqual([{ name: "fund", count: 2 }]);
  });

  it("parses Python repr row arrays with Decimal values", () => {
    const raw = "[{'indexcycle': '一个月', 'avg_return': Decimal('-4.7293'), 'fund_count': 52, 'enabled': True, 'note': None}]";
    expect(parseSqlReturnRows(raw)).toEqual([
      { indexcycle: "一个月", avg_return: "-4.7293", fund_count: 52, enabled: true, note: null },
    ]);
  });

  it("returns an empty array for raw text output", () => {
    expect(parseSqlReturnRows("query ok")).toEqual([]);
  });
});

describe("displaySqlCellValue", () => {
  it("formats nullish and nested values for table cells", () => {
    expect(displaySqlCellValue(null)).toBe("");
    expect(displaySqlCellValue({ a: 1 })).toBe('{"a":1}');
  });
});
