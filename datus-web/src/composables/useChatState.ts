import { useConnection } from "./useConnection";
import { useChatActions } from "./useChatActions";
import { useChatSettings } from "./useChatSettings";
import { useChatSessionFlow } from "./useChatSessionFlow";
import { useChatSessionHistory } from "./useChatSessionHistory";
import { useChatStream, type ChatStreamContext } from "./useChatStream";
import {
  useChatRuntimeStore,
  type ChatRuntimeUpdater,
} from "./useChatRuntimeStore";

const { effectiveBase } = useConnection();
const runtimeStore = useChatRuntimeStore();

function resumeListedSession(sessionId: string) {
  return chatSessionFlow.resumeSession(sessionId);
}

const sessionHistory = useChatSessionHistory({
  effectiveBase,
  runtime: runtimeStore,
  resumeSession: resumeListedSession,
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

const chatSettings = useChatSettings();
const chatSessionFlow = useChatSessionFlow({
  runtime: {
    getSelectedSession: () => selectedSession.value,
    ensureSelectedRuntime: runtimeStore.ensureSelectedRuntime,
    hasController: runtimeStore.hasController,
    getRuntime: runtimeStore.getRuntime,
    ensureRuntime: runtimeStore.ensureRuntime,
    updateRuntime: runtimeStore.updateRuntime,
  },
  history: {
    invalidateHistory,
    clearResumeAttempt,
    startResume,
    finishResume,
    loadSessionHistory,
  },
  stream: chatStream,
  getChatSettings: () => ({
    language: chatSettings.language.value,
    planMode: chatSettings.planMode.value,
    permissionMode: chatSettings.permissionMode.value,
  }),
});
const { sendMessage, resumeSession } = chatSessionFlow;

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
