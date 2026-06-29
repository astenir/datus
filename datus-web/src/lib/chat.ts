import type {
  CatalogRecord,
  ChatDisplayMessage,
  ChatMessage,
  MessageDisplayBlock,
  ChatSessionOption,
  MessageBlock,
  MessageOperation,
  ParsedMessage,
  SelectOption,
  SseEvent,
  SseMessagePayload
} from "@/types";
import { request } from "@/lib/request";

export type ChatStreamRequestInput = {
  message: string;
  sessionId: string;
  selectedAgent: string;
  model: string;
  datasource: string;
  database: string;
  schema: string;
  language: string;
  planMode: boolean;
  permissionMode: string;
};

export function buildChatStreamRequest({
  message,
  sessionId,
  selectedAgent,
  model,
  datasource,
  database,
  schema,
  language,
  planMode,
  permissionMode
}: ChatStreamRequestInput) {
  return {
    message,
    session_id: sessionId || null,
    subagent_id: selectedAgent || null,
    model: model || null,
    datasource: datasource || null,
    database: database || null,
    db_schema: schema || null,
    language: language || null,
    source: "web",
    stream_response: true,
    plan_mode: planMode,
    permission_mode: permissionMode || null
  };
}

export function buildUserInteractionInput(
  sessionId: string,
  interactionKey: string,
  answers: string | string[][],
) {
  const input = typeof answers === "string" ? [[answers]] : answers;
  return {
    session_id: sessionId,
    interaction_key: interactionKey,
    input,
  };
}

export function normalizeBaseUrl(value: string) {
  return value.trim().replace(/\/+$/, "");
}

export function chatSessionsPath() {
  return "/api/v1/chat/sessions";
}

export function isFeedbackSessionId(sessionId: string) {
  return sessionId.startsWith("feedback_session_");
}

export function filterVisibleChatSessions(sessions: ChatSessionOption[]) {
  return sessions.filter((session) => !isFeedbackSessionId(session.session_id));
}

function callToolIdFromPayload(payload: Record<string, unknown>) {
  return stringifyContent(payload.callToolId ?? payload.call_tool_id).trim() || undefined;
}

function parentActionIdFromPayload(payload: SseMessagePayload) {
  const parentActionId = payload.parent_action_id ?? payload.parentActionId;
  return typeof parentActionId === "string" && parentActionId.trim() ? parentActionId.trim() : undefined;
}

function childMessagesForParent(
  messages: readonly ChatMessage[],
  parentCallIds: ReadonlySet<string>,
) {
  const childGroups = new Map<string, ChatMessage[]>();

  for (const message of messages) {
    if (!message.parentActionId || !message.depth || !parentCallIds.has(message.parentActionId)) continue;

    const group = childGroups.get(message.parentActionId);
    if (group) {
      group.push(message);
    } else {
      childGroups.set(message.parentActionId, [message]);
    }
  }

  const displayGroups = new Map<string, ChatDisplayMessage[]>();
  for (const [parentActionId, childMessages] of childGroups) {
    displayGroups.set(parentActionId, mergeToolExecutionMessages(childMessages));
  }

  return displayGroups;
}

function mergeToolCallWithResult(
  block: Extract<MessageBlock, { type: "tool-call" }>,
  result?: Extract<MessageBlock, { type: "tool-result" }>,
  childMessages: readonly ChatDisplayMessage[] = [],
): MessageDisplayBlock {
  if (!result) {
    if (childMessages.length === 0) return block;
    return { ...block, childMessages };
  }

  const callToolId = block.callToolId;
  if (!callToolId) {
    if (childMessages.length === 0) return block;
    return { ...block, childMessages };
  }

  const mergedBlock: Extract<MessageDisplayBlock, { type: "tool-execution" }> = {
    type: "tool-execution",
    callToolId,
    toolName: block.toolName,
    params: block.params,
    result: result.result,
  };
  if (result.duration != null) mergedBlock.duration = result.duration;
  if (result.shortDesc) mergedBlock.shortDesc = result.shortDesc;
  if (result.errorText) mergedBlock.errorText = result.errorText;
  if (childMessages.length > 0) mergedBlock.childMessages = childMessages;
  return mergedBlock;
}

