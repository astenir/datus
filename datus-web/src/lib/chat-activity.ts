import type {
  ChatStreamActivity,
  MessageBlock,
  ParsedMessage,
  SseEvent,
} from "@/types";

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
  };
}

export function startedChatStreamActivity(now = Date.now()): ChatStreamActivity {
  return {
    phase: "submitting",
    startedAt: now,
    connectedAt: null,
    lastEventAt: null,
    lastContentAt: null,
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
    return {
      ...next,
      phase: "running_tool",
      lastContentAt: now,
      activeOperation: block.toolName,
    };
  }
  if (block?.type === "tool-result") {
    return {
      ...next,
      phase: "connected",
      lastContentAt: now,
      activeOperation: undefined,
    };
  }

  return {
    ...next,
    phase: "responding",
    lastContentAt: now,
    activeOperation: undefined,
  };
}

export function continuingChatStreamActivity(
  activity: ChatStreamActivity,
  now = Date.now(),
): ChatStreamActivity {
  return {
    ...activity,
    phase: activity.activeOperation ? "running_tool" : "connected",
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

  const lastActivityAt = activity.lastEventAt ?? startedAt;
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
    return { visible: false, tone: "normal", label: "" };
  }
  if (activity.phase === "running_tool") {
    return {
      visible: true,
      tone: "normal",
      label: activity.activeOperation ? `正在执行 ${activity.activeOperation}` : "正在执行工具",
      detail: elapsedMs >= CHAT_ACTIVITY_LONG_WAIT_MS ? elapsed : undefined,
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
