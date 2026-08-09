import { afterEach, describe, expect, it, vi } from "vitest";

import type { ChatMessage } from "@/types";
import { idleChatStreamActivity } from "@/lib/chat-activity";
import type { ChatStreamContext, ChatStreamRuntimeSource } from "./useChatStream";
import { useChatStream } from "./useChatStream";
import type { ChatRuntimeUpdater, ChatSessionRuntime } from "./useChatRuntimeStore";

function createRuntime(messages: ChatMessage[] = []): ChatSessionRuntime {
  return {
    messages,
    isStreaming: true,
    isInsertReady: false,
    isStopping: false,
    streamActivity: idleChatStreamActivity(),
    transportError: null,
    submittedInteractionKeys: new Set(),
    nextEventCursor: 0,
    needsHistoryRefresh: false,
  };
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
  };
}

const runtimes = new Map<string, ChatSessionRuntime>();
const controllers = new Map<string, AbortController>();
const runtime: ChatStreamRuntimeSource = {
  getController: runtimeKey => controllers.get(runtimeKey),
  setController: (runtimeKey, controller) => controllers.set(runtimeKey, controller),
  deleteController: (runtimeKey, controller) => {
    if (controller && controllers.get(runtimeKey) !== controller) return false;
    return controllers.delete(runtimeKey);
  },
  updateRuntime: (runtimeKey: string, update: ChatRuntimeUpdater) => {
    const currentRuntime = runtimes.get(runtimeKey) ?? createRuntime();
    runtimes.set(runtimeKey, update(currentRuntime));
  },
};

describe("useChatStream", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    runtimes.clear();
    controllers.clear();
  });

  it("consumes SSE events, rekeys the runtime, and finalizes the stream", async () => {
    const stream = controlledSseResponse();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(stream.response);
    runtimes.set("draft:1", createRuntime());

    const onSessionId = vi.fn((context: ChatStreamContext, sessionId: string) => {
      const oldRuntime = runtimes.get(context.runtimeKey);
      const controller = controllers.get(context.runtimeKey);
      if (oldRuntime) runtimes.set(sessionId, oldRuntime);
      if (controller) controllers.set(sessionId, controller);
      runtimes.delete(context.runtimeKey);
      controllers.delete(context.runtimeKey);
      context.runtimeKey = sessionId;
      context.sessionId = sessionId;
    });
    const onStreamCompleted = vi.fn(async () => undefined);
    const onStreamSettled = vi.fn();
    const chatStream = useChatStream({
      effectiveBase: () => "",
      runtime,
      onSessionId,
      onStreamCompleted,
      onStreamSettled,
    });

    const streamTask = chatStream.start({
      runtimeKey: "draft:1",
      sessionId: null,
      path: "/api/v1/chat/stream",
      body: { message: "hello" },
      errorContext: "stream",
    });

    await vi.waitFor(() => expect(globalThis.fetch).toHaveBeenCalledTimes(1));
    stream.emit("session", { session_id: "session-a" }, 7);
    stream.emit("message", {
      type: "createMessage",
      payload: {
        message_id: "message-a",
        role: "assistant",
        content: [{ type: "markdown", payload: { content: "hello back" } }],
      },
    }, 8);
    stream.close();
    await streamTask;

    expect(onSessionId).toHaveBeenCalledWith(expect.any(Object), "session-a");
    expect(runtimes.get("session-a")?.messages.map(message => message.content)).toEqual(["hello back"]);
    expect(runtimes.get("session-a")?.isStreaming).toBe(false);
    expect(runtimes.get("session-a")?.streamActivity.phase).toBe("idle");
    expect(runtime.getController("session-a")).toBeUndefined();
    expect(onStreamCompleted).toHaveBeenCalledWith("session-a");
    expect(onStreamSettled).toHaveBeenCalledTimes(1);
  });
});
