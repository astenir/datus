import { afterEach, describe, expect, it, vi } from "vitest";

function mockJsonResponse(payload: unknown) {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("usePermission", () => {
  afterEach(async () => {
    vi.restoreAllMocks();
    const { usePermission } = await import("./usePermission");
    usePermission().clearPermissions();
  });

  it("normalizes the current /api/v1/me permission summary", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(mockJsonResponse({
      success: true,
      data: {
        user_id: "alice",
        is_admin: false,
        permissions: ["feature:sql", "module.admin.*", "mcp.server.list"],
        features: {
          chat: true,
          admin: false,
        },
        views: {
          chat: true,
          mcp: false,
          permissions: true,
        },
        datasource_grants: {
          fund: { effect: "allow" },
          blocked: { effect: "deny" },
        },
      },
    }));

    const permission = (await import("./usePermission")).usePermission();
    const result = await permission.fetchPermissions();

    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/me",
      expect.objectContaining({ method: "GET" }),
    );
    expect(result).toEqual({
      user_id: "alice",
      features: ["chat"],
      views: ["chat", "permissions"],
      datasources: ["fund"],
      permissions: ["feature:sql", "module.admin.*", "mcp.server.list"],
      datasource_grants: {
        fund: { effect: "allow" },
        blocked: { effect: "deny" },
      },
      is_admin: false,
    });
    expect(permission.hasFeaturePermission("chat")).toBe(true);
    expect(permission.hasFeaturePermission("admin")).toBe(false);
    expect(permission.hasViewPermission("chat")).toBe(true);
    expect(permission.hasViewPermission("mcp")).toBe(false);
    expect(permission.hasViewPermission("permissions")).toBe(true);
    expect(permission.hasPermission("module.admin.agents")).toBe(true);
    expect(permission.hasPermission("mcp.server.list")).toBe(true);
    expect(permission.hasPermission("module.mcp")).toBe(false);
    expect(permission.hasDatasourcePermission("fund")).toBe(true);
    expect(permission.hasDatasourcePermission("blocked")).toBe(false);
  });

  it("keeps backend admin status separate from datasource access", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(mockJsonResponse({
      success: true,
      data: {
        user_id: "operator",
        is_admin: true,
        features: {},
        datasource_grants: {
          fund: { effect: "allow" },
        },
      },
    }));

    const permission = (await import("./usePermission")).usePermission();
    await permission.fetchPermissions();

    expect(permission.isAdmin()).toBe(true);
    expect(permission.hasDatasourcePermission("fund")).toBe(true);
    expect(permission.hasDatasourcePermission("sample-datasource")).toBe(false);
  });

  it("treats wildcard datasource grants as access to concrete datasource names", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(mockJsonResponse({
      success: true,
      data: {
        user_id: "analyst",
        is_admin: false,
        features: {},
        datasource_grants: {
          "*": { effect: "allow", allow_catalog: true },
        },
      },
    }));

    const permission = (await import("./usePermission")).usePermission();
    await permission.fetchPermissions();

    expect(permission.hasDatasourcePermission("fund")).toBe(true);
    expect(permission.hasDatasourcePermission("hr")).toBe(true);
  });

  it("derives workspace views when the backend summary has not sent views yet", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(mockJsonResponse({
      success: true,
      data: {
        user_id: "operator",
        is_admin: false,
        permissions: ["module.config.view", "module.report.view"],
        features: {},
        datasource_grants: {},
      },
    }));

    const permission = (await import("./usePermission")).usePermission();
    const result = await permission.fetchPermissions();

    expect(result?.views).toEqual(["artifacts", "artifact_reports", "configuration", "profile"]);
    expect(permission.hasViewPermission("configuration")).toBe(true);
    expect(permission.hasViewPermission("artifact_dashboards")).toBe(false);
  });

  it("does not derive knowledge view from datasource catalog support permission", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(mockJsonResponse({
      success: true,
      data: {
        user_id: "sql_user",
        is_admin: false,
        permissions: ["module.sql_executor", "module.datasource_catalog"],
        features: {
          datasource_catalog: true,
        },
        datasource_grants: {},
      },
    }));

    const permission = (await import("./usePermission")).usePermission();
    const result = await permission.fetchPermissions();

    expect(result?.views).toEqual(["profile"]);
    expect(permission.hasViewPermission("knowledge")).toBe(false);
    expect(permission.hasFeaturePermission("datasource_catalog")).toBe(true);
    expect(permission.hasPermission("module.datasource_catalog")).toBe(true);
  });
});