export function mergeToolExecutionBlocks(blocks: readonly MessageDisplayBlock[]): MessageDisplayBlock[] {
  const resultByCallId = new Map<string, Extract<MessageBlock, { type: "tool-result" }>>();
  for (const block of blocks) {
    if (block.type === "tool-result" && block.callToolId) {
      resultByCallId.set(block.callToolId, block);
    }
  }

  const consumedResultIds = new Set<string>();
  const merged: MessageDisplayBlock[] = [];

  for (const block of blocks) {
    if (block.type === "tool-call" && block.callToolId) {
      const blockWithCallId = { ...block, callToolId: block.callToolId };
      const result = resultByCallId.get(block.callToolId);
      if (result) {
        consumedResultIds.add(block.callToolId);
        merged.push(mergeToolCallWithResult(blockWithCallId, result, block.childMessages ?? []));
        continue;
      }
    }

    if (block.type === "tool-result" && block.callToolId && consumedResultIds.has(block.callToolId)) {
      continue;
    }

    merged.push(block);
  }

  return merged;
}

export function mergeToolExecutionMessages(messages: readonly ChatMessage[]): ChatDisplayMessage[] {
  const resultByCallId = new Map<string, { messageIndex: number; block: Extract<MessageBlock, { type: "tool-result" }> }>();
  const parentCallIds = new Set<string>();

  messages.forEach((message, messageIndex) => {
    for (const block of message.blocks ?? []) {
      if (block.type === "tool-call" && block.callToolId) {
        parentCallIds.add(block.callToolId);
      }
      if (block.type === "tool-result" && block.callToolId) {
        resultByCallId.set(block.callToolId, { messageIndex, block });
      }
    }
  });

  const childMessagesByParent = childMessagesForParent(messages, parentCallIds);
  const consumedResultKeys = new Set<string>();
  const mergedMessages: ChatDisplayMessage[] = [];

  messages.forEach((message, messageIndex) => {
    if (message.parentActionId && message.depth && parentCallIds.has(message.parentActionId)) {
      return;
    }

    if (!message.blocks?.length) {
      mergedMessages.push(message);
      return;
    }

    const blocks: MessageDisplayBlock[] = [];
    for (const block of message.blocks) {
      if (block.type === "tool-call" && block.callToolId) {
        const blockWithCallId = { ...block, callToolId: block.callToolId };
        const result = resultByCallId.get(block.callToolId);
        const childMessages = childMessagesByParent.get(block.callToolId) ?? [];
        if (result) {
          consumedResultKeys.add(`${result.messageIndex}:${block.callToolId}`);
          blocks.push(mergeToolCallWithResult(blockWithCallId, result.block, childMessages));
          continue;
        }
        if (childMessages.length > 0) {
          blocks.push(mergeToolCallWithResult(blockWithCallId, undefined, childMessages));
          continue;
        }
      }

      if (block.type === "tool-result" && block.callToolId && consumedResultKeys.has(`${messageIndex}:${block.callToolId}`)) {
        continue;
      }

      blocks.push(block);
    }

    if (blocks.length > 0) {
      mergedMessages.push({ ...message, blocks });
    }
  });

  return mergedMessages;
}

function isReviewableMessageBlock(block: MessageBlock) {
  if (block.type === "artifact") return true;
  if (block.type === "code") return true;
  if (block.type !== "markdown") return false;

  const content = block.content.trim();
  return content.length > 0 && !content.startsWith("**子 Agent 完成**");
}

export function isReviewableAssistantMessage(message: ChatMessage) {
  if (message.role !== "assistant") return false;
  if (message.depth && message.depth > 0) return false;

  const blocks = message.blocks?.length
    ? message.blocks
    : [{ type: "markdown" as const, content: message.content }];

  return blocks.some(isReviewableMessageBlock);
}

export function visibleMessageActionTargetId(
  messages: readonly ChatMessage[],
  options: { isStreaming?: boolean } = {},
) {
  const target = [...messages].reverse().find(isReviewableAssistantMessage);
  if (!target) return null;

  const latest = messages[messages.length - 1];
  if (options.isStreaming && latest?.id === target.id) return null;

  return target.id;
}

export function activeStreamingMessageId(messages: readonly ChatMessage[]) {
  return messages[messages.length - 1]?.id ?? null;
}

