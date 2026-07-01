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
    sessions.mockResolvedValue({
      data: {
        sessions: [
          {
            session_id: "session-1",
            user_query: "查询基金规模",
            created_at: "2026-01-01T00:00:00Z",
            last_updated: "2026-01-01T00:01:00Z",
            total_turns: 2,
            token_count: 120,
            is_active: true,
          },
        ],
        total_count: 1,
      },
    });
    usage.mockResolvedValue({
      data: [
        {
          subject_type: "user",
          subject_id: "alice",
          resource: "chat.stream",
          used: 3,
          window_start: "2026-01-01T00:00:00Z",
          window_seconds: 3600,
          updated_at: "2026-01-01T00:05:00Z",
        },
      ],
    });
  });

  it("loads current-user profile, permissions, grants, sessions, and usage", async () => {
    const { useProfileOverview } = await import("./useProfileOverview");
    const profile = useProfileOverview();

    await profile.loadProfile();

    expect(summary).toHaveBeenCalled();
    expect(permissions).toHaveBeenCalled();
    expect(datasourceGrants).toHaveBeenCalled();
    expect(features).toHaveBeenCalled();
    expect(sessions).toHaveBeenCalled();
    expect(usage).toHaveBeenCalled();
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
    expect(profile.runningSessionCount.value).toBe(1);
    expect(profile.totalTokenCount.value).toBe(120);
    expect(profile.totalUsageCount.value).toBe(3);
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

  it("shows a toast and keeps the existing state when loading fails", async () => {
    summary.mockRejectedValue(new Error("AUTH_REQUIRED"));
    const { useProfileOverview } = await import("./useProfileOverview");
    const profile = useProfileOverview();

    await profile.loadProfile();

    expect(profile.error.value).toBe("AUTH_REQUIRED");
    expect(toastError).toHaveBeenCalledWith("加载个人权限与用量失败");
  });
});
