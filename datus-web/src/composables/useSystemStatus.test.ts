import { beforeEach, describe, expect, it, vi } from "vitest";

const status = vi.fn();
const toastError = vi.fn();

vi.mock("@/lib/api", () => ({
  systemApi: {
    status,
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
  },
}));

describe("useSystemStatus", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    status.mockResolvedValue({
      platform_status: "readonly",
      enterprise_enabled: true,
      project_id: "fund",
      current_datasource: "postgres",
      active_tasks: 1,
      known_tasks: 3,
    });
  });

  it("loads and exposes normalized operator status", async () => {
    const { useSystemStatus } = await import("./useSystemStatus");
    const manager = useSystemStatus();

    await manager.loadStatus();

    expect(status).toHaveBeenCalledWith("http://api.test");
    expect(manager.status.value).toEqual({
      platform_status: "readonly",
      enterprise_enabled: true,
      project_id: "fund",
      current_datasource: "postgres",
      active_tasks: 1,
      known_tasks: 3,
    });
    expect(manager.hasActiveTasks.value).toBe(true);
    expect(manager.taskSummary.value).toBe("1 / 3");
  });

  it("normalizes malformed status fields without crashing consumers", async () => {
    status.mockResolvedValue({
      platform_status: "",
      enterprise_enabled: "yes",
      project_id: "",
      current_datasource: "  ",
      active_tasks: -2.5,
      known_tasks: Number.NaN,
    });

    const { useSystemStatus } = await import("./useSystemStatus");
    const manager = useSystemStatus();

    await manager.loadStatus();

    expect(manager.status.value).toEqual({
      platform_status: "unknown",
      enterprise_enabled: false,
      project_id: null,
      current_datasource: null,
      active_tasks: 0,
      known_tasks: 0,
    });
    expect(manager.taskSummary.value).toBe("0 / 0");
  });

  it("reports load failures and clears loading state", async () => {
    status.mockRejectedValue(new Error("denied"));
    const { useSystemStatus } = await import("./useSystemStatus");
    const manager = useSystemStatus();

    await manager.loadStatus();

    expect(manager.loading.value).toBe(false);
    expect(manager.error.value).toBe("读取系统状态失败");
    expect(toastError).toHaveBeenCalledWith("读取系统状态失败");
  });
});

describe("normalizeSystemStatus", () => {
  it("returns null for non-object payloads", async () => {
    const { normalizeSystemStatus } = await import("./useSystemStatus");

    expect(normalizeSystemStatus(null)).toBeNull();
    expect(normalizeSystemStatus("offline")).toBeNull();
  });
});
