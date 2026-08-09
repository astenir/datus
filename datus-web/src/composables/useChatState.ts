import { chatApi } from "@/lib/api";
import {
  activeUserInteractionKey,
  buildChatStreamRequest,
  buildUserInteractionInput,
  createClientId,
  friendlyTransportErrorBlock,
} from "@/lib/chat";
import {
  continuingChatStreamActivity,
  idleChatStreamActivity,
  startedChatStreamActivity,
} from "@/lib/chat-activity";
import type {
  ChatMessage,
  InsertMessageData,
} from "@/types";
import { useConnection } from "./useConnection";
import { useChatSettings } from "./useChatSettings";
import { useChatSessionHistory } from "./useChatSessionHistory";
import { useChatStream, type ChatStreamContext } from "./useChatStream";
import {
  useChatRuntimeStore,
  type ChatRuntimeUpdater,
} from "./useChatRuntimeStore";

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

function rekeyRuntime(context: ChatStreamContext, sessionId: string) {
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

const chatStream = useChatStream({
  effectiveBase,
  runtime: runtimeStore,
  onSessionId: rekeyRuntime,
  onStreamCompleted: async sessionId => {
    markSessionActive(sessionId, false);
    await loadSessionHistory(sessionId);
  },
  onStreamSettled: () => {
    void loadSessions();
  },
});

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
  await chatStream.start({
    runtimeKey,
    sessionId,
    path: "/api/v1/chat/stream",
    body,
    errorContext: "stream",
  });
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

  const nextEventCursor = runtimeStore.getRuntime(targetSession)?.nextEventCursor ?? 0;
  updateRuntime(targetSession, runtime => ({
    ...runtime,
    isStreaming: true,
    isStopping: false,
    streamActivity: startedChatStreamActivity(),
    transportError: null,
  }));
  try {
    await chatStream.start({
      runtimeKey: targetSession,
      sessionId: targetSession,
      path: "/api/v1/chat/resume",
      body: {
        session_id: targetSession,
        ...(nextEventCursor > 0 ? { from_event_id: nextEventCursor } : {}),
      },
      errorContext: "resume",
      onError: error => console.error("Failed to resume session:", error),
    });
  } finally {
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
