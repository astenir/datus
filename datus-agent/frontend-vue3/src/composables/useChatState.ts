import { ref } from "vue";
import { chatApi } from "@/lib/api";
import {
  buildChatStreamRequest,
  consumeSseStream,
  mergeMessage,
  messageFromEvent,
  parseSseBuffer,
  requestJson,
  extractResultData,
  normalizeBaseUrl,
} from "@/lib/chat";
import type { ChatMessage, ChatSessionOption } from "@/types";
import { useConnection } from "./useConnection";
import { useChatSettings } from "./useChatSettings";

const messages = ref<ChatMessage[]>([]);
const sessions = ref<ChatSessionOption[]>([]);
const selectedSession = ref<string | null>(null);
const isStreaming = ref(false);
const isInteracting = ref(false);
const abortRef = { current: null as AbortController | null };
const messageCache = new Map<string, ChatMessage[]>();

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
  const { effectiveBase } = useConnection();
  const base = effectiveBase();
  try {
    const result = await chatApi.sessions(base, subagentId);
    if (result) {
      sessions.value = result.sessions ?? [];
    }
  } catch (error) {
    console.error("Failed to load sessions:", error);
  }
}

async function loadSessionHistory(sessionId: string) {
  const { effectiveBase } = useConnection();
  const base = effectiveBase();
  try {
    const payload = await requestJson<unknown>(base, `/api/v1/chat/history?session_id=${encodeURIComponent(sessionId)}`);
    const data = extractResultData<{ messages?: unknown[] }>(payload);
    const items = (data?.messages ?? []) as Array<{
      message_id?: string | number;
      role?: "user" | "assistant" | "system";
      content?: Array<{ type?: string; payload?: Record<string, unknown> }>;
      depth?: number;
    }>;

    const parsed: ChatMessage[] = [];
    for (const item of items) {
      const msg = messageFromEvent({
        event: "message",
        data: { type: "createMessage", payload: item },
      });
      if (msg) parsed.push(msg.message);
    }
    messages.value = parsed;
  } catch (error) {
    console.error("Failed to load session history:", error);
    messages.value = [];
  }
}

function selectSession(sessionId: string | null) {
  // Abort any active stream before switching
  if (abortRef.current) {
    abortRef.current.abort();
    abortRef.current = null;
  }
  isStreaming.value = false;
  isInteracting.value = false;

  // Cache current messages for the outgoing session
  if (selectedSession.value && messages.value.length > 0) {
    messageCache.set(selectedSession.value, messages.value);
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
  database: string;
  schema: string;
}) {
  const { effectiveBase } = useConnection();
  const { language, planMode, permissionMode } = useChatSettings();
  const base = effectiveBase();

  const userMessage: ChatMessage = {
    id: crypto.randomUUID(),
    role: "user",
    content: opts.message,
  };
  messages.value = [...messages.value, userMessage];

  const body = buildChatStreamRequest({
    message: opts.message,
    sessionId: selectedSession.value ?? "",
    selectedAgent: opts.selectedAgent,
    model: opts.model,
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
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `${response.status} ${response.statusText}`);
    }

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
      messageCache.set(selectedSession.value, messages.value);
    }
    loadSessions();
  }
}

async function stopSession() {
  const { effectiveBase } = useConnection();
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
  const { effectiveBase } = useConnection();
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
  const { effectiveBase } = useConnection();
  const base = effectiveBase();
  try {
    const result = await chatApi.compact(base, sessionId);
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
  const { effectiveBase } = useConnection();
  const base = effectiveBase();
  const controller = new AbortController();
  abortRef.current = controller;
  isStreaming.value = true;
  try {
    const url = `${normalizeBaseUrl(base)}/api/v1/chat/resume`;
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({ session_id: targetSession }),
      signal: controller.signal,
    });
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
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
      messageCache.set(selectedSession.value, messages.value);
    }
    loadSessions();
  }
}

async function sendInteraction(interactionKey: string) {
  const { effectiveBase } = useConnection();
  const base = effectiveBase();
  const sessionId = selectedSession.value;
  if (!sessionId) throw new Error("会话未就绪");

  isInteracting.value = true;

  try {
    // Stop current task to release backend lock
    await stopSession();

    // Wait for backend to release the lock
    await new Promise((r) => setTimeout(r, 1500));

    // Send interaction as JSON (not SSE)
    await chatApi.userInteraction(base, {
      session_id: sessionId,
      interaction_key: interactionKey,
      input: [[interactionKey]],
    });

    // After interaction is submitted, resume to receive continued content via SSE
    await resumeSession(sessionId);
  } finally {
    isInteracting.value = false;
  }
}

function clearMessages() {
  messages.value = [];
  selectedSession.value = null;
  messageCache.clear();
}

export function useChatState() {
  return {
    messages,
    sessions,
    selectedSession,
    isStreaming,
    isInteracting,
    loadSessions,
    selectSession,
    sendMessage,
    stopSession,
    deleteSession,
    compactSession,
    resumeSession,
    sendInteraction,
    clearMessages,
  };
}
