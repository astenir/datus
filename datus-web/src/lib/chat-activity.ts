import type {
  ChatStreamActivity,
  MessageBlock,
  ParsedMessage,
  SseEvent,
} from "@/types";
import { toolDisplayName } from "@/lib/tool-presentation";

export const CHAT_ACTIVITY_REVEAL_DELAY_MS = 800;
export const CHAT_ACTIVITY_LONG_WAIT_MS = 8_000;
export const CHAT_ACTIVITY_EXTENDED_WAIT_MS = 30_000;
export const CHAT_ACTIVITY_STALE_MS = 15_000;

export function idleChatStreamActivity(): ChatStreamActivity {
  return {
    phase: "idle",
    startedAt: null,
    connectedAt: null,
    lastEventAt: null,
    lastContentAt: null,
    activeTools: {},
    toolCallCount: 0,
    toolCompletedCount: 0,
  };
}

export function startedChatStreamActivity(now = Date.now()): ChatStreamActivity {
  return {
    phase: "submitting",
    startedAt: now,
    connectedAt: null,
    lastEventAt: null,
    lastContentAt: null,
    activeTools: {},
    toolCallCount: 0,
    toolCompletedCount: 0,
  };
}

export function connectedChatStreamActivity(
  activity: ChatStreamActivity,
  now = Date.now(),
): ChatStreamActivity {
  return {
    ...activity,
    phase: "connected",
    connectedAt: activity.connectedAt ?? now,
    lastEventAt: now,
  };
}

function latestActivityBlock(blocks: readonly MessageBlock[] = []) {
  return [...blocks].reverse().find((block) =>
    block.type === "user-interaction" ||
    block.type === "tool-call" ||
    block.type === "tool-result" ||
    block.type === "markdown" ||
    block.type === "thinking" ||
    block.type === "code" ||
    block.type === "artifact" ||
    block.type === "subagent-complete",
  );
}

function toolCallKey(incoming: ParsedMessage, callToolId?: string) {
  if (callToolId) return callToolId;
  return incoming.message.id.replace(/^complete_/, "");
}

export function chatStreamActivityAfterEvent(
  activity: ChatStreamActivity,
  event: SseEvent,
  incoming: ParsedMessage | null,
  now = Date.now(),
): ChatStreamActivity {
  const next: ChatStreamActivity = {
    ...activity,
    connectedAt: activity.connectedAt ?? now,
    lastEventAt: now,
  };

  if (event.event === "ping") return next;
  if (!incoming) {
    return event.event === "session" ? { ...next, phase: "connected" } : next;
  }

  const block = latestActivityBlock(incoming.message.blocks);
  if (block?.type === "user-interaction") {
    return { ...next, phase: "awaiting_user", lastContentAt: now };
  }
  if (block?.type === "tool-call") {
    const callToolId = toolCallKey(incoming, block.callToolId);
    const existing = next.activeTools[callToolId];
    return {
      ...next,
      phase: next.phase === "awaiting_user" ? "awaiting_user" : "running_tool",
      lastContentAt: now,
      activeTools: {
        ...next.activeTools,
        [callToolId]: existing ?? { callToolId, toolName: block.toolName, startedAt: now },
      },
      toolCallCount: next.toolCallCount + (existing ? 0 : 1),
    };
  }
  if (block?.type === "tool-result") {
    const callToolId = toolCallKey(incoming, block.callToolId);
    const wasActive = Boolean(next.activeTools[callToolId]);
    const activeTools = { ...next.activeTools };
    delete activeTools[callToolId];
    return {
      ...next,
      phase: next.phase === "awaiting_user"
        ? "awaiting_user"
        : Object.keys(activeTools).length > 0 ? "running_tool" : "preparing_response",
      lastContentAt: now,
      activeTools,
      toolCompletedCount: next.toolCompletedCount + (wasActive ? 1 : 0),
    };
  }

  return {
    ...next,
    phase: next.phase === "awaiting_user"
      ? "awaiting_user"
      : Object.keys(next.activeTools).length > 0 ? "running_tool" : "responding",
    lastContentAt: now,
  };
}

