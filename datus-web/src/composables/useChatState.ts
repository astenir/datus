import { computed, readonly, shallowRef } from "vue";
import { chatApi } from "@/lib/api";
import {
  activeUserInteractionKey,
  buildChatStreamRequest,
  buildUserInteractionInput,
  createClientId,
  extractResultData,
  filterVisibleChatSessions,
  friendlyTransportErrorBlock,
  mergeMessage,
  messageFromEvent,
  normalizeBaseUrl,
  normalizeHistoryMessages,
  parseSseBuffer,
  requestJson,
} from "@/lib/chat";
import { request } from "@/lib/request";
import {
  chatStreamActivityAfterEvent,
  connectedChatStreamActivity,
  continuingChatStreamActivity,
  idleChatStreamActivity,
  startedChatStreamActivity,
} from "@/lib/chat-activity";
import type {
  ChatErrorBlock,
  ChatMessage,
  ChatSessionOption,
  ChatStreamActivity,
  InsertMessageData,
  ParsedMessage,
  SseEvent,
} from "@/types";
import { useConnection } from "./useConnection";
import { useChatSettings } from "./useChatSettings";

type ChatSessionRuntime = {
  messages: ChatMessage[];
  isStreaming: boolean;
  isInsertReady: boolean;
  isStopping: boolean;
  streamActivity: ChatStreamActivity;
  transportError: ChatErrorBlock | null;
  submittedInteractionKeys: ReadonlySet<string>;
  nextEventCursor: number;
  needsHistoryRefresh: boolean;
};

type StreamContext = {
  runtimeKey: string;
  sessionId: string | null;
  controller: AbortController;
};

const { effectiveBase } = useConnection();
const sessions = shallowRef<ChatSessionOption[]>([]);
const selectedSession = shallowRef<string | null>(null);
const selectedRuntimeKey = shallowRef<string | null>(null);
const runtimes = shallowRef<ReadonlyMap<string, ChatSessionRuntime>>(new Map());
const isLoadingSessions = shallowRef(false);
const streamControllers = new Map<string, AbortController>();
const historyRequestIds = new Map<string, number>();
const resumeAttemptedSessions = new Set<string>();
const resumeInFlightSessions = new Set<string>();
const RUNTIME_CACHE_MAX = 20;
let historyRequestSequence = 0;

