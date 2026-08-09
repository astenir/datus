import { buildChatStreamRequest, createClientId } from "@/lib/chat";
import { startedChatStreamActivity } from "@/lib/chat-activity";
import type { ChatMessage } from "@/types";
import type { ChatStreamRequest } from "./useChatStream";
import type { ChatRuntimeUpdater, ChatSessionRuntime } from "./useChatRuntimeStore";

export interface ChatSessionMessageOptions {
  message: string;
  selectedAgent: string;
  model: string;
  datasource: string;
  database: string;
  schema: string;
  personalMcpIds?: readonly string[];
}

export interface ChatSessionSettings {
  language: string;
  planMode: boolean;
  permissionMode: string;
}

export interface ChatSessionFlowRuntimeSource {
  getSelectedSession: () => string | null;
  ensureSelectedRuntime: () => string;
  hasController: (runtimeKey: string) => boolean;
  getRuntime: (runtimeKey: string) => ChatSessionRuntime | undefined;
  ensureRuntime: (runtimeKey: string) => void;
  updateRuntime: (runtimeKey: string, update: ChatRuntimeUpdater) => void;
}

export interface ChatSessionFlowHistorySource {
  invalidateHistory: (runtimeKey: string) => void;
  clearResumeAttempt: (sessionId: string) => void;
  startResume: (sessionId: string) => boolean;
  finishResume: (sessionId: string) => void;
  loadSessionHistory: (sessionId: string) => Promise<void>;
}

export interface ChatSessionFlowStreamSource {
  start: (input: ChatStreamRequest) => Promise<void>;
}

export interface UseChatSessionFlowOptions {
  runtime: ChatSessionFlowRuntimeSource;
  history: ChatSessionFlowHistorySource;
  stream: ChatSessionFlowStreamSource;
  getChatSettings: () => ChatSessionSettings;
}

export function useChatSessionFlow(options: UseChatSessionFlowOptions) {
  async function sendMessage(opts: ChatSessionMessageOptions) {
    const runtimeKey = options.runtime.ensureSelectedRuntime();
    if (options.runtime.hasController(runtimeKey) || options.runtime.getRuntime(runtimeKey)?.isStreaming) return;

    const sessionId = options.runtime.getSelectedSession();
    options.history.invalidateHistory(runtimeKey);
    if (sessionId) options.history.clearResumeAttempt(sessionId);
    const userMessage: ChatMessage = {
      id: createClientId(),
      role: "user",
      content: opts.message,
    };
    options.runtime.updateRuntime(runtimeKey, runtime => ({
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

    const settings = options.getChatSettings();
    const body = buildChatStreamRequest({
      message: opts.message,
      sessionId: sessionId ?? "",
      selectedAgent: opts.selectedAgent,
      model: opts.model,
      datasource: opts.datasource,
      database: opts.database,
      schema: opts.schema,
      language: settings.language,
      planMode: settings.planMode,
      permissionMode: settings.permissionMode,
      personalMcpIds: opts.personalMcpIds,
    });
    await options.stream.start({
      runtimeKey,
      sessionId,
      path: "/api/v1/chat/stream",
      body,
      errorContext: "stream",
    });
  }

  async function resumeSession(sessionId?: string) {
    const targetSession = sessionId ?? options.runtime.getSelectedSession();
    if (!targetSession || options.runtime.hasController(targetSession)) return;
    if (options.runtime.getRuntime(targetSession)?.isStopping) return;
    if (!options.history.startResume(targetSession)) return;
    options.runtime.ensureRuntime(targetSession);
    if ((options.runtime.getRuntime(targetSession)?.messages.length ?? 0) === 0) {
      await options.history.loadSessionHistory(targetSession);
    }
    if (options.runtime.hasController(targetSession)) {
      options.history.finishResume(targetSession);
      return;
    }

    const nextEventCursor = options.runtime.getRuntime(targetSession)?.nextEventCursor ?? 0;
    options.runtime.updateRuntime(targetSession, runtime => ({
      ...runtime,
      isStreaming: true,
      isStopping: false,
      streamActivity: startedChatStreamActivity(),
      transportError: null,
    }));
    try {
      await options.stream.start({
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
      options.history.finishResume(targetSession);
    }
  }

  return { sendMessage, resumeSession };
}
