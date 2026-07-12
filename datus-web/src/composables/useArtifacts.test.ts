import { beforeEach, describe, expect, it, vi } from "vitest";

const dashboardList = vi.fn();
const dashboardDetail = vi.fn();
const dashboardHtmlUrl = vi.fn();
const dashboardHtml = vi.fn();
const dashboardGetAcl = vi.fn();
const dashboardPutAcl = vi.fn();
const dashboardCreateEditSession = vi.fn();
const dashboardQuery = vi.fn();
const listShareUsers = vi.fn();
const listShareRoles = vi.fn();
const reportList = vi.fn();
const reportDetail = vi.fn();
const reportHtmlUrl = vi.fn();
const reportHtml = vi.fn();
const reportGetAcl = vi.fn();
const reportPutAcl = vi.fn();
const reportCreateEditSession = vi.fn();
const toastError = vi.fn();
const toastSuccess = vi.fn();

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });
  return { promise, resolve, reject };
}

vi.mock("@/lib/api", () => ({
  dashboardApi: {
    list: dashboardList,
    detail: dashboardDetail,
    htmlUrl: dashboardHtmlUrl,
    html: dashboardHtml,
    getAcl: dashboardGetAcl,
    putAcl: dashboardPutAcl,
    createEditSession: dashboardCreateEditSession,
    query: dashboardQuery,
  },
  artifactShareApi: {
    listUsers: listShareUsers,
    listRoles: listShareRoles,
  },
  reportApi: {
    list: reportList,
    detail: reportDetail,
    htmlUrl: reportHtmlUrl,
    html: reportHtml,
    getAcl: reportGetAcl,
    putAcl: reportPutAcl,
    createEditSession: reportCreateEditSession,
  },
}));

vi.mock("@/composables/useConnection", () => ({
  useConnection: () => ({
    effectiveBase: () => "http://api.test",
  }),
}));

vi.mock("vue-sonner", () => ({
  toast: {
    error: toastError,
    success: toastSuccess,
  },
}));

