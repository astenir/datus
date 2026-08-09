import { afterEach, describe, expect, it } from "vitest";

import { useChatRuntimeStore } from "./useChatRuntimeStore";

const runtimeStore = useChatRuntimeStore();

describe("useChatRuntimeStore", () => {
  afterEach(() => {
    runtimeStore.dispose();
  });

  it("keeps selected session state isolated by runtime key", () => {
    runtimeStore.selectSession("session-a");
    runtimeStore.updateRuntime("session-a", runtime => ({
      ...runtime,
      messages: [{ id: "message-a", role: "assistant", content: "A" }],
      isStreaming: true,
    }));

    runtimeStore.selectSession("session-b");
    runtimeStore.updateRuntime("session-b", runtime => ({
      ...runtime,
      messages: [{ id: "message-b", role: "assistant", content: "B" }],
    }));

    expect(runtimeStore.selectedSession.value).toBe("session-b");
    expect(runtimeStore.messages.value.map(message => message.content)).toEqual(["B"]);
    expect(runtimeStore.isStreaming.value).toBe(false);

    runtimeStore.selectSession("session-a");
    expect(runtimeStore.messages.value.map(message => message.content)).toEqual(["A"]);
    expect(runtimeStore.isStreaming.value).toBe(true);
  });

  it("rekeys a draft runtime while preserving its controller and history token", () => {
    const draftKey = runtimeStore.createDraftRuntime();
    const controller = new AbortController();
    const requestId = runtimeStore.invalidateHistory(draftKey);
    runtimeStore.setController(draftKey, controller);
    runtimeStore.updateRuntime(draftKey, runtime => ({
      ...runtime,
      messages: [{ id: "draft-message", role: "user", content: "Draft" }],
    }));

    runtimeStore.rekeyRuntime(draftKey, "session-a", { controller });

    expect(runtimeStore.getRuntime(draftKey)).toBeUndefined();
    expect(runtimeStore.getRuntime("session-a")?.messages[0]?.content).toBe("Draft");
    expect(runtimeStore.getController("session-a")).toBe(controller);
    expect(runtimeStore.isHistoryRequestCurrent("session-a", requestId)).toBe(true);
    expect(runtimeStore.selectedSession.value).toBe("session-a");
    expect(runtimeStore.selectedRuntimeKey.value).toBe("session-a");
  });

  it("rejects stale history responses after a newer request starts", () => {
    const firstRequestId = runtimeStore.invalidateHistory("session-a");
    const secondRequestId = runtimeStore.invalidateHistory("session-a");

    expect(runtimeStore.isHistoryRequestCurrent("session-a", firstRequestId)).toBe(false);
    expect(runtimeStore.isHistoryRequestCurrent("session-a", secondRequestId)).toBe(true);
  });

  it("prunes idle runtimes while retaining the selected runtime", () => {
    runtimeStore.selectSession("selected");
    for (let index = 0; index < 20; index += 1) {
      runtimeStore.ensureRuntime(`session-${index}`);
    }

    runtimeStore.ensureRuntime("session-20");

    expect(runtimeStore.getRuntime("selected")).toBeDefined();
    expect(runtimeStore.getRuntime("session-0")).toBeUndefined();
    expect(runtimeStore.getRuntime("session-20")).toBeDefined();
  });
});
