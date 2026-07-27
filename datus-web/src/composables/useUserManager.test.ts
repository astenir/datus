import { beforeEach, describe, expect, it, vi } from "vitest";

const listUsers = vi.fn();
const getUser = vi.fn();
const upsertUser = vi.fn();
const enableUser = vi.fn();
const disableUser = vi.fn();
const getUserRoles = vi.fn();
const updateUserRoles = vi.fn();
const listRoles = vi.fn();
const toastError = vi.fn();

vi.mock("@/lib/api", () => ({
  adminUserApi: {
    listUsers,
    getUser,
    upsertUser,
    enableUser,
    disableUser,
    getUserRoles,
    updateUserRoles,
  },
  adminRoleApi: {
    listRoles,
  },
}));

vi.mock("vue-sonner", () => ({
  toast: {
    error: toastError,
  },
}));

const user = {
  user_id: "alice",
  display_name: "Alice",
  email: "alice@example.com",
  enabled: true,
  external_user_id: "ext-alice",
  department: "数据部",
  title: "分析师",
  last_seen_at: "2026-06-23T00:00:00Z",
  role_ids: ["viewer"],
  role_count: 1,
  direct_datasource_grant_count: 2,
  created_at: "2026-06-22T00:00:00Z",
  updated_at: null,
};

