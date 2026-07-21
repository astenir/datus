import { computed, readonly, shallowRef } from "vue";
import { chatApi } from "@/lib/api";
import {
  activeUserInteractionKey,
  buildChatStreamRequest,
  buildUserInteractionInput,
  consumeSseStream,
  createClientId,
  mergeMessage,
  messageFromEvent,
  normalizeHistoryMessages,
  parseSseBuffer,
  requestJson,
  extractResultData,
  filterVisibleChatSessions,
  normalizeBaseUrl,
} from "@/lib/chat";
import { request } from "@/lib/request";
import {
  chatStreamActivityAfterEvent,
  connectedChatStreamActivity,
  continuingChatStreamActivity,
  idleChatStreamActivity,
  startedChatStreamActivity,
} from "@/lib/chat-activity";
import type { ChatMessage, ChatSessionOption, ParsedMessage, SseEvent } from "@/types";
import { useConnection } from "./useConnection";
import { useChatSettings } from "./useChatSettings";

const { effectiveBase } = useConnection();

const messages = shallowRef<ChatMessage[]>([]);
const sessions = shallowRef<ChatSessionOption[]>([]);
const selectedSession = shallowRef<string | null>(null);
const isStreaming = shallowRef(false);
const streamActivity = shallowRef(idleChatStreamActivity());
const isLoadingSessions = shallowRef(false);
const transportError = shallowRef<string | null>(null);
const submittedInteractionKeys = shallowRef<ReadonlySet<string>>(new Set());
const abortRef = { current: null as AbortController | null };
const messageCache = new Map<string, ChatMessage[]>();
const nonCanonicalSessions = new Set<string>();
const CACHE_MAX = 20;
let historyRequestId = 0;
const activeInteractionKey = computed(() =>
  activeUserInteractionKey(messages.value, {
    isStreaming: isStreaming.value,
    submittedInteractionKeys: submittedInteractionKeys.value,
  })
);

function cacheSet(key: string, value: ChatMessage[]) {
  if (messageCache.size >= CACHE_MAX && !messageCache.has(key)) {
    const oldest = messageCache.keys().next().value;
    if (oldest) messageCache.delete(oldest);
  }
  messageCache.set(key, value);
}

function applyIncomingMessages(incomingMessages: ParsedMessage[]) {
  if (incomingMessages.length === 0) return;

  let nextMessages = messages.value;
  for (const incoming of incomingMessages) {
    nextMessages = mergeMessage(nextMessages, incoming);
  }
  messages.value = nextMessages;
}

function applyStreamEvent(event: SseEvent): ParsedMessage | null {
  captureSessionId(event);
  const incoming = messageFromEvent(event);
  streamActivity.value = chatStreamActivityAfterEvent(streamActivity.value, event, incoming);
  return incoming;
}

/** Try to extract session_id from an SSE event, checking all known locations. */
function captureSessionId(event: { data?: unknown }): boolean {
  if (selectedSession.value) return true;
  const d = event.data as Record<string, unknown> | undefined;
  if (!d) return false;
  const p = (typeof d.payload === "object" && d.payload ? d.payload : undefined) as Record<string, unknown> | undefined;
  const sid = (d.session_id ?? d.sessionId ?? p?.session_id ?? p?.sessionId) as string | undefined;
  if (sid && typeof sid === "string" && sid.length > 0) {
    selectedSession.value = sid;
    return true;
  }
  return false;
}

async function loadSessions(subagentId?: string) {
  const base = effectiveBase();
  isLoadingSessions.value = true;
  try {
    const result = await chatApi.sessions(base, subagentId);
    if (result) {
      const loadedSessions = result.sessions ?? [];
      sessions.value = subagentId ? loadedSessions : filterVisibleChatSessions(loadedSessions);
    }
  } catch (error) {
    console.error("Failed to load sessions:", error);
  } finally {
    isLoadingSessions.value = false;
  }
}

