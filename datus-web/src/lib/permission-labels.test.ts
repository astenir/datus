import { describe, expect, it } from "vitest";

import {
  ROLE_PERMISSION_GROUPS,
  ROLE_PERMISSION_OPTIONS,
  ROLE_PERMISSION_PRESET_GROUPS,
  ROLE_PERMISSION_PRESETS,
  applyPermissionPresetSelection,
  normalizePermissionSelection,
  permissionBadgeItems,
  togglePermissionPresetSelection,
  togglePermissionSelection,
} from "./permission-labels";

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
        expect.objectContaining({ value: "module.*", kind: "wildcard", label: "全部功能权限" }),
        expect.objectContaining({ value: "module.admin.*", kind: "wildcard", label: "全部管理权限" }),
        expect.objectContaining({ value: "module.sql_executor", kind: "regular", label: "SQL 执行" }),
        expect.objectContaining({ value: "mcp.server.edit", kind: "regular", label: "MCP Server 编辑" }),
        expect.objectContaining({ value: "mcp.filter.set", kind: "regular", label: "MCP 过滤设置" }),
        expect.objectContaining({ value: "module.admin.users", kind: "regular", label: "用户管理" }),
        expect.objectContaining({ value: "module.admin.audit.export", kind: "regular", label: "审计导出" }),
      ])
    );
  });

  it("groups enterprise role permission options by product area", () => {
    const groupedValues = ROLE_PERMISSION_GROUPS.flatMap((group) => group.options.map((option) => option.value));

    expect(ROLE_PERMISSION_GROUPS.map((group) => group.label)).toEqual([
      "特殊权限",
      "核心功能",
      "MCP 管理",
      "报表与仪表盘",
      "配置",
      "管理后台",
    ]);
    expect(groupedValues).toHaveLength(ROLE_PERMISSION_OPTIONS.length);
    expect([...groupedValues].sort()).toEqual([...ROLE_PERMISSION_OPTIONS.map((option) => option.value)].sort());
  });

  it("normalizes dependent permissions for MCP page access", () => {
    expect(normalizePermissionSelection(["mcp.server.tools"])).toEqual([
      "module.mcp",
      "mcp.server.list",
      "mcp.server.tools",
    ]);
  });

  it("removes dependent permissions when a prerequisite is toggled off", () => {
    expect(togglePermissionSelection([
      "module.mcp",
      "mcp.server.list",
      "mcp.server.tools",
      "mcp.server.connectivity",
    ], "module.mcp")).toEqual([]);
  });

  it("applies role permission presets with prerequisites", () => {
    expect(ROLE_PERMISSION_PRESETS.map((preset) => preset.id)).toEqual([
      "workspace-basic",
      "sql-analysis",
      "artifact-viewer",
      "artifact-operator",
      "knowledge-user",
      "mcp-observer",
      "user-role-admin",
      "governance-admin",
      "audit-viewer",
      "platform-ops",
      "enterprise-admin",
    ]);
    expect(ROLE_PERMISSION_PRESET_GROUPS.map((group) => ({
      label: group.label,
      presets: group.presets.map((preset) => preset.id),
    }))).toEqual([
      {
        label: "基础使用",
        presets: ["workspace-basic", "knowledge-user", "mcp-observer"],
      },
      {
        label: "数据分析",
        presets: ["sql-analysis", "artifact-viewer", "artifact-operator"],
      },
      {
        label: "治理管理",
        presets: ["user-role-admin", "governance-admin", "audit-viewer"],
      },
      {
        label: "平台运维",
        presets: ["platform-ops", "enterprise-admin"],
      },
    ]);
    expect(applyPermissionPresetSelection([], "artifact-operator")).toEqual([
      "module.report.view",
      "module.report.query",
      "module.report.export",
      "module.dashboard.view",
      "module.dashboard.query",
      "module.dashboard.export",
    ]);
  });

  it("toggles selected role permission presets off", () => {
    const selected = applyPermissionPresetSelection([], "platform-ops");

    expect(selected).toEqual([
      "module.config.view",
      "module.config.edit",
      "module.admin.sessions",
      "module.admin.quotas",
      "module.admin.secrets",
      "module.admin.agents",
      "module.system.status",
    ]);
    expect(togglePermissionPresetSelection(selected, "platform-ops")).toEqual([]);
  });

  it("keeps shared permissions when toggling one selected preset off", () => {
    const selected = applyPermissionPresetSelection(
      applyPermissionPresetSelection([], "workspace-basic"),
      "audit-viewer",
    );

    expect(selected).toEqual([
      "module.chat",
      "module.datasource_catalog",
      "module.config.view",
      "module.admin.audit",
      "module.system.status",
    ]);
    expect(togglePermissionPresetSelection(selected, "workspace-basic")).toEqual([
      "module.admin.audit",
      "module.system.status",
    ]);
  });
});