export function shouldRenderThinkingAsAnswer(message: Pick<ChatDisplayMessage, "role" | "depth" | "blocks">) {
  const blocks = message.blocks ?? [];
  return message.role === "assistant"
    && !message.depth
    && blocks.some((block) => block.type === "thinking")
    && !blocks.some((block) => block.type === "markdown");
}

export function shouldResetConversationOnAgentChange() {
  return false;
}

const DEFAULT_TIMEOUT_MS = 30_000;

export async function requestJson<T>(baseUrl: string, path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);

  try {
    const hasBody = init?.body != null;
    const response = await request(`${normalizeBaseUrl(baseUrl)}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        ...(hasBody ? { "Content-Type": "application/json" } : {}),
        ...init?.headers
      }
    });

    return response.json() as Promise<T>;
  } finally {
    clearTimeout(timeoutId);
  }
}

export class ApiResultError extends Error {
  constructor(
    message: string,
    readonly errorCode?: string,
  ) {
    super(message);
    this.name = "ApiResultError";
  }
}

export async function requestStream(baseUrl: string, path: string, body: unknown): Promise<ReadableStream<Uint8Array> | null> {
  const response = await request(`${normalizeBaseUrl(baseUrl)}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
  });
  return response.body;
}

export function extractResultData<T>(payload: unknown): T | null {
  if (payload && typeof payload === "object" && "success" in payload) {
    const result = payload as { success?: boolean; data?: T; errorCode?: string; errorMessage?: string };
    if (!result.success) {
      throw new ApiResultError(result.errorMessage || result.errorCode || "Backend request failed", result.errorCode);
    }
    return result.data ?? null;
  }
  return payload as T;
}

export function uniqueOptions(options: SelectOption[]) {
  const seen = new Set<string>();
  return options.filter((option) => {
    if (!option.value || seen.has(option.value)) return false;
    seen.add(option.value);
    return true;
  });
}

export function stringifyContent(value: unknown): string {
  if (typeof value === "string") return value;
  if (value == null) return "";
  return JSON.stringify(value, null, 2);
}

export function createClientId(prefix = "msg") {
  const cryptoApi = globalThis.crypto;
  if (typeof cryptoApi?.randomUUID === "function") {
    return cryptoApi.randomUUID();
  }

  if (typeof cryptoApi?.getRandomValues === "function") {
    const bytes = cryptoApi.getRandomValues(new Uint8Array(16));
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0"));
    return `${hex.slice(0, 4).join("")}-${hex.slice(4, 6).join("")}-${hex.slice(6, 8).join("")}-${hex.slice(8, 10).join("")}-${hex.slice(10).join("")}`;
  }

  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

export function databaseNameFromCatalog(item: CatalogRecord) {
  const name = stringifyContent(item.name);
  const schemaName = stringifyContent(item.schema_name);
  if (name && schemaName && name.endsWith(`.${schemaName}`)) {
    return name.slice(0, -schemaName.length - 1);
  }
  return name;
}

export function schemaNameFromCatalog(item: CatalogRecord) {
  return stringifyContent(item.schema_name);
}

export function schemaOptionsForDatabase(entries: readonly CatalogRecord[], databaseName: string) {
  return uniqueOptions(
    entries
      .filter((entry) => !databaseName || databaseNameFromCatalog(entry) === databaseName)
      .map((entry) => {
        const schemaName = schemaNameFromCatalog(entry);
        return { value: schemaName, label: schemaName };
      })
      .filter((option) => option.value)
  );
}

export function sessionTitle(session: ChatSessionOption) {
  const updatedAt = session.last_updated || session.created_at || "";
  return [session.session_id, sessionUserQueryText(session), updatedAt].filter(Boolean).join("\n");
}

export function sessionUserQueryText(session: ChatSessionOption): string {
  const text = stringifyContent(session.user_query).trim();
  if (text) return text.length > 60 ? `${text.slice(0, 60)}…` : text;
  if (session.total_turns && session.total_turns > 0) return `${session.total_turns} 轮对话`;
  return "";
}

export function formatSessionTime(value?: string) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(date);
}

