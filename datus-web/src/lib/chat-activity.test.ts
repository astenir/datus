import { describe, expect, it } from "vitest";
import {
  chatActivityPresentation,
  chatStreamActivityAfterEvent,
  connectedChatStreamActivity,
  startedChatStreamActivity,
} from "./chat-activity";

describe("chat stream activity", () => {
  it("keeps ping events as transport activity without creating visible content", () => {
    const started = startedChatStreamActivity(1_000);
    const connected = connectedChatStreamActivity(started, 1_100);
    const next = chatStreamActivityAfterEvent(
      connected,
      { event: "ping", data: {} },
      null,
      11_100,
    );

    expect(next).toMatchObject({
      phase: "connected",
      connectedAt: 1_100,
      lastEventAt: 11_100,
      lastContentAt: null,
    });
  });

  it("tracks the active tool and switches to awaiting user interaction", () => {
    const connected = connectedChatStreamActivity(startedChatStreamActivity(1_000), 1_100);
    const running = chatStreamActivityAfterEvent(
      connected,
      { event: "message" },
      {
        operation: "createMessage",
        message: {
          id: "tool-1",
          role: "assistant",
          content: "调用工具 search",
          blocks: [{ type: "tool-call", toolName: "search", params: {} }],
        },
      },
      2_000,
    );
    const awaiting = chatStreamActivityAfterEvent(
      running,
      { event: "message" },
      {
        operation: "createMessage",
        message: {
          id: "interaction-1",
          role: "assistant",
          content: "需要确认",
          blocks: [{
            type: "user-interaction",
            interactionKey: "interaction-1",
            actionType: "permission",
            requests: [],
          }],
        },
      },
      3_000,
    );

    expect(running).toMatchObject({ phase: "running_tool", activeOperation: "search" });
    expect(awaiting.phase).toBe("awaiting_user");
  });
});

describe("chat activity presentation", () => {
  it("avoids flashing for fast responses and escalates long waits", () => {
    const activity = connectedChatStreamActivity(startedChatStreamActivity(1_000), 1_100);

    expect(chatActivityPresentation(activity, 1_700).visible).toBe(false);
    expect(chatActivityPresentation(activity, 2_000)).toMatchObject({
      visible: true,
      label: "已连接，正在准备回答…",
    });
    expect(chatActivityPresentation(activity, 10_000)).toMatchObject({
      visible: true,
      label: "仍在处理中",
      detail: "9 秒",
    });
  });

  it("warns when no event has arrived within the stale threshold", () => {
    const activity = connectedChatStreamActivity(startedChatStreamActivity(1_000), 1_100);

    expect(chatActivityPresentation(activity, 16_100)).toEqual({
      visible: true,
      tone: "warning",
      label: "暂未收到新进展",
      detail: "最近更新于 15 秒前",
    });
  });

  it("only resurfaces responding status when the stream becomes stale", () => {
    const activity = {
      phase: "responding" as const,
      startedAt: 1_000,
      connectedAt: 1_100,
      lastEventAt: 2_000,
      lastContentAt: 2_000,
    };

    expect(chatActivityPresentation(activity, 10_000).visible).toBe(false);
    expect(chatActivityPresentation(activity, 17_000)).toMatchObject({
      visible: true,
      tone: "warning",
      label: "暂未收到新进展",
    });
  });

  it("shows the current tool and hides status while waiting for user input", () => {
    expect(chatActivityPresentation({
      phase: "running_tool",
      startedAt: 1_000,
      connectedAt: 1_100,
      lastEventAt: 9_000,
      lastContentAt: 2_000,
      activeOperation: "execute_sql",
    }, 10_000)).toMatchObject({
      visible: true,
      label: "正在执行 execute_sql",
      detail: "9 秒",
    });

    expect(chatActivityPresentation({
      phase: "awaiting_user",
      startedAt: 1_000,
      connectedAt: 1_100,
      lastEventAt: 9_000,
      lastContentAt: 9_000,
    }, 10_000).visible).toBe(false);
  });
});
