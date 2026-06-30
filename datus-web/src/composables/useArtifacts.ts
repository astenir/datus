import { computed, onScopeDispose, readonly, ref, shallowRef } from "vue";
import { toast } from "vue-sonner";

import { useConnection } from "@/composables/useConnection";
import { artifactShareApi, dashboardApi, reportApi } from "@/lib/api";
import type {
  ArtifactManifest,
  ArtifactShare,
  ArtifactShareRoleSummary,
  ArtifactShareUpdate,
  ArtifactShareUserSummary,
  DashboardDetail,
  ReportDetail,
  SqlQueryResultEnvelope,
} from "@/types";
import type { ArtifactViewTab } from "@/features/workspace/types";

export type ArtifactDetail = DashboardDetail | ReportDetail;
export type ArtifactSharePrincipalOption = {
  value: string;
  label: string;
  description?: string;
};

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

export function artifactPreviewKey(tab: ArtifactViewTab, slug: string): string {
  return `${tab}:${slug}`;
}

export async function artifactHtml(baseUrl: string, tab: ArtifactViewTab, slug: string): Promise<string> {
  return tab === "report"
    ? reportApi.html(baseUrl, slug)
    : dashboardApi.html(baseUrl, slug);
}

export function artifactShare(baseUrl: string, tab: ArtifactViewTab, slug: string): Promise<ArtifactShare | null> {
  return tab === "report"
    ? reportApi.getAcl(baseUrl, slug)
    : dashboardApi.getAcl(baseUrl, slug);
}

export function putArtifactShare(
  baseUrl: string,
  tab: ArtifactViewTab,
  slug: string,
  share: ArtifactShareUpdate,
): Promise<ArtifactShare | null> {
  return tab === "report"
    ? reportApi.putAcl(baseUrl, slug, share)
    : dashboardApi.putAcl(baseUrl, slug, share);
}

export function createArtifactPreviewUrl(html: string): string {
  return URL.createObjectURL(new Blob([html], { type: "text/html;charset=utf-8" }));
}

function userOption(user: ArtifactShareUserSummary): ArtifactSharePrincipalOption {
  const userId = user.user_id;
  const descriptionParts = [user.email, user.department, user.title].filter(Boolean);
  return {
    value: userId,
    label: user.display_name ? `${user.display_name} (${userId})` : userId,
    description: descriptionParts.length ? descriptionParts.join(" / ") : undefined,
  };
}