async function loadSessionHistory(sessionId: string, requestId = ++historyRequestId) {
  const base = effectiveBase();
  try {
    const payload = await requestJson<unknown>(base, `/api/v1/chat/history?session_id=${encodeURIComponent(sessionId)}`);
    const data = extractResultData<{ messages?: unknown[] }>(payload);
    const historyMessages = normalizeHistoryMessages(data?.messages ?? []);
    if (requestId !== historyRequestId || selectedSession.value !== sessionId) return;
    cacheSet(sessionId, historyMessages);
    nonCanonicalSessions.delete(sessionId);
    messages.value = historyMessages;
    transportError.value = null;
  } catch (error) {
    if (requestId !== historyRequestId || selectedSession.value !== sessionId) return;
    console.error("Failed to load session history:", error);
    transportError.value = `加载会话历史失败：${error instanceof Error ? error.message : String(error)}`;
  }
}

function selectSession(sessionId: string | null) {
  const requestId = ++historyRequestId;
  const interruptedStream = abortRef.current !== null;
  const outgoingSession = selectedSession.value;
  // Abort the active stream before switching.
  if (abortRef.current) {
    abortRef.current.abort();
    abortRef.current = null;
  }
  isStreaming.value = false;
  streamActivity.value = idleChatStreamActivity();
  submittedInteractionKeys.value = new Set();
  transportError.value = null;

  // Cache current messages for the outgoing session
  if (interruptedStream && outgoingSession) {
    nonCanonicalSessions.add(outgoingSession);
    messageCache.delete(outgoingSession);
  }
  if (outgoingSession && messages.value.length > 0 && !nonCanonicalSessions.has(outgoingSession)) {
    cacheSet(outgoingSession, messages.value);
  }

  selectedSession.value = sessionId;
  if (sessionId) {
    // Restore from cache if available, otherwise load from backend
    const cached = nonCanonicalSessions.has(sessionId) ? undefined : messageCache.get(sessionId);
    if (cached) {
      messages.value = cached;
    } else {
      void loadSessionHistory(sessionId, requestId);
    }
  } else {
    messages.value = [];
  }
  if (interruptedStream) {
    void loadSessions();
  }
}

async function sendMessage(opts: {
  message: string;
  selectedAgent: string;
  model: string;
  datasource: string;
  database: string;
  schema: string;
}) {
  if (isStreaming.value) return;
  submittedInteractionKeys.value = new Set();
  transportError.value = null;
  const { language, planMode, permissionMode } = useChatSettings();
  const base = effectiveBase();

  const userMessage: ChatMessage = {
    id: createClientId(),
    role: "user",
    content: opts.message,
  };
  messages.value = [...messages.value, userMessage];

  const body = buildChatStreamRequest({
    message: opts.message,
    sessionId: selectedSession.value ?? "",
    selectedAgent: opts.selectedAgent,
    model: opts.model,
    datasource: opts.datasource,
    database: opts.database,
    schema: opts.schema,
    language: language.value,
    planMode: planMode.value,
    permissionMode: permissionMode.value,
  });

  const controller = new AbortController();
  abortRef.current = controller;
  isStreaming.value = true;
  streamActivity.value = startedChatStreamActivity();
  let streamCompleted = false;

  try {
    const url = `${normalizeBaseUrl(base)}/api/v1/chat/stream`;
    const response = await request(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (abortRef.current !== controller) return;
    streamActivity.value = connectedChatStreamActivity(streamActivity.value);

    const reader = response.body?.getReader();
    if (!reader) throw new Error("No response body");

    const decoder = new TextDecoder();
    let buffer = "";

    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      if (abortRef.current !== controller) return;

      buffer += decoder.decode(value, { stream: true });
      const parsed = parseSseBuffer(buffer);
      buffer = parsed.rest;

      const incomingMessages: ParsedMessage[] = [];
      for (const event of parsed.events) {
        const incoming = applyStreamEvent(event);
        if (!incoming) continue;
        incomingMessages.push(incoming);
      }
      applyIncomingMessages(incomingMessages);
    }

    if (buffer && abortRef.current === controller) {
      const parsed = parseSseBuffer(buffer, { flush: true });
      const incomingMessages: ParsedMessage[] = [];
      for (const event of parsed.events) {
        const incoming = applyStreamEvent(event);
        if (incoming) incomingMessages.push(incoming);
      }
      applyIncomingMessages(incomingMessages);
    }
    streamCompleted = true;
  } catch (error) {
    if ((error as Error).name !== "AbortError" && abortRef.current === controller) {
      transportError.value = error instanceof Error ? error.message : String(error);
      if (selectedSession.value) {
        nonCanonicalSessions.add(selectedSession.value);
        messageCache.delete(selectedSession.value);
      }
    }
  } finally {
    if (abortRef.current === controller) {
      isStreaming.value = false;
      streamActivity.value = idleChatStreamActivity();
      abortRef.current = null;
      if (selectedSession.value && streamCompleted) {
        const sessionId = selectedSession.value;
        messageCache.delete(sessionId);
        await loadSessionHistory(sessionId);
      }
      void loadSessions();
    }
  }
}

