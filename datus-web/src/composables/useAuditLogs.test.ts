import { beforeEach, describe, expect, it, vi } from "vitest";

const listActionTypes = vi.fn();
const listLogs = vi.fn();

vi.mock("@/lib/api", () => ({
  adminAuditApi: {
    listActionTypes,
    listLogs,
  },
}));

describe("useAuditLogs", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loads action types and maps action labels", async () => {
    listActionTypes.mockResolvedValue({
      data: [{ value: "role_create", label: "创建角色" }],
    });

    const { useAuditLogs } = await import("./useAuditLogs");
    const audit = useAuditLogs();

    await audit.loadActionTypes();

    expect(audit.actionTypes.value).toEqual([{ value: "role_create", label: "创建角色" }]);
    expect(audit.getActionText("role_create")).toBe("创建角色");
    expect(audit.getActionText("unknown_action")).toBe("unknown_action");
  });

  it("loads logs with current filters", async () => {
    listLogs.mockResolvedValue({
      data: {
        logs: [
          {
            id: 1,
            operator_id: "admin",
            operator_name: "Admin",
            action: "role_update",
            target_type: "role",
            target_id: "1",
            target_name: "管理员",
            detail: null,
            ip_address: "127.0.0.1",
            user_agent: null,
            created_at: "2026-06-22T00:00:00Z",
          },
        ],
        total: 1,
        page: 1,
        size: 20,
      },
    });

    const { useAuditLogs } = await import("./useAuditLogs");
    const audit = useAuditLogs();
    audit.searchForm.value = {
      start_date: "2026-06-01",
      end_date: "2026-06-22",
      action: "role_update",
    };

    await audit.loadLogs();

    expect(listLogs).toHaveBeenCalledWith({
      page: 1,
      size: 20,
      startDate: "2026-06-01",
      endDate: "2026-06-22",
      action: "role_update",
    });
    expect(audit.logs.value).toHaveLength(1);
    expect(audit.total.value).toBe(1);
  });

  it("resets filters before reloading logs", () => {
    listLogs.mockResolvedValue({ data: { logs: [], total: 0, page: 1, size: 20 } });

    return import("./useAuditLogs").then(({ useAuditLogs }) => {
      const audit = useAuditLogs();
      audit.searchForm.value = {
        start_date: "2026-06-01",
        end_date: "2026-06-22",
        action: "role_delete",
      };
      audit.page.value = 3;

      audit.handleReset();

      expect(audit.searchForm.value).toEqual({ start_date: "", end_date: "", action: "" });
      expect(audit.page.value).toBe(1);
      expect(listLogs).toHaveBeenCalledWith({
        page: 1,
        size: 20,
        startDate: "",
        endDate: "",
        action: "",
      });
    });
  });

  it("keeps pagination inside valid bounds", async () => {
    listLogs.mockResolvedValue({ data: { logs: [], total: 40, page: 1, size: 20 } });

    const { useAuditLogs } = await import("./useAuditLogs");
    const audit = useAuditLogs();
    audit.total.value = 40;

    audit.goToPage(2);
    audit.goToPage(3);
    audit.goToPage(0);

    expect(audit.page.value).toBe(2);
    expect(listLogs).toHaveBeenCalledTimes(1);
  });

  it("classifies action variants", async () => {
    const { useAuditLogs } = await import("./useAuditLogs");
    const audit = useAuditLogs();

    expect(audit.getActionVariant("role_create")).toBe("success");
    expect(audit.getActionVariant("role_delete")).toBe("destructive");
    expect(audit.getActionVariant("role_update")).toBe("default");
    expect(audit.getActionVariant("role_assign")).toBe("default");
    expect(audit.getActionVariant("login")).toBe("secondary");
  });
});
