import { describe, expect, it } from "vitest";

import { formatDatasourceScope } from "./datasource-scope-labels";

describe("formatDatasourceScope", () => {
  it("renders empty scope as full access", () => {
    expect(formatDatasourceScope(undefined)).toBe("全量访问");
    expect(formatDatasourceScope({})).toBe("全量访问");
  });

  it("renders standard datasource scope as a compact Chinese summary", () => {
    expect(formatDatasourceScope({
      allow_catalog: true,
      allow_sql: true,
      schemas: ["public"],
      tables: ["*"],
    })).toBe("Schema: public · 表: 全部");
  });

  it("renders database schema and table lists with truncation", () => {
    expect(formatDatasourceScope({
      databases: ["analytics"],
      schemas: ["public", "risk"],
      tables: ["orders", "accounts", "positions", "trades"],
    })).toBe("库: analytics · Schema: public、risk · 表: orders、accounts、positions 等 4 项");
  });

  it("hides custom scope internals from list displays", () => {
    expect(formatDatasourceScope({ row_filter: "owner = current_user" })).toBe("自定义范围");
  });

  it("ignores grant metadata when formatting profile grant payloads", () => {
    expect(formatDatasourceScope({ effect: "deny" })).toBe("全量访问");
    expect(formatDatasourceScope({
      effect: "allow",
      allow_sql: true,
      tables: ["public.accounts"],
    })).toBe("表: public.accounts");
  });
});