async function stopSession() {
  const base = effectiveBase();
  if (isStreaming.value) {
    streamActivity.value = { ...streamActivity.value, phase: "stopping" };
  }
  if (abortRef.current) {
    abortRef.current.abort();
    abortRef.current = null;
  }
  if (selectedSession.value) {
    const sessionId = selectedSession.value;
    nonCanonicalSessions.add(sessionId);
    messageCache.delete(sessionId);
    try {
      await chatApi.stop(base, sessionId);
      messageCache.delete(sessionId);
      await loadSessionHistory(sessionId);
    } catch (error) {
      console.error("Failed to stop session:", error);
      transportError.value = error instanceof Error ? error.message : String(error);
    }
  }
  isStreaming.value = false;
  streamActivity.value = idleChatStreamActivity();
  submittedInteractionKeys.value = new Set();
  void loadSessions();
}

async function deleteSession(sessionId: string) {
  const base = effectiveBase();
  try {
    await chatApi.deleteSession(base, sessionId);
    messageCache.delete(sessionId);
    nonCanonicalSessions.delete(sessionId);
    if (selectedSession.value === sessionId) {
      selectSession(null);
    }
    await loadSessions();
  } catch (error) {
    console.error("Failed to delete session:", error);
    throw error;
  }
}

async function compactSession(sessionId: string) {
  const base = effectiveBase();
  try {
    const result = await chatApi.compact(base, sessionId);
    if (result?.success) {
      // Clear cached messages so the compacted summary is shown
      messageCache.delete(sessionId);
      if (selectedSession.value === sessionId) {
        await loadSessionHistory(sessionId);
      }
    }
    return result;
  } catch (error) {
    console.error("Failed to compact session:", error);
    throw error;
  }
}

async function resumeSession(sessionId?: string) {
  // Skip if already streaming (another operation is in progress)
  if (isStreaming.value) return;

  const targetSession = sessionId ?? selectedSession.value;
  if (!targetSession) return;
  transportError.value = null;
  const base = effectiveBase();
  const controller = new AbortController();
  abortRef.current = controller;
  isStreaming.value = true;
  streamActivity.value = startedChatStreamActivity();
  let streamCompleted = false;
  try {
    const url = `${normalizeBaseUrl(base)}/api/v1/chat/resume`;
    const response = await request(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({ session_id: targetSession }),
      signal: controller.signal,
    });
    if (abortRef.current !== controller) return;
    streamActivity.value = connectedChatStreamActivity(streamActivity.value);
    const pendingMessages: ParsedMessage[] = [];
    const flushPendingMessages = () => {
      applyIncomingMessages(pendingMessages.splice(0));
    };
    const tail = await consumeSseStream(response, (event) => {
      if (abortRef.current !== controller) return;
      const incoming = applyStreamEvent(event);
      if (incoming) pendingMessages.push(incoming);
      flushPendingMessages();
    });
    if (tail && abortRef.current === controller) {
      const parsed = parseSseBuffer(tail, { flush: true });
      const incomingMessages: ParsedMessage[] = [];
      for (const event of parsed.events) {
        const incoming = applyStreamEvent(event);
        if (incoming) incomingMessages.push(incoming);
      }
      applyIncomingMessages(incomingMessages);
    }
    streamCompleted = true;
  } catch (error) {
    if ((error as Error).name !== "AbortError" && abortRef.current === controller) {
      console.error("Failed to resume session:", error);
      transportError.value = error instanceof Error ? error.message : String(error);
      nonCanonicalSessions.add(targetSession);
      messageCache.delete(targetSession);
    }
  } finally {
    if (abortRef.current === controller) {
      isStreaming.value = false;
      streamActivity.value = idleChatStreamActivity();
      abortRef.current = null;
      if (selectedSession.value && streamCompleted) {
        const sessionId = selectedSession.value;
        messageCache.delete(sessionId);
        await loadSessionHistory(sessionId);
      }
      void loadSessions();
    }
  }
}

