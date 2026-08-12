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

  it("collapses overlapping wildcard permissions into the covering badge", () => {
    expect(permissionBadgeItems(["module.*", "module.admin.*"])).toEqual([
      { code: "module.*", kind: "wildcard", label: "全部功能权限" },
    ]);
    expect(permissionBadgeItems(["module.*", "module.chat", "module.admin.roles", "mcp.*", "mcp.server.list"])).toEqual([
      { code: "module.*", kind: "wildcard", label: "全部功能权限" },
      { code: "mcp.*", kind: "wildcard", label: "全部 MCP 权限" },
    ]);
  });

  it("collapses covered permissions when the all-permissions badge is present", () => {
    expect(permissionBadgeItems(["*", "module.*", "mcp.*", "module.chat", "mcp.server.add", "module.admin.users"])).toEqual([
      { code: "*", kind: "wildcard", label: "全部权限" },
    ]);
    expect(permissionBadgeItems(["module.report.*", "module.report.view", "module.report.export"])).toEqual([
      { code: "module.report.*", kind: "wildcard", label: "全部报表权限" },
    ]);
  });

  it("exposes enterprise role permission options for the role editor", () => {
    expect(ROLE_PERMISSION_OPTIONS.length).toBeGreaterThan(5);
    expect(ROLE_PERMISSION_OPTIONS).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ value: "module.*", kind: "wildcard", label: "全部功能权限" }),
        expect.objectContaining({ value: "module.admin.*", kind: "wildcard", label: "全部管理权限" }),
        expect.objectContaining({ value: "module.sql_executor", kind: "regular", label: "SQL 执行" }),
        expect.objectContaining({ value: "module.report.edit", kind: "regular", label: "报表编辑" }),
        expect.objectContaining({ value: "module.dashboard.edit", kind: "regular", label: "仪表盘编辑" }),
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
      "功能入口",
      "对话增强",
      "产物操作",
      "MCP 操作",
      "配置与运维",
      "治理权限",
      "特殊权限",
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

  it("removes permissions covered by a broader wildcard during normalization", () => {
    expect(normalizePermissionSelection(["module.chat", "module.*"])).toEqual(["module.*"]);
    expect(normalizePermissionSelection(["module.admin.users", "module.admin.*"])).toEqual(["module.admin.*"]);
    expect(normalizePermissionSelection(["mcp.server.list", "mcp.*"])).toEqual(["module.mcp", "mcp.*"]);
    expect(normalizePermissionSelection(["*", "module.chat", "mcp.server.add"])).toEqual(["*"]);
  });

  it("keeps narrower permissions that are not covered by the selected wildcard", () => {
    expect(normalizePermissionSelection(["module.mcp", "mcp.*"])).toEqual(["module.mcp", "mcp.*"]);
    expect(normalizePermissionSelection(["module.chat", "module.report.*"])).toEqual(["module.chat", "module.report.*"]);
  });

  it("clears previously selected permissions when toggling the all-permissions badge on", () => {
    const selected = togglePermissionSelection(["module.chat", "mcp.server.list", "module.admin.roles"], "*");

    expect(selected).toEqual(["*"]);
    expect(togglePermissionSelection(["*"], "module.chat")).toEqual(["*"]);
  });

  it("applies role permission presets with prerequisites", () => {
    expect(ROLE_PERMISSION_PRESETS.map((preset) => preset.id)).toEqual([
      "view-chat",
      "view-artifacts",
      "view-sql",
      "view-knowledge",
      "view-mcp",
      "view-agent",
      "view-configuration",
      "view-permissions",
      "artifact-editor",
      "artifact-operator",
      "mcp-operator",
      "personal-mcp-user",
      "user-role-admin",
      "governance-admin",
      "audit-viewer",
      "platform-ops",
      "config-editor",
      "enterprise-admin",
    ]);
    expect(ROLE_PERMISSION_PRESET_GROUPS.map((group) => ({
      label: group.label,
      presets: group.presets.map((preset) => preset.id),
    }))).toEqual([
      {
        label: "功能入口",
        presets: [
          "view-chat",
          "view-artifacts",
          "view-sql",
          "view-knowledge",
          "view-mcp",
          "view-agent",
          "view-configuration",
          "view-permissions",
        ],
      },
      {
        label: "增强能力",
        presets: ["artifact-editor", "artifact-operator", "mcp-operator", "personal-mcp-user"],
      },
      {
        label: "治理权限",
        presets: ["user-role-admin", "governance-admin", "audit-viewer"],
      },
      {
        label: "平台运维",
        presets: ["platform-ops", "config-editor", "enterprise-admin"],
      },
    ]);
    expect(applyPermissionPresetSelection([], "view-artifacts")).toEqual([
      "module.report.view",
      "module.dashboard.view",
      "module.report.query",
      "module.dashboard.query",
    ]);
    expect(applyPermissionPresetSelection([], "view-mcp")).toEqual([
      "module.mcp",
      "mcp.server.list",
      "mcp.server.tools",
    ]);
    expect(applyPermissionPresetSelection([], "personal-mcp-user")).toEqual([
      "module.mcp.personal",
      "mcp.personal.list",
      "mcp.personal.create",
      "mcp.personal.edit",
      "mcp.personal.remove",
      "mcp.personal.connectivity",
      "mcp.personal.tools",
      "mcp.personal.use",
    ]);
    expect(applyPermissionPresetSelection([], "view-sql")).toEqual([
      "module.sql_executor",
      "module.datasource_catalog",
    ]);
    expect(applyPermissionPresetSelection([], "view-configuration")).toEqual([
      "module.config.view",
      "module.system.status",
    ]);
    expect(applyPermissionPresetSelection([], "artifact-operator")).toEqual([
      "module.report.view",
      "module.dashboard.view",
      "module.report.query",
      "module.report.export",
      "module.dashboard.query",
      "module.dashboard.export",
    ]);
    expect(applyPermissionPresetSelection([], "artifact-editor")).toEqual([
      "module.report.view",
      "module.dashboard.view",
      "module.report.edit",
      "module.dashboard.edit",
    ]);
  });

  it("toggles selected role permission presets off", () => {
    const selected = applyPermissionPresetSelection([], "platform-ops");

    expect(selected).toEqual([
      "module.admin.agents",
      "module.config.view",
      "module.config.edit",
      "module.admin.sessions",
      "module.admin.quotas",
      "module.admin.secrets",
      "module.system.status",
    ]);
    expect(togglePermissionPresetSelection(selected, "platform-ops")).toEqual([]);
  });

  it("keeps shared permissions when toggling one selected preset off", () => {
    const selected = applyPermissionPresetSelection(
      applyPermissionPresetSelection([], "view-configuration"),
      "audit-viewer",
    );

    expect(selected).toEqual([
      "module.config.view",
      "module.admin.audit",
      "module.system.status",
    ]);
    expect(togglePermissionPresetSelection(selected, "view-configuration")).toEqual([
      "module.admin.audit",
      "module.system.status",
    ]);
  });
});