export function continuingChatStreamActivity(
  activity: ChatStreamActivity,
  now = Date.now(),
): ChatStreamActivity {
  return {
    ...activity,
    phase: Object.keys(activity.activeTools).length > 0 ? "running_tool" : "connected",
    lastEventAt: now,
  };
}

export type ChatActivityPresentation = {
  visible: boolean;
  tone: "normal" | "warning";
  label: string;
  detail?: string;
};

function formatElapsed(seconds: number) {
  if (seconds < 60) return `${seconds} 秒`;
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return remainder ? `${minutes} 分 ${remainder} 秒` : `${minutes} 分钟`;
}

export function chatActivityPresentation(
  activity: ChatStreamActivity,
  now = Date.now(),
): ChatActivityPresentation {
  if (activity.phase === "idle" || activity.phase === "awaiting_user") {
    return { visible: false, tone: "normal", label: "" };
  }

  const startedAt = activity.startedAt ?? now;
  const elapsedMs = Math.max(0, now - startedAt);
  if (elapsedMs < CHAT_ACTIVITY_REVEAL_DELAY_MS) {
    return { visible: false, tone: "normal", label: "" };
  }

  const lastActivityAt = activity.lastContentAt ?? activity.connectedAt ?? startedAt;
  const idleMs = Math.max(0, now - lastActivityAt);
  const elapsed = formatElapsed(Math.floor(elapsedMs / 1000));

  if (activity.phase === "stopping") {
    return { visible: true, tone: "normal", label: "正在停止…" };
  }
  if (idleMs >= CHAT_ACTIVITY_STALE_MS) {
    return {
      visible: true,
      tone: "warning",
      label: "暂未收到新进展",
      detail: `最近更新于 ${formatElapsed(Math.floor(idleMs / 1000))}前`,
    };
  }
  if (activity.phase === "responding") {
    return {
      visible: true,
      tone: "normal",
      label: "正在生成回答…",
      detail: idleMs >= CHAT_ACTIVITY_LONG_WAIT_MS
        ? `已等待 ${formatElapsed(Math.floor(idleMs / 1000))}`
        : undefined,
    };
  }
  if (activity.phase === "preparing_response") {
    return {
      visible: true,
      tone: "normal",
      label: "正在整理工具结果…",
      detail: idleMs >= CHAT_ACTIVITY_LONG_WAIT_MS
        ? `已等待 ${formatElapsed(Math.floor(idleMs / 1000))}`
        : undefined,
    };
  }
  if (activity.phase === "running_tool") {
    const activeTools = Object.values(activity.activeTools);
    const activeCount = activeTools.length;
    const progress = activity.toolCallCount > 1
      ? `已完成 ${activity.toolCompletedCount}/${activity.toolCallCount}`
      : undefined;
    const activeStartedAt = Math.min(...activeTools.map((tool) => tool.startedAt));
    const toolElapsedMs = Math.max(0, now - activeStartedAt);
    const elapsedDetail = toolElapsedMs >= CHAT_ACTIVITY_LONG_WAIT_MS
      ? formatElapsed(Math.floor(toolElapsedMs / 1000))
      : undefined;
    return {
      visible: true,
      tone: "normal",
      label: activeCount === 1
        ? `正在执行：${toolDisplayName(activeTools[0]?.toolName ?? "工具")}`
        : `正在并行执行 ${activeCount} 个工具`,
      detail: [progress, elapsedDetail].filter(Boolean).join(" · ") || undefined,
    };
  }
  if (elapsedMs >= CHAT_ACTIVITY_EXTENDED_WAIT_MS) {
    return { visible: true, tone: "normal", label: "处理时间较长", detail: elapsed };
  }
  if (elapsedMs >= CHAT_ACTIVITY_LONG_WAIT_MS) {
    return { visible: true, tone: "normal", label: "仍在处理中", detail: elapsed };
  }
  return {
    visible: true,
    tone: "normal",
    label: activity.phase === "submitting" ? "正在发送…" : "已连接，正在准备回答…",
  };
}
