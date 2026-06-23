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
}

// 权限数据缓存
const permissions = ref<UserPermissions | null>(null);
const loading = ref(false);
const error = ref<string | null>(null);

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
      const result = await get<ApiResponse<UserPermissions>>("/api/v1/permissions/me");

      permissions.value = result?.data || null;
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

    // admin 用户（datasources 为空）拥有所有数据源权限
    if (permissions.value.user_id === "admin" && permissions.value.datasources.length === 0) {
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
    return permissions.value.user_id === "admin";
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