function newRuntime(messages: ChatMessage[] = []): ChatSessionRuntime {
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

const EMPTY_RUNTIME = newRuntime();

function pruneRuntimeCache(next: Map<string, ChatSessionRuntime>) {
  if (next.size <= RUNTIME_CACHE_MAX) return;
  for (const [key, runtime] of next) {
    if (next.size <= RUNTIME_CACHE_MAX) break;
    if (key === selectedRuntimeKey.value || runtime.isStreaming || streamControllers.has(key)) continue;
    next.delete(key);
    historyRequestIds.delete(key);
  }
}

function setRuntime(key: string, runtime: ChatSessionRuntime) {
  const next = new Map(runtimes.value);
  next.delete(key);
  next.set(key, runtime);
  pruneRuntimeCache(next);
  runtimes.value = next;
}

function updateRuntime(key: string, update: (runtime: ChatSessionRuntime) => ChatSessionRuntime) {
  setRuntime(key, update(runtimes.value.get(key) ?? newRuntime()));
}

function removeRuntime(key: string) {
  const next = new Map(runtimes.value);
  next.delete(key);
  runtimes.value = next;
  historyRequestIds.delete(key);
  resumeAttemptedSessions.delete(key);
}

function createDraftRuntime() {
  const key = `draft:${createClientId()}`;
  setRuntime(key, newRuntime());
  selectedRuntimeKey.value = key;
  selectedSession.value = null;
  return key;
}

function ensureSelectedRuntime() {
  return selectedRuntimeKey.value ?? createDraftRuntime();
}

const selectedRuntime = computed(() => {
  const key = selectedRuntimeKey.value;
  return key ? runtimes.value.get(key) ?? EMPTY_RUNTIME : EMPTY_RUNTIME;
});
const messages = computed(() => selectedRuntime.value.messages);
const isStreaming = computed(() => selectedRuntime.value.isStreaming);
const isInsertReady = computed(() => selectedRuntime.value.isInsertReady);
const isStopping = computed(() => selectedRuntime.value.isStopping);
const streamActivity = computed(() => selectedRuntime.value.streamActivity);
const transportError = computed(() => selectedRuntime.value.transportError);
const activeInteractionKey = computed(() =>
  activeUserInteractionKey(messages.value, {
    isStreaming: isStreaming.value,
    submittedInteractionKeys: selectedRuntime.value.submittedInteractionKeys,
  })
);

function invalidateHistory(runtimeKey: string) {
  historyRequestIds.set(runtimeKey, ++historyRequestSequence);
}

function sessionFirstUserMessage(runtime: ChatSessionRuntime) {
  return runtime.messages.find(message => message.role === "user" && message.content.trim())?.content;
}

function markSessionActive(sessionId: string, active: boolean, runtimeKey = sessionId) {
  const existing = sessions.value.find(session => session.session_id === sessionId);
  if (existing) {
    sessions.value = sessions.value.map(session =>
      session.session_id === sessionId ? { ...session, is_active: active } : session
    );
    return;
  }
  if (!active) return;

  const now = new Date().toISOString();
  const runtime = runtimes.value.get(runtimeKey) ?? EMPTY_RUNTIME;
  sessions.value = [{
    session_id: sessionId,
    user_query: sessionFirstUserMessage(runtime),
    created_at: now,
    last_updated: now,
    total_turns: 0,
    is_active: true,
  }, ...sessions.value];
}

function rekeyRuntime(context: StreamContext, sessionId: string) {
  const oldKey = context.runtimeKey;
  if (oldKey === sessionId) {
    context.sessionId = sessionId;
    return;
  }

  const oldRuntime = runtimes.value.get(oldKey) ?? newRuntime();
  const existingRuntime = runtimes.value.get(sessionId);
  const messagesById = new Map<string, ChatMessage>();
  for (const message of existingRuntime?.messages ?? []) messagesById.set(message.id, message);
  for (const message of oldRuntime.messages) messagesById.set(message.id, message);
  const nextRuntime: ChatSessionRuntime = {
    ...(existingRuntime ?? newRuntime()),
    ...oldRuntime,
    messages: [...messagesById.values()],
  };
  const next = new Map(runtimes.value);
  next.delete(oldKey);
  next.set(sessionId, nextRuntime);
  runtimes.value = next;

  const controller = streamControllers.get(oldKey);
  if (controller === context.controller) {
    streamControllers.delete(oldKey);
    streamControllers.set(sessionId, controller);
  }
  const historyRequestId = historyRequestIds.get(oldKey);
  historyRequestIds.delete(oldKey);
  if (historyRequestId != null) historyRequestIds.set(sessionId, historyRequestId);
  resumeAttemptedSessions.delete(oldKey);

  if (selectedRuntimeKey.value === oldKey) {
    selectedRuntimeKey.value = sessionId;
    selectedSession.value = sessionId;
  }
  context.runtimeKey = sessionId;
  context.sessionId = sessionId;
  markSessionActive(sessionId, true);
}

function captureSessionId(context: StreamContext, event: { data?: unknown }) {
  if (context.sessionId) return;
  const data = event.data as Record<string, unknown> | undefined;
  if (!data) return;
  const payload = (
    typeof data.payload === "object" && data.payload ? data.payload : undefined
  ) as Record<string, unknown> | undefined;
  const candidate = data.session_id ?? data.sessionId ?? payload?.session_id ?? payload?.sessionId;
  if (typeof candidate === "string" && candidate.trim()) {
    rekeyRuntime(context, candidate);
  }
}

function applyIncomingMessages(runtimeKey: string, incomingMessages: ParsedMessage[]) {
  if (incomingMessages.length === 0) return;
  updateRuntime(runtimeKey, (runtime) => {
    let nextMessages = runtime.messages;
    for (const incoming of incomingMessages) {
      nextMessages = mergeMessage(nextMessages, incoming);
    }
    return { ...runtime, messages: nextMessages };
  });
}

function applyStreamEvent(context: StreamContext, event: SseEvent): ParsedMessage | null {
  captureSessionId(context, event);
  const incoming = messageFromEvent(event);
  const eventId = Number.parseInt(event.id ?? "", 10);
  updateRuntime(context.runtimeKey, runtime => ({
    ...runtime,
    isInsertReady: event.event === "session" || runtime.isInsertReady,
    streamActivity: chatStreamActivityAfterEvent(runtime.streamActivity, event, incoming),
    nextEventCursor: Number.isInteger(eventId) && eventId >= 0
      ? Math.max(runtime.nextEventCursor, eventId + 1)
      : runtime.nextEventCursor,
  }));
  return incoming;
}

async function consumeChatResponse(context: StreamContext, response: Response) {
  if (streamControllers.get(context.runtimeKey) !== context.controller) return;
  updateRuntime(context.runtimeKey, runtime => ({
    ...runtime,
    streamActivity: connectedChatStreamActivity(runtime.streamActivity),
  }));

  const reader = response.body?.getReader();
  if (!reader) throw new Error("No response body");
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    if (streamControllers.get(context.runtimeKey) !== context.controller) return;
    buffer += decoder.decode(value, { stream: true });
    const parsed = parseSseBuffer(buffer);
    buffer = parsed.rest;
    const incomingMessages: ParsedMessage[] = [];
    for (const event of parsed.events) {
      const incoming = applyStreamEvent(context, event);
      if (incoming) incomingMessages.push(incoming);
    }
    applyIncomingMessages(context.runtimeKey, incomingMessages);
  }

  buffer += decoder.decode();
  if (!buffer || streamControllers.get(context.runtimeKey) !== context.controller) return;
  const parsed = parseSseBuffer(buffer, { flush: true });
  const incomingMessages: ParsedMessage[] = [];
  for (const event of parsed.events) {
    const incoming = applyStreamEvent(context, event);
    if (incoming) incomingMessages.push(incoming);
  }
  applyIncomingMessages(context.runtimeKey, incomingMessages);
}

