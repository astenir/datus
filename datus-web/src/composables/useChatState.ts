import {
  buildChatStreamRequest,
  createClientId,
} from "@/lib/chat";
import {
  startedChatStreamActivity,
} from "@/lib/chat-activity";
import type { ChatMessage } from "@/types";
import { useConnection } from "./useConnection";
import { useChatActions } from "./useChatActions";
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

const chatActions = useChatActions({
  effectiveBase,
  runtime: {
    getSelectedSession: () => selectedSession.value,
    getSelectedRuntimeKey: () => selectedRuntimeKey.value,
    getIsStreaming: () => isStreaming.value,
    getIsInsertReady: () => isInsertReady.value,
    getIsStopping: () => isStopping.value,
    getActiveInteractionKey: () => activeInteractionKey.value,
    getRuntime: runtimeStore.getRuntime,
    getController: runtimeStore.getController,
    deleteController: runtimeStore.deleteController,
    updateRuntime: runtimeStore.updateRuntime,
    removeRuntime: runtimeStore.removeRuntime,
  },
  history: {
    loadSessions,
    loadSessionHistory,
    markSessionActive,
    clearResumeAttempt,
    removeSession,
  },
  clearSelectedSession: () => selectSession(null),
});
const {
  stopSession,
  deleteSession,
  compactSession,
  insertMessage,
  sendInteraction,
} = chatActions;

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

function clearTransportError() {
  const runtimeKey = selectedRuntimeKey.value;
  if (!runtimeKey) return;
  updateRuntime(runtimeKey, runtime => ({ ...runtime, transportError: null }));
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
