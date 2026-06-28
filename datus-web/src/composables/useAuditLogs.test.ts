import { beforeEach, describe, expect, it, vi } from "vitest";

const listLogs = vi.fn();
const exportLogs = vi.fn();
const toastSuccess = vi.fn();
const toastError = vi.fn();

vi.mock("@/lib/api", () => ({
  adminAuditApi: {
    listLogs,
    exportLogs,
  },
}));

vi.mock("vue-sonner", () => ({
  toast: {
    success: toastSuccess,
    error: toastError,
  },
}));

describe("useAuditLogs", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
    listLogs.mockResolvedValue({ data: [] });
    exportLogs.mockResolvedValue({
      filename: "audit-logs.csv",
      contentType: "text/csv",
      content: "user_id,action\nadmin,role_update\n",
    });
  });

  it("loads logs with current OpenAPI filters", async () => {
    const entry = {
      user_id: "admin",
      action: "role_update",
      resource_type: "role",
      resource_id: "resource_admin",
      decision: "allow",
      reason: null,
      request_id: "req-1",
      metadata: null,
    };
    listLogs.mockResolvedValue({ data: [entry] });

    const { useAuditLogs } = await import("./useAuditLogs");
    const audit = useAuditLogs();
    audit.searchForm.value = {
      user_id: "admin",
      action: "role_update",
      resource_type: "role",
      resource_id: "resource_admin",
      decision: "allow",
    };

    await audit.loadLogs();

    expect(listLogs).toHaveBeenCalledWith({
      limit: 50,
      userId: "admin",
      action: "role_update",
      resourceType: "role",
      resourceId: "resource_admin",
      decision: "allow",
    });
    expect(audit.logs.value).toEqual([entry]);
    expect(audit.total.value).toBe(1);
    expect(audit.activeFilterCount.value).toBe(5);
    expect(audit.hasActiveFilters.value).toBe(true);
  });

  it("resets filters before reloading logs", async () => {
    const { useAuditLogs } = await import("./useAuditLogs");
    const audit = useAuditLogs();
    audit.searchForm.value = {
      user_id: "admin",
      action: "role_delete",
      resource_type: "role",
      resource_id: "viewer",
      decision: "deny",
    };

    audit.handleReset();

    expect(audit.searchForm.value).toEqual({
      user_id: "",
      action: "",
      resource_type: "",
      resource_id: "",
      decision: "",
    });
    expect(listLogs).toHaveBeenCalledWith({
      limit: 50,
      userId: undefined,
      action: undefined,
      resourceType: undefined,
      resourceId: undefined,
      decision: undefined,
    });
  });

  it("applies route-backed audit filters before loading logs", async () => {
    const { useAuditLogs } = await import("./useAuditLogs");
    const audit = useAuditLogs();

    const changed = audit.applyRouteFilters({
      userId: "alice",
      action: "sql.execute",
      resourceType: "datasource",
      resourceId: "fund",
      decision: "allow",
      limit: 200,
    });

    expect(changed).toBe(true);
    expect(audit.searchForm.value).toEqual({
      user_id: "alice",
      action: "sql.execute",
      resource_type: "datasource",
      resource_id: "fund",
      decision: "allow",
    });
    expect(audit.limit.value).toBe(200);

    await audit.loadLogs();

    expect(listLogs).toHaveBeenCalledWith({
      limit: 200,
      userId: "alice",
      action: "sql.execute",
      resourceType: "datasource",
      resourceId: "fund",
      decision: "allow",
    });
    expect(audit.applyRouteFilters({
      userId: "alice",
      action: "sql.execute",
      resourceType: "datasource",
      resourceId: "fund",
      decision: "allow",
      limit: 200,
    })).toBe(false);
  });

  it("exports filtered audit logs as a CSV download", async () => {
    const clickAnchor = vi.fn();
    const anchor = {
      href: "",
      download: "",
      rel: "",
      click: clickAnchor,
    };
    const createElement = vi.fn(() => anchor);
    const createObjectUrl = vi.fn(() => "blob:audit");
    const revokeObjectUrl = vi.fn();
    vi.stubGlobal("document", { createElement });
    vi.stubGlobal("URL", {
      createObjectURL: createObjectUrl,
      revokeObjectURL: revokeObjectUrl,
    });

    const { useAuditLogs } = await import("./useAuditLogs");
    const audit = useAuditLogs();
    audit.limitValue.value = "200";
    audit.searchForm.value = {
      user_id: " admin ",
      action: " role_update ",
      resource_type: " role ",
      resource_id: " viewer ",
      decision: " allow ",
    };

    await audit.exportLogs();

    expect(exportLogs).toHaveBeenCalledWith({
      limit: 200,
      userId: "admin",
      action: "role_update",
      resourceType: "role",
      resourceId: "viewer",
      decision: "allow",
    });
    expect(createObjectUrl).toHaveBeenCalled();
    expect(anchor.download).toBe("audit-logs.csv");
    expect(clickAnchor).toHaveBeenCalled();
    expect(revokeObjectUrl).toHaveBeenCalledWith("blob:audit");
    expect(toastSuccess).toHaveBeenCalledWith("审计日志已导出");
  });

  it("classifies action variants with supported badge variants", async () => {
    const { useAuditLogs } = await import("./useAuditLogs");
    const audit = useAuditLogs();

    expect(audit.getActionVariant("role_create")).toBe("default");
    expect(audit.getActionVariant("role_delete")).toBe("destructive");
    expect(audit.getActionVariant("role_update")).toBe("default");
    expect(audit.getActionVariant("role_assign")).toBe("default");
    expect(audit.getActionVariant("login")).toBe("secondary");
  });
});
