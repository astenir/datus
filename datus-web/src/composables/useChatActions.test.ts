import { afterEach, describe, expect, it, vi } from "vitest";

import { idleChatStreamActivity } from "@/lib/chat-activity";
import type { ChatActionsHistorySource, ChatActionsRuntimeSource } from "./useChatActions";
import type { ChatRuntimeUpdater, ChatSessionRuntime } from "./useChatRuntimeStore";

const chatApi = {
  compact: vi.fn(),
  deleteSession: vi.fn(),
  insert: vi.fn(),
  stop: vi.fn(),
  userInteraction: vi.fn(),
};

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

function createHarness() {
  const selectedSession = { value: "session-a" };
  const selectedRuntimeKey = { value: "session-a" };
  const runtimes = new Map<string, ChatSessionRuntime>([["session-a", createRuntime()]]);
  const controllers = new Map<string, AbortController>();
  const runtime: ChatActionsRuntimeSource = {
    getSelectedSession: () => selectedSession.value,
    getSelectedRuntimeKey: () => selectedRuntimeKey.value,
    getIsStreaming: () => runtimes.get(selectedRuntimeKey.value)?.isStreaming ?? false,
    getIsInsertReady: () => runtimes.get(selectedRuntimeKey.value)?.isInsertReady ?? false,
    getIsStopping: () => runtimes.get(selectedRuntimeKey.value)?.isStopping ?? false,
    getActiveInteractionKey: () => "interaction-a",
    getRuntime: runtimeKey => runtimes.get(runtimeKey),
    getController: runtimeKey => controllers.get(runtimeKey),
    deleteController: (runtimeKey, controller) => {
      if (controller && controllers.get(runtimeKey) !== controller) return false;
      return controllers.delete(runtimeKey);
    },
    updateRuntime: (runtimeKey: string, update: ChatRuntimeUpdater) => {
      const currentRuntime = runtimes.get(runtimeKey) ?? createRuntime();
      runtimes.set(runtimeKey, update(currentRuntime));
    },
    removeRuntime: runtimeKey => {
      runtimes.delete(runtimeKey);
    },
  };
  const history: ChatActionsHistorySource = {
    loadSessions: vi.fn().mockResolvedValue(undefined),
    loadSessionHistory: vi.fn().mockResolvedValue(undefined),
    markSessionActive: vi.fn(),
    clearResumeAttempt: vi.fn(),
    removeSession: vi.fn(),
  };

  return {
    runtime,
    history,
    runtimes,
    controllers,
    clearSelectedSession: vi.fn(),
  };
}

async function createActions(harness: ReturnType<typeof createHarness>) {
  const { useChatActions } = await import("./useChatActions");
  return useChatActions({
    effectiveBase: () => "",
    runtime: harness.runtime,
    history: harness.history,
    clearSelectedSession: harness.clearSelectedSession,
  });
}

describe("useChatActions", () => {
  afterEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
    vi.doUnmock("@/lib/api");
  });

  it("submits an interaction and resumes the stream activity", async () => {
    vi.doMock("@/lib/api", () => ({ chatApi }));
    const harness = createHarness();
    harness.runtime.updateRuntime("session-a", runtime => ({
      ...runtime,
      isStreaming: true,
      streamActivity: { ...runtime.streamActivity, phase: "awaiting_user" },
    }));
    chatApi.userInteraction.mockResolvedValue({ success: true });

    const actions = await createActions(harness);
    await actions.sendInteraction("interaction-a", "Allow");

    expect(chatApi.userInteraction).toHaveBeenCalledWith("", {
      session_id: "session-a",
      interaction_key: "interaction-a",
      input: [["Allow"]],
    });
    expect(harness.runtimes.get("session-a")?.submittedInteractionKeys.has("interaction-a")).toBe(true);
    expect(harness.runtimes.get("session-a")?.streamActivity.phase).toBe("connected");
  });

  it("aborts and removes a deleted session before refreshing its list", async () => {
    vi.doMock("@/lib/api", () => ({ chatApi }));
    const harness = createHarness();
    const controller = new AbortController();
    harness.controllers.set("session-a", controller);
    chatApi.deleteSession.mockResolvedValue({ success: true });

    const actions = await createActions(harness);
    await actions.deleteSession("session-a");

    expect(controller.signal.aborted).toBe(true);
    expect(harness.runtimes.has("session-a")).toBe(false);
    expect(harness.history.clearResumeAttempt).toHaveBeenCalledWith("session-a");
    expect(harness.history.removeSession).toHaveBeenCalledWith("session-a");
    expect(harness.history.loadSessions).toHaveBeenCalledTimes(1);
    expect(harness.clearSelectedSession).toHaveBeenCalledTimes(1);
  });
});
