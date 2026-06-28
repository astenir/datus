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

    expect(listUsers).toHaveBeenCalledWith({ enabled: true });
    expect(manager.users.value).toEqual([user]);
    expect(manager.total.value).toBe(1);
  });

  it("resets filters before reloading users", async () => {
    const { useUserManager } = await import("./useUserManager");
    const manager = useUserManager();
    manager.searchForm.value = { status: "disabled" };

    manager.handleReset();

    expect(manager.searchForm.value).toEqual({ status: "all" });
    expect(listUsers).toHaveBeenCalledWith({ enabled: undefined });
  });

  it("opens role dialog with current and assignable role ids", async () => {
    getUserRoles.mockResolvedValue({ data: { user_id: "alice", role_ids: ["viewer"] } });
    listRoles.mockResolvedValue({
      data: [{ role_id: "viewer", name: "查看员", description: null, permissions: [], built_in: false }],
    });

    const { useUserManager } = await import("./useUserManager");
    const manager = useUserManager();

    await manager.openRoleDialog(user);

    expect(getUserRoles).toHaveBeenCalledWith("alice");
    expect(listRoles).toHaveBeenCalled();
    expect(manager.selectedUser.value).toEqual(user);
    expect(manager.selectedRoleIds.value).toEqual(["viewer"]);
    expect(manager.showRoleDialog.value).toBe(true);
    expect(manager.roleOptions.value).toEqual([{ value: "viewer", label: "查看员" }]);
  });

  it("opens user detail with a normalized route user id", async () => {
    getUser.mockResolvedValue({ data: { ...user, display_name: "Alice Admin" } });

    const { useUserManager } = await import("./useUserManager");
    const manager = useUserManager();

    const detailPromise = manager.openUserDetail(" alice ");

    expect(manager.showUserDetailDialog.value).toBe(true);
    expect(manager.selectedUserDetailId.value).toBe("alice");
    expect(manager.loadingUserDetail.value).toBe(true);

    await detailPromise;

    expect(getUser).toHaveBeenCalledWith("alice");
    expect(manager.selectedUserDetail.value?.display_name).toBe("Alice Admin");
    expect(manager.userDetailError.value).toBeNull();
    expect(manager.loadingUserDetail.value).toBe(false);

    manager.closeUserDetail();

    expect(manager.showUserDetailDialog.value).toBe(false);
    expect(manager.selectedUserDetail.value).toBeNull();
    expect(manager.selectedUserDetailId.value).toBeNull();
  });

  it("saves role assignment for selected user", async () => {
    const { useUserManager } = await import("./useUserManager");
    const manager = useUserManager();
    manager.selectedUser.value = user;
    manager.selectedRoleIds.value = ["admin", "viewer"];

    await manager.saveRoles();

    expect(updateUserRoles).toHaveBeenCalledWith("alice", ["admin", "viewer"]);
    expect(manager.showRoleDialog.value).toBe(false);
    expect(listUsers).toHaveBeenCalled();
  });

  it("uses enable and disable endpoints for user state changes", async () => {
    const { useUserManager } = await import("./useUserManager");
    const manager = useUserManager();

    await manager.setUserEnabled(user, false);
    await manager.setUserEnabled({ ...user, enabled: false }, true);

    expect(disableUser).toHaveBeenCalledWith("alice");
    expect(enableUser).toHaveBeenCalledWith("alice");
  });

  it("requires a user id before upserting a user", async () => {
    const { useUserManager } = await import("./useUserManager");
    const manager = useUserManager();
    manager.newUserForm.value = {
      user_id: " ",
      display_name: "",
      email: "",
      enabled: true,
    };

    await manager.addUser();

    expect(toastError).toHaveBeenCalledWith("请输入用户 ID");
    expect(upsertUser).not.toHaveBeenCalled();
  });
});
