import { afterEach, describe, expect, it } from "vitest";

import type { ChatMessage } from "@/types";
import { idleChatStreamActivity } from "@/lib/chat-activity";
import type { ChatRuntimeUpdater, ChatSessionRuntime } from "./useChatRuntimeStore";
import { useChatSessionHistory } from "./useChatSessionHistory";

function createRuntime(messages: ChatMessage[] = []): ChatSessionRuntime {
  return {
    messages,
    isStreaming: false,
    isInsertReady: false,
    isStopping: false,
    streamActivity: idleChatStreamActivity(),
    transportError: null,
    submittedInteractionKeys: new Set(),
    nextEventCursor: 0,
    needsHistoryRefresh: false,
  };
}

const runtimes = new Map<string, ChatSessionRuntime>();
const historyRequestIds = new Map<string, number>();
let historyRequestSequence = 0;

const history = useChatSessionHistory({
  effectiveBase: () => "",
  runtime: {
    getRuntime: runtimeKey => runtimes.get(runtimeKey),
    getController: () => undefined,
    ensureRuntime: runtimeKey => {
      if (!runtimes.has(runtimeKey)) runtimes.set(runtimeKey, createRuntime());
    },
    updateRuntime: (runtimeKey: string, update: ChatRuntimeUpdater) => {
      const runtime = runtimes.get(runtimeKey) ?? createRuntime();
      runtimes.set(runtimeKey, update(runtime));
    },
    invalidateHistory: runtimeKey => {
      const requestId = ++historyRequestSequence;
      historyRequestIds.set(runtimeKey, requestId);
      return requestId;
    },
    isHistoryRequestCurrent: (runtimeKey, requestId) => historyRequestIds.get(runtimeKey) === requestId,
  },
  resumeSession: async () => undefined,
});

describe("useChatSessionHistory", () => {
  afterEach(() => {
    history.dispose();
    runtimes.clear();
    historyRequestIds.clear();
  });

  it("deduplicates concurrent resume attempts for one session", () => {
    expect(history.startResume("session-a")).toBe(true);
    expect(history.startResume("session-a")).toBe(false);

    history.finishResume("session-a");

    expect(history.startResume("session-a")).toBe(true);
  });

  it("tracks active sessions and derives their first user query", () => {
    runtimes.set("session-a", createRuntime([
      { id: "system-message", role: "system", content: "System" },
      { id: "user-message", role: "user", content: "Show the latest orders" },
    ]));

    history.markSessionActive("session-a", true);

    expect(history.sessions.value[0]).toMatchObject({
      session_id: "session-a",
      user_query: "Show the latest orders",
      is_active: true,
    });

    history.markSessionActive("session-a", false);
    expect(history.sessions.value[0]?.is_active).toBe(false);

    history.removeSession("session-a");
    expect(history.sessions.value).toEqual([]);
  });
});
