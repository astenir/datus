import { describe, expect, it } from "vitest";

import {
  buildCatalogTree,
  catalogSchemaRows,
  catalogTableRows,
  fullTableName,
} from "./catalog-tree";
import type { CatalogRecord } from "@/types";

const catalog: CatalogRecord[] = [
  {
    name: "fund.public",
    schema_name: "public",
    type: "postgresql",
    tables: [
      "fund_nav",
      {
        name: "fund_profile",
        table_type: "BASE TABLE",
        row_count: 20,
        columns_count: 6,
      },
    ],
  },
  {
    name: "fund.risk",
    schema_name: "risk",
    type: "postgresql",
    tables: [
      {
        table_name: "risk_limits",
        table_type: "VIEW",
      },
    ],
  },
];

describe("catalog tree helpers", () => {
  it("keeps fully-qualified table names unchanged", () => {
    expect(fullTableName("fund", "public", "fund.public.fund_nav")).toBe("fund.public.fund_nav");
    expect(fullTableName("fund", "public", "fund_nav")).toBe("fund.public.fund_nav");
  });

  it("normalizes catalog table rows from string and object payloads", () => {
    expect(catalogTableRows(catalog)).toEqual([
      {
        key: "fund:public:fund_nav:0",
        database: "fund",
        schema: "public",
        table: "fund_nav",
        tableType: "",
        rowsLabel: "-",
        columnsLabel: "-",
        fullName: "fund.public.fund_nav",
      },
      {
        key: "fund:public:fund_profile:1",
        database: "fund",
        schema: "public",
        table: "fund_profile",
        tableType: "BASE TABLE",
        rowsLabel: "20",
        columnsLabel: "6",
        fullName: "fund.public.fund_profile",
      },
      {
        key: "fund:risk:risk_limits:0",
        database: "fund",
        schema: "risk",
        table: "risk_limits",
        tableType: "VIEW",
        rowsLabel: "-",
        columnsLabel: "-",
        fullName: "fund.risk.risk_limits",
      },
    ]);
  });

  it("builds schema rows and expanded tree folders", () => {
    expect(catalogSchemaRows(catalog)).toEqual([
      {
        key: "fund:public:postgresql",
        database: "fund",
        schema: "public",
        type: "postgresql",
        tableCount: 2,
      },
      {
        key: "fund:risk:postgresql",
        database: "fund",
        schema: "risk",
        type: "postgresql",
        tableCount: 1,
      },
    ]);

    const tree = buildCatalogTree(catalog);

    expect(tree.databases).toHaveLength(1);
    expect(tree.databases[0]?.schemas.map((schema) => schema.name)).toEqual(["public", "risk"]);
    expect(tree.databases[0]?.schemas[0]?.tables.map((table) => table.fullName)).toEqual([
      "fund.public.fund_nav",
      "fund.public.fund_profile",
    ]);
    expect(Array.from(tree.expandedPaths)).toEqual([
      "database:fund",
      "database:fund:schema:public",
      "database:fund:schema:risk",
    ]);
  });
});
