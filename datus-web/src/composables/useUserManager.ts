import { computed, ref, shallowRef } from "vue";
import { toast } from "vue-sonner";

import { adminUserApi } from "@/lib/api";
import type { AdminUser, AdminUserFormData, AdminUserSearchForm, AssignableRole } from "@/types/admin";

export const userStatusOptions = [
  { value: "", label: "全部状态" },
  { value: "active", label: "启用" },
  { value: "inactive", label: "未激活" },
  { value: "disabled", label: "禁用" },
];

export function useUserManager() {
  const searchForm = ref<AdminUserSearchForm>({
    keyword: "",
    status: "",
  });

  const page = shallowRef(1);
  const size = shallowRef(20);
  const total = shallowRef(0);
  const users = ref<AdminUser[]>([]);
  const loading = shallowRef(false);

  const showRoleDialog = shallowRef(false);
  const selectedUser = shallowRef<AdminUser | null>(null);
  const allRoles = ref<AssignableRole[]>([]);
  const selectedRoleIds = ref<number[]>([]);
  const savingRoles = shallowRef(false);

  const showAddUserDialog = shallowRef(false);
  const newUserForm = ref<AdminUserFormData>({
    user_id: "",
    username: "",
    realname: "",
    email: "",
    department: "",
  });
  const savingUser = shallowRef(false);

  const totalPages = computed(() => Math.ceil(total.value / size.value) || 1);
  const activeUserCount = computed(() => users.value.filter((user) => user.status === "active").length);
  const assignedUserCount = computed(() => users.value.filter((user) => user.roles?.length).length);
  const roleOptions = computed(() =>
    allRoles.value.map((role) => ({
      value: role.id,
      label: `${role.role_name} (${role.role_type === "resource" ? "资源" : "数据源"})`,
    }))
  );

  async function loadUsers() {
    loading.value = true;
    try {
      const result = await adminUserApi.listUsers({
        page: page.value,
        size: size.value,
        keyword: searchForm.value.keyword,
        status: searchForm.value.status,
      });
      users.value = result?.data?.users || [];
      total.value = result?.data?.total || 0;
    } catch (err) {
      console.error("加载用户列表失败:", err);
      users.value = [];
    } finally {
      loading.value = false;
    }
  }

  async function loadRoles() {
    try {
      const result = await adminUserApi.listAssignableRoles();
      allRoles.value = result?.data?.roles || [];
    } catch (err) {
      console.error("加载角色列表失败:", err);
      allRoles.value = [];
    }
  }

  function handleSearch() {
    page.value = 1;
    void loadUsers();
  }

  function handleReset() {
    searchForm.value = { keyword: "", status: "" };
    page.value = 1;
    void loadUsers();
  }

  function goToPage(nextPage: number) {
    if (nextPage < 1 || nextPage > totalPages.value) return;
    page.value = nextPage;
    void loadUsers();
  }

  async function openRoleDialog(user: AdminUser) {
    selectedUser.value = user;

    try {
      const result = await adminUserApi.getUserRoles(user.user_id);
      selectedRoleIds.value = (result?.data || []).map((role) => role.id);
    } catch (err) {
      console.error("加载用户角色失败:", err);
      selectedRoleIds.value = [];
    }

    await loadRoles();
    showRoleDialog.value = true;
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

  async function updateStatus(user: AdminUser, status: string) {
    try {
      await adminUserApi.updateUserStatus(user.user_id, status);
      void loadUsers();
    } catch (err) {
      console.error("更新状态失败:", err);
      toast.error("更新失败，请重试");
    }
  }

  function openAddUserDialog() {
    newUserForm.value = {
      user_id: "",
      username: "",
      realname: "",
      email: "",
      department: "",
    };
    showAddUserDialog.value = true;
  }

  async function addUser() {
    if (!newUserForm.value.user_id.trim()) {
      toast.error("请输入用户 ID");
      return;
    }

    savingUser.value = true;
    try {
      await adminUserApi.createUser(newUserForm.value);
      showAddUserDialog.value = false;
      void loadUsers();
    } catch (err) {
      console.error("新增用户失败:", err);
      toast.error("新增失败，请重试");
    } finally {
      savingUser.value = false;
    }
  }

  return {
    statusOptions: userStatusOptions,
    searchForm,
    page,
    size,
    total,
    users,
    loading,
    showRoleDialog,
    selectedUser,
    allRoles,
    selectedRoleIds,
    savingRoles,
    showAddUserDialog,
    newUserForm,
    savingUser,
    totalPages,
    activeUserCount,
    assignedUserCount,
    roleOptions,
    loadUsers,
    loadRoles,
    handleSearch,
    handleReset,
    goToPage,
    openRoleDialog,
    saveRoles,
    updateStatus,
    openAddUserDialog,
    addUser,
  };
}
