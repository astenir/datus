import { chatApi } from "@/lib/api";
import {
  activeUserInteractionKey,
  buildChatStreamRequest,
  buildUserInteractionInput,
  createClientId,
  friendlyTransportErrorBlock,
  mergeMessage,
  messageFromEvent,
  normalizeBaseUrl,
  parseSseBuffer,
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
  ChatMessage,
  InsertMessageData,
  ParsedMessage,
  SseEvent,
} from "@/types";
import { useConnection } from "./useConnection";
import { useChatSettings } from "./useChatSettings";
import { useChatSessionHistory } from "./useChatSessionHistory";
import {
  useChatRuntimeStore,
  type ChatRuntimeUpdater,
} from "./useChatRuntimeStore";

type StreamContext = {
  runtimeKey: string;
  sessionId: string | null;
  controller: AbortController;
};

const { effectiveBase } = useConnection();
const runtimeStore = useChatRuntimeStore();
const sessionHistory = useChatSessionHistory({
  effectiveBase,
  runtime: runtimeStore,
  resumeSession,
});
const {
  sessions,
  isLoadingSessions,
  loadSessions,
  loadSessionHistory,
  markSessionActive,
  invalidateHistory,
  removeSession,
  clearResumeAttempt,
  startResume,
  finishResume,
} = sessionHistory;

const {
  messages,
  selectedSession,
  selectedRuntimeKey,
  isStreaming,
  isInsertReady,
  isStopping,
  streamActivity,
  transportError,
  activeInteractionKey,
} = runtimeStore;

function updateRuntime(key: string, update: ChatRuntimeUpdater) {
  runtimeStore.updateRuntime(key, update);
}

function removeRuntime(key: string) {
  runtimeStore.removeRuntime(key);
  clearResumeAttempt(key);
}

function rekeyRuntime(context: StreamContext, sessionId: string) {
  const oldKey = context.runtimeKey;
  if (oldKey === sessionId) {
    context.sessionId = sessionId;
    return;
  }

  runtimeStore.rekeyRuntime(oldKey, sessionId, { controller: context.controller });
  clearResumeAttempt(oldKey);
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
  if (runtimeStore.getController(context.runtimeKey) !== context.controller) return;
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
    if (runtimeStore.getController(context.runtimeKey) !== context.controller) return;
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
  if (!buffer || runtimeStore.getController(context.runtimeKey) !== context.controller) return;
  const parsed = parseSseBuffer(buffer, { flush: true });
  const incomingMessages: ParsedMessage[] = [];
  for (const event of parsed.events) {
    const incoming = applyStreamEvent(context, event);
    if (incoming) incomingMessages.push(incoming);
  }
  applyIncomingMessages(context.runtimeKey, incomingMessages);
}

function selectSession(sessionId: string | null) {
  if (!sessionId) {
    runtimeStore.selectSession(null);
    return;
  }

  const runtime = runtimeStore.getRuntime(sessionId);
  runtimeStore.selectSession(sessionId);
  if (!runtime) {
    void loadSessionHistory(sessionId);
  } else if (!runtime.isStreaming && runtime.needsHistoryRefresh) {
    void loadSessionHistory(sessionId);
  }
  const listedSession = sessions.value.find(session => session.session_id === sessionId);
  if (listedSession?.is_active && !runtimeStore.hasController(sessionId) && !runtimeStore.getRuntime(sessionId)?.isStopping) {
    void resumeSession(sessionId);
  }
}

async function finalizeStream(context: StreamContext, streamCompleted: boolean) {
  if (runtimeStore.getController(context.runtimeKey) !== context.controller) return;
  runtimeStore.deleteController(context.runtimeKey, context.controller);
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
  const runtimeKey = runtimeStore.ensureSelectedRuntime();
  if (runtimeStore.hasController(runtimeKey) || runtimeStore.getRuntime(runtimeKey)?.isStreaming) return;

  const sessionId = selectedSession.value;
  invalidateHistory(runtimeKey);
  if (sessionId) clearResumeAttempt(sessionId);
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
  runtimeStore.setController(runtimeKey, controller);
  let streamCompleted = false;

  try {
    const response = await request(`${normalizeBaseUrl(effectiveBase())}/api/v1/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    await consumeChatResponse(context, response);
    if (runtimeStore.getController(context.runtimeKey) === controller) streamCompleted = true;
  } catch (error) {
    if ((error as Error).name !== "AbortError" && runtimeStore.getController(context.runtimeKey) === controller) {
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
  const currentRuntime = runtimeStore.getRuntime(runtimeKey);
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

  const controller = runtimeStore.getController(runtimeKey);
  if (controller) {
    runtimeStore.deleteController(runtimeKey, controller);
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
    if (sessionId) clearResumeAttempt(sessionId);
    void loadSessions();
  }
}

async function deleteSession(sessionId: string) {
  const controller = runtimeStore.getController(sessionId);
  if (controller) {
    runtimeStore.deleteController(sessionId, controller);
    controller.abort();
  }
  try {
    await chatApi.deleteSession(effectiveBase(), sessionId);
    removeRuntime(sessionId);
    removeSession(sessionId);
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
  if (!targetSession || runtimeStore.hasController(targetSession)) return;
  if (runtimeStore.getRuntime(targetSession)?.isStopping) return;
  if (!startResume(targetSession)) return;
  runtimeStore.ensureRuntime(targetSession);
  if ((runtimeStore.getRuntime(targetSession)?.messages.length ?? 0) === 0) {
    await loadSessionHistory(targetSession);
  }
  if (runtimeStore.hasController(targetSession)) {
    finishResume(targetSession);
    return;
  }

  const controller = new AbortController();
  const context: StreamContext = {
    runtimeKey: targetSession,
    sessionId: targetSession,
    controller,
  };
  const nextEventCursor = runtimeStore.getRuntime(targetSession)?.nextEventCursor ?? 0;
  runtimeStore.setController(targetSession, controller);
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
    if (runtimeStore.getController(targetSession) === controller) streamCompleted = true;
  } catch (error) {
    if ((error as Error).name !== "AbortError" && runtimeStore.getController(targetSession) === controller) {
      console.error("Failed to resume session:", error);
      updateRuntime(targetSession, runtime => ({
        ...runtime,
        transportError: friendlyTransportErrorBlock(error, "resume"),
        needsHistoryRefresh: true,
      }));
    }
  } finally {
    await finalizeStream(context, streamCompleted);
    finishResume(targetSession);
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
    updateRuntime(sessionId, runtime => {
      const pendingInteractionKey = activeUserInteractionKey(runtime.messages, {
        isStreaming: runtime.isStreaming,
        isAwaitingUser: runtime.streamActivity.phase === "awaiting_user",
        submittedInteractionKeys: runtime.submittedInteractionKeys,
      });

      return {
        ...runtime,
        streamActivity: pendingInteractionKey && pendingInteractionKey !== interactionKey
          ? runtime.streamActivity
          : continuingChatStreamActivity(runtime.streamActivity),
      };
    });
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
  runtimeStore.dispose();
  sessionHistory.dispose();
}

export function useChatState() {
  return {
    messages,
    sessions,
    selectedSession,
    isStreaming,
    isInsertReady,
    isStopping,
    streamActivity,
    isLoadingSessions,
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
