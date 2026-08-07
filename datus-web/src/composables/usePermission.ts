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
  views: string[];         // 工作区视图代码数组
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
  views?: Record<string, boolean>;
  is_admin?: boolean;
};

function datasourceGrantAllowsAccess(grant: unknown): boolean {
  if (grant === true) return true;
  if (typeof grant !== "object" || grant === null || Array.isArray(grant)) return false;
  const effect = "effect" in grant && typeof grant.effect === "string"
    ? grant.effect.trim().toLowerCase()
    : "allow";
  return effect === "allow";
}

// 权限数据缓存
const permissions = ref<UserPermissions | null>(null);
const loading = ref(false);
const error = ref<string | null>(null);

function normalizeMeSummary(payload: MeSummaryPayload | null | undefined): UserPermissions | null {
  if (!payload) return null;

  const featureEntries = Object.entries(payload.features ?? {});
  const viewEntries = Object.entries(payload.views ?? deriveViews(payload));
  const datasourceGrants = payload.datasource_grants ?? {};
  return {
    user_id: payload.user_id ?? "",
    features: featureEntries.filter(([, enabled]) => enabled).map(([feature]) => feature),
    views: viewEntries.filter(([, enabled]) => enabled).map(([view]) => view),
    datasources: Object.entries(datasourceGrants)
      .filter(([, grant]) => datasourceGrantAllowsAccess(grant))
      .map(([datasource]) => datasource),
    permissions: payload.permissions ?? [],
    datasource_grants: datasourceGrants,
    is_admin: payload.is_admin === true,
  };
}

function deriveViews(payload: MeSummaryPayload): Record<string, boolean> {
  const permissions = payload.permissions ?? [];
  const features = payload.features ?? {};
  const isAdmin = payload.is_admin === true;
  const hasPermission = (permissionCode: string) =>
    permissions.some((permission) => permissionMatches(permissionCode, permission));
  const hasFeature = (featureCode: string) => features[featureCode] === true;

  return {
    chat: isAdmin || hasFeature("chat") || hasPermission("module.chat"),
    artifacts: isAdmin
      || hasFeature("report")
      || hasFeature("dashboard")
      || hasFeature("report_view")
      || hasFeature("dashboard_view")
      || hasPermission("module.report.view")
      || hasPermission("module.dashboard.view"),
    artifact_reports: isAdmin || hasFeature("report") || hasFeature("report_view") || hasPermission("module.report.view"),
    artifact_dashboards: isAdmin
      || hasFeature("dashboard")
      || hasFeature("dashboard_view")
      || hasPermission("module.dashboard.view"),
    knowledge: isAdmin
      || hasFeature("kb")
      || hasPermission("module.kb"),
    mcp: isAdmin
      || hasFeature("mcp")
      || hasFeature("mcp_personal")
      || hasPermission("module.mcp")
      || hasPermission("module.mcp.personal"),
    agents: isAdmin || hasPermission("module.admin.agents"),
    configuration: isAdmin
      || hasFeature("config_view")
      || hasFeature("config_edit")
      || hasPermission("module.config.view")
      || hasPermission("module.config.edit"),
    permissions: isAdmin
      || hasFeature("admin")
      || hasPermission("module.admin.users")
      || hasPermission("module.admin.roles"),
    profile: true,
  };
}

function permissionMatches(required: string, granted: string): boolean {
  const requiredCode = required.trim();
  const grantedCode = granted.trim();
  if (!requiredCode || !grantedCode) return false;
  if (grantedCode === "*" || grantedCode === requiredCode) return true;

  const pattern = grantedCode
    .replace(/[.+?^${}()|[\]\\]/g, "\\$&")
    .replace(/\*/g, ".*");
  return new RegExp(`^${pattern}$`).test(requiredCode);
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

  function hasPermission(permissionCode: string): boolean {
    if (!permissions.value) return false;
    return permissions.value.permissions.some((permission) => permissionMatches(permissionCode, permission));
  }

  function hasViewPermission(viewCode: string): boolean {
    if (!permissions.value) return viewCode === "profile";
    return permissions.value.views.includes(viewCode);
  }

  /**
   * 检查是否有数据源访问权限
   * @param datasourceName 数据源名称
   * @returns 是否有权限
   */
  function hasDatasourcePermission(datasourceName: string): boolean {
    if (!permissions.value) return false;
    return permissions.value.datasources.includes(datasourceName) || permissions.value.datasources.includes("*");
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
    hasViewPermission,
    hasPermission,
    hasDatasourcePermission,
    isAdmin,
    clearPermissions,
  };
}
