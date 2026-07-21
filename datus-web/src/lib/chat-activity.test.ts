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
      activeTools: {},
    });
  });

  it("tracks parallel tools independently and keeps running until all complete", () => {
    const connected = connectedChatStreamActivity(startedChatStreamActivity(1_000), 1_100);
    const firstRunning = chatStreamActivityAfterEvent(
      connected,
      { event: "message" },
      {
        operation: "createMessage",
        message: {
          id: "tool-1",
          role: "assistant",
          content: "调用工具 search",
          blocks: [{ type: "tool-call", callToolId: "call-1", toolName: "search", params: {} }],
        },
      },
      2_000,
    );
    const parallelRunning = chatStreamActivityAfterEvent(
      firstRunning,
      { event: "message" },
      {
        operation: "createMessage",
        message: {
          id: "tool-2",
          role: "assistant",
          content: "调用工具 query",
          blocks: [{ type: "tool-call", callToolId: "call-2", toolName: "query", params: {} }],
        },
      },
      3_000,
    );
    const oneCompleted = chatStreamActivityAfterEvent(
      parallelRunning,
      { event: "message" },
      {
        operation: "createMessage",
        message: {
          id: "complete_call-1",
          role: "assistant",
          content: "工具完成 search",
          blocks: [{ type: "tool-result", callToolId: "call-1", toolName: "search", result: {} }],
        },
      },
      4_000,
    );

    expect(parallelRunning).toMatchObject({
      phase: "running_tool",
      toolCallCount: 2,
      toolCompletedCount: 0,
    });
    expect(Object.keys(parallelRunning.activeTools)).toEqual(["call-1", "call-2"]);
    expect(oneCompleted).toMatchObject({
      phase: "running_tool",
      toolCallCount: 2,
      toolCompletedCount: 1,
    });
    expect(Object.keys(oneCompleted.activeTools)).toEqual(["call-2"]);
  });

  it("switches to awaiting user without losing the pending tool set", () => {
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
          blocks: [{ type: "tool-call", callToolId: "call-1", toolName: "search", params: {} }],
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

    expect(awaiting.phase).toBe("awaiting_user");
    expect(Object.keys(awaiting.activeTools)).toEqual(["call-1"]);

    const completedWhileAwaiting = chatStreamActivityAfterEvent(
      awaiting,
      { event: "message" },
      {
        operation: "createMessage",
        message: {
          id: "complete_call-1",
          role: "assistant",
          content: "工具完成 search",
          blocks: [{ type: "tool-result", callToolId: "call-1", toolName: "search", result: {} }],
        },
      },
      4_000,
    );

    expect(completedWhileAwaiting.phase).toBe("awaiting_user");
    expect(completedWhileAwaiting.activeTools).toEqual({});
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

  it("warns when no business progress has arrived within the stale threshold", () => {
    const activity = connectedChatStreamActivity(startedChatStreamActivity(1_000), 1_100);

    const afterPing = chatStreamActivityAfterEvent(activity, { event: "ping", data: {} }, null, 15_000);

    expect(chatActivityPresentation(afterPing, 16_100)).toEqual({
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
      activeTools: {},
      toolCallCount: 0,
      toolCompletedCount: 0,
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
      activeTools: {
        "call-1": { callToolId: "call-1", toolName: "execute_sql", startedAt: 2_000 },
      },
      toolCallCount: 1,
      toolCompletedCount: 0,
    }, 10_000)).toMatchObject({
      visible: true,
      label: "正在执行 execute_sql",
      detail: "8 秒",
    });

    expect(chatActivityPresentation({
      phase: "awaiting_user",
      startedAt: 1_000,
      connectedAt: 1_100,
      lastEventAt: 9_000,
      lastContentAt: 9_000,
      activeTools: {},
      toolCallCount: 0,
      toolCompletedCount: 0,
    }, 10_000).visible).toBe(false);
  });

  it("shows parallel completion counts", () => {
    expect(chatActivityPresentation({
      phase: "running_tool",
      startedAt: 1_000,
      connectedAt: 1_100,
      lastEventAt: 9_000,
      lastContentAt: 9_000,
      activeTools: {
        "call-2": { callToolId: "call-2", toolName: "query", startedAt: 2_000 },
        "call-3": { callToolId: "call-3", toolName: "search", startedAt: 2_100 },
      },
      toolCallCount: 3,
      toolCompletedCount: 1,
    }, 10_000)).toMatchObject({
      label: "正在并行执行 2 个工具",
      detail: "已完成 1/3 · 8 秒",
    });
  });
});
