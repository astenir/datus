import { describe, expect, it } from "vitest";

import { adminDatasourceLabel, datasourceLabel, selectedOptionLabel } from "./datasource-display";

describe("datasource display labels", () => {
  it("keeps the stable datasource key visible beside a Chinese alias", () => {
    expect(datasourceLabel("fund_pg", { display_name: "基金分析库" })).toBe("基金分析库 (fund_pg)");
    expect(adminDatasourceLabel({
      name: "fund_pg",
      display_name: "基金分析库",
      type: "postgres",
      is_default: false,
    })).toBe("基金分析库 (fund_pg)");
  });

  it("falls back to the datasource key", () => {
    expect(datasourceLabel("warehouse", {})).toBe("warehouse");
    expect(selectedOptionLabel("warehouse", [])).toBe("warehouse");
  });
});
