import { computed, ref, shallowRef } from "vue";
import { toast } from "vue-sonner";

import { adminRoleApi, adminUserApi } from "@/lib/api";
import type {
  AdminUser,
  AdminUserDetail,
  AdminUserFormData,
  AdminUserRolesData,
  AdminUserSearchForm,
  ApiResponse,
  AssignableRole,
} from "@/types/admin";

export const userStatusOptions = [
  { value: "all", label: "全部状态" },
  { value: "enabled", label: "启用" },
  { value: "disabled", label: "禁用" },
] as const;

type UserDialogMode = "create" | "edit";

function statusToEnabled(status: AdminUserSearchForm["status"]): boolean | undefined {
  if (status === "enabled") return true;
  if (status === "disabled") return false;
  return undefined;
}

function emptyUserForm(): AdminUserFormData {
  return {
    user_id: "",
    display_name: "",
    email: "",
    external_user_id: "",
    department: "",
    title: "",
    enabled: true,
  };
}

function userFormFromUser(user: AdminUser): AdminUserFormData {
  return {
    user_id: user.user_id,
    display_name: user.display_name ?? "",
    email: user.email ?? "",
    external_user_id: user.external_user_id ?? "",
    department: user.department ?? "",
    title: user.title ?? "",
    enabled: user.enabled,
  };
}

function userStatusFailureMessage(result: ApiResponse<AdminUser>, enabled: boolean): string {
  if (result.errorCode === "USER_DISABLE_SELF_FORBIDDEN") return "不能禁用当前登录用户";
  if (result.errorCode === "USER_DISABLE_ADMIN_FORBIDDEN") return "不能禁用企业管理员；请先移除管理员角色";
  return enabled ? "启用失败，请重试" : "禁用失败，请重试";
}

function userSaveFailureMessage(result: ApiResponse<AdminUser>): string {
  if (result.errorCode === "USER_DISABLE_SELF_FORBIDDEN") return "不能禁用当前登录用户";
  if (result.errorCode === "USER_DISABLE_ADMIN_FORBIDDEN") return "不能禁用企业管理员；请先移除管理员角色";
  return "保存失败，请重试";
}

