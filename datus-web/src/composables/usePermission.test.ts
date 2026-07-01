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
        permissions: ["feature:sql"],
        features: {
          chat: true,
          admin: false,
        },
        datasource_grants: {
          fund: { effect: "allow" },
          blocked: null,
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
      datasources: ["fund"],
      permissions: ["feature:sql"],
      datasource_grants: {
        fund: { effect: "allow" },
        blocked: null,
      },
      is_admin: false,
    });
    expect(permission.hasFeaturePermission("chat")).toBe(true);
    expect(permission.hasFeaturePermission("admin")).toBe(false);
    expect(permission.hasDatasourcePermission("fund")).toBe(true);
    expect(permission.hasDatasourcePermission("blocked")).toBe(false);
  });

  it("treats backend admin status as global datasource access", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(mockJsonResponse({
      success: true,
      data: {
        user_id: "operator",
        is_admin: true,
        features: {},
        datasource_grants: {},
      },
    }));

    const permission = (await import("./usePermission")).usePermission();
    await permission.fetchPermissions();

    expect(permission.isAdmin()).toBe(true);
    expect(permission.hasDatasourcePermission("sample-datasource")).toBe(true);
  });
});
