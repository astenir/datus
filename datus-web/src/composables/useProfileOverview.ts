import { computed, ref, shallowRef } from "vue";
import { toast } from "vue-sonner";

import { meApi } from "@/lib/api";
import { formatDatasourceScope } from "@/lib/datasource-scope-labels";
import type {
  MeDatasourceGrantView,
  MeFeatureView,
  MeSession,
  MeSummary,
  MeUsage,
} from "@/types/profile";

const featureLabels: Record<string, string> = {
  chat: "对话",
  sql_executor: "SQL 执行",
  datasource_catalog: "数据目录",
  report_view: "报表查看",
  report_query: "报表查询",
  dashboard_view: "仪表盘查看",
  dashboard_query: "仪表盘查询",
  kb: "知识库",
  mcp: "MCP",
  config_view: "配置查看",
  config_edit: "配置编辑",
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function stringField(source: Record<string, unknown>, key: string): string {
  const value = source[key];
  return typeof value === "string" ? value : "";
}

function numberField(source: Record<string, unknown>, key: string): number {
  const value = source[key];
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function nullableNumberField(source: Record<string, unknown>, key: string): number | null {
  const value = source[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function nullableStringField(source: Record<string, unknown>, key: string): string | null {
  const value = source[key];
  return typeof value === "string" && value.trim() ? value : null;
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

function normalizeUsageRecord(raw: MeUsage): MeUsage {
  if (isRecord(raw)) {
    return {
      subject_type: stringField(raw, "subject_type"),
      subject_id: stringField(raw, "subject_id"),
      resource: stringField(raw, "resource"),
      used: numberField(raw, "used"),
      window_start: nullableStringField(raw, "window_start"),
      window_seconds: nullableNumberField(raw, "window_seconds"),
      updated_at: nullableStringField(raw, "updated_at"),
    };
  }
  return {
    subject_type: "",
    subject_id: "",
    resource: "",
    used: 0,
    window_start: null,
    window_seconds: null,
    updated_at: null,
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
  const sessions = ref<MeSession[]>([]);
  const usage = ref<MeUsage[]>([]);

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
  const runningSessionCount = computed(() => sessions.value.filter(session => session.is_active).length);
  const totalTokenCount = computed(() => {
    return sessions.value.reduce((total, session) => total + (session.token_count ?? 0), 0);
  });
  const totalUsageCount = computed(() => usage.value.reduce((total, item) => total + item.used, 0));

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
        sessionResult,
        usageResult,
      ] = await Promise.all([
        meApi.summary(),
        meApi.permissions(),
        meApi.datasourceGrants(),
        meApi.features(),
        meApi.sessions(),
        meApi.usage(),
      ]);

      summary.value = summaryResult.data ?? null;
      permissions.value = permissionResult.data ?? summaryResult.data?.permissions ?? [];
      datasourceGrants.value = grantResult.data ?? summaryResult.data?.datasource_grants ?? {};
      features.value = featureResult.data ?? summaryResult.data?.features ?? {};
      sessions.value = sessionResult.data?.sessions ?? [];
      usage.value = (usageResult.data ?? []).map(normalizeUsageRecord);
      loaded.value = true;
    } catch (err) {
      console.error("加载个人权限与用量失败:", err);
      error.value = err instanceof Error ? err.message : "加载个人权限与用量失败";
      toast.error("加载个人权限与用量失败");
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
    sessions,
    usage,
    roles,
    projectId,
    userId,
    isAdmin,
    enabledFeatures,
    datasourceGrantList,
    allowedDatasourceCount,
    runningSessionCount,
    totalTokenCount,
    totalUsageCount,
    featureList,
    loadProfile,
  };
}