describe("useArtifacts", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
    dashboardList.mockResolvedValue([
      {
        slug: "fund-overview",
        name: "Fund Overview",
        description: "Dashboard",
        can_manage_share: true,
      },
    ]);
    reportList.mockResolvedValue([
      {
        slug: "fund-report",
        name: "Fund Report",
        description: "Report",
        can_manage_share: false,
      },
    ]);
    dashboardDetail.mockResolvedValue({
      slug: "fund-overview",
      name: "Fund Overview",
      description: "Dashboard",
      manifest: {
        slug: "fund-overview",
        name: "Fund Overview",
        description: "Dashboard",
      },
      files: [],
      templates: [],
    });
    reportDetail.mockResolvedValue({
      slug: "fund-report",
      name: "Fund Report",
      description: "Report",
      manifest: {
        slug: "fund-report",
        name: "Fund Report",
        description: "Report",
      },
      files: [],
    });
    dashboardHtmlUrl.mockReturnValue("http://api.test/api/v1/dashboards/fund-overview/html");
    dashboardQuery.mockResolvedValue({
      executed_at: "2026-06-01T00:00:00Z",
      datasource: "demo",
      row_count: 1,
      columns: [{ name: "total", type: "number" }],
      rows: [{ total: 10 }],
      sql: "select 10 as total",
    });
    reportHtmlUrl.mockReturnValue("http://api.test/api/v1/reports/fund-report/html");
    dashboardHtml.mockResolvedValue("<!doctype html><html><body>dashboard</body></html>");
    reportHtml.mockResolvedValue("<!doctype html><html><body>report</body></html>");
    dashboardGetAcl.mockResolvedValue({
      owner_user_id: "alice",
      visibility: "private",
      allowed_roles: [],
      allowed_user_ids: [],
    });
    dashboardPutAcl.mockResolvedValue({
      owner_user_id: "alice",
      visibility: "enterprise",
      allowed_roles: [],
      allowed_user_ids: [],
    });
    dashboardCreateEditSession.mockResolvedValue({
      edit_session_id: "edit-2",
      subagent_id: "dashboard_edit__edit_2",
      artifact_type: "dashboard",
      artifact_slug: "fund-overview",
      owner_user_id: "alice",
      created_at: "2026-07-08T00:00:00Z",
    });
    reportGetAcl.mockResolvedValue({
      owner_user_id: "alice",
      visibility: "role",
      allowed_roles: ["analyst"],
      allowed_user_ids: ["bob"],
    });
    reportPutAcl.mockResolvedValue({
      owner_user_id: "alice",
      visibility: "role",
      allowed_roles: ["analyst"],
      allowed_user_ids: ["bob", "charlie"],
    });
    reportCreateEditSession.mockResolvedValue({
      edit_session_id: "edit-1",
      subagent_id: "report_edit__edit_1",
      artifact_type: "report",
      artifact_slug: "fund-report",
      owner_user_id: "alice",
      created_at: "2026-07-08T00:00:00Z",
    });
    listShareUsers.mockResolvedValue([
      {
        user_id: "bob",
        display_name: "Bob",
        email: "bob@example.com",
        department: "Data",
        title: "Analyst",
      },
      {
        user_id: "charlie",
        display_name: "Charlie",
        email: null,
        department: null,
        title: null,
      },
    ]);
    listShareRoles.mockResolvedValue([
      {
        role_id: "analyst",
        name: "分析师",
        description: "分析角色",
        built_in: false,
      },
    ]);
  });

  it("loads dashboard and report collections from the active connection", async () => {
    const { useArtifacts } = await import("./useArtifacts");
    const artifacts = useArtifacts();

    await artifacts.loadArtifacts();

    expect(dashboardList).toHaveBeenCalledWith("http://api.test");
    expect(reportList).toHaveBeenCalledWith("http://api.test");
    expect(artifacts.dashboards.value).toHaveLength(1);
    expect(artifacts.reports.value).toHaveLength(1);
    expect(artifacts.dashboards.value[0]?.can_manage_share).toBe(true);
    expect(artifacts.reports.value[0]?.can_manage_share).toBe(false);
    expect(artifacts.listError.value).toBeNull();
  });

  it("loads only the scoped artifact collection when refreshing a tab", async () => {
    const { useArtifacts } = await import("./useArtifacts");
    const artifacts = useArtifacts();

    await artifacts.loadArtifacts("report");

    expect(reportList).toHaveBeenCalledWith("http://api.test");
    expect(dashboardList).not.toHaveBeenCalled();
    expect(artifacts.reports.value).toHaveLength(1);
    expect(artifacts.dashboards.value).toHaveLength(0);
    expect(artifacts.listError.value).toBeNull();
  });

  it("loads the route-selected artifact detail and clears the opposite family", async () => {
    const { useArtifacts } = await import("./useArtifacts");
    const artifacts = useArtifacts();

    await artifacts.loadDetail("dashboard", "fund-overview");

    expect(dashboardDetail).toHaveBeenCalledWith("http://api.test", "fund-overview");
    expect(artifacts.activeDetail.value?.slug).toBe("fund-overview");
    expect(artifacts.activeDetailTab.value).toBe("dashboard");

    await artifacts.loadDetail("report", "fund-report");

    expect(reportDetail).toHaveBeenCalledWith("http://api.test", "fund-report");
    expect(artifacts.activeDetail.value?.slug).toBe("fund-report");
    expect(artifacts.activeDetailTab.value).toBe("report");
  });

  it("clears detail state when the route has no slug", async () => {
    const { useArtifacts } = await import("./useArtifacts");
    const artifacts = useArtifacts();

    await artifacts.loadDetail("dashboard", "fund-overview");
    await artifacts.loadDetail("dashboard", "");

    expect(artifacts.activeDetail.value).toBeNull();
    expect(artifacts.activeDetailSlug.value).toBeNull();
    expect(artifacts.detailLoading.value).toBe(false);
  });

  it("reports detail failures without leaving loading active", async () => {
    dashboardDetail.mockRejectedValue(new Error("denied"));
    const { useArtifacts } = await import("./useArtifacts");
    const artifacts = useArtifacts();

    await artifacts.loadDetail("dashboard", "fund-overview");

    expect(artifacts.detailLoading.value).toBe(false);
    expect(artifacts.detailError.value).toBe("读取仪表盘详情失败");
    expect(toastError).toHaveBeenCalledWith("读取仪表盘详情失败");
  });

  it("builds artifact preview URLs through the owning API helper", async () => {
    const { artifactHtml, artifactHtmlUrl } = await import("./useArtifacts");

    expect(artifactHtmlUrl("http://api.test", "dashboard", "fund-overview")).toBe(
      "http://api.test/api/v1/dashboards/fund-overview/html",
    );
    expect(artifactHtmlUrl("http://api.test", "report", "fund-report")).toBe(
      "http://api.test/api/v1/reports/fund-report/html",
    );
    await expect(artifactHtml("http://api.test", "dashboard", "fund-overview")).resolves.toContain("dashboard");
    await expect(artifactHtml("http://api.test", "report", "fund-report")).resolves.toContain("report");
    expect(dashboardHtml).toHaveBeenCalledWith("http://api.test", "fund-overview");
    expect(reportHtml).toHaveBeenCalledWith("http://api.test", "fund-report");
  });

  it("loads artifact sharing ACL through the owning API helper", async () => {
    const { useArtifacts } = await import("./useArtifacts");
    const artifacts = useArtifacts();

    const share = await artifacts.loadShare("report", "fund-report");

    expect(reportGetAcl).toHaveBeenCalledWith("http://api.test", "fund-report");
    expect(dashboardGetAcl).not.toHaveBeenCalled();
    expect(share?.visibility).toBe("role");
    expect(artifacts.activeShare.value?.allowed_user_ids).toEqual(["bob"]);
    expect(artifacts.activeShareTab.value).toBe("report");
    expect(artifacts.activeShareSlug.value).toBe("fund-report");
    expect(artifacts.shareLoadingKey.value).toBeNull();
  });

  it("saves artifact sharing ACL for the active share target", async () => {
    const { useArtifacts } = await import("./useArtifacts");
    const artifacts = useArtifacts();

    await artifacts.loadShare("report", "fund-report");
    const saved = await artifacts.saveShare({
      visibility: "role",
      allowed_roles: ["analyst"],
      allowed_user_ids: ["bob", "charlie"],
    });

    expect(saved).toBe(true);
    expect(reportPutAcl).toHaveBeenCalledWith("http://api.test", "fund-report", {
      visibility: "role",
      allowed_roles: ["analyst"],
      allowed_user_ids: ["bob", "charlie"],
    });
    expect(artifacts.activeShare.value?.allowed_user_ids).toEqual(["bob", "charlie"]);
    expect(artifacts.shareSaving.value).toBe(false);
    expect(toastSuccess).toHaveBeenCalledWith("分享设置已保存");
  });

  it("creates report edit sessions through the report API helper", async () => {
    const { useArtifacts } = await import("./useArtifacts");
    const artifacts = useArtifacts();

    const session = await artifacts.createReportEditSession("fund-report");

    expect(reportCreateEditSession).toHaveBeenCalledWith("http://api.test", "fund-report");
    expect(session?.subagent_id).toBe("report_edit__edit_1");
    expect(artifacts.editLoadingKey.value).toBeNull();
    expect(artifacts.editError.value).toBeNull();
    expect(toastSuccess).toHaveBeenCalledWith("报表编辑会话已创建");
  });

  it("creates dashboard edit sessions through the dashboard API helper", async () => {
    const { useArtifacts } = await import("./useArtifacts");
    const artifacts = useArtifacts();

    const session = await artifacts.createDashboardEditSession("fund-overview");

    expect(dashboardCreateEditSession).toHaveBeenCalledWith("http://api.test", "fund-overview");
    expect(session?.subagent_id).toBe("dashboard_edit__edit_2");
    expect(artifacts.editLoadingKey.value).toBeNull();
    expect(artifacts.editError.value).toBeNull();
    expect(toastSuccess).toHaveBeenCalledWith("仪表盘编辑会话已创建");
  });

  it("loads candidate users and roles for the share picker", async () => {
    const { useArtifacts } = await import("./useArtifacts");
    const artifacts = useArtifacts();

    await artifacts.loadShareDirectory("report");

    expect(listShareUsers).toHaveBeenCalledWith("http://api.test", { artifactType: "report", limit: 100 });
    expect(listShareRoles).toHaveBeenCalledWith("http://api.test", { artifactType: "report", limit: 100 });
    expect(artifacts.shareUserOptions.value).toEqual([
      {
        value: "bob",
        label: "Bob (bob)",
        description: "bob@example.com / Data / Analyst",
      },
      {
        value: "charlie",
        label: "Charlie (charlie)",
        description: undefined,
      },
    ]);
    expect(artifacts.shareRoleOptions.value).toEqual([
      {
        value: "analyst",
        label: "分析师 (analyst)",
        description: "分析角色",
      },
    ]);
    expect(artifacts.shareDirectoryError.value).toBeNull();
  });

  it("loads artifact previews into an embedded viewer from authenticated HTML responses", async () => {
    const createObjectUrl = vi.fn(() => "blob:artifact-preview");
    const revokeObjectUrl = vi.fn();
    vi.stubGlobal("URL", {
      createObjectURL: createObjectUrl,
      revokeObjectURL: revokeObjectUrl,
    });
    const { useArtifacts } = await import("./useArtifacts");
    const artifacts = useArtifacts();

    const url = await artifacts.openHtmlPreview("report", "fund-report");

    expect(reportHtml).toHaveBeenCalledWith("http://api.test", "fund-report");
    expect(createObjectUrl).toHaveBeenCalled();
    expect(url).toBe("blob:artifact-preview");
    expect(artifacts.activePreviewUrl.value).toBe("blob:artifact-preview");
    expect(artifacts.activePreviewTab.value).toBe("report");
    expect(artifacts.activePreviewSlug.value).toBe("fund-report");
    expect(artifacts.previewLoadingKey.value).toBeNull();
    expect(artifacts.previewError.value).toBeNull();
  });

  it("ignores a stale preview failure after a newer preview succeeds", async () => {
    const stalePreview = deferred<string>();
    reportHtml.mockReturnValueOnce(stalePreview.promise);
    dashboardHtml.mockResolvedValueOnce("<!doctype html><html><body>current</body></html>");
    vi.stubGlobal("URL", {
      createObjectURL: vi.fn(() => "blob:current-preview"),
      revokeObjectURL: vi.fn(),
    });
    const { useArtifacts } = await import("./useArtifacts");
    const artifacts = useArtifacts();

    const staleLoad = artifacts.openHtmlPreview("report", "old-report");
    await artifacts.openHtmlPreview("dashboard", "current-dashboard");
    stalePreview.reject(new Error("old preview failed"));
    await staleLoad;

    expect(artifacts.activePreviewUrl.value).toBe("blob:current-preview");
    expect(artifacts.previewError.value).toBeNull();
    expect(toastError).not.toHaveBeenCalledWith("打开 HTML 预览失败");
  });


  it("runs dashboard queries with route-selected slug and template params", async () => {
    const { useArtifacts } = await import("./useArtifacts");
    const artifacts = useArtifacts();

    const result = await artifacts.runDashboardQuery("fund-overview", "total_nav", {
      trade_date: "2026-06-01",
    });

    expect(dashboardQuery).toHaveBeenCalledWith("http://api.test", "fund-overview", "total_nav", {
      trade_date: "2026-06-01",
    });
    expect(result?.row_count).toBe(1);
    expect(artifacts.queryResult.value?.sql).toBe("select 10 as total");
    expect(artifacts.activeQuerySlug.value).toBe("total_nav");
    expect(artifacts.queryError.value).toBeNull();
  });

  it("runs preview dashboard queries without sharing detail-query state", async () => {
    const { useArtifacts } = await import("./useArtifacts");
    const artifacts = useArtifacts();

    const result = await artifacts.runDashboardPreviewQuery(
      "fund-overview",
      "total_nav",
      { trade_date: "2026-06-01" },
      3,
    );

    expect(dashboardQuery).toHaveBeenCalledWith(
      "http://api.test",
      "fund-overview",
      "total_nav",
      { trade_date: "2026-06-01" },
      3,
    );
    expect(result?.row_count).toBe(1);
    expect(artifacts.queryResult.value).toBeNull();
    expect(artifacts.activeQuerySlug.value).toBeNull();
  });

  it("resets dashboard query state when detail target changes", async () => {
    const { useArtifacts } = await import("./useArtifacts");
    const artifacts = useArtifacts();

    await artifacts.runDashboardQuery("fund-overview", "total_nav", {});
    await artifacts.loadDetail("report", "fund-report");

    expect(artifacts.queryResult.value).toBeNull();
    expect(artifacts.activeQuerySlug.value).toBeNull();
    expect(artifacts.queryLoading.value).toBe(false);
  });
});
