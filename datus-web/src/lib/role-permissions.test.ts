import { describe, expect, it } from "vitest";

import {
  buildDatasourceTreeOptions,
  datasourceNodeIdsFromPermissions,
  featurePermissionCodes,
  rolePermissionsFromSelections,
} from "./role-permissions";
import type { CatalogDatabase, RolePermissionRecord } from "@/types/admin";

const catalog: CatalogDatabase[] = [
  {
    datasourceName: "fund",
    name: "analytics",
    type: "postgresql",
    schemaName: "public",
    tables: ["orders", "accounts"],
  },
  {
    datasourceName: "fund",
    name: "analytics",
    type: "postgresql",
    schemaName: "risk",
    tables: ["limits"],
  },
];

describe("role permission helpers", () => {
  it("builds datasource tree options by datasource, database, schema, and table", () => {
    expect(buildDatasourceTreeOptions(catalog)).toEqual([
      {
        id: "ds:fund",
        label: "fund",
        children: [
          {
            id: "db:fund:analytics",
            label: "analytics",
            children: [
              {
                id: "schema:fund:analytics:public",
                label: "public",
                children: [
                  { id: "table:fund:analytics:public:orders", label: "orders" },
                  { id: "table:fund:analytics:public:accounts", label: "accounts" },
                ],
              },
              {
                id: "schema:fund:analytics:risk",
                label: "risk",
                children: [
                  { id: "table:fund:analytics:risk:limits", label: "limits" },
                ],
              },
            ],
          },
        ],
      },
    ]);
  });

  it("normalizes feature permission codes", () => {
    const permissions: RolePermissionRecord[] = [
      { permission_type: "feature", resource_code: "sql", permission_value: "allow" },
      { permission_type: "feature", resource_code: "sql_generation", permission_value: "allow" },
      { permission_type: "feature", resource_code: "chat", permission_value: "deny" },
    ];

    expect(featurePermissionCodes(permissions)).toEqual(["sql_generation"]);
  });

  it("converts datasource permission payloads to tree node ids", () => {
    const permissions: RolePermissionRecord[] = [
      {
        permission_type: "datasource",
        resource_code: "fund",
        permission_value: JSON.stringify({
          databases: ["analytics"],
          schemas: ["analytics.public"],
          tables: ["risk.limits"],
        }),
      },
    ];

    expect(datasourceNodeIdsFromPermissions(permissions, catalog)).toEqual([
      "db:fund:analytics",
      "schema:fund:analytics:public",
      "table:fund:analytics:risk:limits",
    ]);
  });

  it("drops broader datasource selections when child nodes are selected", () => {
    const permissions = rolePermissionsFromSelections("datasource", [], [
      "ds:fund",
      "db:fund:analytics",
      "schema:fund:analytics:public",
      "table:fund:analytics:public:orders",
      "table:fund:analytics:risk:limits",
    ]);

    expect(permissions).toEqual([
      {
        permission_type: "datasource",
        resource_code: "fund",
        permission_value: JSON.stringify({
          databases: [],
          schemas: [],
          tables: ["analytics.public.orders", "analytics.risk.limits"],
        }),
      },
    ]);
  });

  it("builds resource feature permissions", () => {
    expect(rolePermissionsFromSelections("resource", ["chat", "report"], [])).toEqual([
      { permission_type: "feature", resource_code: "chat", permission_value: "allow" },
      { permission_type: "feature", resource_code: "report", permission_value: "allow" },
    ]);
  });
});
