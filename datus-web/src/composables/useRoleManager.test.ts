import { beforeEach, describe, expect, it, vi } from "vitest";

const listRoles = vi.fn();
const createRole = vi.fn();
const updateRole = vi.fn();
const deleteRole = vi.fn();
const getRolePermissions = vi.fn();
const updateRolePermissions = vi.fn();
const getAgent = vi.fn();
const listCatalog = vi.fn();
const toastError = vi.fn();

vi.mock("@/lib/api", () => ({
  adminRoleApi: {
    listRoles,
    createRole,
    updateRole,
    deleteRole,
    getRolePermissions,
    updateRolePermissions,
  },
  configApi: {
    getAgent,
  },
  catalogApi: {
    list: listCatalog,
  },
}));

vi.mock("@/composables/useConnection", () => ({
  useConnection: () => ({
    effectiveBase: () => "",
  }),
}));

vi.mock("vue-sonner", () => ({
  toast: {
    error: toastError,
  },
}));

const role = {
  id: 7,
  role_code: "resource_admin",
  role_name: "资源管理员",
  role_type: "resource",
  description: "desc",
  is_system: false,
  created_at: "2026-06-22T00:00:00Z",
  user_count: 2,
};

describe("useRoleManager", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listRoles.mockResolvedValue({ data: { roles: [], total: 0, page: 1, size: 20 } });
    getAgent.mockResolvedValue({ datasources: {}, current_datasource: null });
    listCatalog.mockResolvedValue({ databases: [] });
  });

  it("loads roles with current filters", async () => {
    listRoles.mockResolvedValue({
      data: {
        roles: [role],
        total: 1,
        page: 1,
        size: 20,
      },
    });

    const { useRoleManager } = await import("./useRoleManager");
    const manager = useRoleManager();
    manager.searchForm.value = {
      role_type: "resource",
      keyword: "管理员",
    };

    await manager.loadRoles();

    expect(listRoles).toHaveBeenCalledWith({
      page: 1,
      size: 20,
      roleType: "resource",
      keyword: "管理员",
    });
    expect(manager.roles.value).toEqual([role]);
    expect(manager.total.value).toBe(1);
  });

  it("resets filters before reloading roles", async () => {
    const { useRoleManager } = await import("./useRoleManager");
    const manager = useRoleManager();
    manager.searchForm.value = {
      role_type: "datasource",
      keyword: "ods",
    };
    manager.page.value = 3;

    manager.handleReset();

    expect(manager.searchForm.value).toEqual({ role_type: "", keyword: "" });
    expect(manager.page.value).toBe(1);
    expect(listRoles).toHaveBeenCalledWith({
      page: 1,
      size: 20,
      roleType: "",
      keyword: "",
    });
  });

  it("keeps pagination inside valid bounds", async () => {
    const { useRoleManager } = await import("./useRoleManager");
    const manager = useRoleManager();
    manager.total.value = 40;

    manager.goToPage(2);
    manager.goToPage(3);
    manager.goToPage(0);

    expect(manager.page.value).toBe(2);
    expect(listRoles).toHaveBeenCalledTimes(1);
  });

  it("creates a role and saves selected permissions", async () => {
    createRole.mockResolvedValue({ success: true, data: { role_id: 11 } });

    const { useRoleManager } = await import("./useRoleManager");
    const manager = useRoleManager();
    manager.roleForm.value = {
      role_code: "resource_viewer",
      role_name: "资源查看员",
      role_type: "resource",
      description: "read only",
    };
    manager.selectedFeatures.value = ["dashboard"];

    await manager.saveRole();

    expect(createRole).toHaveBeenCalledWith({
      role_code: "resource_viewer",
      role_name: "资源查看员",
      role_type: "resource",
      description: "read only",
    });
    expect(updateRolePermissions).toHaveBeenCalledWith(11, [
      {
        permission_type: "feature",
        resource_code: "dashboard",
        permission_value: "allow",
      },
    ]);
    expect(manager.showDialog.value).toBe(false);
  });

  it("blocks system role deletion", async () => {
    const { useRoleManager } = await import("./useRoleManager");
    const manager = useRoleManager();

    manager.requestDeleteRole({ ...role, is_system: true });

    expect(toastError).toHaveBeenCalledWith("系统内置角色不可删除");
    expect(manager.showDeleteConfirm.value).toBe(false);
    expect(manager.roleToDelete.value).toBeNull();
  });
});