export function contentFromPayloadBlocks(
  content: Array<{ type?: string; payload?: Record<string, unknown> }> | null | undefined = [],
  _operation: MessageOperation = "createMessage"
) {
  const items = Array.isArray(content) ? content : [];
  const blocks: MessageBlock[] = [];

  for (const item of items) {
    const payload = item && typeof item.payload === "object" && item.payload ? item.payload : {};
    const type = item?.type ?? "markdown";

    if (type === "markdown") {
      blocks.push({ type: "markdown", content: stringifyContent(payload.content) });
    } else if (type === "thinking") {
      blocks.push({ type: "thinking", content: stringifyContent(payload.content) });
    } else if (type === "code") {
      const language = stringifyContent(payload.codeType ?? payload.code_type ?? "text") || "text";
      blocks.push({ type: "code", language, content: stringifyContent(payload.content ?? payload.code) });
    } else if (type === "call-tool") {
      const callToolId = callToolIdFromPayload(payload);
      const toolName = stringifyContent(payload.toolName ?? payload.tool_name ?? "tool");
      const toolParams = payload.toolParams ?? payload.tool_params ?? {};
      blocks.push({ type: "tool-call", callToolId, toolName, params: toolParams });
    } else if (type === "call-tool-result") {
      const callToolId = callToolIdFromPayload(payload);
      const toolName = stringifyContent(payload.toolName ?? payload.tool_name ?? "tool");
      const duration = typeof payload.duration === "number" ? payload.duration : undefined;
      const shortDesc = stringifyContent(payload.shortDesc ?? payload.short_desc);
      const errorText = toolErrorText(payload);
      const block: Extract<MessageBlock, { type: "tool-result" }> = {
        type: "tool-result",
        toolName,
        result: unwrapToolResult(payload.result),
      };
      if (callToolId) block.callToolId = callToolId;
      if (duration != null) block.duration = duration;
      if (shortDesc) block.shortDesc = shortDesc;
      if (errorText) block.errorText = errorText;
      blocks.push(block);
    } else if (type === "error") {
      blocks.push({ type: "markdown", content: `**错误**\n\n${stringifyContent(payload.content)}` });
    } else if (type === "user-interaction") {
      const interactionKey = stringifyContent(payload.interactionKey ?? payload.interaction_key);
      const actionType = stringifyContent(payload.actionType ?? payload.action_type ?? "interaction");
      const legacyRequest =
        payload.content || payload.options
          ? [{ content: payload.content, options: payload.options }]
          : [];
      const rawRequests = Array.isArray(payload.requests) ? payload.requests : legacyRequest;
      const requests = rawRequests.map((request) => {
        const req = request as Record<string, unknown>;
        const rawOptions = Array.isArray(req.options) ? req.options : [];
        const options = rawOptions.map((option) => {
          const opt = option as Record<string, unknown>;
          return { key: stringifyContent(opt.key), title: stringifyContent(opt.title) };
        });
        const allowFreeText = req.allowFreeText ?? req.allow_free_text ?? false;
        const multiSelect = req.multiSelect ?? req.multi_select ?? false;
        return { content: stringifyContent(req.content), options, allowFreeText: !!allowFreeText, multiSelect: !!multiSelect };
      });
      blocks.push({ type: "user-interaction", interactionKey, actionType, requests });
    } else if (type === "subagent-complete") {
      const subagent = stringifyContent(payload.subagentType ?? payload.subagent_type ?? "subagent");
      const toolCount = payload.toolCount ?? payload.tool_count;
      const duration = typeof payload.duration === "number" ? payload.duration : undefined;
      const errorText = stringifyContent(payload.error);
      const block: Extract<MessageBlock, { type: "subagent-complete" }> = {
        type: "subagent-complete",
        subagent,
      };
      if (typeof toolCount === "number") block.toolCount = toolCount;
      if (duration != null) block.duration = duration;
      if (errorText) block.errorText = errorText;
      blocks.push(block);
    } else if (type === "artifact") {
      const kind = stringifyContent(payload.kind ?? "dashboard");
      const slug = stringifyContent(payload.slug ?? "");
      const name = stringifyContent(payload.name ?? payload.slug ?? "artifact");
      const description = stringifyContent(payload.preview_summary ?? payload.description ?? "");
      const mode = stringifyContent(payload.mode);
      const block: Extract<MessageBlock, { type: "artifact" }> = { type: "artifact", kind, slug, name };
      if (description) block.description = description;
      if (mode) block.mode = mode;
      blocks.push(block);
    } else {
      if (typeof payload.content === "string") blocks.push({ type: "markdown", content: payload.content });
      else if (typeof payload.code === "string") blocks.push({ type: "markdown", content: payload.code });
      else blocks.push({ type: "markdown", content: stringifyContent(payload) });
    }
  }

  const text = blocks
    .map((block) => {
      if (block.type === "markdown") return block.content;
      if (block.type === "thinking") return block.content;
      if (block.type === "code") return block.content;
      if (block.type === "tool-call") return `调用工具 ${block.toolName}`;
      if (block.type === "tool-result") return `工具结果 ${block.toolName}${block.shortDesc ? `\n${block.shortDesc}` : ""}`;
      if (block.type === "user-interaction") return `需要用户确认 (${block.actionType})`;
      if (block.type === "subagent-complete") return `子 Agent 完成 ${block.subagent}`;
      if (block.type === "artifact") return block.name;
      return "";
    })
    .filter(Boolean)
    .join("\n\n");

  return { text, blocks };
}

