import { computed, ref, shallowRef } from "vue";
import { toast } from "vue-sonner";

import { adminRoleApi } from "@/lib/api";
import { ROLE_PERMISSION_GROUPS, ROLE_PERMISSION_OPTIONS } from "@/lib/permission-labels";
import type { Role, RoleFormData, RoleSearchForm } from "@/types/admin";

export function useRoleManager() {
  const featureOptions = ROLE_PERMISSION_OPTIONS;
  const featureGroups = ROLE_PERMISSION_GROUPS;

  const searchForm = ref<RoleSearchForm>({
    keyword: "",
  });

  const total = shallowRef(0);
  const roles = ref<Role[]>([]);
  const loading = shallowRef(false);
  const loadingRoleDetail = shallowRef(false);
  const showRoleDetailDialog = shallowRef(false);
  const selectedRoleDetailId = shallowRef<string | null>(null);
  const selectedRoleDetail = shallowRef<Role | null>(null);
  const roleDetailError = shallowRef<string | null>(null);
  let roleDetailRequestId = 0;

  const showDialog = shallowRef(false);
  const dialogMode = shallowRef<"create" | "edit">("create");
  const editingRole = shallowRef<Role | null>(null);
  const roleForm = ref<RoleFormData>({
    name: "",
    description: "",
    permissions: [],
  });
  const saving = shallowRef(false);
  const showDeleteConfirm = shallowRef(false);
  const roleToDelete = shallowRef<Role | null>(null);
  const deleting = shallowRef(false);

  const selectedFeatures = ref<string[]>([]);

  const filteredRoles = computed(() => {
    const keyword = searchForm.value.keyword.trim().toLowerCase();
    if (!keyword) return roles.value;
    return roles.value.filter((role) =>
      [role.role_id, role.name, role.description ?? ""].some((value) => value.toLowerCase().includes(keyword))
    );
  });
  const builtInRoleCount = computed(() => roles.value.filter((role) => role.built_in).length);
  const customRoleCount = computed(() => roles.value.filter((role) => !role.built_in).length);

  async function loadRoles() {
    loading.value = true;
    try {
      const result = await adminRoleApi.listRoles();
      roles.value = result?.data ?? [];
      total.value = roles.value.length;
    } catch (err) {
      console.error("加载角色列表失败:", err);
      roles.value = [];
      total.value = 0;
    } finally {
      loading.value = false;
    }
  }

  function handleSearch() {
    return filteredRoles.value;
  }

  function handleReset() {
    searchForm.value = { keyword: "" };
  }

  async function openRoleDetail(roleId: string) {
    const normalizedRoleId = roleId.trim();
    if (!normalizedRoleId) return;

    const requestId = roleDetailRequestId + 1;
    roleDetailRequestId = requestId;
    showRoleDetailDialog.value = true;
    selectedRoleDetailId.value = normalizedRoleId;
    selectedRoleDetail.value = null;
    roleDetailError.value = null;
    loadingRoleDetail.value = true;

    try {
      const result = await adminRoleApi.getRole(normalizedRoleId);
      if (requestId !== roleDetailRequestId) return;
      selectedRoleDetail.value = result.data ?? null;
      if (!selectedRoleDetail.value) {
        roleDetailError.value = "未找到角色详情";
      }
    } catch (err) {
      if (requestId !== roleDetailRequestId) return;
      console.error("加载角色详情失败:", err);
      roleDetailError.value = "加载角色详情失败";
      toast.error("加载角色详情失败");
    } finally {
      if (requestId === roleDetailRequestId) {
        loadingRoleDetail.value = false;
      }
    }
  }

  function closeRoleDetail() {
    roleDetailRequestId += 1;
    showRoleDetailDialog.value = false;
    selectedRoleDetailId.value = null;
    selectedRoleDetail.value = null;
    roleDetailError.value = null;
    loadingRoleDetail.value = false;
  }

  function openCreateDialog() {
    dialogMode.value = "create";
    editingRole.value = null;
    roleForm.value = {
      name: "",
      description: "",
      permissions: [],
    };
    selectedFeatures.value = [];
    showDialog.value = true;
  }

  function openEditDialog(role: Role) {
    dialogMode.value = "edit";
    editingRole.value = role;
    roleForm.value = {
      name: role.name,
      description: role.description ?? "",
      permissions: role.permissions ?? [],
    };
    selectedFeatures.value = [...(role.permissions ?? [])];
    showDialog.value = true;
  }

  async function saveRole() {
    const name = roleForm.value.name.trim();
    if (!name) {
      toast.error("请填写角色名称");
      return;
    }

    const roleId = editingRole.value?.role_id ?? name;
    saving.value = true;
    try {
      await adminRoleApi.upsertRole(roleId, {
        name,
        description: roleForm.value.description.trim() || null,
        permissions: selectedFeatures.value,
      });
      showDialog.value = false;
      void loadRoles();
    } catch (err) {
      console.error("保存角色失败:", err);
      toast.error("保存失败，请重试");
    } finally {
      saving.value = false;
    }
  }

  function toggleSelectedFeature(featureCode: string) {
    selectedFeatures.value = selectedFeatures.value.includes(featureCode)
      ? selectedFeatures.value.filter(item => item !== featureCode)
      : [...selectedFeatures.value, featureCode];
  }

  function requestDeleteRole(role: Role) {
    if (role.built_in) {
      toast.error("系统内置角色不可删除");
      return;
    }

    roleToDelete.value = role;
    showDeleteConfirm.value = true;
  }

  async function deleteRole() {
    if (!roleToDelete.value) return;

    deleting.value = true;
    try {
      await adminRoleApi.deleteRole(roleToDelete.value.role_id);
      void loadRoles();
    } catch (err) {
      console.error("删除角色失败:", err);
      toast.error("删除失败，请重试");
    } finally {
      deleting.value = false;
      showDeleteConfirm.value = false;
      roleToDelete.value = null;
    }
  }

  return {
    featureOptions,
    featureGroups,
    searchForm,
    total,
    roles,
    filteredRoles,
    loading,
    loadingRoleDetail,
    showRoleDetailDialog,
    selectedRoleDetailId,
    selectedRoleDetail,
    roleDetailError,
    showDialog,
    dialogMode,
    editingRole,
    roleForm,
    saving,
    showDeleteConfirm,
    roleToDelete,
    deleting,
    selectedFeatures,
    builtInRoleCount,
    customRoleCount,
    loadRoles,
    handleSearch,
    handleReset,
    openRoleDetail,
    closeRoleDetail,
    openCreateDialog,
    openEditDialog,
    saveRole,
    toggleSelectedFeature,
    requestDeleteRole,
    deleteRole,
  };
}
