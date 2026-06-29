import { readonly, ref, shallowRef } from "vue";
import { chatApi } from "@/lib/api";
import {
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
import type { ChatMessage, ChatSessionOption } from "@/types";
import { useConnection } from "./useConnection";
import { useChatSettings } from "./useChatSettings";

const { effectiveBase } = useConnection();

const messages = ref<ChatMessage[]>([]);
const sessions = ref<ChatSessionOption[]>([]);
const selectedSession = shallowRef<string | null>(null);
const isStreaming = shallowRef(false);
const isLoadingSessions = shallowRef(false);
const abortRef = { current: null as AbortController | null };
const messageCache = new Map<string, ChatMessage[]>();
const CACHE_MAX = 20;

function cacheSet(key: string, value: ChatMessage[]) {
  if (messageCache.size >= CACHE_MAX && !messageCache.has(key)) {
    const oldest = messageCache.keys().next().value;
    if (oldest) messageCache.delete(oldest);
  }
  messageCache.set(key, value);
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

async function loadSessionHistory(sessionId: string) {
  const base = effectiveBase();
  try {
    const payload = await requestJson<unknown>(base, `/api/v1/chat/history?session_id=${encodeURIComponent(sessionId)}`);
    const data = extractResultData<{ messages?: unknown[] }>(payload);
    messages.value = normalizeHistoryMessages(data?.messages ?? []);
  } catch (error) {
    console.error("Failed to load session history:", error);
    messages.value = [];
  }
}

function selectSession(sessionId: string | null) {
  // Abort the active stream before switching.
  if (abortRef.current) {
    abortRef.current.abort();
    abortRef.current = null;
  }
  isStreaming.value = false;

  // Cache current messages for the outgoing session
  if (selectedSession.value && messages.value.length > 0) {
    cacheSet(selectedSession.value, messages.value);
  }

  selectedSession.value = sessionId;
  if (sessionId) {
    // Restore from cache if available, otherwise load from backend
    const cached = messageCache.get(sessionId);
    if (cached) {
      messages.value = cached;
    } else {
      loadSessionHistory(sessionId);
    }
  } else {
    messages.value = [];
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

  try {
    const url = `${normalizeBaseUrl(base)}/api/v1/chat/stream`;
    const response = await request(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });

    const reader = response.body?.getReader();
    if (!reader) throw new Error("No response body");

    const decoder = new TextDecoder();
    let buffer = "";

    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const parsed = parseSseBuffer(buffer);
      buffer = parsed.rest;

      for (const event of parsed.events) {
        // Capture session ID from ALL events, before type filtering
        captureSessionId(event);

        const incoming = messageFromEvent(event);
        if (!incoming) continue;
        messages.value = mergeMessage(messages.value, incoming);
      }
    }

    if (buffer) {
      const parsed = parseSseBuffer(buffer, { flush: true });
      for (const event of parsed.events) {
        captureSessionId(event);
        const incoming = messageFromEvent(event);
        if (incoming) messages.value = mergeMessage(messages.value, incoming);
      }
    }
  } catch (error) {
    if ((error as Error).name !== "AbortError") {
      messages.value = [
        ...messages.value,
        {
          id: `error-${Date.now()}`,
          role: "system",
          content: `**错误** ${error instanceof Error ? error.message : String(error)}`,
        },
      ];
    }
  } finally {
    isStreaming.value = false;
    abortRef.current = null;
    // Update cache with latest messages
    if (selectedSession.value) {
      cacheSet(selectedSession.value, messages.value);
    }
    loadSessions();
  }
}

async function stopSession() {
  const base = effectiveBase();
  if (abortRef.current) {
    abortRef.current.abort();
    abortRef.current = null;
  }
  if (selectedSession.value) {
    try {
      await chatApi.stop(base, selectedSession.value);
    } catch (error) {
      console.error("Failed to stop session:", error);
    }
  }
  isStreaming.value = false;
}

async function deleteSession(sessionId: string) {
  const base = effectiveBase();
  try {
    await chatApi.deleteSession(base, sessionId);
    messageCache.delete(sessionId);
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
  const base = effectiveBase();
  const controller = new AbortController();
  abortRef.current = controller;
  isStreaming.value = true;
  try {
    const url = `${normalizeBaseUrl(base)}/api/v1/chat/resume`;
    const response = await request(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({ session_id: targetSession }),
      signal: controller.signal,
    });
    const tail = await consumeSseStream(response, (event) => {
      captureSessionId(event);
      const incoming = messageFromEvent(event);
      if (incoming) messages.value = mergeMessage(messages.value, incoming);
    });
    if (tail) {
      const parsed = parseSseBuffer(tail, { flush: true });
      for (const event of parsed.events) {
        captureSessionId(event);
        const incoming = messageFromEvent(event);
        if (incoming) messages.value = mergeMessage(messages.value, incoming);
      }
    }
  } catch (error) {
    if ((error as Error).name !== "AbortError") {
      console.error("Failed to resume session:", error);
    }
  } finally {
    isStreaming.value = false;
    abortRef.current = null;
    if (selectedSession.value) {
      cacheSet(selectedSession.value, messages.value);
    }
    loadSessions();
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
    messages.value = [
      ...messages.value,
      {
        id: `error-${Date.now()}`,
        role: "system",
        content: `**注入失败** ${error instanceof Error ? error.message : String(error)}`,
      },
    ];
  }
}

async function sendInteraction(interactionKey: string, answers: string | string[][]) {
  const base = effectiveBase();
  const sessionId = selectedSession.value;
  if (!sessionId) throw new Error("会话未就绪");
  if (!interactionKey) throw new Error("交互请求未就绪");

  // Do NOT stopSession — the task is alive and waiting for interaction.
  // The SSE stream from sendMessage is still open; broker.submit() will
  // unblock the task and new events flow through the same stream.

  const result = await chatApi.userInteraction(base, buildUserInteractionInput(sessionId, interactionKey, answers));
  if (!result) throw new Error("后端未接受本次交互提交");
  // No resumeSession needed — sendMessage's SSE reader is still running.
}

function clearMessages() {
  messages.value = [];
  selectedSession.value = null;
  messageCache.clear();
}

function dispose() {
  if (abortRef.current) {
    abortRef.current.abort();
    abortRef.current = null;
  }
  isStreaming.value = false;
}

export function useChatState() {
  return {
    messages: readonly(messages),
    sessions: readonly(sessions),
    selectedSession: readonly(selectedSession),
    isStreaming: readonly(isStreaming),
    isLoadingSessions: readonly(isLoadingSessions),
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
    dispose,
  };
}
