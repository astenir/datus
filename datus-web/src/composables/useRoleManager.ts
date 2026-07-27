import { computed, ref, shallowRef } from "vue";
import { toast } from "vue-sonner";

import { adminRoleApi } from "@/lib/api";
import { useAdminPagination } from "@/composables/useAdminPagination";
import {
  ROLE_PERMISSION_GROUPS,
  ROLE_PERMISSION_OPTIONS,
  ROLE_PERMISSION_PRESET_GROUPS,
  ROLE_PERMISSION_PRESETS,
  normalizePermissionSelection,
  permissionPresetSelected,
  togglePermissionPresetSelection,
  togglePermissionSelection,
} from "@/lib/permission-labels";
import type { Role, RoleFormData, RoleSearchForm } from "@/types/admin";

interface BackendFailure {
  errorCode?: string;
  errorMessage?: string;
}

const ROLE_ID_PATTERN = /^[A-Za-z0-9_-]+$/;

function roleSaveFailureMessage(result: BackendFailure): string {
  if (result.errorCode === "ROLE_PERMISSION_FORBIDDEN") return "不能授予自己尚未拥有的权限";
  return "保存失败，请重试";
}

function roleDeleteFailureMessage(result: BackendFailure): string {
  if (result.errorCode === "ROLE_DELETE_FORBIDDEN") return "角色仍是系统内置角色或已分配给用户，不能删除";
  return "删除失败，请重试";
}

