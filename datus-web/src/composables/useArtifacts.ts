import { computed, readonly, ref, shallowRef } from "vue";
import { toast } from "vue-sonner";

import { useConnection } from "@/composables/useConnection";
import { dashboardApi, reportApi } from "@/lib/api";
import type { ArtifactManifest, DashboardDetail, ReportDetail, SqlQueryResultEnvelope } from "@/types";
import type { ArtifactViewTab } from "@/features/workspace/types";

export type ArtifactDetail = DashboardDetail | ReportDetail;

function nonEmptySlug(value: string | null | undefined): string | null {
  const trimmed = value?.trim() ?? "";
  return trimmed || null;
}

function detailsErrorMessage(tab: ArtifactViewTab): string {
  return tab === "report" ? "读取报表详情失败" : "读取仪表盘详情失败";
}

export function artifactHtmlUrl(baseUrl: string, tab: ArtifactViewTab, slug: string): string {
  return tab === "report"
    ? reportApi.htmlUrl(baseUrl, slug)
    : dashboardApi.htmlUrl(baseUrl, slug);
}

export function useArtifacts() {
  const connection = useConnection();

  const dashboards = ref<ArtifactManifest[]>([]);
  const reports = ref<ArtifactManifest[]>([]);
  const dashboardDetail = ref<DashboardDetail | null>(null);
  const reportDetail = ref<ReportDetail | null>(null);
  const listLoading = shallowRef(false);
  const detailLoading = shallowRef(false);
  const listError = shallowRef<string | null>(null);
  const detailError = shallowRef<string | null>(null);
  const activeDetailTab = shallowRef<ArtifactViewTab | null>(null);
  const activeDetailSlug = shallowRef<string | null>(null);
  const detailRequestId = shallowRef(0);
  const queryLoading = shallowRef(false);
  const queryError = shallowRef<string | null>(null);
  const queryResult = ref<SqlQueryResultEnvelope | null>(null);
  const activeQuerySlug = shallowRef<string | null>(null);
  const queryRequestId = shallowRef(0);

  const activeDetail = computed<ArtifactDetail | null>(() => {
    if (activeDetailTab.value === "report") return reportDetail.value;
    if (activeDetailTab.value === "dashboard") return dashboardDetail.value;
    return null;
  });

  async function loadArtifacts() {
    listLoading.value = true;
    listError.value = null;

    try {
      const base = connection.effectiveBase();
      const [dashboardResult, reportResult] = await Promise.all([
        dashboardApi.list(base),
        reportApi.list(base),
      ]);
      dashboards.value = dashboardResult ?? [];
      reports.value = reportResult ?? [];
    } catch (err) {
      console.error("读取产物列表失败:", err);
      listError.value = "读取产物列表失败";
      toast.error("读取产物列表失败");
    } finally {
      listLoading.value = false;
    }
  }

  function resetDashboardQuery() {
    queryLoading.value = false;
    queryError.value = null;
    queryResult.value = null;
    activeQuerySlug.value = null;
  }

  async function loadDetail(tab: ArtifactViewTab, slugValue: string | null | undefined) {
    const slug = nonEmptySlug(slugValue);
    const requestId = detailRequestId.value + 1;
    const detailTargetChanged = activeDetailTab.value !== tab || activeDetailSlug.value !== slug;
    detailRequestId.value = requestId;
    activeDetailTab.value = tab;
    activeDetailSlug.value = slug;
    detailError.value = null;

    if (detailTargetChanged) {
      resetDashboardQuery();
    }

    if (!slug) {
      detailLoading.value = false;
      dashboardDetail.value = null;
      reportDetail.value = null;
      activeDetailTab.value = null;
      return;
    }

    detailLoading.value = true;

    try {
      const base = connection.effectiveBase();

      if (tab === "report") {
        const detail = await reportApi.detail(base, slug);
        if (detailRequestId.value !== requestId) return;
        reportDetail.value = detail;
        dashboardDetail.value = null;
        return;
      }

      const detail = await dashboardApi.detail(base, slug);
      if (detailRequestId.value !== requestId) return;
      dashboardDetail.value = detail;
      reportDetail.value = null;
    } catch (err) {
      if (detailRequestId.value !== requestId) return;

      const message = detailsErrorMessage(tab);
      console.error(`${message}:`, err);
      detailError.value = message;
      dashboardDetail.value = null;
      reportDetail.value = null;
      toast.error(message);
    } finally {
      if (detailRequestId.value === requestId) {
        detailLoading.value = false;
      }
    }
  }

  async function runDashboardQuery(
    dashboardSlugValue: string | null | undefined,
    querySlugValue: string | null | undefined,
    params: Record<string, unknown>,
  ) {
    const dashboardSlug = nonEmptySlug(dashboardSlugValue);
    const querySlug = nonEmptySlug(querySlugValue);
    const requestId = queryRequestId.value + 1;
    queryRequestId.value = requestId;
    activeQuerySlug.value = querySlug;
    queryError.value = null;
    queryResult.value = null;

    if (!dashboardSlug || !querySlug) {
      queryLoading.value = false;
      queryError.value = "请选择可运行的仪表盘查询";
      return null;
    }

    queryLoading.value = true;

    try {
      const result = await dashboardApi.query(connection.effectiveBase(), dashboardSlug, querySlug, params);
      if (queryRequestId.value !== requestId) return null;
      queryResult.value = result;
      return result;
    } catch (err) {
      if (queryRequestId.value !== requestId) return null;

      console.error("运行仪表盘查询失败:", err);
      queryResult.value = null;
      queryError.value = "运行仪表盘查询失败";
      toast.error("运行仪表盘查询失败");
      return null;
    } finally {
      if (queryRequestId.value === requestId) {
        queryLoading.value = false;
      }
    }
  }

  function htmlUrl(tab: ArtifactViewTab, slug: string): string {
    return artifactHtmlUrl(connection.effectiveBase(), tab, slug);
  }

  return {
    dashboards: readonly(dashboards),
    reports: readonly(reports),
    activeDetail,
    activeDetailTab: readonly(activeDetailTab),
    activeDetailSlug: readonly(activeDetailSlug),
    listLoading: readonly(listLoading),
    detailLoading: readonly(detailLoading),
    listError: readonly(listError),
    detailError: readonly(detailError),
    queryLoading: readonly(queryLoading),
    queryError: readonly(queryError),
    queryResult: readonly(queryResult),
    activeQuerySlug: readonly(activeQuerySlug),
    loadArtifacts,
    loadDetail,
    runDashboardQuery,
    htmlUrl,
  };
}
