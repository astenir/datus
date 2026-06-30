import { describe, expect, it } from "vitest";

import { ROLE_PERMISSION_GROUPS, ROLE_PERMISSION_OPTIONS, permissionBadgeItems } from "./permission-labels";

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

  it("exposes enterprise role permission options for the role editor", () => {
    expect(ROLE_PERMISSION_OPTIONS.length).toBeGreaterThan(5);
    expect(ROLE_PERMISSION_OPTIONS).toEqual(
      expect.arrayContaining([
        { value: "module.*", kind: "wildcard", label: "全部功能权限" },
        { value: "module.admin.*", kind: "wildcard", label: "全部管理权限" },
        { value: "module.sql_executor", kind: "regular", label: "SQL 执行" },
        { value: "module.admin.users", kind: "regular", label: "用户管理" },
        { value: "module.admin.audit.export", kind: "regular", label: "审计导出" },
      ])
    );
  });

  it("groups enterprise role permission options by product area", () => {
    const groupedValues = ROLE_PERMISSION_GROUPS.flatMap((group) => group.options.map((option) => option.value));

    expect(ROLE_PERMISSION_GROUPS.map((group) => group.label)).toEqual([
      "特殊权限",
      "核心功能",
      "报表与仪表盘",
      "配置",
      "管理后台",
    ]);
    expect(groupedValues).toHaveLength(ROLE_PERMISSION_OPTIONS.length);
    expect([...groupedValues].sort()).toEqual([...ROLE_PERMISSION_OPTIONS.map((option) => option.value)].sort());
  });
});