function userRoleAssignmentFailureMessage(result: ApiResponse<AdminUserRolesData>): string {
  if (result.errorCode === "USER_ROLES_FORBIDDEN") return "不能分配包含自己尚未拥有权限的角色";
  return "角色分配失败，请重试";
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

  const allRoles = ref<AssignableRole[]>([]);
  const selectedRoleIds = ref<string[]>([]);
  const loadingRoleAssignment = shallowRef(false);
  const roleAssignmentLoaded = shallowRef(false);
  const roleAssignmentError = shallowRef<string | null>(null);
  let roleAssignmentRequestId = 0;

  const showAddUserDialog = shallowRef(false);
  const userDialogMode = shallowRef<UserDialogMode>("create");
  const editingUser = shallowRef<AdminUser | null>(null);
  const newUserForm = ref<AdminUserFormData>(emptyUserForm());
  const userDialogError = shallowRef<string | null>(null);
  const savingUser = shallowRef(false);

  const activeUserCount = computed(() => users.value.filter((user) => user.enabled).length);
  const disabledUserCount = computed(() => users.value.filter((user) => !user.enabled).length);
  const isEditingUser = computed(() => userDialogMode.value === "edit");
  const userDialogTitle = computed(() => isEditingUser.value ? "编辑用户" : "新增用户");
  const roleOptions = computed(() =>
    allRoles.value.map((role) => ({
      value: role.role_id,
      label: role.name,
    }))
  );
  const selectedRoleCount = computed(() => selectedRoleIds.value.length);

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

  function handleSearch() {
    void loadUsers();
  }

  function handleReset() {
    searchForm.value = { status: "all" };
    void loadUsers();
  }

  async function loadRoleAssignment(user: AdminUser) {
    const requestId = roleAssignmentRequestId + 1;
    roleAssignmentRequestId = requestId;
    selectedRoleIds.value = [...(user.role_ids ?? [])];
    loadingRoleAssignment.value = true;
    roleAssignmentLoaded.value = false;
    roleAssignmentError.value = null;

    try {
      const [userRoleResult, roleResult] = await Promise.all([
        adminUserApi.getUserRoles(user.user_id),
        adminRoleApi.listRoles(),
      ]);
      if (requestId !== roleAssignmentRequestId) return;
      selectedRoleIds.value = userRoleResult?.data?.role_ids ?? [];
      allRoles.value = (roleResult?.data ?? []).map((role) => ({
        role_id: role.role_id,
        name: role.name,
      }));
      roleAssignmentLoaded.value = true;
    } catch (err) {
      if (requestId !== roleAssignmentRequestId) return;
      console.error("加载用户角色失败:", err);
      selectedRoleIds.value = [...(user.role_ids ?? [])];
      roleAssignmentError.value = "加载角色失败";
    } finally {
      if (requestId === roleAssignmentRequestId) {
        loadingRoleAssignment.value = false;
      }
    }
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

  function toggleSelectedRole(roleId: string) {
    selectedRoleIds.value = selectedRoleIds.value.includes(roleId)
      ? selectedRoleIds.value.filter(item => item !== roleId)
      : [...selectedRoleIds.value, roleId];
  }

  async function setUserEnabled(user: AdminUser, enabled: boolean) {
    try {
      const result = enabled
        ? await adminUserApi.enableUser(user.user_id)
        : await adminUserApi.disableUser(user.user_id);
      if (result?.success === false) {
        toast.error(userStatusFailureMessage(result, enabled));
        return;
      }
      void loadUsers();
    } catch (err) {
      console.error("更新用户状态失败:", err);
      toast.error("更新失败，请重试");
    }
  }

  function openAddUserDialog() {
    roleAssignmentRequestId += 1;
    userDialogMode.value = "create";
    editingUser.value = null;
    selectedRoleIds.value = [];
    roleAssignmentLoaded.value = false;
    roleAssignmentError.value = null;
    loadingRoleAssignment.value = false;
    newUserForm.value = emptyUserForm();
    userDialogError.value = null;
    showAddUserDialog.value = true;
  }

  async function openEditUserDialog(user: AdminUser) {
    userDialogMode.value = "edit";
    editingUser.value = user;
    selectedRoleIds.value = [...(user.role_ids ?? [])];
    newUserForm.value = userFormFromUser(user);
    userDialogError.value = null;
    showAddUserDialog.value = true;
    await loadRoleAssignment(user);
  }

  function closeUserDialog() {
    roleAssignmentRequestId += 1;
    showAddUserDialog.value = false;
    editingUser.value = null;
    selectedRoleIds.value = [];
    roleAssignmentLoaded.value = false;
    roleAssignmentError.value = null;
    loadingRoleAssignment.value = false;
    userDialogMode.value = "create";
    userDialogError.value = null;
  }

  async function saveUser() {
    const userId = isEditingUser.value
      ? editingUser.value?.user_id ?? newUserForm.value.user_id.trim()
      : newUserForm.value.user_id.trim();
    if (!userId) {
      userDialogError.value = "请输入用户 ID";
      toast.error("请输入用户 ID");
      return;
    }
    if (isEditingUser.value && loadingRoleAssignment.value) {
      userDialogError.value = "请等待角色加载完成";
      toast.error("请等待角色加载完成");
      return;
    }
    if (isEditingUser.value && roleAssignmentError.value) {
      userDialogError.value = "角色加载失败，请重新打开后再保存";
      toast.error("角色加载失败，请重新打开后再保存");
      return;
    }

    savingUser.value = true;
    userDialogError.value = null;
    try {
      const result = await adminUserApi.upsertUser(userId, {
        display_name: newUserForm.value.display_name.trim() || null,
        email: newUserForm.value.email.trim() || null,
        external_user_id: newUserForm.value.external_user_id.trim() || null,
        department: newUserForm.value.department.trim() || null,
        title: newUserForm.value.title.trim() || null,
        enabled: newUserForm.value.enabled,
      });
      if (result?.success === false) {
        const message = userSaveFailureMessage(result);
        userDialogError.value = message;
        toast.error(message);
        return;
      }
      if (isEditingUser.value && roleAssignmentLoaded.value && !roleAssignmentError.value) {
        const roleResult = await adminUserApi.updateUserRoles(userId, selectedRoleIds.value);
        if (roleResult?.success === false) {
          const message = userRoleAssignmentFailureMessage(roleResult);
          userDialogError.value = message;
          toast.error(message);
          return;
        }
      }
      closeUserDialog();
      void loadUsers();
    } catch (err) {
      console.error("保存用户失败:", err);
      userDialogError.value = "保存失败，请重试";
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
    allRoles,
    selectedRoleIds,
    loadingRoleAssignment,
    roleAssignmentLoaded,
    roleAssignmentError,
    showAddUserDialog,
    newUserForm,
    userDialogError,
    savingUser,
    activeUserCount,
    disabledUserCount,
    userDialogMode,
    editingUser,
    isEditingUser,
    userDialogTitle,
    roleOptions,
    selectedRoleCount,
    loadUsers,
    handleSearch,
    handleReset,
    openUserDetail,
    closeUserDetail,
    toggleSelectedRole,
    setUserEnabled,
    openAddUserDialog,
    openEditUserDialog,
    closeUserDialog,
    saveUser,
    addUser: saveUser,
  };
}
