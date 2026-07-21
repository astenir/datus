import { afterEach, describe, expect, it, vi } from "vitest";

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });
  return { promise, resolve, reject };
}

const chatApi = {
  compact: vi.fn(),
  deleteSession: vi.fn(),
  insert: vi.fn(),
  sessions: vi.fn().mockResolvedValue({ sessions: [] }),
  stop: vi.fn(),
  userInteraction: vi.fn(),
};

describe("useChatState", () => {
  afterEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
    vi.doUnmock("@/lib/api");
    vi.doUnmock("@/lib/chat");
    vi.doUnmock("@/lib/request");
    vi.doUnmock("@/composables/useConnection");
  });

  it("does not let a stale history response replace the selected session", async () => {
    const historyA = deferred<unknown>();
    const historyB = deferred<unknown>();
    const requestJson = vi.fn()
      .mockReturnValueOnce(historyA.promise)
      .mockReturnValueOnce(historyB.promise);

    vi.doMock("@/lib/api", () => ({ chatApi }));
    vi.doMock("@/composables/useConnection", () => ({
      useConnection: () => ({ effectiveBase: () => "" }),
    }));
    vi.doMock("@/lib/chat", async () => ({
      ...await vi.importActual<typeof import("@/lib/chat")>("@/lib/chat"),
      requestJson,
    }));

    const { useChatState } = await import("./useChatState");
    const state = useChatState();

    state.selectSession("session-a");
    state.selectSession("session-b");

    historyB.resolve({
      success: true,
      data: {
        messages: [{
          message_id: "message-b",
          role: "assistant",
          content: [{ type: "markdown", payload: { content: "history b" } }],
        }],
      },
    });
    await historyB.promise;
    await vi.waitFor(() => {
      expect(state.messages.value.some(message => message.content === "history b")).toBe(true);
    });

    historyA.resolve({
      success: true,
      data: {
        messages: [{
          message_id: "message-a",
          role: "assistant",
          content: [{ type: "markdown", payload: { content: "history a" } }],
        }],
      },
    });
    await historyA.promise;
    await Promise.resolve();

    expect(state.selectedSession.value).toBe("session-b");
    expect(state.messages.value.some(message => message.content === "history b")).toBe(true);
    expect(state.messages.value.some(message => message.content === "history a")).toBe(false);
  });

  it("does not let an aborted stream clear a newer stream controller", async () => {
    const request = vi.fn((_url: string, init?: RequestInit) => new Promise<Response>((_resolve, reject) => {
      init?.signal?.addEventListener("abort", () => {
        reject(new DOMException("aborted", "AbortError"));
      }, { once: true });
    }));

    vi.doMock("@/lib/api", () => ({ chatApi }));
    vi.doMock("@/composables/useConnection", () => ({
      useConnection: () => ({ effectiveBase: () => "" }),
    }));
    vi.doMock("@/lib/request", () => ({ request }));

    const { useChatState } = await import("./useChatState");
    const state = useChatState();
    const messageOptions = {
      message: "hello",
      selectedAgent: "",
      model: "",
      datasource: "",
      database: "",
      schema: "",
    };

    const firstStream = state.sendMessage(messageOptions);
    state.selectSession(null);
    const secondStream = state.sendMessage({ ...messageOptions, message: "next" });
    await firstStream;

    expect(state.isStreaming.value).toBe(true);

    const secondSignal = request.mock.calls[1]?.[1]?.signal;
    expect(secondSignal?.aborted).toBe(false);
    await state.stopSession();
    expect(secondSignal?.aborted).toBe(true);
    await secondStream;
  });

  it("keeps browser transport failures outside durable conversation messages", async () => {
    const request = vi.fn().mockRejectedValue(new Error("network disconnected"));

    vi.doMock("@/lib/api", () => ({ chatApi }));
    vi.doMock("@/composables/useConnection", () => ({
      useConnection: () => ({ effectiveBase: () => "" }),
    }));
    vi.doMock("@/lib/request", () => ({ request }));

    const { useChatState } = await import("./useChatState");
    const state = useChatState();
    await state.sendMessage({
      message: "hello",
      selectedAgent: "",
      model: "",
      datasource: "",
      database: "",
      schema: "",
    });

    expect(state.messages.value).toHaveLength(1);
    expect(state.messages.value[0]?.role).toBe("user");
    expect(state.transportError.value).toEqual({
      type: "error",
      title: "无法连接到对话服务",
      message: "请检查网络连接和服务地址后重试。已保存的会话内容不会受影响。",
    });

    state.clearTransportError();
    expect(state.transportError.value).toBeNull();
  });

  it("does not cache a partial transcript after a transport failure", async () => {
    const requestJson = vi.fn()
      .mockResolvedValueOnce({
        success: true,
        data: {
          messages: [{
            message_id: "before-failure",
            role: "assistant",
            content: [{ type: "markdown", payload: { content: "before failure" } }],
          }],
        },
      })
      .mockResolvedValueOnce({
        success: true,
        data: {
          messages: [{
            message_id: "canonical-after-failure",
            role: "assistant",
            content: [{ type: "markdown", payload: { content: "canonical history" } }],
          }],
        },
      });
    const request = vi.fn().mockRejectedValue(new Error("network disconnected"));

    vi.doMock("@/lib/api", () => ({ chatApi }));
    vi.doMock("@/composables/useConnection", () => ({
      useConnection: () => ({ effectiveBase: () => "" }),
    }));
    vi.doMock("@/lib/request", () => ({ request }));
    vi.doMock("@/lib/chat", async () => ({
      ...await vi.importActual<typeof import("@/lib/chat")>("@/lib/chat"),
      requestJson,
    }));

    const { useChatState } = await import("./useChatState");
    const state = useChatState();
    state.selectSession("session-a");
    await vi.waitFor(() => {
      expect(state.messages.value[0]?.content).toBe("before failure");
    });

    await state.sendMessage({
      message: "new turn",
      selectedAgent: "",
      model: "",
      datasource: "",
      database: "",
      schema: "",
    });
    state.selectSession(null);
    state.selectSession("session-a");

    await vi.waitFor(() => {
      expect(state.messages.value[0]?.content).toBe("canonical history");
    });
    expect(requestJson).toHaveBeenCalledTimes(2);
  });

  it("preserves the current transcript when a history refresh fails", async () => {
    const requestJson = vi.fn()
      .mockResolvedValueOnce({
        success: true,
        data: {
          messages: [{
            message_id: "persisted-message",
            role: "assistant",
            content: [{ type: "markdown", payload: { content: "saved answer" } }],
          }],
        },
      })
      .mockRejectedValueOnce(new Error("history unavailable"));
    chatApi.compact.mockResolvedValueOnce({ success: true });

    vi.doMock("@/lib/api", () => ({ chatApi }));
    vi.doMock("@/composables/useConnection", () => ({
      useConnection: () => ({ effectiveBase: () => "" }),
    }));
    vi.doMock("@/lib/chat", async () => ({
      ...await vi.importActual<typeof import("@/lib/chat")>("@/lib/chat"),
      requestJson,
    }));

    const { useChatState } = await import("./useChatState");
    const state = useChatState();
    state.selectSession("session-a");
    await vi.waitFor(() => {
      expect(state.messages.value[0]?.content).toBe("saved answer");
    });

    await state.compactSession("session-a");

    expect(state.messages.value[0]?.content).toBe("saved answer");
    expect(state.transportError.value).toEqual({
      type: "error",
      title: "会话历史加载失败",
      message: "请检查网络连接和服务地址后重试。已保存的会话内容不会受影响。",
    });
  });
});
