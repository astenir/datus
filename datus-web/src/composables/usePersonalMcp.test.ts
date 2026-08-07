import { beforeEach, describe, expect, it, vi } from "vitest";

import { HttpError } from "@/lib/request";

const personalMcpOptions = vi.fn();
const personalMcpServers = vi.fn();
const createPersonalMcp = vi.fn();
const updatePersonalMcp = vi.fn();
const deletePersonalMcp = vi.fn();
const testPersonalMcp = vi.fn();
const personalMcpTools = vi.fn();
const personalMcpSessionBinding = vi.fn();
const toastSuccess = vi.fn();
const toastError = vi.fn();

const server = {
  id: "11111111111111111111111111111111",
  display_name: "个人分析工具",
  transport: "http" as const,
  url: "https://mcp.example.com/api",
  auth_mode: "static_bearer" as const,
  credential_configured: true,
  token_hint: "***oken",
  allowed_tools: ["query"],
  blocked_tools: [],
  enabled: true,
  revision: 1,
};

vi.mock("@/lib/api", () => ({
  meApi: {
    personalMcpOptions,
    personalMcpServers,
    createPersonalMcp,
    updatePersonalMcp,
    deletePersonalMcp,
    testPersonalMcp,
    personalMcpTools,
    personalMcpSessionBinding,
  },
}));

vi.mock("vue-sonner", () => ({
  toast: {
    success: toastSuccess,
    error: toastError,
  },
}));

function abortablePending(signal?: AbortSignal): Promise<never> {
  return new Promise((_, reject) => {
    signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")), { once: true });
  });
}

describe("usePersonalMcp", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    personalMcpOptions.mockResolvedValue({
      success: true,
      data: {
        enabled: true,
        allowed_hosts: ["mcp.example.com"],
        max_servers_per_user: 10,
        max_selected_per_session: 1,
      },
    });
    personalMcpServers.mockResolvedValue({ success: true, data: [server] });
    createPersonalMcp.mockResolvedValue({ success: true, data: server });
    updatePersonalMcp.mockResolvedValue({ success: true, data: { ...server, revision: 2 } });
    deletePersonalMcp.mockResolvedValue({ success: true, data: { deleted: true } });
    testPersonalMcp.mockResolvedValue({
      success: true,
      data: { connected: true, message: "Connected", tools_count: 1 },
    });
    personalMcpTools.mockResolvedValue({
      success: true,
      data: [{ name: "query", description: "Run a query", inputSchema: { type: "object" } }],
    });
    personalMcpSessionBinding.mockResolvedValue({
      success: true,
      data: { session_id: "session-1", servers: [{ mcp_id: server.id, revision: 1 }] },
    });
  });

  it("loads organization options and owner-visible servers", async () => {
    const { usePersonalMcp } = await import("./usePersonalMcp");
    const manager = usePersonalMcp();

    await manager.load();

    expect(manager.isAvailable.value).toBe(true);
    expect(manager.maxSelected.value).toBe(1);
    expect(manager.servers.value).toEqual([server]);
  });

  it("creates and updates without exposing a bearer token in state", async () => {
    const { usePersonalMcp } = await import("./usePersonalMcp");
    const manager = usePersonalMcp();
    const input = {
      display_name: "个人分析工具",
      transport: "http" as const,
      url: "https://mcp.example.com/api",
      token: "raw-secret-token",
      allowed_tools: ["query"],
      blocked_tools: [],
      enabled: true,
    };

    await manager.createServer(input);
    await manager.updateServer(server.id, { ...input, token: undefined });

    expect(createPersonalMcp).toHaveBeenCalledWith(input);
    expect(updatePersonalMcp).toHaveBeenCalledWith(server.id, { ...input, token: undefined });
    expect(JSON.stringify(manager.servers.value)).not.toContain("raw-secret-token");
    expect(manager.servers.value[0]?.revision).toBe(2);
  });

  it("enforces enabled-only selection and the per-session limit", async () => {
    personalMcpServers.mockResolvedValueOnce({
      success: true,
      data: [
        server,
        { ...server, id: "22222222222222222222222222222222", display_name: "第二个工具" },
        { ...server, id: "33333333333333333333333333333333", display_name: "已停用", enabled: false },
      ],
    });
    const { usePersonalMcp } = await import("./usePersonalMcp");
    const manager = usePersonalMcp();
    await manager.load();

    expect(manager.toggleSelection(server.id)).toBe(true);
    expect(manager.toggleSelection("22222222222222222222222222222222")).toBe(false);
    expect(manager.toggleSelection("33333333333333333333333333333333")).toBe(false);
    expect(manager.selectedIds.value).toEqual([server.id]);
    expect(toastError).toHaveBeenCalledWith("每个会话最多选择 1 个个人 MCP");
  });

  it("restores a canonical session binding, locks it, and resets only for a draft", async () => {
    const { usePersonalMcp } = await import("./usePersonalMcp");
    const manager = usePersonalMcp();
    await manager.load();

    await manager.loadSessionBinding("session-1");

    expect(manager.selectedIds.value).toEqual([server.id]);
    expect(manager.selectionLocked.value).toBe(true);
    expect(manager.toggleSelection(server.id)).toBe(false);

    manager.resetDraftSelection();
    expect(manager.selectedIds.value).toEqual([]);
    expect(manager.selectionLocked.value).toBe(false);
    expect(manager.boundSessionId.value).toBeNull();
  });

  it("shows a safe reference count when deletion is blocked", async () => {
    const response = new Response(JSON.stringify({
      detail: { code: "PERSONAL_MCP_SERVER_IN_USE", session_count: 2 },
    }), { status: 409, statusText: "Conflict", headers: { "Content-Type": "application/json" } });
    deletePersonalMcp.mockRejectedValueOnce(new HttpError(409, "Conflict", response));
    const { usePersonalMcp } = await import("./usePersonalMcp");
    const manager = usePersonalMcp();

    expect(await manager.deleteServer(server.id)).toBe(false);
    expect(toastError).toHaveBeenCalledWith("该 MCP 仍被 2 个会话引用，暂时不能删除");
    expect(JSON.stringify(toastError.mock.calls)).not.toContain("mcp.example.com");
  });

  it("aborts a superseded load before applying its result", async () => {
    let firstSignal: AbortSignal | undefined;
    personalMcpOptions.mockImplementationOnce((signal?: AbortSignal) => {
      firstSignal = signal;
      return abortablePending(signal);
    });
    personalMcpServers.mockImplementationOnce((signal?: AbortSignal) => abortablePending(signal));
    const { usePersonalMcp } = await import("./usePersonalMcp");
    const manager = usePersonalMcp();

    const firstLoad = manager.load();
    const secondLoad = manager.load();
    await Promise.all([firstLoad, secondLoad]);

    expect(firstSignal?.aborted).toBe(true);
    expect(manager.servers.value).toEqual([server]);
    expect(manager.loading.value).toBe(false);
  });
});
