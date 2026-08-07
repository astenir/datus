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

function controlledSseResponse() {
  let streamController!: ReadableStreamDefaultController<Uint8Array>;
  const response = new Response(new ReadableStream<Uint8Array>({
    start(controller) {
      streamController = controller;
    },
  }), {
    headers: { "Content-Type": "text/event-stream" },
  });
  const encoder = new TextEncoder();
  return {
    response,
    emit(event: string, data: unknown, id?: number) {
      const eventId = typeof id === "number" ? `id: ${id}\n` : "";
      streamController.enqueue(encoder.encode(`${eventId}event: ${event}\ndata: ${JSON.stringify(data)}\n\n`));
    },
    close() {
      streamController.close();
    },
    fail(error: Error) {
      streamController.error(error);
    },
  };
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

  it("keeps concurrent session streams alive while switching between them", async () => {
    const streamA = controlledSseResponse();
    const streamB = controlledSseResponse();
    const request = vi.fn()
      .mockResolvedValueOnce(streamA.response)
      .mockResolvedValueOnce(streamB.response);
    const requestJson = vi.fn().mockResolvedValue({
      success: true,
      data: { messages: [] },
    });

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
    const options = {
      selectedAgent: "",
      model: "",
      datasource: "",
      database: "",
      schema: "",
    };

    const firstStream = state.sendMessage({ ...options, message: "first" });
    streamA.emit("session", { session_id: "session-a" });
    await vi.waitFor(() => expect(state.selectedSession.value).toBe("session-a"));

    state.selectSession(null);
    const secondStream = state.sendMessage({ ...options, message: "second" });
    streamB.emit("session", { session_id: "session-b" });
    await vi.waitFor(() => expect(state.selectedSession.value).toBe("session-b"));

    const firstSignal = request.mock.calls[0]?.[1]?.signal;
    const secondSignal = request.mock.calls[1]?.[1]?.signal;
    expect(firstSignal?.aborted).toBe(false);
    expect(secondSignal?.aborted).toBe(false);

    state.selectSession("session-a");
    expect(state.isStreaming.value).toBe(true);
    expect(state.messages.value.some(message => message.content === "first")).toBe(true);

    state.selectSession("session-b");
    expect(state.isStreaming.value).toBe(true);
    expect(state.messages.value.some(message => message.content === "second")).toBe(true);
    expect(firstSignal?.aborted).toBe(false);

    await state.stopSession();
    expect(secondSignal?.aborted).toBe(true);
    expect(firstSignal?.aborted).toBe(false);
    expect(chatApi.stop).toHaveBeenCalledWith("", "session-b");

    state.selectSession("session-a");
    expect(state.isStreaming.value).toBe(true);

    streamA.close();
    streamB.close();
    await Promise.all([firstStream, secondStream]);
  });

  it("resumes every active owned session from the session list", async () => {
    const streamA = controlledSseResponse();
    const streamB = controlledSseResponse();
    chatApi.sessions.mockResolvedValueOnce({
      sessions: [
        { session_id: "session-a", is_active: true },
        { session_id: "session-b", is_active: true },
        { session_id: "session-c", is_active: false },
      ],
    });
    const request = vi.fn()
      .mockResolvedValueOnce(streamA.response)
      .mockResolvedValueOnce(streamB.response);
    const requestJson = vi.fn().mockResolvedValue({
      success: true,
      data: { messages: [] },
    });

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
    await state.loadSessions();

    await vi.waitFor(() => expect(request).toHaveBeenCalledTimes(2));
    const requestedBodies = request.mock.calls.map(call => JSON.parse(String(call[1]?.body)) as { session_id: string });
    expect(requestedBodies.map(body => body.session_id).sort()).toEqual(["session-a", "session-b"]);

    state.selectSession("session-a");
    expect(state.isStreaming.value).toBe(true);
    state.selectSession("session-b");
    expect(state.isStreaming.value).toBe(true);
    state.selectSession("session-c");
    expect(state.isStreaming.value).toBe(false);

    streamA.close();
    streamB.close();
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

  it("allows a supplemental message only after the current session event", async () => {
    const stream = controlledSseResponse();
    const request = vi.fn().mockResolvedValue(stream.response);
    const requestJson = vi.fn().mockResolvedValue({ success: true, data: { messages: [] } });
    chatApi.insert.mockResolvedValueOnce({ session_id: "session-a", queued_count: 1 });

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
    const streamTask = state.sendMessage({
      message: "分析当前持仓",
      selectedAgent: "",
      model: "",
      datasource: "",
      database: "",
      schema: "",
    });

    expect(state.isStreaming.value).toBe(true);
    expect(state.isInsertReady.value).toBe(false);
    await expect(state.insertMessage("补充条件")).rejects.toThrow("当前会话尚未建立");
    expect(chatApi.insert).not.toHaveBeenCalled();

    stream.emit("session", { session_id: "session-a" });
    await vi.waitFor(() => expect(state.isInsertReady.value).toBe(true));

    await expect(state.insertMessage("  补充条件  ")).resolves.toEqual({
      session_id: "session-a",
      queued_count: 1,
    });

    expect(chatApi.insert).toHaveBeenCalledWith("", "session-a", "补充条件");
    expect(state.transportError.value).toBeNull();

    stream.close();
    await streamTask;
    expect(state.isInsertReady.value).toBe(false);
  });

  it("waits for a new session event before supplementing a later turn in the same session", async () => {
    const firstStream = controlledSseResponse();
    const secondStream = controlledSseResponse();
    const request = vi.fn()
      .mockResolvedValueOnce(firstStream.response)
      .mockResolvedValueOnce(secondStream.response);
    const requestJson = vi.fn().mockResolvedValue({ success: true, data: { messages: [] } });

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
    const options = {
      selectedAgent: "",
      model: "",
      datasource: "",
      database: "",
      schema: "",
    };

    const firstTask = state.sendMessage({ ...options, message: "第一轮" });
    firstStream.emit("session", { session_id: "session-a" });
    await vi.waitFor(() => expect(state.isInsertReady.value).toBe(true));
    firstStream.close();
    await firstTask;

    const secondTask = state.sendMessage({ ...options, message: "第二轮" });
    expect(state.selectedSession.value).toBe("session-a");
    expect(state.isStreaming.value).toBe(true);
    expect(state.isInsertReady.value).toBe(false);
    await expect(state.insertMessage("补充条件")).rejects.toThrow("正在建立会话，请稍候");
    expect(chatApi.insert).not.toHaveBeenCalled();

    secondStream.emit("session", { session_id: "session-a" });
    await vi.waitFor(() => expect(state.isInsertReady.value).toBe(true));
    secondStream.close();
    await secondTask;
  });

  it("keeps insert readiness when resuming from a cursor after the session event", async () => {
    const firstStream = controlledSseResponse();
    const resumedStream = controlledSseResponse();
    const request = vi.fn()
      .mockResolvedValueOnce(firstStream.response)
      .mockResolvedValueOnce(resumedStream.response);
    const requestJson = vi.fn().mockResolvedValue({ success: true, data: { messages: [] } });

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
    const streamTask = state.sendMessage({
      message: "分析当前持仓",
      selectedAgent: "",
      model: "",
      datasource: "",
      database: "",
      schema: "",
    });
    firstStream.emit("session", { session_id: "session-a" }, 0);
    await vi.waitFor(() => expect(state.isInsertReady.value).toBe(true));

    firstStream.fail(new Error("network disconnected"));
    await streamTask;
    expect(state.isStreaming.value).toBe(false);
    expect(state.isInsertReady.value).toBe(true);

    const resumeTask = state.resumeSession();
    await vi.waitFor(() => expect(request).toHaveBeenCalledTimes(2));
    expect(JSON.parse(String(request.mock.calls[1]?.[1]?.body))).toEqual({
      session_id: "session-a",
      from_event_id: 1,
    });
    expect(state.isStreaming.value).toBe(true);
    expect(state.isInsertReady.value).toBe(true);

    resumedStream.close();
    await resumeTask;
  });

  it("keeps a resumed permission active after a late todo result", async () => {
    const stream = controlledSseResponse();
    const request = vi.fn().mockResolvedValue(stream.response);
    const requestJson = vi.fn().mockResolvedValue({ success: true, data: { messages: [] } });

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
    await vi.waitFor(() => expect(requestJson).toHaveBeenCalledTimes(1));

    const resumeTask = state.resumeSession("session-a");
    stream.emit("message", {
      type: "createMessage",
      payload: {
        message_id: "write-call",
        role: "assistant",
        content: [{
          type: "call-tool",
          payload: {
            callToolId: "write-call",
            toolName: "write_file",
            toolParams: { path: "report.md" },
          },
        }],
      },
    }, 3744);
    stream.emit("message", {
      type: "createMessage",
      payload: {
        message_id: "permission-action-1",
        role: "assistant",
        content: [{
          type: "user-interaction",
          payload: {
            interactionKey: "permission-action-1",
            actionType: "request_choice",
            requests: [{
              content: "Permission Request",
              options: [{ key: "y", title: "Allow" }, { key: "n", title: "Deny" }],
            }],
          },
        }],
      },
    }, 3746);
    stream.emit("message", {
      type: "createMessage",
      payload: {
        message_id: "late-todo-result",
        role: "assistant",
        content: [{
          type: "call-tool-result",
          payload: {
            callToolId: "todo-call-1",
            toolName: "todo_update",
            result: {},
          },
        }],
      },
    }, 3747);

    await vi.waitFor(() => {
      expect(state.streamActivity.value.phase).toBe("awaiting_user");
      expect(state.activeInteractionKey.value).toBe("permission-action-1");
    });

    stream.close();
    await resumeTask;
  });

  it("propagates a ready supplemental-message rejection without turning it into a stream error", async () => {
    const stream = controlledSseResponse();
    const request = vi.fn().mockResolvedValue(stream.response);
    const requestJson = vi.fn().mockResolvedValue({ success: true, data: { messages: [] } });
    chatApi.insert.mockRejectedValueOnce(new Error("chat task is ending"));

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
    const streamTask = state.sendMessage({
      message: "分析当前持仓",
      selectedAgent: "",
      model: "",
      datasource: "",
      database: "",
      schema: "",
    });
    stream.emit("session", { session_id: "session-a" });
    await vi.waitFor(() => expect(state.isInsertReady.value).toBe(true));

    await expect(state.insertMessage("补充条件")).rejects.toThrow("chat task is ending");

    expect(state.transportError.value).toBeNull();

    stream.close();
    await streamTask;
  });

  it("keeps the session streaming while stop is pending and blocks supplemental messages", async () => {
    const stream = controlledSseResponse();
    const request = vi.fn().mockResolvedValue(stream.response);
    const requestJson = vi.fn().mockResolvedValue({ success: true, data: { messages: [] } });
    const stop = deferred<unknown>();
    chatApi.stop.mockReturnValueOnce(stop.promise);

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
    const streamTask = state.sendMessage({
      message: "分析当前持仓",
      selectedAgent: "",
      model: "",
      datasource: "",
      database: "",
      schema: "",
    });
    stream.emit("session", { session_id: "session-a" });
    await vi.waitFor(() => expect(state.isInsertReady.value).toBe(true));

    const stopTask = state.stopSession();
    expect(state.isStreaming.value).toBe(true);
    expect(state.isStopping.value).toBe(true);
    expect(state.isInsertReady.value).toBe(false);
    expect(state.streamActivity.value.phase).toBe("stopping");
    await expect(state.insertMessage("补充条件")).rejects.toThrow("正在停止当前任务");
    expect(chatApi.insert).not.toHaveBeenCalled();

    stop.resolve({ session_id: "session-a", stopped: true });
    await stopTask;

    expect(state.isStreaming.value).toBe(false);
    expect(state.isStopping.value).toBe(false);
    expect(state.isInsertReady.value).toBe(false);
    expect(state.streamActivity.value.phase).toBe("idle");

    stream.close();
    await streamTask;
  });

  it("keeps insert readiness for a later resume when stopping fails", async () => {
    const stream = controlledSseResponse();
    const request = vi.fn().mockResolvedValue(stream.response);
    const requestJson = vi.fn().mockResolvedValue({ success: true, data: { messages: [] } });
    chatApi.stop.mockRejectedValueOnce(new Error("stop request failed"));

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
    const streamTask = state.sendMessage({
      message: "分析当前持仓",
      selectedAgent: "",
      model: "",
      datasource: "",
      database: "",
      schema: "",
    });
    stream.emit("session", { session_id: "session-a" });
    await vi.waitFor(() => expect(state.isInsertReady.value).toBe(true));

    await state.stopSession();

    expect(state.isStreaming.value).toBe(false);
    expect(state.isStopping.value).toBe(false);
    expect(state.isInsertReady.value).toBe(true);
    expect(state.transportError.value?.title).toBe("停止会话失败");

    stream.close();
    await streamTask;
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