describe("useUserManager", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listUsers.mockResolvedValue({ data: [] });
    getUser.mockResolvedValue({ data: user });
    listRoles.mockResolvedValue({ data: [] });
    getUserRoles.mockResolvedValue({ data: { user_id: "alice", role_ids: [] } });
  });

  it("loads users with the current enabled filter", async () => {
    listUsers.mockResolvedValue({ data: [user] });

    const { useUserManager } = await import("./useUserManager");
    const manager = useUserManager();
    manager.searchForm.value = { status: "enabled" };

    await manager.loadUsers();

    expect(listUsers).toHaveBeenCalledWith({ enabled: true, limit: 20, offset: 0 });
    expect(manager.users.value).toEqual([user]);
    expect(manager.total.value).toBe(1);
  });

  it("resets filters before reloading users", async () => {
    const { useUserManager } = await import("./useUserManager");
    const manager = useUserManager();
    manager.searchForm.value = { status: "disabled" };

    manager.handleReset();

    expect(manager.searchForm.value).toEqual({ status: "all" });
    expect(listUsers).toHaveBeenCalledWith({ enabled: undefined, limit: 20, offset: 0 });
  });

  it("opens user detail with a normalized route user id", async () => {
    getUser.mockResolvedValue({
      data: {
        ...user,
        display_name: "Alice Admin",
        roles: [{ role_id: "viewer", name: "查看员", permissions: ["chat"], built_in: false }],
        effective_permissions: ["module.chat"],
        direct_datasource_grants: [{
          subject_type: "user",
          subject_id: "alice",
          datasource_key: "fund",
          effect: "allow",
          scope: {},
        }],
        role_datasource_grants: [],
        role_datasource_grant_count: 0,
        effective_datasource_grant_count: 2,
      },
    });

    const { useUserManager } = await import("./useUserManager");
    const manager = useUserManager();

    const detailPromise = manager.openUserDetail(" alice ");

    expect(manager.showUserDetailDialog.value).toBe(true);
    expect(manager.selectedUserDetailId.value).toBe("alice");
    expect(manager.loadingUserDetail.value).toBe(true);

    await detailPromise;

    expect(getUser).toHaveBeenCalledWith("alice");
    expect(manager.selectedUserDetail.value?.display_name).toBe("Alice Admin");
    expect(manager.selectedUserDetail.value?.effective_permissions).toEqual(["module.chat"]);
    expect(manager.selectedUserDetail.value?.direct_datasource_grants?.[0]?.datasource_key).toBe("fund");
    expect(manager.userDetailError.value).toBeNull();
    expect(manager.loadingUserDetail.value).toBe(false);

    manager.closeUserDetail();

    expect(manager.showUserDetailDialog.value).toBe(false);
    expect(manager.selectedUserDetail.value).toBeNull();
    expect(manager.selectedUserDetailId.value).toBeNull();
  });

  it("uses enable and disable endpoints for user state changes", async () => {
    const { useUserManager } = await import("./useUserManager");
    const manager = useUserManager();

    await manager.setUserEnabled(user, false);
    await manager.setUserEnabled({ ...user, enabled: false }, true);

    expect(disableUser).toHaveBeenCalledWith("alice");
    expect(enableUser).toHaveBeenCalledWith("alice");
  });

  it("shows backend safety errors when disabling protected users", async () => {
    disableUser.mockResolvedValue({
      success: false,
      errorCode: "USER_DISABLE_ADMIN_FORBIDDEN",
      errorMessage: "Cannot disable an enterprise administrator.",
    });

    const { useUserManager } = await import("./useUserManager");
    const manager = useUserManager();

    await manager.setUserEnabled(user, false);

    expect(toastError).toHaveBeenCalledWith("不能禁用企业管理员；请先移除管理员角色");
    expect(listUsers).not.toHaveBeenCalled();
  });

  it("does not expose unknown user status errors", async () => {
    disableUser.mockResolvedValue({
      success: false,
      errorCode: "INTERNAL_ERROR",
      errorMessage: "RuntimeError: https://users.private failed",
    });
    const { useUserManager } = await import("./useUserManager");
    const manager = useUserManager();

    await manager.setUserEnabled(user, false);

    expect(toastError).toHaveBeenCalledWith("禁用失败，请重试");
    expect(JSON.stringify(toastError.mock.calls)).not.toContain("users.private");
  });

  it("requires a user id before upserting a user", async () => {
    const { useUserManager } = await import("./useUserManager");
    const manager = useUserManager();
    manager.newUserForm.value = {
      user_id: " ",
      display_name: "",
      email: "",
      external_user_id: "",
      department: "",
      title: "",
      enabled: true,
    };

    await manager.addUser();

    expect(toastError).toHaveBeenCalledWith("请输入用户 ID");
    expect(upsertUser).not.toHaveBeenCalled();
  });

  it("sends enterprise identity metadata when adding a user", async () => {
    const { useUserManager } = await import("./useUserManager");
    const manager = useUserManager();
    manager.newUserForm.value = {
      user_id: " alice ",
      display_name: " Alice ",
      email: " alice@example.com ",
      external_user_id: " ext-alice ",
      department: " 数据部 ",
      title: " 分析师 ",
      enabled: true,
    };

    await manager.addUser();

    expect(upsertUser).toHaveBeenCalledWith("alice", {
      display_name: "Alice",
      email: "alice@example.com",
      external_user_id: "ext-alice",
      department: "数据部",
      title: "分析师",
      enabled: true,
    });
    expect(manager.showAddUserDialog.value).toBe(false);
    expect(listUsers).toHaveBeenCalled();
  });

  it("opens an existing user in edit mode with metadata prefilled", async () => {
    const { useUserManager } = await import("./useUserManager");
    const manager = useUserManager();

    const roleLoad = manager.openEditUserDialog(user);

    expect(manager.showAddUserDialog.value).toBe(true);
    expect(manager.userDialogMode.value).toBe("edit");
    expect(manager.userDialogTitle.value).toBe("编辑用户");
    expect(manager.editingUser.value).toEqual(user);
    expect(manager.newUserForm.value).toEqual({
      user_id: "alice",
      display_name: "Alice",
      email: "alice@example.com",
      external_user_id: "ext-alice",
      department: "数据部",
      title: "分析师",
      enabled: true,
    });

    await roleLoad;
    expect(getUserRoles).toHaveBeenCalledWith("alice");
  });

  it("updates the selected user and role assignment from the edit dialog", async () => {
    getUserRoles.mockResolvedValue({ data: { user_id: "alice", role_ids: ["viewer"] } });

    const { useUserManager } = await import("./useUserManager");
    const manager = useUserManager();
    await manager.openEditUserDialog(user);
    manager.newUserForm.value = {
      ...manager.newUserForm.value,
      user_id: "bob",
      display_name: " Alice Admin ",
      email: " admin@example.com ",
      enabled: false,
    };
    manager.toggleSelectedRole("admin");

    await manager.saveUser();

    expect(upsertUser).toHaveBeenCalledWith("alice", {
      display_name: "Alice Admin",
      email: "admin@example.com",
      external_user_id: "ext-alice",
      department: "数据部",
      title: "分析师",
      enabled: false,
    });
    expect(updateUserRoles).toHaveBeenCalledWith("alice", ["viewer", "admin"]);
    expect(manager.showAddUserDialog.value).toBe(false);
    expect(manager.userDialogMode.value).toBe("create");
    expect(manager.editingUser.value).toBeNull();
    expect(listUsers).toHaveBeenCalled();
  });

  it("keeps the edit dialog open when backend blocks disabling a protected user", async () => {
    getUserRoles.mockResolvedValue({ data: { user_id: "alice", role_ids: ["viewer"] } });
    upsertUser.mockResolvedValue({
      success: false,
      errorCode: "USER_DISABLE_SELF_FORBIDDEN",
      errorMessage: "Cannot disable the current user.",
    });

    const { useUserManager } = await import("./useUserManager");
    const manager = useUserManager();
    await manager.openEditUserDialog(user);
    manager.newUserForm.value = {
      ...manager.newUserForm.value,
      enabled: false,
    };

    await manager.saveUser();

    expect(toastError).toHaveBeenCalledWith("不能禁用当前登录用户");
    expect(updateUserRoles).not.toHaveBeenCalled();
    expect(manager.showAddUserDialog.value).toBe(true);
  });

  it("keeps the edit dialog open when backend rejects ungrantable role assignment", async () => {
    getUserRoles.mockResolvedValue({ data: { user_id: "alice", role_ids: ["viewer"] } });
    upsertUser.mockResolvedValueOnce({ success: true, data: user });
    updateUserRoles.mockResolvedValueOnce({
      success: false,
      errorCode: "USER_ROLES_FORBIDDEN",
      errorMessage: "Cannot assign roles with permissions that the actor does not have.",
    });

    const { useUserManager } = await import("./useUserManager");
    const manager = useUserManager();
    await manager.openEditUserDialog(user);
    manager.toggleSelectedRole("admin");

    await manager.saveUser();

    expect(updateUserRoles).toHaveBeenCalledWith("alice", ["viewer", "admin"]);
    expect(toastError).toHaveBeenCalledWith("不能分配包含自己尚未拥有权限的角色");
    expect(manager.userDialogError.value).toBe("不能分配包含自己尚未拥有权限的角色");
    expect(manager.showAddUserDialog.value).toBe(true);
    expect(listUsers).not.toHaveBeenCalled();
  });

  it("keeps the edit dialog open while role assignment is loading", async () => {
    let resolveUserRoles: (value: { data: { user_id: string; role_ids: string[] } }) => void = () => {};
    getUserRoles.mockReturnValue(new Promise(resolve => {
      resolveUserRoles = resolve;
    }));

    const { useUserManager } = await import("./useUserManager");
    const manager = useUserManager();

    const roleLoad = manager.openEditUserDialog(user);

    expect(manager.showAddUserDialog.value).toBe(true);
    expect(manager.loadingRoleAssignment.value).toBe(true);
    expect(manager.selectedRoleIds.value).toEqual(["viewer"]);

    resolveUserRoles({ data: { user_id: "alice", role_ids: ["admin"] } });
    await roleLoad;

    expect(manager.loadingRoleAssignment.value).toBe(false);
    expect(manager.roleAssignmentLoaded.value).toBe(true);
    expect(manager.selectedRoleIds.value).toEqual(["admin"]);
  });
});
