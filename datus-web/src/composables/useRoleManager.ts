import { computed, ref, shallowRef } from "vue";
import { toast } from "vue-sonner";

import { useConnection } from "@/composables/useConnection";
import { adminRoleApi, catalogApi, configApi } from "@/lib/api";
import { ROLE_FEATURE_OPTIONS } from "@/lib/navigation";
import {
  buildDatasourceTreeOptions,
  datasourceNodeIdsFromPermissions,
  featurePermissionCodes,
  rolePermissionsFromSelections,
} from "@/lib/role-permissions";
import type { CatalogDatabase, Role, RoleFormData, RoleSearchForm } from "@/types/admin";

export const roleTypeOptions = [
  { value: "", label: "全部类型" },
  { value: "resource", label: "资源角色" },
  { value: "datasource", label: "数据源角色" },
];

export function useRoleManager() {
  const featureOptions = ROLE_FEATURE_OPTIONS;
  const { effectiveBase } = useConnection();

  const searchForm = ref<RoleSearchForm>({
    role_type: "",
    keyword: "",
  });

  const page = shallowRef(1);
  const size = shallowRef(20);
  const total = shallowRef(0);
  const roles = ref<Role[]>([]);
  const loading = shallowRef(false);

  const showDialog = shallowRef(false);
  const dialogMode = shallowRef<"create" | "edit">("create");
  const editingRole = shallowRef<Role | null>(null);
  const roleForm = ref<RoleFormData>({
    role_code: "",
    role_name: "",
    role_type: "resource",
    description: "",
  });
  const saving = shallowRef(false);
  const showDeleteConfirm = shallowRef(false);
  const roleToDelete = shallowRef<Role | null>(null);
  const deleting = shallowRef(false);

  const selectedFeatures = ref<string[]>([]);
  const selectedDatasourceNodes = ref<string[]>([]);
  const catalogDatabases = ref<CatalogDatabase[]>([]);
  const loadingDatasources = shallowRef(false);

  const datasourceTreeOptions = computed(() => buildDatasourceTreeOptions(catalogDatabases.value));
  const totalPages = computed(() => Math.ceil(total.value / size.value) || 1);
  const resourceRoleCount = computed(() => roles.value.filter((role) => role.role_type === "resource").length);
  const datasourceRoleCount = computed(() => roles.value.filter((role) => role.role_type === "datasource").length);
  const systemRoleCount = computed(() => roles.value.filter((role) => role.is_system).length);

  async function loadRoles() {
    loading.value = true;
    try {
      const result = await adminRoleApi.listRoles({
        page: page.value,
        size: size.value,
        roleType: searchForm.value.role_type,
        keyword: searchForm.value.keyword,
      });
      roles.value = result?.data?.roles || [];
      total.value = result?.data?.total || 0;
    } catch (err) {
      console.error("加载角色列表失败:", err);
      roles.value = [];
    } finally {
      loading.value = false;
    }
  }

  function handleSearch() {
    page.value = 1;
    void loadRoles();
  }

  function handleReset() {
    searchForm.value = { role_type: "", keyword: "" };
    page.value = 1;
    void loadRoles();
  }

  function goToPage(nextPage: number) {
    if (nextPage < 1 || nextPage > totalPages.value) return;
    page.value = nextPage;
    void loadRoles();
  }

  async function loadDatasources() {
    if (catalogDatabases.value.length > 0) return;
    loadingDatasources.value = true;
    try {
      const base = effectiveBase();
      const config = await configApi.getAgent(base);
      const datasourceNames = Object.keys(config?.datasources || {});
      const names = datasourceNames.length > 0
        ? datasourceNames
        : config?.current_datasource
          ? [config.current_datasource]
          : [];

      const catalogRows: CatalogDatabase[] = [];
      for (const datasourceName of names) {
        try {
          const result = await catalogApi.list(base, {
            datasource_id: datasourceName,
            include_sys_schemas: false,
          });
          for (const db of result?.databases || []) {
            catalogRows.push({
              datasourceName,
              name: db.name,
              type: db.type || "unknown",
              catalogName: db.catalog_name,
              schemaName: db.schema_name,
              tables: db.tables || [],
            });
          }
        } catch (err) {
          console.error(`加载数据源目录失败: ${datasourceName}`, err);
        }
      }

      catalogDatabases.value = catalogRows;
    } catch (err) {
      console.error("加载数据源目录失败:", err);
      catalogDatabases.value = [];
    } finally {
      loadingDatasources.value = false;
    }
  }

  async function loadRolePermissions(roleId: number, roleType: string) {
    try {
      const result = await adminRoleApi.getRolePermissions(roleId);
      const perms = result?.data || [];

      if (roleType === "resource") {
        selectedFeatures.value = featurePermissionCodes(perms);
      } else {
        selectedDatasourceNodes.value = datasourceNodeIdsFromPermissions(perms, catalogDatabases.value);
      }
    } catch (err) {
      console.error("加载角色权限失败:", err);
      selectedFeatures.value = [];
      selectedDatasourceNodes.value = [];
    }
  }

  async function openCreateDialog() {
    dialogMode.value = "create";
    editingRole.value = null;
    roleForm.value = {
      role_code: "",
      role_name: "",
      role_type: "resource",
      description: "",
    };
    selectedFeatures.value = [];
    selectedDatasourceNodes.value = [];
    await loadDatasources();
    showDialog.value = true;
  }

  async function openEditDialog(role: Role) {
    dialogMode.value = "edit";
    editingRole.value = role;
    roleForm.value = {
      role_code: role.role_code,
      role_name: role.role_name,
      role_type: role.role_type,
      description: role.description || "",
    };
    selectedFeatures.value = [];
    selectedDatasourceNodes.value = [];
    await loadDatasources();
    await loadRolePermissions(role.id, role.role_type);
    showDialog.value = true;
  }

  async function saveRole() {
    if (!roleForm.value.role_code || !roleForm.value.role_name) {
      toast.error("请填写角色编码和名称");
      return;
    }

    saving.value = true;
    try {
      let roleId: number | null = null;

      if (dialogMode.value === "create") {
        const result = await adminRoleApi.createRole(roleForm.value);
        if (!result?.success || !result.data?.role_id) {
          throw new Error(result?.errorMessage || "创建角色失败");
        }
        roleId = result.data.role_id;
      } else if (editingRole.value) {
        await adminRoleApi.updateRole(editingRole.value.id, {
          role_name: roleForm.value.role_name,
          description: roleForm.value.description,
        });
        roleId = editingRole.value.id;
      }

      if (roleId) {
        await adminRoleApi.updateRolePermissions(
          roleId,
          rolePermissionsFromSelections(roleForm.value.role_type, selectedFeatures.value, selectedDatasourceNodes.value)
        );
      }

      showDialog.value = false;
      void loadRoles();
    } catch (err) {
      console.error("保存角色失败:", err);
      toast.error("保存失败，请重试");
    } finally {
      saving.value = false;
    }
  }

  function requestDeleteRole(role: Role) {
    if (role.is_system) {
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
      await adminRoleApi.deleteRole(roleToDelete.value.id);
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
    roleTypeOptions,
    searchForm,
    page,
    size,
    total,
    roles,
    loading,
    showDialog,
    dialogMode,
    editingRole,
    roleForm,
    saving,
    showDeleteConfirm,
    roleToDelete,
    deleting,
    selectedFeatures,
    selectedDatasourceNodes,
    catalogDatabases,
    loadingDatasources,
    datasourceTreeOptions,
    totalPages,
    resourceRoleCount,
    datasourceRoleCount,
    systemRoleCount,
    loadRoles,
    handleSearch,
    handleReset,
    goToPage,
    loadDatasources,
    loadRolePermissions,
    openCreateDialog,
    openEditDialog,
    saveRole,
    requestDeleteRole,
    deleteRole,
  };
}
