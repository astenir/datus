import { beforeEach, describe, expect, it, vi } from "vitest";

const dashboardList = vi.fn();
const dashboardDetail = vi.fn();
const dashboardHtmlUrl = vi.fn();
const dashboardHtml = vi.fn();
const dashboardGetAcl = vi.fn();
const dashboardPutAcl = vi.fn();
const dashboardQuery = vi.fn();
const listShareUsers = vi.fn();
const listShareRoles = vi.fn();
const reportList = vi.fn();
const reportDetail = vi.fn();
const reportHtmlUrl = vi.fn();
const reportHtml = vi.fn();
const reportGetAcl = vi.fn();
const reportPutAcl = vi.fn();
const toastError = vi.fn();
const toastSuccess = vi.fn();

vi.mock("@/lib/api", () => ({
  dashboardApi: {
    list: dashboardList,
    detail: dashboardDetail,
    htmlUrl: dashboardHtmlUrl,
    html: dashboardHtml,
    getAcl: dashboardGetAcl,
    putAcl: dashboardPutAcl,
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
      },
    ]);
    reportList.mockResolvedValue([
      {
        slug: "fund-report",
        name: "Fund Report",
        description: "Report",
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

  it("opens artifact previews from authenticated HTML responses instead of raw backend URLs", async () => {
    const openedWindow = {
      location: { href: "" },
      opener: {},
      close: vi.fn(),
    };
    const openWindow = vi.fn(() => openedWindow);
    const createObjectUrl = vi.fn(() => "blob:artifact-preview");
    const revokeObjectUrl = vi.fn();
    vi.stubGlobal("window", { open: openWindow });
    vi.stubGlobal("URL", {
      createObjectURL: createObjectUrl,
      revokeObjectURL: revokeObjectUrl,
    });
    const { useArtifacts } = await import("./useArtifacts");
    const artifacts = useArtifacts();

    await artifacts.openHtmlPreview("report", "fund-report");

    expect(openWindow).toHaveBeenCalledWith("about:blank", "_blank");
    expect(openedWindow.opener).toBeNull();
    expect(reportHtml).toHaveBeenCalledWith("http://api.test", "fund-report");
    expect(createObjectUrl).toHaveBeenCalled();
    expect(openedWindow.location.href).toBe("blob:artifact-preview");
    expect(artifacts.previewLoadingKey.value).toBeNull();
    expect(artifacts.previewError.value).toBeNull();
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
