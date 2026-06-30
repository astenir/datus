import { describe, expect, it } from "vitest";

import { permissionBadgeItems } from "./permission-labels";

describe("permission labels", () => {
  it("renders known module permissions as Chinese badge labels", () => {
    expect(permissionBadgeItems(["module.chat", "module.sql_executor"])).toEqual([
      { code: "module.chat", kind: "regular", label: "对话" },
      { code: "module.sql_executor", kind: "regular", label: "SQL 执行" },
    ]);
  });

  it("renders legacy role permission codes as Chinese badge labels", () => {
    expect(permissionBadgeItems(["chat", "sql_generation", "admin"])).toEqual([
      { code: "chat", kind: "regular", label: "对话" },
      { code: "sql_generation", kind: "regular", label: "SQL 生成" },
      { code: "admin", kind: "regular", label: "管理" },
    ]);
  });

  it("renders wildcard permissions as aggregate badges", () => {
    expect(permissionBadgeItems(["module.admin.*", "module.chat"])).toEqual([
      { code: "module.admin.*", kind: "wildcard", label: "全部管理权限" },
      { code: "module.chat", kind: "regular", label: "对话" },
    ]);
  });

  it("does not expand overlapping wildcard permissions into many badges", () => {
    expect(permissionBadgeItems(["module.*", "module.admin.*"])).toEqual([
      { code: "module.*", kind: "wildcard", label: "全部功能权限" },
      { code: "module.admin.*", kind: "wildcard", label: "全部管理权限" },
    ]);
  });
});