async function loadSessionHistory(sessionId: string) {
  const requestId = ++historyRequestSequence;
  historyRequestIds.set(sessionId, requestId);
  if (!runtimes.value.has(sessionId)) setRuntime(sessionId, newRuntime());
  const base = effectiveBase();
  try {
    const payload = await requestJson<unknown>(
      base,
      `/api/v1/chat/history?session_id=${encodeURIComponent(sessionId)}`,
    );
    if (historyRequestIds.get(sessionId) !== requestId) return;
    const data = extractResultData<{ messages?: unknown[] }>(payload);
    const historyMessages = normalizeHistoryMessages(data?.messages ?? []);
    updateRuntime(sessionId, runtime => ({
      ...runtime,
      messages: historyMessages,
      transportError: null,
      needsHistoryRefresh: false,
    }));
  } catch (error) {
    if (historyRequestIds.get(sessionId) !== requestId) return;
    console.error("Failed to load session history:", error);
    updateRuntime(sessionId, runtime => ({
      ...runtime,
      transportError: friendlyTransportErrorBlock(error, "history"),
    }));
  }
}

async function loadSessions(subagentId?: string) {
  const base = effectiveBase();
  isLoadingSessions.value = true;
  try {
    const result = await chatApi.sessions(base, subagentId);
    if (!result) return;
    const loadedSessions = result.sessions ?? [];
    const visibleSessions = subagentId ? loadedSessions : filterVisibleChatSessions(loadedSessions);
    sessions.value = visibleSessions.map(session => ({
      ...session,
      is_active: Boolean(session.is_active || streamControllers.has(session.session_id)),
    }));

    for (const session of sessions.value) {
      if (!session.is_active) {
        resumeAttemptedSessions.delete(session.session_id);
        continue;
      }
      if (runtimes.value.get(session.session_id)?.isStopping) continue;
      if (!streamControllers.has(session.session_id) && !resumeAttemptedSessions.has(session.session_id)) {
        void resumeSession(session.session_id);
      }
    }
  } catch (error) {
    console.error("Failed to load sessions:", error);
  } finally {
    isLoadingSessions.value = false;
  }
}

