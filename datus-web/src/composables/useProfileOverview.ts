import { computed, ref, shallowRef } from "vue";
import { toast } from "vue-sonner";

import { meApi } from "@/lib/api";
import { formatDatasourceScope } from "@/lib/datasource-scope-labels";
import type {
  MeDatasourceGrantView,
  MeFeatureView,
  MeSummary,
} from "@/types/profile";

const featureLabels: Record<string, string> = {
  chat: "对话",
  chat_permission_mode: "高危对话模式",
  sql_executor: "SQL 执行",
  datasource_catalog: "数据目录",
  kb: "知识库",
  mcp: "MCP",
  mcp_personal: "个人 MCP",
  mcp_server: "MCP Server 操作",
  mcp_filter: "MCP 过滤规则",
  mcp_personal_ops: "个人 MCP 操作",
  report_view: "报表查看",
  report_query: "报表查询",
  report_export: "报表导出",
  report_edit: "报表编辑",
  dashboard_view: "仪表盘查看",
  dashboard_query: "仪表盘查询",
  dashboard_export: "仪表盘导出",
  dashboard_edit: "仪表盘编辑",
  agent_manage: "Agent 管理",
  user_manage: "用户管理",
  role_manage: "角色管理",
  datasource_manage: "数据授权管理",
  artifact_manage: "产物 ACL 管理",
  session_manage: "会话管理",
  audit_view: "审计查看",
  audit_export: "审计导出",
  quota_manage: "额度管理",
  secret_manage: "密钥管理",
  config_view: "配置查看",
  config_edit: "配置编辑",
  system_status: "系统状态",
  admin: "全部管理权限",
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function stringField(source: Record<string, unknown>, key: string): string {
  const value = source[key];
  return typeof value === "string" ? value : "";
}

const datasourceScopeKeys = [
  "allow_catalog",
  "allow_sql",
  "allow_report",
  "allow_dashboard",
  "catalogs",
  "databases",
  "schemas",
  "tables",
] as const;

function summarizeGrantScope(value: unknown): string {
  if (value === true) return "全量";
  if (value === false || value === null || value === undefined) return "-";
  if (!isRecord(value)) return String(value);

  if (isRecord(value.scope)) {
    return formatDatasourceScope(value.scope);
  }

  const scope: Record<string, unknown> = {};
  for (const key of datasourceScopeKeys) {
    if (key in value) {
      scope[key] = value[key];
    }
  }
  return formatDatasourceScope(scope);
}

function normalizeGrant(datasource: string, raw: unknown): MeDatasourceGrantView {
  if (!isRecord(raw)) {
    return {
      datasource,
      enabled: raw === true,
      effect: raw === false ? "deny" : raw === true ? "allow" : "unknown",
      scopeText: summarizeGrantScope(raw),
      raw,
    };
  }

  const effect = stringField(raw, "effect") || "allow";
  return {
    datasource,
    enabled: effect !== "deny",
    effect,
    scopeText: summarizeGrantScope(raw),
    raw,
  };
}

export function useProfileOverview() {
  const loading = shallowRef(false);
  const loaded = shallowRef(false);
  const error = shallowRef<string | null>(null);
  const summary = ref<MeSummary | null>(null);
  const permissions = ref<string[]>([]);
  const datasourceGrants = ref<Record<string, unknown>>({});
  const features = ref<Record<string, boolean>>({});

  const roles = computed(() => summary.value?.roles ?? []);
  const projectId = computed(() => summary.value?.project_id || "-");
  const userId = computed(() => summary.value?.user_id || "-");
  const isAdmin = computed(() => summary.value?.is_admin === true);
  const enabledFeatures = computed(() => featureList.value.filter(item => item.enabled));
  const datasourceGrantList = computed(() => {
    return Object.entries(datasourceGrants.value)
      .map(([datasource, raw]) => normalizeGrant(datasource, raw))
      .sort((a, b) => a.datasource.localeCompare(b.datasource));
  });
  const allowedDatasourceCount = computed(() => datasourceGrantList.value.filter(item => item.enabled).length);

  const featureList = computed<MeFeatureView[]>(() => {
    return Object.entries(features.value)
      .map(([code, enabled]) => ({
        code,
        label: featureLabels[code] ?? code,
        enabled,
      }))
      .sort((a, b) => Number(b.enabled) - Number(a.enabled) || a.label.localeCompare(b.label));
  });

  async function loadProfile() {
    loading.value = true;
    error.value = null;
    try {
      const [
        summaryResult,
        permissionResult,
        grantResult,
        featureResult,
      ] = await Promise.all([
        meApi.summary(),
        meApi.permissions(),
        meApi.datasourceGrants(),
        meApi.features(),
      ]);

      summary.value = summaryResult.data ?? null;
      permissions.value = permissionResult.data ?? summaryResult.data?.permissions ?? [];
      datasourceGrants.value = grantResult.data ?? summaryResult.data?.datasource_grants ?? {};
      features.value = featureResult.data ?? summaryResult.data?.features ?? {};
      loaded.value = true;
    } catch (err) {
      console.error("加载个人权限失败:", err);
      error.value = err instanceof Error ? err.message : "加载个人权限失败";
      toast.error("加载个人权限失败");
    } finally {
      loading.value = false;
    }
  }

  return {
    loading,
    loaded,
    error,
    summary,
    permissions,
    datasourceGrants,
    features,
    roles,
    projectId,
    userId,
    isAdmin,
    enabledFeatures,
    datasourceGrantList,
    allowedDatasourceCount,
    featureList,
    loadProfile,
  };
}