export function useRoleManager() {
  const featureOptions = ROLE_PERMISSION_OPTIONS;
  const featureGroups = ROLE_PERMISSION_GROUPS;
  const permissionPresets = ROLE_PERMISSION_PRESETS;
  const permissionPresetGroups = ROLE_PERMISSION_PRESET_GROUPS;

  const searchForm = ref<RoleSearchForm>({
    keyword: "",
  });

  const total = shallowRef(0);
  const pagination = useAdminPagination();
  const roles = ref<Role[]>([]);
  const loading = shallowRef(false);
  const loadingRoleDetail = shallowRef(false);
  const showRoleDetailDialog = shallowRef(false);
  const selectedRoleDetailId = shallowRef<string | null>(null);
  const selectedRoleDetail = shallowRef<Role | null>(null);
  const roleDetailError = shallowRef<string | null>(null);
  let roleDetailRequestId = 0;
  let roleListRequestId = 0;
  let listFilters: { builtIn?: boolean; search?: string } | null = null;

  const showDialog = shallowRef(false);
  const dialogMode = shallowRef<"create" | "edit">("create");
  const editingRole = shallowRef<Role | null>(null);
  const roleDialogError = shallowRef<string | null>(null);
  const roleForm = ref<RoleFormData>({
    role_id: "",
    name: "",
    description: "",
    permissions: [],
  });
  const roleValidationRequested = shallowRef(false);
  const saving = shallowRef(false);
  const showDeleteConfirm = shallowRef(false);
  const roleToDelete = shallowRef<Role | null>(null);
  const deleting = shallowRef(false);

  const selectedFeatures = ref<string[]>([]);
  const advancedPermissionsOpen = shallowRef(false);

  const filteredRoles = computed(() => {
    const keyword = searchForm.value.keyword.trim().toLowerCase();
    if (!keyword) return roles.value;
    return roles.value.filter((role) =>
      [role.role_id, role.name, role.description ?? ""].some((value) => value.toLowerCase().includes(keyword))
    );
  });
  const builtInRoleCount = computed(() => roles.value.filter((role) => role.built_in).length);
  const customRoleCount = computed(() => roles.value.filter((role) => !role.built_in).length);
  const selectedPermissionCount = computed(() => selectedFeatures.value.length);
  const selectedHighRiskCount = computed(() =>
    selectedFeatures.value.filter((permission) =>
      featureOptions.find((option) => option.value === permission)?.risk === "high"
    ).length
  );
  const selectedPresetIds = computed(() =>
    permissionPresets
      .filter((preset) => permissionPresetSelected(selectedFeatures.value, preset))
      .map((preset) => preset.id)
  );
  const roleIdValidationError = computed(() => {
    if (dialogMode.value === "edit") return null;
    const roleId = roleForm.value.role_id.trim();
    if (!roleId) return roleValidationRequested.value ? "请填写 Role ID" : null;
    if (!ROLE_ID_PATTERN.test(roleId)) return "Role ID 仅支持英文字母、数字、下划线和连字符";
    return null;
  });

  async function loadRoles() {
    const requestId = roleListRequestId + 1;
    roleListRequestId = requestId;
    loading.value = true;
    try {
      const result = await adminRoleApi.listRoles({
        ...(listFilters ?? {}),
        limit: pagination.pageSize.value,
        offset: pagination.offset.value,
      });
      if (requestId !== roleListRequestId) return;
      roles.value = pagination.applyResponse(result);
      total.value = roles.value.length;
    } catch (err) {
      if (requestId !== roleListRequestId) return;
      console.error("加载角色列表失败:", err);
      roles.value = [];
      total.value = 0;
    } finally {
      if (requestId === roleListRequestId) {
        loading.value = false;
      }
    }
  }

  function applyListFilters(filters: { builtIn?: boolean; search?: string }) {
    listFilters = filters;
    pagination.reset();
    void loadRoles();
  }

  function loadNextPage() {
    if (pagination.prepareNext()) void loadRoles();
  }

  function loadPreviousPage() {
    if (pagination.preparePrevious()) void loadRoles();
  }

  function setPageSize(value: number) {
    if (pagination.setPageSize(value)) void loadRoles();
  }

  function handleSearch() {
    return filteredRoles.value;
  }

  function handleReset() {
    searchForm.value = { keyword: "" };
    listFilters = null;
    pagination.reset();
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
      role_id: "",
      name: "",
      description: "",
      permissions: [],
    };
    roleValidationRequested.value = false;
    selectedFeatures.value = [];
    advancedPermissionsOpen.value = false;
    roleDialogError.value = null;
    showDialog.value = true;
  }

  function openEditDialog(role: Role) {
    dialogMode.value = "edit";
    editingRole.value = role;
    roleForm.value = {
      role_id: role.role_id,
      name: role.name,
      description: role.description ?? "",
      permissions: role.permissions ?? [],
    };
    roleValidationRequested.value = false;
    selectedFeatures.value = normalizePermissionSelection(role.permissions ?? []);
    advancedPermissionsOpen.value = false;
    roleDialogError.value = null;
    showDialog.value = true;
  }

  async function saveRole() {
    roleValidationRequested.value = true;
    if (roleIdValidationError.value) {
      toast.error(roleIdValidationError.value);
      return;
    }

    const name = roleForm.value.name.trim();
    if (!name) {
      roleDialogError.value = "请填写角色名称";
      toast.error("请填写角色名称");
      return;
    }

    const roleId = editingRole.value?.role_id ?? roleForm.value.role_id.trim();
    saving.value = true;
    roleDialogError.value = null;
    try {
      const result = await adminRoleApi.upsertRole(roleId, {
        name,
        description: roleForm.value.description.trim() || null,
        permissions: normalizePermissionSelection(selectedFeatures.value),
      });
      if (result?.success === false) {
        const message = roleSaveFailureMessage(result);
        roleDialogError.value = message;
        toast.error(message);
        return;
      }
      showDialog.value = false;
      void loadRoles();
    } catch (err) {
      console.error("保存角色失败:", err);
      roleDialogError.value = "保存失败，请重试";
      toast.error("保存失败，请重试");
    } finally {
      saving.value = false;
    }
  }

  function toggleSelectedFeature(featureCode: string) {
    selectedFeatures.value = togglePermissionSelection(selectedFeatures.value, featureCode);
  }

  function togglePermissionPreset(presetId: string) {
    selectedFeatures.value = togglePermissionPresetSelection(selectedFeatures.value, presetId);
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
      const result = await adminRoleApi.deleteRole(roleToDelete.value.role_id);
      if (result?.success === false) {
        toast.error(roleDeleteFailureMessage(result));
        return;
      }
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
    permissionPresets,
    permissionPresetGroups,
    searchForm,
    total,
    pagination,
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
    roleDialogError,
    roleForm,
    roleIdValidationError,
    saving,
    showDeleteConfirm,
    roleToDelete,
    deleting,
    selectedFeatures,
    advancedPermissionsOpen,
    builtInRoleCount,
    customRoleCount,
    selectedPermissionCount,
    selectedHighRiskCount,
    selectedPresetIds,
    loadRoles,
    applyListFilters,
    loadNextPage,
    loadPreviousPage,
    setPageSize,
    handleSearch,
    handleReset,
    openRoleDetail,
    closeRoleDetail,
    openCreateDialog,
    openEditDialog,
    saveRole,
    toggleSelectedFeature,
    togglePermissionPreset,
    requestDeleteRole,
    deleteRole,
  };
}