function unwrapToolResult(value: unknown): unknown {
  if (isRecord(value) && "result" in value) {
    return value.result;
  }
  return value;
}

function toolErrorText(payload: Record<string, unknown>): string | undefined {
  const directError = stringifyContent(payload.error).trim();
  if (directError) return directError;

  const result = payload.result;
  if (isRecord(result)) {
    const nestedError = stringifyContent(result.error).trim();
    if (nestedError) return nestedError;
  }

  return undefined;
}

export function parseSseBuffer(
  buffer: string,
  options: { flush?: boolean } = {}
): { events: SseEvent[]; rest: string } {
  const parts = buffer.split(/\r?\n\r?\n/);
  const rest = options.flush ? "" : (parts.pop() ?? "");
  if (options.flush && parts.length === 0 && buffer) parts.push(buffer);
  const events = parts
    .map((part) => {
      const event: SseEvent = {};
      const dataLines: string[] = [];

      for (const rawLine of part.split(/\r?\n/)) {
        const line = rawLine.trimEnd();
        if (!line || line.startsWith(":")) continue;
        const separator = line.indexOf(":");
        const field = separator >= 0 ? line.slice(0, separator) : line;
        const value = separator >= 0 ? line.slice(separator + 1).replace(/^ /, "") : "";

        if (field === "id") event.id = value;
        if (field === "event") event.event = value;
        if (field === "data") dataLines.push(value);
      }

      if (dataLines.length > 0) {
        const dataText = dataLines.join("\n");
        try {
          event.data = JSON.parse(dataText);
        } catch {
          event.data = dataText;
        }
      }

      return event;
    })
    .filter((event) => event.event || event.data);

  return { events, rest };
}

