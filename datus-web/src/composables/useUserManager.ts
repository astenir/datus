import { computed, ref, shallowRef } from "vue";
import { toast } from "vue-sonner";

import { adminRoleApi, adminUserApi } from "@/lib/api";
import type { AdminUser, AdminUserDetail, AdminUserFormData, AdminUserSearchForm, AssignableRole } from "@/types/admin";

export const userStatusOptions = [
  { value: "all", label: "全部状态" },
  { value: "enabled", label: "启用" },
  { value: "disabled", label: "禁用" },
] as const;

function statusToEnabled(status: AdminUserSearchForm["status"]): boolean | undefined {
  if (status === "enabled") return true;
  if (status === "disabled") return false;
  return undefined;
}

export function useUserManager() {
  const searchForm = ref<AdminUserSearchForm>({
    status: "all",
  });

  const total = shallowRef(0);
  const users = ref<AdminUser[]>([]);
  const loading = shallowRef(false);
  const loadingUserDetail = shallowRef(false);
  const showUserDetailDialog = shallowRef(false);
  const selectedUserDetailId = shallowRef<string | null>(null);
  const selectedUserDetail = shallowRef<AdminUserDetail | null>(null);
  const userDetailError = shallowRef<string | null>(null);
  let userDetailRequestId = 0;

  const showRoleDialog = shallowRef(false);
  const selectedUser = shallowRef<AdminUser | null>(null);
  const allRoles = ref<AssignableRole[]>([]);
  const selectedRoleIds = ref<string[]>([]);
  const savingRoles = shallowRef(false);

  const showAddUserDialog = shallowRef(false);
  const newUserForm = ref<AdminUserFormData>({
    user_id: "",
    display_name: "",
    email: "",
    external_user_id: "",
    department: "",
    title: "",
    last_seen_at: "",
    enabled: true,
  });
  const savingUser = shallowRef(false);

  const activeUserCount = computed(() => users.value.filter((user) => user.enabled).length);
  const disabledUserCount = computed(() => users.value.filter((user) => !user.enabled).length);
  const roleOptions = computed(() =>
    allRoles.value.map((role) => ({
      value: role.role_id,
      label: role.name,
    }))
  );

  async function loadUsers() {
    loading.value = true;
    try {
      const result = await adminUserApi.listUsers({ enabled: statusToEnabled(searchForm.value.status) });
      users.value = result?.data ?? [];
      total.value = users.value.length;
    } catch (err) {
      console.error("加载用户列表失败:", err);
      users.value = [];
      total.value = 0;
    } finally {
      loading.value = false;
    }
  }

  async function loadRoles() {
    try {
      const result = await adminRoleApi.listRoles();
      allRoles.value = (result?.data ?? []).map((role) => ({
        role_id: role.role_id,
        name: role.name,
      }));
    } catch (err) {
      console.error("加载角色列表失败:", err);
      allRoles.value = [];
    }
  }

  function handleSearch() {
    void loadUsers();
  }

  function handleReset() {
    searchForm.value = { status: "all" };
    void loadUsers();
  }

  async function openRoleDialog(user: AdminUser) {
    selectedUser.value = user;

    try {
      const result = await adminUserApi.getUserRoles(user.user_id);
      selectedRoleIds.value = result?.data?.role_ids ?? [];
    } catch (err) {
      console.error("加载用户角色失败:", err);
      selectedRoleIds.value = [];
    }

    await loadRoles();
    showRoleDialog.value = true;
  }

  async function openUserDetail(userId: string) {
    const normalizedUserId = userId.trim();
    if (!normalizedUserId) return;

    const requestId = userDetailRequestId + 1;
    userDetailRequestId = requestId;
    showUserDetailDialog.value = true;
    selectedUserDetailId.value = normalizedUserId;
    selectedUserDetail.value = null;
    userDetailError.value = null;
    loadingUserDetail.value = true;

    try {
      const result = await adminUserApi.getUser(normalizedUserId);
      if (requestId !== userDetailRequestId) return;
      selectedUserDetail.value = result.data ?? null;
      if (!selectedUserDetail.value) {
        userDetailError.value = "未找到用户详情";
      }
    } catch (err) {
      if (requestId !== userDetailRequestId) return;
      console.error("加载用户详情失败:", err);
      userDetailError.value = "加载用户详情失败";
      toast.error("加载用户详情失败");
    } finally {
      if (requestId === userDetailRequestId) {
        loadingUserDetail.value = false;
      }
    }
  }

  function closeUserDetail() {
    userDetailRequestId += 1;
    showUserDetailDialog.value = false;
    selectedUserDetailId.value = null;
    selectedUserDetail.value = null;
    userDetailError.value = null;
    loadingUserDetail.value = false;
  }

  async function saveRoles() {
    if (!selectedUser.value) return;

    savingRoles.value = true;
    try {
      await adminUserApi.updateUserRoles(selectedUser.value.user_id, selectedRoleIds.value);
      showRoleDialog.value = false;
      void loadUsers();
    } catch (err) {
      console.error("保存角色失败:", err);
      toast.error("保存失败，请重试");
    } finally {
      savingRoles.value = false;
    }
  }

  function toggleSelectedRole(roleId: string) {
    selectedRoleIds.value = selectedRoleIds.value.includes(roleId)
      ? selectedRoleIds.value.filter(item => item !== roleId)
      : [...selectedRoleIds.value, roleId];
  }

  async function setUserEnabled(user: AdminUser, enabled: boolean) {
    try {
      if (enabled) {
        await adminUserApi.enableUser(user.user_id);
      } else {
        await adminUserApi.disableUser(user.user_id);
      }
      void loadUsers();
    } catch (err) {
      console.error("更新用户状态失败:", err);
      toast.error("更新失败，请重试");
    }
  }

  function openAddUserDialog() {
    newUserForm.value = {
      user_id: "",
      display_name: "",
      email: "",
      external_user_id: "",
      department: "",
      title: "",
      last_seen_at: "",
      enabled: true,
    };
    showAddUserDialog.value = true;
  }

  async function addUser() {
    const userId = newUserForm.value.user_id.trim();
    if (!userId) {
      toast.error("请输入用户 ID");
      return;
    }

    savingUser.value = true;
    try {
      await adminUserApi.upsertUser(userId, {
        display_name: newUserForm.value.display_name.trim() || null,
        email: newUserForm.value.email.trim() || null,
        external_user_id: newUserForm.value.external_user_id.trim() || null,
        department: newUserForm.value.department.trim() || null,
        title: newUserForm.value.title.trim() || null,
        last_seen_at: newUserForm.value.last_seen_at.trim() || null,
        enabled: newUserForm.value.enabled,
      });
      showAddUserDialog.value = false;
      void loadUsers();
    } catch (err) {
      console.error("保存用户失败:", err);
      toast.error("保存失败，请重试");
    } finally {
      savingUser.value = false;
    }
  }

  return {
    statusOptions: userStatusOptions,
    searchForm,
    total,
    users,
    loading,
    loadingUserDetail,
    showUserDetailDialog,
    selectedUserDetailId,
    selectedUserDetail,
    userDetailError,
    showRoleDialog,
    selectedUser,
    allRoles,
    selectedRoleIds,
    savingRoles,
    showAddUserDialog,
    newUserForm,
    savingUser,
    activeUserCount,
    disabledUserCount,
    roleOptions,
    loadUsers,
    loadRoles,
    handleSearch,
    handleReset,
    openUserDetail,
    closeUserDetail,
    openRoleDialog,
    saveRoles,
    toggleSelectedRole,
    setUserEnabled,
    openAddUserDialog,
    addUser,
  };
}
