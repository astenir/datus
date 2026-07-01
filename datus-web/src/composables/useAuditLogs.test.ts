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
    listLogs.mockResolvedValue({ data: { entries: [], limit: 20, has_more: false } });
    exportLogs.mockResolvedValue({
      filename: "audit-logs.csv",
      contentType: "text/csv",
      content: "user_id,action\nadmin,role_update\n",
    });
  });

  it("loads logs with current OpenAPI filters", async () => {
    const entry = {
      id: 42,
      created_at: "2026-07-01T10:00:00Z",
      user_id: "admin",
      action: "role_update",
      resource_type: "role",
      resource_id: "resource_admin",
      decision: "allow",
      reason: null,
      request_id: "req-1",
      metadata: {},
    };
    listLogs.mockResolvedValue({
      data: {
        entries: [entry],
        limit: 20,
        before_id: null,
        next_before_id: null,
        has_more: false,
      },
    });

    const { useAuditLogs } = await import("./useAuditLogs");
    const audit = useAuditLogs();
    audit.searchForm.value = {
      user_id: "admin",
      action: "role_update",
      resource_type: "role",
      resource_id: "resource_admin",
      decision: "allow",
      request_id: "req-1",
      created_after: "2026-07-01T09:00",
      created_before: "2026-07-01T11:00",
    };

    await audit.loadLogs();

    expect(listLogs).toHaveBeenCalledWith({
      limit: 20,
      beforeId: undefined,
      userId: "admin",
      action: "role_update",
      resourceType: "role",
      resourceId: "resource_admin",
      decision: "allow",
      requestId: "req-1",
      createdAfter: "2026-07-01T09:00",
      createdBefore: "2026-07-01T11:00",
    });
    expect(audit.logs.value).toEqual([entry]);
    expect(audit.total.value).toBe(1);
    expect(audit.activeFilterCount.value).toBe(8);
    expect(audit.hasActiveFilters.value).toBe(true);
    expect(audit.formatLogKey(entry, 0)).toBe("audit-log:42");
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
      request_id: "req-1",
      created_after: "2026-07-01T09:00",
      created_before: "2026-07-01T11:00",
    };

    audit.handleReset();

    expect(audit.searchForm.value).toEqual({
      user_id: "",
      action: "",
      resource_type: "",
      resource_id: "",
      decision: "",
      request_id: "",
      created_after: "",
      created_before: "",
    });
    expect(listLogs).toHaveBeenCalledWith({
      limit: 20,
      beforeId: undefined,
      userId: undefined,
      action: undefined,
      resourceType: undefined,
      resourceId: undefined,
      decision: undefined,
      requestId: undefined,
      createdAfter: undefined,
      createdBefore: undefined,
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
      requestId: "req-1",
      createdAfter: "2026-07-01T09:00",
      createdBefore: "2026-07-01T10:00",
      limit: 200,
      beforeId: 42,
    });

    expect(changed).toBe(true);
    expect(audit.searchForm.value).toEqual({
      user_id: "alice",
      action: "sql.execute",
      resource_type: "datasource",
      resource_id: "fund",
      decision: "allow",
      request_id: "req-1",
      created_after: "2026-07-01T09:00",
      created_before: "2026-07-01T10:00",
    });
    expect(audit.limit.value).toBe(200);
    expect(audit.beforeId.value).toBe(42);

    await audit.loadLogs();

    expect(listLogs).toHaveBeenCalledWith({
      limit: 200,
      beforeId: 42,
      userId: "alice",
      action: "sql.execute",
      resourceType: "datasource",
      resourceId: "fund",
      decision: "allow",
      requestId: "req-1",
      createdAfter: "2026-07-01T09:00",
      createdBefore: "2026-07-01T10:00",
    });
    expect(audit.applyRouteFilters({
      userId: "alice",
      action: "sql.execute",
      resourceType: "datasource",
      resourceId: "fund",
      decision: "allow",
      requestId: "req-1",
      createdAfter: "2026-07-01T09:00",
      createdBefore: "2026-07-01T10:00",
      limit: 200,
      beforeId: 42,
    })).toBe(false);
  });

  it("tracks cursor pagination for audit logs", async () => {
    const firstEntry = {
      id: 5,
      created_at: "2026-07-01T10:00:00Z",
      user_id: "admin",
      action: "role_update",
      resource_type: "role",
      resource_id: "resource_admin",
      decision: "allow",
      reason: null,
      request_id: "req-1",
      metadata: {},
    };
    listLogs.mockResolvedValue({
      data: {
        entries: [firstEntry],
        limit: 20,
        before_id: null,
        next_before_id: 5,
        has_more: true,
      },
    });

    const { useAuditLogs } = await import("./useAuditLogs");
    const audit = useAuditLogs();

    await audit.loadLogs();

    expect(audit.hasNextPage.value).toBe(true);
    expect(audit.currentPage.value).toBe(1);
    expect(audit.prepareNextPage()).toBe(5);
    expect(audit.currentPage.value).toBe(2);
    expect(audit.preparePreviousPage()).toBeNull();
    expect(audit.currentPage.value).toBe(1);
  });

  it("falls back to the last entry id when the page omits next cursor", async () => {
    const firstEntry = {
      id: 7,
      created_at: "2026-07-01T10:00:00Z",
      user_id: "admin",
      action: "role_update",
      resource_type: "role",
      resource_id: "resource_admin",
      decision: "allow",
      reason: null,
      request_id: "req-1",
      metadata: {},
    };
    listLogs.mockResolvedValue({
      data: {
        entries: [firstEntry],
        limit: 20,
        before_id: null,
        next_before_id: null,
        has_more: true,
      },
    });

    const { useAuditLogs } = await import("./useAuditLogs");
    const audit = useAuditLogs();

    await audit.loadLogs();

    expect(audit.hasNextPage.value).toBe(true);
    expect(audit.prepareNextPage()).toBe(7);
  });

  it("infers a next cursor for full legacy array pages", async () => {
    const entries = Array.from({ length: 20 }, (_, index) => ({
      id: 100 - index,
      created_at: "2026-07-01T10:00:00Z",
      user_id: "admin",
      action: "role_update",
      resource_type: "role",
      resource_id: "resource_admin",
      decision: "allow",
      reason: null,
      request_id: "req-1",
      metadata: {},
    }));
    listLogs.mockResolvedValue({ data: entries });

    const { useAuditLogs } = await import("./useAuditLogs");
    const audit = useAuditLogs();

    await audit.loadLogs();

    expect(audit.hasNextPage.value).toBe(true);
    expect(audit.prepareNextPage()).toBe(81);
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
      request_id: " req-1 ",
      created_after: " 2026-07-01T09:00 ",
      created_before: " 2026-07-01T11:00 ",
    };

    await audit.exportLogs();

    expect(exportLogs).toHaveBeenCalledWith({
      limit: 200,
      beforeId: undefined,
      userId: "admin",
      action: "role_update",
      resourceType: "role",
      resourceId: "viewer",
      decision: "allow",
      requestId: "req-1",
      createdAfter: "2026-07-01T09:00",
      createdBefore: "2026-07-01T11:00",
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
