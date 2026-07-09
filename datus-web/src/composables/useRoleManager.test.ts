import { beforeEach, describe, expect, it, vi } from "vitest";

const listRoles = vi.fn();
const getRole = vi.fn();
const upsertRole = vi.fn();
const deleteRole = vi.fn();
const toastError = vi.fn();

vi.mock("@/lib/api", () => ({
  adminRoleApi: {
    listRoles,
    getRole,
    upsertRole,
    deleteRole,
  },
}));

vi.mock("vue-sonner", () => ({
  toast: {
    error: toastError,
  },
}));

const role = {
  role_id: "resource_admin",
  name: "资源管理员",
  description: "desc",
  permissions: ["module.dashboard.view"],
  built_in: false,
  created_at: "2026-06-22T00:00:00Z",
  updated_at: null,
};

describe("useRoleManager", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listRoles.mockResolvedValue({ data: [] });
    getRole.mockResolvedValue({ data: role });
  });

  it("loads roles from the current enterprise role list endpoint", async () => {
    listRoles.mockResolvedValue({ data: [role] });

    const { useRoleManager } = await import("./useRoleManager");
    const manager = useRoleManager();

    await manager.loadRoles();

    expect(listRoles).toHaveBeenCalledWith();
    expect(manager.roles.value).toEqual([role]);
    expect(manager.total.value).toBe(1);
  });

  it("exposes the full enterprise permission option set for role editing", async () => {
    const { useRoleManager } = await import("./useRoleManager");
    const manager = useRoleManager();
    const optionValues = manager.featureOptions.map((option) => option.value);

    expect(optionValues.length).toBeGreaterThan(5);
    expect(optionValues).toEqual(
      expect.arrayContaining([
        "module.*",
        "module.admin.*",
        "module.sql_executor",
        "mcp.server.edit",
        "mcp.filter.set",
        "module.admin.users",
      ])
    );
  });

  it("exposes grouped enterprise permission options for role editing", async () => {
    const { useRoleManager } = await import("./useRoleManager");
    const manager = useRoleManager();

    expect(manager.featureGroups.map((group) => group.label)).toEqual([
      "功能入口",
      "对话增强",
      "产物操作",
      "MCP 操作",
      "配置与运维",
      "治理权限",
      "特殊权限",
    ]);
    expect(manager.featureGroups.flatMap((group) => group.options).length).toBe(manager.featureOptions.length);
    expect(manager.permissionPresetGroups.map((group) => group.label)).toEqual([
      "功能入口",
      "增强能力",
      "治理权限",
      "平台运维",
    ]);
  });

  it("filters roles locally by keyword", async () => {
    listRoles.mockResolvedValue({
      data: [
        role,
        { ...role, role_id: "viewer", name: "查看员", permissions: ["module.report.view"] },
      ],
    });

    const { useRoleManager } = await import("./useRoleManager");
    const manager = useRoleManager();
    await manager.loadRoles();
    manager.searchForm.value = { keyword: "查看" };

    expect(manager.filteredRoles.value.map((item) => item.role_id)).toEqual(["viewer"]);
  });

  it("opens role detail with a normalized route role id", async () => {
    getRole.mockResolvedValue({
      data: { ...role, name: "分析师", permissions: ["module.datasource_catalog", "module.dashboard.view"] },
    });

    const { useRoleManager } = await import("./useRoleManager");
    const manager = useRoleManager();

    const detailPromise = manager.openRoleDetail(" analyst ");

    expect(manager.showRoleDetailDialog.value).toBe(true);
    expect(manager.selectedRoleDetailId.value).toBe("analyst");
    expect(manager.loadingRoleDetail.value).toBe(true);

    await detailPromise;

    expect(getRole).toHaveBeenCalledWith("analyst");
    expect(manager.selectedRoleDetail.value?.name).toBe("分析师");
    expect(manager.selectedRoleDetail.value?.permissions).toEqual([
      "module.datasource_catalog",
      "module.dashboard.view",
    ]);
    expect(manager.roleDetailError.value).toBeNull();
    expect(manager.loadingRoleDetail.value).toBe(false);

    manager.closeRoleDetail();

    expect(manager.showRoleDetailDialog.value).toBe(false);
    expect(manager.selectedRoleDetail.value).toBeNull();
    expect(manager.selectedRoleDetailId.value).toBeNull();
  });

  it("upserts a role with selected permission codes", async () => {
    const { useRoleManager } = await import("./useRoleManager");
    const manager = useRoleManager();
    manager.roleForm.value = {
      name: "资源查看员",
      description: "read only",
      permissions: [],
    };
    manager.selectedFeatures.value = ["module.dashboard.view"];

    await manager.saveRole();

    expect(upsertRole).toHaveBeenCalledWith("资源查看员", {
      name: "资源查看员",
      description: "read only",
      permissions: ["module.dashboard.view"],
    });
    expect(manager.showDialog.value).toBe(false);
  });

  it("keeps the role dialog open when backend rejects ungrantable permissions", async () => {
    upsertRole.mockResolvedValueOnce({
      success: false,
      errorCode: "ROLE_PERMISSION_FORBIDDEN",
      errorMessage: "Cannot grant permissions that the actor does not have.",
    });

    const { useRoleManager } = await import("./useRoleManager");
    const manager = useRoleManager();
    manager.openCreateDialog();
    manager.roleForm.value = {
      name: "越权角色",
      description: "",
      permissions: [],
    };
    manager.selectedFeatures.value = ["module.admin.*"];

    await manager.saveRole();

    expect(toastError).toHaveBeenCalledWith("不能授予自己尚未拥有的权限");
    expect(manager.roleDialogError.value).toBe("不能授予自己尚未拥有的权限");
    expect(manager.showDialog.value).toBe(true);
    expect(listRoles).not.toHaveBeenCalled();
  });

  it("normalizes role permissions when toggling dependent MCP permissions", async () => {
    const { useRoleManager } = await import("./useRoleManager");
    const manager = useRoleManager();

    manager.toggleSelectedFeature("mcp.server.tools");

    expect(manager.selectedFeatures.value).toEqual([
      "module.mcp",
      "mcp.server.list",
      "mcp.server.tools",
    ]);

    manager.toggleSelectedFeature("module.mcp");

    expect(manager.selectedFeatures.value).toEqual([]);
  });

  it("applies role permission presets", async () => {
    const { useRoleManager } = await import("./useRoleManager");
    const manager = useRoleManager();

    manager.togglePermissionPreset("view-mcp");

    expect(manager.selectedFeatures.value).toEqual([
      "module.mcp",
      "mcp.server.list",
      "mcp.server.tools",
    ]);
    expect(manager.selectedPresetIds.value).toContain("view-mcp");
    expect(manager.selectedPresetIds.value).not.toContain("mcp-operator");

    manager.togglePermissionPreset("view-mcp");
    manager.togglePermissionPreset("mcp-operator");

    expect(manager.selectedFeatures.value).toEqual([
      "module.mcp",
      "mcp.server.list",
      "mcp.server.tools",
      "mcp.server.connectivity",
    ]);
    expect(manager.selectedPresetIds.value).toContain("mcp-operator");
    expect(manager.selectedHighRiskCount.value).toBe(0);
  });

  it("toggles selected role permission presets off", async () => {
    const { useRoleManager } = await import("./useRoleManager");
    const manager = useRoleManager();

    manager.togglePermissionPreset("view-configuration");

    expect(manager.selectedFeatures.value).toEqual([
      "module.config.view",
      "module.system.status",
    ]);
    expect(manager.selectedPresetIds.value).toContain("view-configuration");

    manager.togglePermissionPreset("view-configuration");
    manager.togglePermissionPreset("view-knowledge");

    expect(manager.selectedFeatures.value).toEqual([
      "module.datasource_catalog",
      "module.kb",
    ]);
    expect(manager.selectedPresetIds.value).toContain("view-knowledge");

    manager.togglePermissionPreset("view-knowledge");

    expect(manager.selectedFeatures.value).toEqual([]);
    expect(manager.selectedPresetIds.value).not.toContain("view-knowledge");
  });

  it("keeps shared permissions when toggling one selected preset off", async () => {
    const { useRoleManager } = await import("./useRoleManager");
    const manager = useRoleManager();

    manager.togglePermissionPreset("view-configuration");
    manager.togglePermissionPreset("audit-viewer");
    manager.togglePermissionPreset("view-configuration");

    expect(manager.selectedFeatures.value).toEqual([
      "module.admin.audit",
      "module.system.status",
    ]);
    expect(manager.selectedPresetIds.value).toEqual(["audit-viewer"]);
  });

  it("resets advanced permission controls when opening the role dialog", async () => {
    const { useRoleManager } = await import("./useRoleManager");
    const manager = useRoleManager();
    manager.advancedPermissionsOpen.value = true;

    manager.openCreateDialog();

    expect(manager.advancedPermissionsOpen.value).toBe(false);

    manager.advancedPermissionsOpen.value = true;
    manager.openEditDialog(role);

    expect(manager.advancedPermissionsOpen.value).toBe(false);
  });

  it("saves selected permissions after dependency normalization", async () => {
    const { useRoleManager } = await import("./useRoleManager");
    const manager = useRoleManager();
    manager.roleForm.value = {
      name: "MCP 查看员",
      description: "",
      permissions: [],
    };
    manager.selectedFeatures.value = ["mcp.server.connectivity"];

    await manager.saveRole();

    expect(upsertRole).toHaveBeenCalledWith("MCP 查看员", {
      name: "MCP 查看员",
      description: null,
      permissions: ["module.mcp", "mcp.server.list", "mcp.server.connectivity"],
    });
  });

  it("opens edit dialog with normalized existing permissions", async () => {
    const { useRoleManager } = await import("./useRoleManager");
    const manager = useRoleManager();

    manager.openEditDialog({ ...role, permissions: ["mcp.server.tools"] });

    expect(manager.selectedFeatures.value).toEqual([
      "module.mcp",
      "mcp.server.list",
      "mcp.server.tools",
    ]);
  });

  it("blocks built-in role deletion", async () => {
    const { useRoleManager } = await import("./useRoleManager");
    const manager = useRoleManager();

    manager.requestDeleteRole({ ...role, built_in: true });

    expect(toastError).toHaveBeenCalledWith("系统内置角色不可删除");
    expect(manager.showDeleteConfirm.value).toBe(false);
    expect(manager.roleToDelete.value).toBeNull();
  });

  it("shows backend role deletion failures", async () => {
    deleteRole.mockResolvedValueOnce({
      success: false,
      errorCode: "ROLE_DELETE_FORBIDDEN",
      errorMessage: "Role has assigned users.",
    });

    const { useRoleManager } = await import("./useRoleManager");
    const manager = useRoleManager();

    manager.requestDeleteRole(role);
    await manager.deleteRole();

    expect(deleteRole).toHaveBeenCalledWith("resource_admin");
    expect(toastError).toHaveBeenCalledWith("角色仍是系统内置角色或已分配给用户，不能删除");
    expect(listRoles).not.toHaveBeenCalled();
  });
});
