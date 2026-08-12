import { beforeEach, describe, expect, it, vi } from "vitest";

const summary = vi.fn();
const permissions = vi.fn();
const datasourceGrants = vi.fn();
const features = vi.fn();
const sessions = vi.fn();
const usage = vi.fn();
const toastError = vi.fn();

vi.mock("@/lib/api", () => ({
  meApi: {
    summary,
    permissions,
    datasourceGrants,
    features,
    sessions,
    usage,
  },
}));

vi.mock("vue-sonner", () => ({
  toast: {
    error: toastError,
  },
}));

describe("useProfileOverview", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    summary.mockResolvedValue({
      data: {
        user_id: "alice",
        project_id: "fund",
        roles: ["analyst"],
        permissions: ["module.chat"],
        datasource_grants: {},
        features: {},
        is_admin: false,
      },
    });
    permissions.mockResolvedValue({ data: ["module.chat", "module.sql_executor"] });
    datasourceGrants.mockResolvedValue({
      data: {
        finance: { effect: "allow", tables: ["public.accounts"], allow_sql: true },
        blocked: { effect: "deny" },
      },
    });
    features.mockResolvedValue({
      data: {
        chat: true,
        sql_executor: true,
        config_edit: false,
      },
    });
  });

  it("loads the current-user permission overview", async () => {
    const { useProfileOverview } = await import("./useProfileOverview");
    const profile = useProfileOverview();

    await profile.loadProfile();

    expect(summary).toHaveBeenCalled();
    expect(permissions).toHaveBeenCalled();
    expect(datasourceGrants).toHaveBeenCalled();
    expect(features).toHaveBeenCalled();
    expect(sessions).not.toHaveBeenCalled();
    expect(usage).not.toHaveBeenCalled();
    expect(profile.userId.value).toBe("alice");
    expect(profile.roles.value).toEqual(["analyst"]);
    expect(new Set(profile.enabledFeatures.value.map(item => item.code))).toEqual(new Set(["chat", "sql_executor"]));
    expect(profile.datasourceGrantList.value).toEqual([
      {
        datasource: "blocked",
        enabled: false,
        effect: "deny",
        scopeText: "全量访问",
        raw: { effect: "deny" },
      },
      {
        datasource: "finance",
        enabled: true,
        effect: "allow",
        scopeText: "表: public.accounts",
        raw: { effect: "allow", tables: ["public.accounts"], allow_sql: true },
      },
    ]);
  });

  it("falls back to summary fields when detail endpoints return no data", async () => {
    permissions.mockResolvedValue({ data: null });
    datasourceGrants.mockResolvedValue({ data: null });
    features.mockResolvedValue({ data: null });

    const { useProfileOverview } = await import("./useProfileOverview");
    const profile = useProfileOverview();

    await profile.loadProfile();

    expect(profile.permissions.value).toEqual(["module.chat"]);
    expect(profile.datasourceGrantList.value).toEqual([]);
    expect(profile.featureList.value).toEqual([]);
  });

  it("labels every profile feature with the same wording as the role page", async () => {
    features.mockResolvedValue({
      data: {
        chat: true,
        chat_permission_mode: true,
        sql_executor: true,
        datasource_catalog: true,
        kb: true,
        mcp: true,
        mcp_personal: true,
        mcp_server: true,
        mcp_filter: true,
        mcp_personal_ops: true,
        report_view: true,
        report_query: true,
        report_export: true,
        report_edit: true,
        dashboard_view: true,
        dashboard_query: true,
        dashboard_export: true,
        dashboard_edit: true,
        agent_manage: true,
        user_manage: true,
        role_manage: true,
        datasource_manage: true,
        artifact_manage: true,
        session_manage: true,
        audit_view: true,
        audit_export: true,
        quota_manage: true,
        secret_manage: true,
        config_view: true,
        config_edit: true,
        system_status: true,
        admin: true,
      },
    });

    const { useProfileOverview } = await import("./useProfileOverview");
    const profile = useProfileOverview();

    await profile.loadProfile();

    const byCode = new Map(profile.enabledFeatures.value.map(item => [item.code, item.label]));
    expect(byCode.get("chat")).toBe("对话");
    expect(byCode.get("chat_permission_mode")).toBe("高危对话模式");
    expect(byCode.get("mcp_personal")).toBe("个人 MCP");
    expect(byCode.get("mcp_server")).toBe("MCP Server 操作");
    expect(byCode.get("mcp_filter")).toBe("MCP 过滤规则");
    expect(byCode.get("mcp_personal_ops")).toBe("个人 MCP 操作");
    expect(byCode.get("report_export")).toBe("报表导出");
    expect(byCode.get("report_edit")).toBe("报表编辑");
    expect(byCode.get("dashboard_export")).toBe("仪表盘导出");
    expect(byCode.get("dashboard_edit")).toBe("仪表盘编辑");
    expect(byCode.get("agent_manage")).toBe("Agent 管理");
    expect(byCode.get("user_manage")).toBe("用户管理");
    expect(byCode.get("role_manage")).toBe("角色管理");
    expect(byCode.get("datasource_manage")).toBe("数据授权管理");
    expect(byCode.get("artifact_manage")).toBe("产物 ACL 管理");
    expect(byCode.get("session_manage")).toBe("会话管理");
    expect(byCode.get("audit_view")).toBe("审计查看");
    expect(byCode.get("audit_export")).toBe("审计导出");
    expect(byCode.get("quota_manage")).toBe("额度管理");
    expect(byCode.get("secret_manage")).toBe("密钥管理");
    expect(byCode.get("config_view")).toBe("配置查看");
    expect(byCode.get("config_edit")).toBe("配置编辑");
    expect(byCode.get("system_status")).toBe("系统状态");
    expect(byCode.get("admin")).toBe("全部管理权限");
  });

  it("falls back to the raw code for unknown feature codes", async () => {
    features.mockResolvedValue({
      data: { chat: false, future_feature: true },
    });

    const { useProfileOverview } = await import("./useProfileOverview");
    const profile = useProfileOverview();

    await profile.loadProfile();

    expect(profile.enabledFeatures.value).toEqual([{ code: "future_feature", label: "future_feature", enabled: true }]);
  });

  it("shows a toast and keeps the existing state when loading fails", async () => {
    summary.mockRejectedValue(new Error("AUTH_REQUIRED"));
    const { useProfileOverview } = await import("./useProfileOverview");
    const profile = useProfileOverview();

    await profile.loadProfile();

    expect(profile.error.value).toBe("AUTH_REQUIRED");
    expect(toastError).toHaveBeenCalledWith("加载个人权限失败");
  });
});
