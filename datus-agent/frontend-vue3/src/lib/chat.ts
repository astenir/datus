import type {
  CatalogRecord,
  ChatMessage,
  ChatSessionOption,
  MessageBlock,
  MessageOperation,
  ParsedMessage,
  SelectOption,
  SseEvent,
  SseMessagePayload
} from "@/types";

export type ChatStreamRequestInput = {
  message: string;
  sessionId: string;
  selectedAgent: string;
  model: string;
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
    database: database || null,
    db_schema: schema || null,
    language: language || null,
    source: "web",
    stream_response: true,
    plan_mode: planMode,
    permission_mode: permissionMode || null
  };
}

export function normalizeBaseUrl(value: string) {
  return value.trim().replace(/\/+$/, "");
}

export function chatSessionsPath() {
  return "/api/v1/chat/sessions";
}

export function shouldResetConversationOnAgentChange() {
  return false;
}

export async function requestJson<T>(baseUrl: string, path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${normalizeBaseUrl(baseUrl)}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers
    }
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `${response.status} ${response.statusText}`);
  }

  return response.json() as Promise<T>;
}

export function extractResultData<T>(payload: unknown): T | null {
  if (payload && typeof payload === "object" && "success" in payload) {
    const result = payload as { success?: boolean; data?: T };
    return result.success ? (result.data ?? null) : null;
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

export function schemaOptionsForDatabase(entries: CatalogRecord[], databaseName: string) {
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

export function sessionUserQueryText(session: ChatSessionOption) {
  return stringifyContent(session.user_query).trim();
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

function blockquote(value: string) {
  return value
    .split("\n")
    .map((line) => `> ${line}`)
    .join("\n");
}

export function contentFromPayloadBlocks(
  content: Array<{ type?: string; payload?: Record<string, unknown> }> | null | undefined = [],
  operation: MessageOperation = "createMessage"
) {
  const items = Array.isArray(content) ? content : [];
  const hasNonThinking = items.some((item) => (item?.type ?? "markdown") !== "thinking");
  const blocks: MessageBlock[] = [];

  for (const item of items) {
    const payload = item && typeof item.payload === "object" && item.payload ? item.payload : {};
    const type = item?.type ?? "markdown";

    if (type === "markdown") blocks.push({ type: "markdown", content: stringifyContent(payload.content) });
    if (type === "thinking") {
      const text = stringifyContent(payload.content);
      // Only wrap in "Thinking" blockquote when mixed with non-thinking blocks
      if (hasNonThinking && operation !== "appendMessage") {
        blocks.push({ type: "markdown", content: `**Thinking**\n\n${blockquote(text)}` });
      } else {
        blocks.push({ type: "markdown", content: text });
      }
    }
    if (type === "code") {
      const language = stringifyContent(payload.codeType ?? payload.code_type ?? "text") || "text";
      blocks.push({ type: "markdown", content: `\`\`\`${language}\n${stringifyContent(payload.content ?? payload.code)}\n\`\`\`` });
    }
    if (type === "call-tool") {
      const toolName = stringifyContent(payload.toolName ?? payload.tool_name ?? "tool");
      const toolParams = payload.toolParams ?? payload.tool_params ?? {};
      blocks.push({ type: "tool-call", toolName, params: toolParams });
    }
    if (type === "call-tool-result") {
      const toolName = stringifyContent(payload.toolName ?? payload.tool_name ?? "tool");
      const duration = typeof payload.duration === "number" ? payload.duration : undefined;
      const shortDesc = stringifyContent(payload.shortDesc ?? payload.short_desc);
      blocks.push({ type: "tool-result", toolName, duration, shortDesc, result: payload.result });
    }
    if (type === "error") blocks.push({ type: "markdown", content: `**错误**\n\n${stringifyContent(payload.content)}` });
    if (type === "user-interaction") {
      const requests = Array.isArray(payload.requests) ? payload.requests : [];
      const title = `**需要用户确认** \`${stringifyContent(payload.actionType ?? payload.action_type ?? "interaction")}\``;
      const body = requests
        .map((request, index) => {
          const item = request as Record<string, unknown>;
          const options = Array.isArray(item.options)
            ? item.options
                .map((option) => {
                  const optionItem = option as Record<string, unknown>;
                  return `- \`${stringifyContent(optionItem.key)}\` ${stringifyContent(optionItem.title)}`;
                })
                .join("\n")
            : "";
          return `${index + 1}. ${stringifyContent(item.content)}${options ? `\n${options}` : ""}`;
        })
        .join("\n\n");
      blocks.push({ type: "markdown", content: `${title}\n\n${body}` });
    }
    if (type === "subagent-complete") {
      const subagent = stringifyContent(payload.subagentType ?? payload.subagent_type ?? "subagent");
      const toolCount = payload.toolCount ?? payload.tool_count;
      const duration = typeof payload.duration === "number" ? ` · ${payload.duration.toFixed(2)}s` : "";
      blocks.push({ type: "markdown", content: `**子 Agent 完成** \`${subagent}\`${toolCount == null ? "" : ` · ${toolCount} tools`}${duration}` });
    }
    if (item.type === "artifact") {
      const title = stringifyContent(payload.name ?? payload.slug ?? "artifact");
      const summary = stringifyContent(payload.preview_summary ?? payload.description);
      blocks.push({ type: "markdown", content: `**Artifact** ${title}${summary ? `\n\n${summary}` : ""}` });
    }
    if (!["markdown", "thinking", "code", "call-tool", "call-tool-result", "error", "user-interaction", "subagent-complete", "artifact"].includes(type)) {
      if (typeof payload.content === "string") blocks.push({ type: "markdown", content: payload.content });
      else if (typeof payload.code === "string") blocks.push({ type: "markdown", content: payload.code });
      else blocks.push({ type: "markdown", content: stringifyContent(payload) });
    }
  }

  const text = blocks
    .map((block) => {
      if (block.type === "markdown") return block.content;
      if (block.type === "tool-call") return `调用工具 ${block.toolName}`;
      return `工具结果 ${block.toolName}${block.shortDesc ? `\n${block.shortDesc}` : ""}`;
    })
    .filter(Boolean)
    .join("\n\n");

  return { text, blocks };
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
  fallbackId: string = crypto.randomUUID()
): ChatMessage | null {
  if (!payload.role) return null;

  const { text: content, blocks } = contentFromPayloadBlocks(payload.content, operation);
  if (!content) return null;

  return {
    id: String(payload.message_id ?? fallbackId),
    role: payload.role,
    content,
    blocks,
    depth: payload.depth
  };
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

  const message = messageFromPayload(payload, operation, event.id ?? crypto.randomUUID());
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
      : incomingMessage.content || previous.content;

  next[index] = {
    ...previous,
    content,
    blocks: operation === "appendMessage" ? mergeBlocks(previous.blocks, incomingMessage.blocks) : incomingMessage.blocks ?? previous.blocks,
    depth: incomingMessage.depth ?? previous.depth
  };
  return next;
}

function mergeBlocks(previous: MessageBlock[] = [], incoming: MessageBlock[] = []) {
  if (incoming.length === 0) return previous;
  const next = [...previous];
  for (const block of incoming) {
    const last = next[next.length - 1];
    if (last?.type === "markdown" && block.type === "markdown") {
      next[next.length - 1] = { type: "markdown", content: `${last.content}${block.content}` };
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