function roleOption(role: ArtifactShareRoleSummary): ArtifactSharePrincipalOption {
  return {
    value: role.role_id,
    label: role.name ? `${role.name} (${role.role_id})` : role.role_id,
    description: role.description ?? undefined,
  };
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
  const previewLoadingKey = shallowRef<string | null>(null);
  const previewError = shallowRef<string | null>(null);
  const activeShare = ref<ArtifactShare | null>(null);
  const activeShareTab = shallowRef<ArtifactViewTab | null>(null);
  const activeShareSlug = shallowRef<string | null>(null);
  const shareLoadingKey = shallowRef<string | null>(null);
  const shareSaving = shallowRef(false);
  const shareError = shallowRef<string | null>(null);
  const shareRequestId = shallowRef(0);
  const shareUserOptions = ref<ArtifactSharePrincipalOption[]>([]);
  const shareRoleOptions = ref<ArtifactSharePrincipalOption[]>([]);
  const shareDirectoryLoading = shallowRef(false);
  const shareDirectoryError = shallowRef<string | null>(null);
  const shareDirectoryRequestId = shallowRef(0);
  const previewUrls: string[] = [];

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

  function rememberPreviewUrl(url: string) {
    previewUrls.push(url);
    if (previewUrls.length <= 12) return;

    const stale = previewUrls.shift();
    if (stale) URL.revokeObjectURL(stale);
  }

  async function openHtmlPreview(tab: ArtifactViewTab, slugValue: string | null | undefined) {
    const slug = nonEmptySlug(slugValue);
    if (!slug) return;

    const key = artifactPreviewKey(tab, slug);
    previewLoadingKey.value = key;
    previewError.value = null;

    const previewWindow = window.open("about:blank", "_blank");
    if (previewWindow) {
      previewWindow.opener = null;
    }

    try {
      const html = await artifactHtml(connection.effectiveBase(), tab, slug);
      const url = createArtifactPreviewUrl(html);
      rememberPreviewUrl(url);

      if (previewWindow) {
        previewWindow.location.href = url;
        return;
      }

      window.open(url, "_blank", "noopener,noreferrer");
    } catch (err) {
      console.error("打开产物 HTML 预览失败:", err);
      previewWindow?.close();
      previewError.value = "打开 HTML 预览失败";
      toast.error("打开 HTML 预览失败");
    } finally {
      if (previewLoadingKey.value === key) {
        previewLoadingKey.value = null;
      }
    }
  }

  function clearShare() {
    shareRequestId.value += 1;
    shareDirectoryRequestId.value += 1;
    activeShare.value = null;
    activeShareTab.value = null;
    activeShareSlug.value = null;
    shareLoadingKey.value = null;
    shareSaving.value = false;
    shareError.value = null;
    shareDirectoryLoading.value = false;
    shareDirectoryError.value = null;
  }

  async function loadShare(tab: ArtifactViewTab, slugValue: string | null | undefined) {
    const slug = nonEmptySlug(slugValue);
    const requestId = shareRequestId.value + 1;
    shareRequestId.value = requestId;
    activeShare.value = null;
    activeShareTab.value = tab;
    activeShareSlug.value = slug;
    shareError.value = null;

    if (!slug) {
      shareLoadingKey.value = null;
      return null;
    }

    const key = artifactPreviewKey(tab, slug);
    shareLoadingKey.value = key;

    try {
      const share = await artifactShare(connection.effectiveBase(), tab, slug);
      if (shareRequestId.value !== requestId) return null;
      activeShare.value = share;
      return share;
    } catch (err) {
      if (shareRequestId.value !== requestId) return null;

      console.error("读取产物分享设置失败:", err);
      shareError.value = "读取分享设置失败";
      toast.error("读取分享设置失败");
      return null;
    } finally {
      if (shareRequestId.value === requestId) {
        shareLoadingKey.value = null;
      }
    }
  }

  async function loadShareDirectory(tab: ArtifactViewTab) {
    const requestId = shareDirectoryRequestId.value + 1;
    shareDirectoryRequestId.value = requestId;
    shareDirectoryLoading.value = true;
    shareDirectoryError.value = null;

    try {
      const base = connection.effectiveBase();
      const [usersResult, rolesResult] = await Promise.all([
        artifactShareApi.listUsers(base, { artifactType: tab, limit: 100 }),
        artifactShareApi.listRoles(base, { artifactType: tab, limit: 100 }),
      ]);
      if (shareDirectoryRequestId.value !== requestId) return;

      shareUserOptions.value = (usersResult ?? []).map(userOption);
      shareRoleOptions.value = (rolesResult ?? []).map(roleOption);
    } catch (err) {
      if (shareDirectoryRequestId.value !== requestId) return;

      console.error("读取分享候选用户和角色失败:", err);
      shareDirectoryError.value = "读取可分享用户和角色失败";
      shareUserOptions.value = [];
      shareRoleOptions.value = [];
      toast.error("读取可分享用户和角色失败");
    } finally {
      if (shareDirectoryRequestId.value === requestId) {
        shareDirectoryLoading.value = false;
      }
    }
  }

  async function saveShare(share: ArtifactShareUpdate): Promise<boolean> {
    const tab = activeShareTab.value;
    const slug = activeShareSlug.value;

    if (!tab || !slug) {
      shareError.value = "请选择要分享的产物";
      toast.error("请选择要分享的产物");
      return false;
    }

    shareSaving.value = true;
    shareError.value = null;

    try {
      const nextShare = await putArtifactShare(connection.effectiveBase(), tab, slug, share);
      activeShare.value = nextShare;
      toast.success("分享设置已保存");
      return true;
    } catch (err) {
      console.error("保存产物分享设置失败:", err);
      shareError.value = "保存分享设置失败";
      toast.error("保存分享设置失败");
      return false;
    } finally {
      shareSaving.value = false;
    }
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

  onScopeDispose(() => {
    for (const url of previewUrls) {
      URL.revokeObjectURL(url);
    }
    previewUrls.length = 0;
  });

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
    previewLoadingKey: readonly(previewLoadingKey),
    previewError: readonly(previewError),
    activeShare: readonly(activeShare),
    activeShareTab: readonly(activeShareTab),
    activeShareSlug: readonly(activeShareSlug),
    shareLoadingKey: readonly(shareLoadingKey),
    shareSaving: readonly(shareSaving),
    shareError: readonly(shareError),
    shareUserOptions: readonly(shareUserOptions),
    shareRoleOptions: readonly(shareRoleOptions),
    shareDirectoryLoading: readonly(shareDirectoryLoading),
    shareDirectoryError: readonly(shareDirectoryError),
    loadArtifacts,
    loadDetail,
    runDashboardQuery,
    htmlUrl,
    openHtmlPreview,
    loadShare,
    loadShareDirectory,
    saveShare,
    clearShare,
  };
}
