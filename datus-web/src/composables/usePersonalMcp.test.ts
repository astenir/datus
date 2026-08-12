import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { HttpError } from "@/lib/request";
import { personalMcpDisplayName } from "@/lib/personal-mcp-display";
import { usePersonalMcp } from "./usePersonalMcp";

// vi.mock 工厂会被提升到文件顶部执行，mock 函数必须通过 vi.hoisted 声明，
// 否则静态导入 usePersonalMcp 时会在这些 const 初始化前被引用（TDZ）。
const {
  personalMcpOptions,
  personalMcpServers,
  createPersonalMcp,
  updatePersonalMcp,
  deletePersonalMcp,
  testPersonalMcp,
  personalMcpTools,
  personalMcpSessionBinding,
  personalMcpReferences,
  toastSuccess,
  toastError,
} = vi.hoisted(() => ({
  personalMcpOptions: vi.fn(),
  personalMcpServers: vi.fn(),
  createPersonalMcp: vi.fn(),
  updatePersonalMcp: vi.fn(),
  deletePersonalMcp: vi.fn(),
  testPersonalMcp: vi.fn(),
  personalMcpTools: vi.fn(),
  personalMcpSessionBinding: vi.fn(),
  personalMcpReferences: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));

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
    personalMcpReferences,
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
  let manager: ReturnType<typeof usePersonalMcp> | undefined;

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
      data: {
        session_id: "session-1",
        servers: [{ mcp_id: server.id, revision: 1, display_name: server.display_name }],
      },
    });
    personalMcpReferences.mockResolvedValue({ success: true, data: [] });
  });

  // 状态在模块级共享（会话选择器与管理页共用），每个用例结束后必须 dispose
  // 复位，避免用例间串扰，与 useChatSessionHistory.test.ts 的隔离方式一致。
  afterEach(() => {
    manager?.dispose();
  });

  it("loads organization options and owner-visible servers", async () => {
    manager = usePersonalMcp();

    await manager.load();

    expect(manager.isAvailable.value).toBe(true);
    expect(manager.maxSelected.value).toBe(1);
    expect(manager.servers.value).toEqual([server]);
  });

  it("creates and updates without exposing a bearer token in state", async () => {
    manager = usePersonalMcp();
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
    manager = usePersonalMcp();
    await manager.load();

    expect(manager.toggleSelection(server.id)).toBe(true);
    expect(manager.toggleSelection("22222222222222222222222222222222")).toBe(false);
    expect(manager.toggleSelection("33333333333333333333333333333333")).toBe(false);
    expect(manager.selectedIds.value).toEqual([server.id]);
    expect(toastError).toHaveBeenCalledWith("每个会话最多选择 1 个个人 MCP");
  });

  it("restores a canonical session binding, locks it, and resets only for a draft", async () => {
    manager = usePersonalMcp();
    await manager.load();

    await manager.loadSessionBinding("session-1");

    expect(manager.selectedIds.value).toEqual([server.id]);
    expect(manager.selectionLocked.value).toBe(true);
    expect(manager.toggleSelection(server.id)).toBe(false);
    // 会话绑定把运行时别名 personal_<id> 与 MCP 名称一起注册，供工具卡片解析。
    expect(personalMcpDisplayName(`personal_${server.id}`)).toBe("个人分析工具");

    manager.resetDraftSelection();
    expect(manager.selectedIds.value).toEqual([]);
    expect(manager.selectionLocked.value).toBe(false);
    expect(manager.boundSessionId.value).toBeNull();
    expect(personalMcpDisplayName(`personal_${server.id}`)).toBeUndefined();
  });

  it("shares one server list across instances and keeps it while any instance lives", async () => {
    manager = usePersonalMcp();
    await manager.load();
    const workspaceInstance = usePersonalMcp();
    const managementInstance = usePersonalMcp();

    // 会话选择器（workspace）与管理页（management）读写同一份 servers。
    expect(workspaceInstance.servers.value).toEqual([server]);
    expect(managementInstance.servers.value).toEqual([server]);

    // 管理页实例随 Tab 切换卸载：只要工作区实例还存活，共享状态不得被清空。
    managementInstance.dispose();
    expect(workspaceInstance.servers.value).toEqual([server]);
    expect(workspaceInstance.selectedIds.value).toEqual([]);

    // 工作区实例也卸载（应用卸载）：最后一个实例释放共享状态。
    workspaceInstance.dispose();
    manager.dispose();
    expect(manager.servers.value).toEqual([]);
    expect(manager.options.value).toMatchObject({ enabled: false, allowed_hosts: [] });
  });

  it("shows a safe reference count when deletion is blocked", async () => {
    const response = new Response(JSON.stringify({
      detail: { code: "PERSONAL_MCP_SERVER_IN_USE", session_count: 2 },
    }), { status: 409, statusText: "Conflict", headers: { "Content-Type": "application/json" } });
    deletePersonalMcp.mockRejectedValueOnce(new HttpError(409, "Conflict", response));
    manager = usePersonalMcp();

    expect(await manager.deleteServer(server.id)).toBe(false);
    expect(deletePersonalMcp).toHaveBeenCalledWith(server.id, false);
    expect(toastError).toHaveBeenCalledWith("该 MCP 仍被 2 个会话引用，暂时不能删除");
    expect(JSON.stringify(toastError.mock.calls)).not.toContain("mcp.example.com");
  });

  it("loads the referencing sessions for the delete dialog", async () => {
    personalMcpReferences.mockResolvedValueOnce({
      success: true,
      data: [
        { session_id: "session-1", title: "帮我分析季度销售", updated_at: "2025-01-02T00:00:00Z" },
        { session_id: "session-2", title: "", updated_at: null },
      ],
    });
    manager = usePersonalMcp();

    const references = await manager.loadReferences(server.id);

    expect(personalMcpReferences).toHaveBeenCalledWith(server.id);
    expect(references).toHaveLength(2);
    expect(manager.references(server.id)).toEqual(references);
    expect(manager.referencesLoadingId.value).toBeNull();
  });

  it("force deletes and reports how many session references were unbound", async () => {
    deletePersonalMcp.mockResolvedValueOnce({ success: true, data: { deleted: true, unbound_sessions: 2 } });
    manager = usePersonalMcp();
    await manager.load();
    await manager.loadReferences(server.id);

    expect(await manager.deleteServer(server.id, true)).toBe(true);
    expect(deletePersonalMcp).toHaveBeenCalledWith(server.id, true);
    expect(toastSuccess).toHaveBeenCalledWith("个人 MCP 已删除，并解除 2 个会话的引用");
    expect(manager.servers.value).toEqual([]);
    expect(manager.references(server.id)).toEqual([]);
  });

  it("aborts a superseded load before applying its result", async () => {
    let firstSignal: AbortSignal | undefined;
    personalMcpOptions.mockImplementationOnce((signal?: AbortSignal) => {
      firstSignal = signal;
      return abortablePending(signal);
    });
    personalMcpServers.mockImplementationOnce((signal?: AbortSignal) => abortablePending(signal));
    manager = usePersonalMcp();

    const firstLoad = manager.load();
    const secondLoad = manager.load();
    await Promise.all([firstLoad, secondLoad]);

    expect(firstSignal?.aborted).toBe(true);
    expect(manager.servers.value).toEqual([server]);
    expect(manager.loading.value).toBe(false);
  });
});
