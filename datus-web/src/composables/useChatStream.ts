import {
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
  idleChatStreamActivity,
} from "@/lib/chat-activity";
import type { ParsedMessage, SseEvent } from "@/types";
import type { ChatRuntimeUpdater } from "./useChatRuntimeStore";

export type ChatStreamContext = {
  runtimeKey: string;
  sessionId: string | null;
  controller: AbortController;
};

export interface ChatStreamRuntimeSource {
  getController: (runtimeKey: string) => AbortController | undefined;
  setController: (runtimeKey: string, controller: AbortController) => void;
  deleteController: (runtimeKey: string, controller?: AbortController) => boolean;
  updateRuntime: (runtimeKey: string, update: ChatRuntimeUpdater) => void;
}

export interface ChatStreamRequest {
  runtimeKey: string;
  sessionId: string | null;
  path: string;
  body: unknown;
  errorContext: "stream" | "resume";
  onError?: (error: unknown) => void;
}

export interface UseChatStreamOptions {
  effectiveBase: () => string;
  runtime: ChatStreamRuntimeSource;
  onSessionId: (context: ChatStreamContext, sessionId: string) => void;
  onStreamCompleted: (sessionId: string) => Promise<void>;
  onStreamSettled: () => void;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function captureSessionId(
  context: ChatStreamContext,
  event: SseEvent,
  onSessionId: UseChatStreamOptions["onSessionId"],
) {
  if (context.sessionId || !isRecord(event.data)) return;
  const payload = isRecord(event.data.payload) ? event.data.payload : undefined;
  const candidate = event.data.session_id ?? event.data.sessionId ?? payload?.session_id ?? payload?.sessionId;
  if (typeof candidate === "string" && candidate.trim()) {
    onSessionId(context, candidate);
  }
}

function applyIncomingMessages(
  runtime: ChatStreamRuntimeSource,
  runtimeKey: string,
  incomingMessages: ParsedMessage[],
) {
  if (incomingMessages.length === 0) return;
  runtime.updateRuntime(runtimeKey, (currentRuntime) => {
    let nextMessages = currentRuntime.messages;
    for (const incoming of incomingMessages) {
      nextMessages = mergeMessage(nextMessages, incoming);
    }
    return { ...currentRuntime, messages: nextMessages };
  });
}

function applyStreamEvent(
  context: ChatStreamContext,
  event: SseEvent,
  options: UseChatStreamOptions,
) {
  captureSessionId(context, event, options.onSessionId);
  const incoming = messageFromEvent(event);
  const eventId = Number.parseInt(event.id ?? "", 10);
  options.runtime.updateRuntime(context.runtimeKey, runtime => ({
    ...runtime,
    isInsertReady: event.event === "session" || runtime.isInsertReady,
    streamActivity: chatStreamActivityAfterEvent(runtime.streamActivity, event, incoming),
    nextEventCursor: Number.isInteger(eventId) && eventId >= 0
      ? Math.max(runtime.nextEventCursor, eventId + 1)
      : runtime.nextEventCursor,
  }));
  return incoming;
}

async function consumeChatResponse(
  context: ChatStreamContext,
  response: Response,
  options: UseChatStreamOptions,
) {
  if (options.runtime.getController(context.runtimeKey) !== context.controller) return;
  options.runtime.updateRuntime(context.runtimeKey, runtime => ({
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
    if (options.runtime.getController(context.runtimeKey) !== context.controller) return;
    buffer += decoder.decode(value, { stream: true });
    const parsed = parseSseBuffer(buffer);
    buffer = parsed.rest;
    const incomingMessages: ParsedMessage[] = [];
    for (const event of parsed.events) {
      const incoming = applyStreamEvent(context, event, options);
      if (incoming) incomingMessages.push(incoming);
    }
    applyIncomingMessages(options.runtime, context.runtimeKey, incomingMessages);
  }

  buffer += decoder.decode();
  if (!buffer || options.runtime.getController(context.runtimeKey) !== context.controller) return;
  const parsed = parseSseBuffer(buffer, { flush: true });
  const incomingMessages: ParsedMessage[] = [];
  for (const event of parsed.events) {
    const incoming = applyStreamEvent(context, event, options);
    if (incoming) incomingMessages.push(incoming);
  }
  applyIncomingMessages(options.runtime, context.runtimeKey, incomingMessages);
}

async function finalizeStream(
  context: ChatStreamContext,
  streamCompleted: boolean,
  options: UseChatStreamOptions,
) {
  if (options.runtime.getController(context.runtimeKey) !== context.controller) return;
  options.runtime.deleteController(context.runtimeKey, context.controller);
  options.runtime.updateRuntime(context.runtimeKey, runtime => ({
    ...runtime,
    isStreaming: false,
    isInsertReady: streamCompleted ? false : runtime.isInsertReady,
    isStopping: false,
    streamActivity: idleChatStreamActivity(),
    submittedInteractionKeys: new Set(),
    nextEventCursor: streamCompleted ? 0 : runtime.nextEventCursor,
  }));

  if (context.sessionId && streamCompleted) {
    await options.onStreamCompleted(context.sessionId);
  }
  options.onStreamSettled();
}

export function useChatStream(options: UseChatStreamOptions) {
  async function start(input: ChatStreamRequest) {
    const controller = new AbortController();
    const context: ChatStreamContext = {
      runtimeKey: input.runtimeKey,
      sessionId: input.sessionId,
      controller,
    };
    options.runtime.setController(input.runtimeKey, controller);
    let streamCompleted = false;

    try {
      const response = await request(`${normalizeBaseUrl(options.effectiveBase())}${input.path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify(input.body),
        signal: controller.signal,
      });
      await consumeChatResponse(context, response, options);
      if (options.runtime.getController(context.runtimeKey) === controller) streamCompleted = true;
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") return;
      if (options.runtime.getController(context.runtimeKey) === controller) {
        input.onError?.(error);
        options.runtime.updateRuntime(context.runtimeKey, runtime => ({
          ...runtime,
          transportError: friendlyTransportErrorBlock(error, input.errorContext),
          needsHistoryRefresh: true,
        }));
      }
    } finally {
      await finalizeStream(context, streamCompleted, options);
    }
  }

  return { start };
}
