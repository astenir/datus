import {
  useChatSessionFlow,
  type ChatSessionFlowRuntimeSource,
  type ChatSessionSettings,
} from "./useChatSessionFlow";
import { useChatSessionHistory } from "./useChatSessionHistory";
import {
  useChatStream,
  type ChatStreamContext,
  type ChatStreamRuntimeSource,
} from "./useChatStream";

export interface ChatSessionRuntimeRekeyOptions {
  controller: AbortController;
}

export interface ChatSessionCoordinatorRuntimeSource
  extends ChatSessionFlowRuntimeSource, ChatStreamRuntimeSource {
  selectSession: (sessionId: string | null) => void;
  rekeyRuntime: (
    oldKey: string,
    sessionId: string,
    options: ChatSessionRuntimeRekeyOptions,
  ) => void;
  isHistoryRequestCurrent: (runtimeKey: string, requestId: number) => boolean;
  invalidateHistory: (runtimeKey: string) => number;
  dispose: () => void;
}

export interface UseChatSessionCoordinatorOptions {
  effectiveBase: () => string;
  runtime: ChatSessionCoordinatorRuntimeSource;
  getChatSettings: () => ChatSessionSettings;
}

export function useChatSessionCoordinator(options: UseChatSessionCoordinatorOptions) {
  function resumeListedSession(sessionId: string) {
    return chatSessionFlow.resumeSession(sessionId);
  }

  const sessionHistory = useChatSessionHistory({
    effectiveBase: options.effectiveBase,
    runtime: {
      getRuntime: options.runtime.getRuntime,
      getController: options.runtime.getController,
      ensureRuntime: options.runtime.ensureRuntime,
      updateRuntime: options.runtime.updateRuntime,
      invalidateHistory: options.runtime.invalidateHistory,
      isHistoryRequestCurrent: options.runtime.isHistoryRequestCurrent,
    },
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

  function rekeyRuntime(context: ChatStreamContext, sessionId: string) {
    const oldKey = context.runtimeKey;
    if (oldKey === sessionId) {
      context.sessionId = sessionId;
      return;
    }

    options.runtime.rekeyRuntime(oldKey, sessionId, { controller: context.controller });
    clearResumeAttempt(oldKey);
    context.runtimeKey = sessionId;
    context.sessionId = sessionId;
    markSessionActive(sessionId, true);
  }

  const chatStream = useChatStream({
    effectiveBase: options.effectiveBase,
    runtime: {
      getController: options.runtime.getController,
      setController: options.runtime.setController,
      deleteController: options.runtime.deleteController,
      updateRuntime: options.runtime.updateRuntime,
    },
    onSessionId: rekeyRuntime,
    onStreamCompleted: async sessionId => {
      markSessionActive(sessionId, false);
      await loadSessionHistory(sessionId);
    },
    onStreamSettled: () => {
      void loadSessions();
    },
  });

  const chatSessionFlow = useChatSessionFlow({
    runtime: {
      getSelectedSession: options.runtime.getSelectedSession,
      ensureSelectedRuntime: options.runtime.ensureSelectedRuntime,
      hasController: options.runtime.hasController,
      getRuntime: options.runtime.getRuntime,
      ensureRuntime: options.runtime.ensureRuntime,
      updateRuntime: options.runtime.updateRuntime,
    },
    history: {
      invalidateHistory,
      clearResumeAttempt,
      startResume,
      finishResume,
      loadSessionHistory,
    },
    stream: chatStream,
    getChatSettings: options.getChatSettings,
  });
  const { sendMessage, resumeSession } = chatSessionFlow;

  function selectSession(sessionId: string | null) {
    if (!sessionId) {
      options.runtime.selectSession(null);
      return;
    }

    const runtime = options.runtime.getRuntime(sessionId);
    options.runtime.selectSession(sessionId);
    if (!runtime) {
      void loadSessionHistory(sessionId);
    } else if (!runtime.isStreaming && runtime.needsHistoryRefresh) {
      void loadSessionHistory(sessionId);
    }
    const listedSession = sessions.value.find(session => session.session_id === sessionId);
    if (listedSession?.is_active
      && !options.runtime.hasController(sessionId)
      && !options.runtime.getRuntime(sessionId)?.isStopping) {
      void resumeSession(sessionId);
    }
  }

  function dispose() {
    options.runtime.dispose();
    sessionHistory.dispose();
  }

  return {
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
  };
}
