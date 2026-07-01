/**
 * 权限管理 Composable
 * 用于获取和管理用户权限数据
 *
 * 权限格式（简化版）：
 * - features: 字符串数组，包含用户可访问的功能代码
 * - datasources: 字符串数组，包含用户可访问的数据源名称
 */
import { ref, computed } from "vue";
import { get } from "@/lib/request";

/**
 * API 响应格式
 */
interface ApiResponse<T> {
  success: boolean;
  data: T;
  errorCode?: string;
  errorMessage?: string;
}

/**
 * 用户权限信息（简化格式）
 */
export interface UserPermissions {
  user_id: string;
  features: string[];      // 功能权限代码数组
  datasources: string[];   // 数据源名称数组
  permissions: string[];
  datasource_grants: Record<string, unknown>;
  is_admin: boolean;
}

type MeSummaryPayload = {
  user_id?: string | null;
  permissions?: string[];
  datasource_grants?: Record<string, unknown>;
  features?: Record<string, boolean>;
  is_admin?: boolean;
};

// 权限数据缓存
const permissions = ref<UserPermissions | null>(null);
const loading = ref(false);
const error = ref<string | null>(null);

function normalizeMeSummary(payload: MeSummaryPayload | null | undefined): UserPermissions | null {
  if (!payload) return null;

  const featureEntries = Object.entries(payload.features ?? {});
  const datasourceGrants = payload.datasource_grants ?? {};
  return {
    user_id: payload.user_id ?? "",
    features: featureEntries.filter(([, enabled]) => enabled).map(([feature]) => feature),
    datasources: Object.keys(datasourceGrants).filter((datasource) => Boolean(datasourceGrants[datasource])),
    permissions: payload.permissions ?? [],
    datasource_grants: datasourceGrants,
    is_admin: payload.is_admin === true,
  };
}

/**
 * 权限管理 Composable
 */
export function usePermission() {
  /**
   * 获取当前用户权限
   */
  async function fetchPermissions(): Promise<UserPermissions | null> {
    loading.value = true;
    error.value = null;

    try {
      const result = await get<ApiResponse<MeSummaryPayload>>("/api/v1/me");

      permissions.value = normalizeMeSummary(result?.data);
      return permissions.value;
    } catch (err) {
      console.error("获取权限失败:", err);
      error.value = err instanceof Error ? err.message : "获取权限失败";
      return null;
    } finally {
      loading.value = false;
    }
  }

  /**
   * 检查是否有功能权限
   * @param featureCode 功能代码
   * @returns 是否有权限
   */
  function hasFeaturePermission(featureCode: string): boolean {
    if (!permissions.value) return false;
    return permissions.value.features.includes(featureCode);
  }

  /**
   * 检查是否有数据源访问权限
   * @param datasourceName 数据源名称
   * @returns 是否有权限
   */
  function hasDatasourcePermission(datasourceName: string): boolean {
    if (!permissions.value) return false;

    if (permissions.value.is_admin) {
      return true;
    }

    return permissions.value.datasources.includes(datasourceName);
  }

  /**
   * 检查是否为管理员
   * @returns 是否为管理员
   */
  function isAdmin(): boolean {
    if (!permissions.value) return false;
    return permissions.value.is_admin;
  }

  /**
   * 清除权限缓存
   */
  function clearPermissions(): void {
    permissions.value = null;
    error.value = null;
  }

  /**
   * 权限是否已加载
   */
  const isLoaded = computed(() => permissions.value !== null);

  return {
    permissions,
    loading,
    error,
    isLoaded,
    fetchPermissions,
    hasFeaturePermission,
    hasDatasourcePermission,
    isAdmin,
    clearPermissions,
  };
}