async function insertMessage(message: string) {
  const sessionId = selectedSession.value;
  if (!sessionId || !message.trim()) return;

  // Optimistic insert: show the user message immediately
  const userMessage: ChatMessage = {
    id: createClientId(),
    role: "user",
    content: message,
  };
  messages.value = [...messages.value, userMessage];

  try {
    const base = effectiveBase();
    await chatApi.insert(base, sessionId, message);
  } catch (error) {
    console.error("Failed to insert message:", error);
    messages.value = messages.value.filter((item) => item.id !== userMessage.id);
    transportError.value = `注入失败：${error instanceof Error ? error.message : String(error)}`;
  }
}

function clearTransportError() {
  transportError.value = null;
}

async function sendInteraction(interactionKey: string, answers: string | string[][]) {
  const base = effectiveBase();
  const sessionId = selectedSession.value;
  if (!sessionId) throw new Error("会话未就绪");
  if (!interactionKey) throw new Error("交互请求未就绪");
  if (activeInteractionKey.value !== interactionKey) throw new Error("交互请求已失效");

  // Do NOT stopSession — the task is alive and waiting for interaction.
  // The SSE stream from sendMessage is still open; broker.submit() will
  // unblock the task and new events flow through the same stream.

  submittedInteractionKeys.value = new Set([...submittedInteractionKeys.value, interactionKey]);
  try {
    const result = await chatApi.userInteraction(base, buildUserInteractionInput(sessionId, interactionKey, answers));
    if (!result) throw new Error("后端未接受本次交互提交");
    streamActivity.value = continuingChatStreamActivity(streamActivity.value);
  } catch (error) {
    const next = new Set(submittedInteractionKeys.value);
    next.delete(interactionKey);
    submittedInteractionKeys.value = next;
    throw error;
  }
  // No resumeSession needed — sendMessage's SSE reader is still running.
}

function clearMessages() {
  historyRequestId += 1;
  messages.value = [];
  selectedSession.value = null;
  submittedInteractionKeys.value = new Set();
  streamActivity.value = idleChatStreamActivity();
  transportError.value = null;
  messageCache.clear();
  nonCanonicalSessions.clear();
}

function dispose() {
  historyRequestId += 1;
  if (abortRef.current) {
    abortRef.current.abort();
    abortRef.current = null;
  }
  isStreaming.value = false;
  streamActivity.value = idleChatStreamActivity();
  submittedInteractionKeys.value = new Set();
  transportError.value = null;
}

export function useChatState() {
  return {
    messages: readonly(messages),
    sessions: readonly(sessions),
    selectedSession: readonly(selectedSession),
    isStreaming: readonly(isStreaming),
    streamActivity: readonly(streamActivity),
    isLoadingSessions: readonly(isLoadingSessions),
    transportError: readonly(transportError),
    activeInteractionKey: readonly(activeInteractionKey),
    loadSessions,
    selectSession,
    sendMessage,
    insertMessage,
    stopSession,
    deleteSession,
    compactSession,
    resumeSession,
    sendInteraction,
    clearMessages,
    clearTransportError,
    dispose,
  };
}
