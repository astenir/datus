import { describe, expect, it, vi } from "vitest";

import { idleChatStreamActivity } from "@/lib/chat-activity";
import type {
  ChatSessionFlowHistorySource,
  ChatSessionFlowRuntimeSource,
  ChatSessionMessageOptions,
  ChatSessionSettings,
} from "./useChatSessionFlow";
import { useChatSessionFlow } from "./useChatSessionFlow";
import type { ChatStreamRequest } from "./useChatStream";
import type { ChatRuntimeUpdater, ChatSessionRuntime } from "./useChatRuntimeStore";

function createRuntime(): ChatSessionRuntime {
  return {
    messages: [],
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

function createHarness(sessionId: string | null = null) {
  const runtimeKey = sessionId ?? "draft:one";
  const selectedSession = { value: sessionId };
  const selectedRuntimeKey = { value: runtimeKey };
  const runtimes = new Map<string, ChatSessionRuntime>([[runtimeKey, createRuntime()]]);
  const controllers = new Set<string>();
  const resumeInFlight = new Set<string>();
  const streamStart = vi.fn<(input: ChatStreamRequest) => Promise<void>>().mockResolvedValue(undefined);
  const runtime: ChatSessionFlowRuntimeSource = {
    getSelectedSession: () => selectedSession.value,
    ensureSelectedRuntime: () => selectedRuntimeKey.value,
    hasController: key => controllers.has(key),
    getRuntime: key => runtimes.get(key),
    ensureRuntime: key => {
      if (!runtimes.has(key)) runtimes.set(key, createRuntime());
    },
    updateRuntime: (key: string, update: ChatRuntimeUpdater) => {
      runtimes.set(key, update(runtimes.get(key) ?? createRuntime()));
    },
  };
  const history: ChatSessionFlowHistorySource = {
    invalidateHistory: vi.fn(),
    clearResumeAttempt: vi.fn(),
    startResume: vi.fn(key => {
      if (resumeInFlight.has(key)) return false;
      resumeInFlight.add(key);
      return true;
    }),
    finishResume: vi.fn(key => {
      resumeInFlight.delete(key);
    }),
    loadSessionHistory: vi.fn().mockResolvedValue(undefined),
  };
  const settings: ChatSessionSettings = {
    language: "zh",
    planMode: true,
    permissionMode: "normal",
  };

  return {
    runtime,
    history,
    streamStart,
    runtimes,
    settings,
  };
}

function createFlow(harness: ReturnType<typeof createHarness>) {
  return useChatSessionFlow({
    runtime: harness.runtime,
    history: harness.history,
    stream: { start: harness.streamStart },
    getChatSettings: () => harness.settings,
  });
}

describe("useChatSessionFlow", () => {
  it("initializes a new message runtime and builds the stream request", async () => {
    const harness = createHarness();
    const flow = createFlow(harness);
    const options: ChatSessionMessageOptions = {
      message: "查看销售额",
      selectedAgent: "chat",
      model: "model-a",
      datasource: "warehouse",
      database: "analytics",
      schema: "public",
      personalMcpIds: ["mcp-a"],
    };

    await flow.sendMessage(options);

    const runtime = harness.runtimes.get("draft:one");
    expect(runtime?.messages).toHaveLength(1);
    expect(runtime?.messages[0]?.content).toBe("查看销售额");
    expect(runtime?.isStreaming).toBe(true);
    expect(runtime?.streamActivity.phase).toBe("submitting");
    expect(harness.history.invalidateHistory).toHaveBeenCalledWith("draft:one");

    expect(harness.streamStart).toHaveBeenCalledTimes(1);
    expect(harness.streamStart.mock.calls[0]?.[0]).toMatchObject({
      runtimeKey: "draft:one",
      sessionId: null,
      path: "/api/v1/chat/stream",
      errorContext: "stream",
      body: {
        message: "查看销售额",
        session_id: null,
        subagent_id: "chat",
        model: "model-a",
        datasource: "warehouse",
        database: "analytics",
        db_schema: "public",
        language: "zh",
        plan_mode: true,
        permission_mode: "normal",
        personal_mcp_ids: ["mcp-a"],
      },
    });
  });

  it("loads an empty session before resuming from its event cursor", async () => {
    const harness = createHarness("session-a");
    harness.runtime.updateRuntime("session-a", runtime => ({ ...runtime, nextEventCursor: 4 }));
    const flow = createFlow(harness);

    await flow.resumeSession();

    expect(harness.history.startResume).toHaveBeenCalledWith("session-a");
    expect(harness.history.loadSessionHistory).toHaveBeenCalledWith("session-a");
    expect(harness.history.finishResume).toHaveBeenCalledWith("session-a");
    expect(harness.streamStart).toHaveBeenCalledWith(expect.objectContaining({
      runtimeKey: "session-a",
      sessionId: "session-a",
      path: "/api/v1/chat/resume",
      errorContext: "resume",
      body: {
        session_id: "session-a",
        from_event_id: 4,
      },
    }));
    expect(harness.runtimes.get("session-a")?.isStreaming).toBe(true);
  });
});
