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
        "module.admin.users",
      ])
    );
  });

  it("exposes grouped enterprise permission options for role editing", async () => {
    const { useRoleManager } = await import("./useRoleManager");
    const manager = useRoleManager();

    expect(manager.featureGroups.map((group) => group.label)).toEqual([
      "特殊权限",
      "核心功能",
      "报表与仪表盘",
      "配置",
      "管理后台",
    ]);
    expect(manager.featureGroups.flatMap((group) => group.options).length).toBe(manager.featureOptions.length);
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

  it("blocks built-in role deletion", async () => {
    const { useRoleManager } = await import("./useRoleManager");
    const manager = useRoleManager();

    manager.requestDeleteRole({ ...role, built_in: true });

    expect(toastError).toHaveBeenCalledWith("系统内置角色不可删除");
    expect(manager.showDeleteConfirm.value).toBe(false);
    expect(manager.roleToDelete.value).toBeNull();
  });
});
