import { readonly, shallowRef } from "vue";

import { chatApi } from "@/lib/api";
import {
  extractResultData,
  filterVisibleChatSessions,
  friendlyTransportErrorBlock,
  normalizeHistoryMessages,
  requestJson,
} from "@/lib/chat";
import type { ChatSessionOption } from "@/types";
import type { ChatRuntimeUpdater, ChatSessionRuntime } from "./useChatRuntimeStore";

interface ChatSessionHistoryRuntimeSource {
  getRuntime: (runtimeKey: string) => ChatSessionRuntime | undefined;
  getController: (runtimeKey: string) => AbortController | undefined;
  ensureRuntime: (runtimeKey: string) => void;
  updateRuntime: (runtimeKey: string, update: ChatRuntimeUpdater) => void;
  invalidateHistory: (runtimeKey: string) => number;
  isHistoryRequestCurrent: (runtimeKey: string, requestId: number) => boolean;
}

export interface UseChatSessionHistoryOptions {
  effectiveBase: () => string;
  runtime: ChatSessionHistoryRuntimeSource;
  resumeSession: (sessionId: string) => Promise<void>;
}

const sessions = shallowRef<ChatSessionOption[]>([]);
const isLoadingSessions = shallowRef(false);
const resumeAttemptedSessions = new Set<string>();
const resumeInFlightSessions = new Set<string>();

function sessionFirstUserMessage(runtime: ChatSessionRuntime) {
  return runtime.messages.find(message => message.role === "user" && message.content.trim())?.content;
}

export function useChatSessionHistory(options: UseChatSessionHistoryOptions) {
  function clearResumeAttempt(sessionId: string) {
    resumeAttemptedSessions.delete(sessionId);
  }

  function hasResumeAttempt(sessionId: string) {
    return resumeAttemptedSessions.has(sessionId);
  }

  function startResume(sessionId: string) {
    if (resumeInFlightSessions.has(sessionId)) return false;
    resumeInFlightSessions.add(sessionId);
    resumeAttemptedSessions.add(sessionId);
    return true;
  }

  function finishResume(sessionId: string) {
    resumeInFlightSessions.delete(sessionId);
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
    const runtime = options.runtime.getRuntime(runtimeKey);
    sessions.value = [{
      session_id: sessionId,
      user_query: runtime ? sessionFirstUserMessage(runtime) : undefined,
      created_at: now,
      last_updated: now,
      total_turns: 0,
      is_active: true,
    }, ...sessions.value];
  }

  async function loadSessionHistory(sessionId: string) {
    const requestId = options.runtime.invalidateHistory(sessionId);
    options.runtime.ensureRuntime(sessionId);
    const base = options.effectiveBase();
    try {
      const payload = await requestJson<unknown>(
        base,
        `/api/v1/chat/history?session_id=${encodeURIComponent(sessionId)}`,
      );
      if (!options.runtime.isHistoryRequestCurrent(sessionId, requestId)) return;
      const data = extractResultData<{ messages?: unknown[] }>(payload);
      const historyMessages = normalizeHistoryMessages(data?.messages ?? []);
      options.runtime.updateRuntime(sessionId, runtime => ({
        ...runtime,
        messages: historyMessages,
        transportError: null,
        needsHistoryRefresh: false,
      }));
    } catch (error) {
      if (!options.runtime.isHistoryRequestCurrent(sessionId, requestId)) return;
      console.error("Failed to load session history:", error);
      options.runtime.updateRuntime(sessionId, runtime => ({
        ...runtime,
        transportError: friendlyTransportErrorBlock(error, "history"),
      }));
    }
  }

  async function loadSessions(subagentId?: string) {
    const base = options.effectiveBase();
    isLoadingSessions.value = true;
    try {
      const result = await chatApi.sessions(base, subagentId);
      if (!result) return;
      const loadedSessions = result.sessions ?? [];
      const visibleSessions = subagentId ? loadedSessions : filterVisibleChatSessions(loadedSessions);
      sessions.value = visibleSessions.map(session => ({
        ...session,
        is_active: Boolean(session.is_active || options.runtime.getController(session.session_id)),
      }));

      for (const session of sessions.value) {
        if (!session.is_active) {
          clearResumeAttempt(session.session_id);
          continue;
        }
        if (options.runtime.getRuntime(session.session_id)?.isStopping) continue;
        if (!options.runtime.getController(session.session_id) && !hasResumeAttempt(session.session_id)) {
          void options.resumeSession(session.session_id);
        }
      }
    } catch (error) {
      console.error("Failed to load sessions:", error);
    } finally {
      isLoadingSessions.value = false;
    }
  }

  function invalidateHistory(runtimeKey: string) {
    options.runtime.invalidateHistory(runtimeKey);
  }

  function removeSession(sessionId: string) {
    sessions.value = sessions.value.filter(session => session.session_id !== sessionId);
  }

  function dispose() {
    resumeAttemptedSessions.clear();
    resumeInFlightSessions.clear();
    sessions.value = [];
    isLoadingSessions.value = false;
  }

  return {
    sessions: readonly(sessions),
    isLoadingSessions: readonly(isLoadingSessions),
    loadSessions,
    loadSessionHistory,
    markSessionActive,
    invalidateHistory,
    removeSession,
    clearResumeAttempt,
    startResume,
    finishResume,
    dispose,
  };
}