function selectSession(sessionId: string | null) {
  if (!sessionId) {
    createDraftRuntime();
    return;
  }

  selectedSession.value = sessionId;
  selectedRuntimeKey.value = sessionId;
  const runtime = runtimes.value.get(sessionId);
  if (!runtime) {
    setRuntime(sessionId, newRuntime());
    void loadSessionHistory(sessionId);
  } else if (!runtime.isStreaming && runtime.needsHistoryRefresh) {
    void loadSessionHistory(sessionId);
  }
  const listedSession = sessions.value.find(session => session.session_id === sessionId);
  if (listedSession?.is_active && !streamControllers.has(sessionId) && !runtimes.value.get(sessionId)?.isStopping) {
    void resumeSession(sessionId);
  }
}

async function finalizeStream(context: StreamContext, streamCompleted: boolean) {
  if (streamControllers.get(context.runtimeKey) !== context.controller) return;
  streamControllers.delete(context.runtimeKey);
  updateRuntime(context.runtimeKey, runtime => ({
    ...runtime,
    isStreaming: false,
    isInsertReady: streamCompleted ? false : runtime.isInsertReady,
    isStopping: false,
    streamActivity: idleChatStreamActivity(),
    submittedInteractionKeys: new Set(),
    nextEventCursor: streamCompleted ? 0 : runtime.nextEventCursor,
  }));

  if (context.sessionId && streamCompleted) {
    markSessionActive(context.sessionId, false);
    await loadSessionHistory(context.sessionId);
  }
  void loadSessions();
}

