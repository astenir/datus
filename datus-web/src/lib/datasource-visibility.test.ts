import { describe, expect, it } from "vitest";
import { canAccessDatasource, visibleDatasourceEntries } from "@/lib/datasource-visibility";

describe("datasource visibility", () => {
  const datasources = {
    ccks_fund: { type: "postgresql" },
    other_fund: { type: "mysql" },
    research: { type: "duckdb" },
  };

  it("shows only granted datasources for regular users", () => {
    const visible = visibleDatasourceEntries(datasources, {
      isAdmin: false,
      allowedDatasourceNames: ["ccks_fund", "research"],
    });

    expect(visible.map(([name]) => name)).toEqual(["ccks_fund", "research"]);
    expect(canAccessDatasource("other_fund", { isAdmin: false, allowedDatasourceNames: ["ccks_fund"] })).toBe(false);
  });

  it("hides all datasources when a regular user has no datasource grant", () => {
    expect(visibleDatasourceEntries(datasources, { isAdmin: false, allowedDatasourceNames: [] })).toEqual([]);
    expect(canAccessDatasource("ccks_fund", { isAdmin: false, allowedDatasourceNames: [] })).toBe(false);
  });

  it("shows all configured datasources for admins", () => {
    const visible = visibleDatasourceEntries(datasources, {
      isAdmin: true,
      allowedDatasourceNames: [],
    });

    expect(visible.map(([name]) => name)).toEqual(["ccks_fund", "other_fund", "research"]);
    expect(canAccessDatasource("other_fund", { isAdmin: true, allowedDatasourceNames: [] })).toBe(true);
  });
});
