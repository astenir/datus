import { beforeEach, describe, expect, it, vi } from "vitest";

const listUsers = vi.fn();
const listAssignableRoles = vi.fn();
const getUserRoles = vi.fn();
const updateUserRoles = vi.fn();
const updateUserStatus = vi.fn();
const createUser = vi.fn();
const toastError = vi.fn();

vi.mock("@/lib/api", () => ({
  adminUserApi: {
    listUsers,
    listAssignableRoles,
    getUserRoles,
    updateUserRoles,
    updateUserStatus,
    createUser,
  },
}));

vi.mock("vue-sonner", () => ({
  toast: {
    error: toastError,
  },
}));

const user = {
  id: 1,
  user_id: "alice",
  username: "alice",
  realname: "Alice",
  email: "alice@example.com",
  department: "IT",
  status: "active",
  is_builtin: false,
  created_at: "2026-06-22T00:00:00Z",
  last_login_at: null,
  login_count: 0,
  roles: ["资源管理员"],
};

describe("useUserManager", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listUsers.mockResolvedValue({ data: { users: [], total: 0, page: 1, size: 20 } });
    listAssignableRoles.mockResolvedValue({ data: { roles: [] } });
    getUserRoles.mockResolvedValue({ data: [] });
  });

  it("loads users with current filters", async () => {
    listUsers.mockResolvedValue({
      data: {
        users: [user],
        total: 1,
        page: 1,
        size: 20,
      },
    });

    const { useUserManager } = await import("./useUserManager");
    const manager = useUserManager();
    manager.searchForm.value = {
      keyword: "alice",
      status: "active",
    };

    await manager.loadUsers();

    expect(listUsers).toHaveBeenCalledWith({
      page: 1,
      size: 20,
      keyword: "alice",
      status: "active",
    });
    expect(manager.users.value).toEqual([user]);
    expect(manager.total.value).toBe(1);
  });

  it("resets filters before reloading users", async () => {
    const { useUserManager } = await import("./useUserManager");
    const manager = useUserManager();
    manager.searchForm.value = {
      keyword: "alice",
      status: "disabled",
    };
    manager.page.value = 2;

    manager.handleReset();

    expect(manager.searchForm.value).toEqual({ keyword: "", status: "" });
    expect(manager.page.value).toBe(1);
    expect(listUsers).toHaveBeenCalledWith({
      page: 1,
      size: 20,
      keyword: "",
      status: "",
    });
  });

  it("opens role dialog with current and assignable roles", async () => {
    getUserRoles.mockResolvedValue({ data: [{ id: 3, role_code: "viewer", role_name: "查看员" }] });
    listAssignableRoles.mockResolvedValue({
      data: {
        roles: [{ id: 3, role_code: "viewer", role_name: "查看员", role_type: "resource" }],
      },
    });

    const { useUserManager } = await import("./useUserManager");
    const manager = useUserManager();

    await manager.openRoleDialog(user);

    expect(getUserRoles).toHaveBeenCalledWith("alice");
    expect(listAssignableRoles).toHaveBeenCalled();
    expect(manager.selectedUser.value).toEqual(user);
    expect(manager.selectedRoleIds.value).toEqual([3]);
    expect(manager.showRoleDialog.value).toBe(true);
    expect(manager.roleOptions.value).toEqual([{ value: 3, label: "查看员 (资源)" }]);
  });

  it("saves role assignment for selected user", async () => {
    const { useUserManager } = await import("./useUserManager");
    const manager = useUserManager();
    manager.selectedUser.value = user;
    manager.selectedRoleIds.value = [1, 2];

    await manager.saveRoles();

    expect(updateUserRoles).toHaveBeenCalledWith("alice", [1, 2]);
    expect(manager.showRoleDialog.value).toBe(false);
    expect(listUsers).toHaveBeenCalled();
  });

  it("requires a user id before creating user", async () => {
    const { useUserManager } = await import("./useUserManager");
    const manager = useUserManager();
    manager.newUserForm.value = {
      user_id: " ",
      username: "",
      realname: "",
      email: "",
      department: "",
    };

    await manager.addUser();

    expect(toastError).toHaveBeenCalledWith("请输入用户 ID");
    expect(createUser).not.toHaveBeenCalled();
  });
});