async function sendMessage(opts: {
  message: string;
  selectedAgent: string;
  model: string;
  datasource: string;
  database: string;
  schema: string;
  personalMcpIds?: readonly string[];
}) {
  const runtimeKey = ensureSelectedRuntime();
  if (streamControllers.has(runtimeKey) || runtimes.value.get(runtimeKey)?.isStreaming) return;

  const sessionId = selectedSession.value;
  invalidateHistory(runtimeKey);
  if (sessionId) resumeAttemptedSessions.delete(sessionId);
  const userMessage: ChatMessage = {
    id: createClientId(),
    role: "user",
    content: opts.message,
  };
  updateRuntime(runtimeKey, runtime => ({
    ...runtime,
    messages: [...runtime.messages, userMessage],
    isStreaming: true,
    isInsertReady: false,
    isStopping: false,
    streamActivity: startedChatStreamActivity(),
    transportError: null,
    submittedInteractionKeys: new Set(),
    nextEventCursor: 0,
  }));

  const { language, planMode, permissionMode } = useChatSettings();
  const body = buildChatStreamRequest({
    message: opts.message,
    sessionId: sessionId ?? "",
    selectedAgent: opts.selectedAgent,
    model: opts.model,
    datasource: opts.datasource,
    database: opts.database,
    schema: opts.schema,
    language: language.value,
    planMode: planMode.value,
    permissionMode: permissionMode.value,
    personalMcpIds: opts.personalMcpIds,
  });
  const controller = new AbortController();
  const context: StreamContext = { runtimeKey, sessionId, controller };
  streamControllers.set(runtimeKey, controller);
  let streamCompleted = false;

  try {
    const response = await request(`${normalizeBaseUrl(effectiveBase())}/api/v1/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    await consumeChatResponse(context, response);
    if (streamControllers.get(context.runtimeKey) === controller) streamCompleted = true;
  } catch (error) {
    if ((error as Error).name !== "AbortError" && streamControllers.get(context.runtimeKey) === controller) {
      updateRuntime(context.runtimeKey, runtime => ({
        ...runtime,
        transportError: friendlyTransportErrorBlock(error, "stream"),
        needsHistoryRefresh: true,
      }));
    }
  } finally {
    await finalizeStream(context, streamCompleted);
  }
}

async function stopSession() {
  const runtimeKey = selectedRuntimeKey.value;
  if (!runtimeKey) return;
  const sessionId = selectedSession.value;
  const currentRuntime = runtimes.value.get(runtimeKey);
  if (!currentRuntime?.isStreaming || currentRuntime.isStopping) return;
  const wasInsertReady = currentRuntime.isInsertReady;
  let stopSucceeded = false;

  updateRuntime(runtimeKey, runtime => ({
    ...runtime,
    isStreaming: true,
    isInsertReady: false,
    isStopping: true,
    streamActivity: { ...runtime.streamActivity, phase: "stopping" },
  }));

  const controller = streamControllers.get(runtimeKey);
  if (controller) {
    streamControllers.delete(runtimeKey);
    controller.abort();
  }

  try {
    if (sessionId) {
      await chatApi.stop(effectiveBase(), sessionId);
      stopSucceeded = true;
      markSessionActive(sessionId, false);
      await loadSessionHistory(sessionId);
    }
  } catch (error) {
    console.error("Failed to stop session:", error);
    updateRuntime(runtimeKey, runtime => ({
      ...runtime,
      transportError: friendlyTransportErrorBlock(error, "stop"),
    }));
  } finally {
    updateRuntime(runtimeKey, runtime => ({
      ...runtime,
      isStreaming: false,
      isInsertReady: stopSucceeded ? false : wasInsertReady,
      isStopping: false,
      streamActivity: idleChatStreamActivity(),
      submittedInteractionKeys: new Set(),
    }));
    if (sessionId) resumeAttemptedSessions.delete(sessionId);
    void loadSessions();
  }
}

async function deleteSession(sessionId: string) {
  const controller = streamControllers.get(sessionId);
  if (controller) {
    streamControllers.delete(sessionId);
    controller.abort();
  }
  try {
    await chatApi.deleteSession(effectiveBase(), sessionId);
    removeRuntime(sessionId);
    sessions.value = sessions.value.filter(session => session.session_id !== sessionId);
    if (selectedSession.value === sessionId) selectSession(null);
    await loadSessions();
  } catch (error) {
    console.error("Failed to delete session:", error);
    throw error;
  }
}

async function compactSession(sessionId: string) {
  try {
    const result = await chatApi.compact(effectiveBase(), sessionId);
    if (result?.success) await loadSessionHistory(sessionId);
    return result;
  } catch (error) {
    console.error("Failed to compact session:", error);
    throw error;
  }
}

async function resumeSession(sessionId?: string) {
  const targetSession = sessionId ?? selectedSession.value;
  if (!targetSession || streamControllers.has(targetSession) || resumeInFlightSessions.has(targetSession)) return;
  if (runtimes.value.get(targetSession)?.isStopping) return;
  resumeInFlightSessions.add(targetSession);
  resumeAttemptedSessions.add(targetSession);
  if (!runtimes.value.has(targetSession)) setRuntime(targetSession, newRuntime());
  if ((runtimes.value.get(targetSession)?.messages.length ?? 0) === 0) {
    await loadSessionHistory(targetSession);
  }
  if (streamControllers.has(targetSession)) {
    resumeInFlightSessions.delete(targetSession);
    return;
  }

  const controller = new AbortController();
  const context: StreamContext = {
    runtimeKey: targetSession,
    sessionId: targetSession,
    controller,
  };
  const nextEventCursor = runtimes.value.get(targetSession)?.nextEventCursor ?? 0;
  streamControllers.set(targetSession, controller);
  updateRuntime(targetSession, runtime => ({
    ...runtime,
    isStreaming: true,
    isStopping: false,
    streamActivity: startedChatStreamActivity(),
    transportError: null,
  }));
  let streamCompleted = false;

  try {
    const response = await request(`${normalizeBaseUrl(effectiveBase())}/api/v1/chat/resume`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({
        session_id: targetSession,
        ...(nextEventCursor > 0 ? { from_event_id: nextEventCursor } : {}),
      }),
      signal: controller.signal,
    });
    await consumeChatResponse(context, response);
    if (streamControllers.get(targetSession) === controller) streamCompleted = true;
  } catch (error) {
    if ((error as Error).name !== "AbortError" && streamControllers.get(targetSession) === controller) {
      console.error("Failed to resume session:", error);
      updateRuntime(targetSession, runtime => ({
        ...runtime,
        transportError: friendlyTransportErrorBlock(error, "resume"),
        needsHistoryRefresh: true,
      }));
    }
  } finally {
    await finalizeStream(context, streamCompleted);
    resumeInFlightSessions.delete(targetSession);
  }
}

async function insertMessage(message: string): Promise<InsertMessageData> {
  const sessionId = selectedSession.value;
  const text = message.trim();
  if (!sessionId) throw new Error("当前会话尚未建立，无法补充消息");
  if (!text) throw new Error("补充内容不能为空");
  if (!isStreaming.value) throw new Error("当前会话未在生成中，无法补充消息");
  if (isStopping.value) throw new Error("正在停止当前任务");
  if (!isInsertReady.value) throw new Error("正在建立会话，请稍候");

  const result = await chatApi.insert(effectiveBase(), sessionId, text);
  if (!result) throw new Error("后端未确认本次补充消息");
  return result;
}

function clearTransportError() {
  const runtimeKey = selectedRuntimeKey.value;
  if (!runtimeKey) return;
  updateRuntime(runtimeKey, runtime => ({ ...runtime, transportError: null }));
}

async function sendInteraction(interactionKey: string, answers: string | string[][]) {
  const sessionId = selectedSession.value;
  if (!sessionId) throw new Error("会话未就绪");
  if (!interactionKey) throw new Error("交互请求未就绪");
  if (activeInteractionKey.value !== interactionKey) throw new Error("交互请求已失效");

  updateRuntime(sessionId, runtime => ({
    ...runtime,
    submittedInteractionKeys: new Set([...runtime.submittedInteractionKeys, interactionKey]),
  }));
  try {
    const result = await chatApi.userInteraction(
      effectiveBase(),
      buildUserInteractionInput(sessionId, interactionKey, answers),
    );
    if (!result) throw new Error("后端未接受本次交互提交");
    updateRuntime(sessionId, runtime => ({
      ...runtime,
      streamActivity: continuingChatStreamActivity(runtime.streamActivity),
    }));
  } catch (error) {
    updateRuntime(sessionId, runtime => {
      const next = new Set(runtime.submittedInteractionKeys);
      next.delete(interactionKey);
      return { ...runtime, submittedInteractionKeys: next };
    });
    throw error;
  }
}

function clearMessages() {
  selectSession(null);
}

function dispose() {
  for (const controller of streamControllers.values()) controller.abort();
  streamControllers.clear();
  historyRequestIds.clear();
  resumeAttemptedSessions.clear();
  resumeInFlightSessions.clear();
  runtimes.value = new Map();
  sessions.value = [];
  selectedRuntimeKey.value = null;
  selectedSession.value = null;
  isLoadingSessions.value = false;
}

export function useChatState() {
  return {
    messages,
    sessions: readonly(sessions),
    selectedSession: readonly(selectedSession),
    isStreaming,
    isInsertReady,
    isStopping,
    streamActivity,
    isLoadingSessions: readonly(isLoadingSessions),
    transportError,
    activeInteractionKey,
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