export function messageFromPayload(
  payload: SseMessagePayload,
  operation: MessageOperation = "createMessage",
  fallbackId: string = createClientId()
): ChatMessage | null {
  if (!payload.role) return null;

  const { text: content, blocks } = contentFromPayloadBlocks(payload.content, operation);
  if (!content) return null;

  return {
    id: String(payload.message_id ?? fallbackId),
    role: payload.role,
    content,
    blocks,
    depth: payload.depth,
    parentActionId: parentActionIdFromPayload(payload)
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

function isRole(value: unknown): value is NonNullable<SseMessagePayload["role"]> {
  return value === "user" || value === "assistant" || value === "system";
}

function normalizePayloadContent(value: unknown): SseMessagePayload["content"] {
  if (!Array.isArray(value)) return undefined;

  return value
    .map((item) => {
      if (!isRecord(item)) return null;
      const type = typeof item.type === "string" ? item.type : undefined;
      const payload = isRecord(item.payload) ? item.payload : undefined;
      const normalized: { type?: string; payload?: Record<string, unknown> } = {};
      if (type) normalized.type = type;
      if (payload) normalized.payload = payload;
      return normalized;
    })
    .filter((item): item is { type?: string; payload?: Record<string, unknown> } => item !== null);
}

function historyPayloadFromUnknown(value: unknown): SseMessagePayload | null {
  if (!isRecord(value) || !isRole(value.role)) return null;

  const messageId = value.message_id ?? value.messageId;
  const depth = typeof value.depth === "number" ? value.depth : undefined;
  const parentActionId = value.parent_action_id ?? value.parentActionId;

  return {
    message_id: typeof messageId === "string" || typeof messageId === "number" ? messageId : undefined,
    role: value.role,
    content: normalizePayloadContent(value.content),
    depth,
    parent_action_id: typeof parentActionId === "string" ? parentActionId : undefined
  };
}

export function normalizeHistoryMessages(items: readonly unknown[]) {
  let parsed: ChatMessage[] = [];

  for (const item of items) {
    const payload = historyPayloadFromUnknown(item);
    if (!payload) continue;

    const incoming = messageFromEvent({
      event: "message",
      data: { type: "createMessage", payload }
    });
    if (incoming) parsed = mergeMessage(parsed, incoming);
  }

  return parsed;
}

export function messageFromEvent(event: SseEvent): ParsedMessage | null {
  const data = event.data as
    | {
        type?: MessageOperation;
        payload?: SseMessagePayload;
        error?: string;
        error_type?: string;
        session_id?: string;
        total_tokens?: number;
        duration?: number;
      }
    | undefined;

  if (!data) return null;

  if (event.event === "error" || data.error) {
    return {
      operation: "createMessage",
      message: {
        id: `error-${event.id ?? Date.now()}`,
        role: "system",
        content: data.error ? `**${data.error_type ?? "Error"}**\n\n${data.error}` : stringifyContent(data)
      }
    };
  }

  if (event.event === "end") {
    const usage = typeof data.total_tokens === "number" ? ` · ${data.total_tokens} tokens` : "";
    const duration = typeof data.duration === "number" ? `${data.duration.toFixed(1)}s` : "完成";
    return {
      operation: "createMessage",
      message: {
        id: `end-${event.id ?? Date.now()}`,
        role: "system",
        content: `本轮完成：${duration}${usage}`
      }
    };
  }

  const payload = data.payload;
  const operation = data.type ?? "createMessage";
  if (!payload) return null;

  const message = messageFromPayload(payload, operation, event.id ?? createClientId());
  return message ? { operation, message } : null;
}

export function mergeMessage(messages: ChatMessage[], incoming: ParsedMessage) {
  const { message: incomingMessage, operation } = incoming;
  const index = messages.findIndex(
    (message) => message.id === incomingMessage.id && message.role === incomingMessage.role
  );
  if (index < 0) return [...messages, incomingMessage];

  const next = [...messages];
  const previous = next[index];
  const content =
    operation === "appendMessage"
      ? `${previous.content}${incomingMessage.content}`
      : incomingMessage.content ?? previous.content;

  next[index] = {
    ...previous,
    content,
    blocks: operation === "appendMessage" ? mergeBlocks(previous.blocks, incomingMessage.blocks) : incomingMessage.blocks ?? previous.blocks,
    depth: incomingMessage.depth ?? previous.depth,
    parentActionId: incomingMessage.parentActionId ?? previous.parentActionId
  };
  return next;
}

function mergeBlocks(previous: readonly MessageBlock[] = [], incoming: readonly MessageBlock[] = []) {
  if (incoming.length === 0) return previous;
  const next = [...previous];
  for (const block of incoming) {
    const last = next[next.length - 1];
    if (last?.type === "markdown" && block.type === "markdown") {
      next[next.length - 1] = { type: "markdown", content: `${last.content}${block.content}` };
    } else if (last?.type === "thinking" && block.type === "thinking") {
      next[next.length - 1] = { type: "thinking", content: `${last.content}${block.content}` };
    } else {
      next.push(block);
    }
  }
  return next;
}

// ─── SSE stream consumer ────────────────────────────────────────────────────

/**
 * Read an SSE stream from a Response body, parse events, and invoke a callback for each.
 * Returns the trailing buffer (for optional flush after the loop).
 */
export async function consumeSseStream(
  response: Response,
  onEvent: (event: SseEvent) => void,
): Promise<string> {
  const reader = response.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const { events, rest } = parseSseBuffer(buffer);
    buffer = rest;

    for (const event of events) {
      onEvent(event);
    }
  }

  return buffer;
}
