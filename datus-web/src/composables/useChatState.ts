import { useConnection } from "./useConnection";
import { useChatActions } from "./useChatActions";
import { useChatSettings } from "./useChatSettings";
import { useChatSessionCoordinator } from "./useChatSessionCoordinator";
import { useChatRuntimeStore } from "./useChatRuntimeStore";

const { effectiveBase } = useConnection();
const runtimeStore = useChatRuntimeStore();
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

const chatSettings = useChatSettings();
const chatSessionCoordinator = useChatSessionCoordinator({
  effectiveBase,
  runtime: {
    getSelectedSession: () => selectedSession.value,
    ensureSelectedRuntime: runtimeStore.ensureSelectedRuntime,
    hasController: runtimeStore.hasController,
    getRuntime: runtimeStore.getRuntime,
    ensureRuntime: runtimeStore.ensureRuntime,
    updateRuntime: runtimeStore.updateRuntime,
    getController: runtimeStore.getController,
    setController: runtimeStore.setController,
    deleteController: runtimeStore.deleteController,
    selectSession: runtimeStore.selectSession,
    rekeyRuntime: runtimeStore.rekeyRuntime,
    isHistoryRequestCurrent: runtimeStore.isHistoryRequestCurrent,
    invalidateHistory: runtimeStore.invalidateHistory,
    dispose: runtimeStore.dispose,
  },
  getChatSettings: () => ({
    language: chatSettings.language.value,
    planMode: chatSettings.planMode.value,
    permissionMode: chatSettings.permissionMode.value,
  }),
});
const {
  sessions,
  isLoadingSessions,
  loadSessions,
  loadSessionHistory,
  markSessionActive,
  removeSession,
  clearResumeAttempt,
  sendMessage,
  resumeSession,
  selectSession,
  dispose,
} = chatSessionCoordinator;

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
  runtimeStore.updateRuntime(runtimeKey, runtime => ({ ...runtime, transportError: null }));
}

function clearMessages() {
  selectSession(null);
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
