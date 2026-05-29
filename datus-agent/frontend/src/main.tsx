import React, { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Activity,
  ChevronDown,
  Bot,
  CheckCircle2,
  CircleStop,
  Database,
  Loader2,
  Play,
  RefreshCw,
  Send,
  Server,
  Settings2,
  Sparkles,
  TerminalSquare,
  Trash2,
  WifiOff
} from "lucide-react";
import "./styles.css";

type Role = "user" | "assistant" | "system";

type ChatMessage = {
  id: string;
  role: Role;
  content: string;
  blocks?: MessageBlock[];
  depth?: number;
};

type MessageOperation = "createMessage" | "appendMessage" | "updateMessage";

type MessageBlock =
  | { type: "markdown"; content: string }
  | { type: "tool-call"; toolName: string; params: unknown }
  | { type: "tool-result"; toolName: string; duration?: number; shortDesc?: string; result?: unknown };

type ParsedMessage = {
  message: ChatMessage;
  operation: MessageOperation;
};

type AgentOption = {
  id: string;
  name: string;
  type?: string;
};

type ConfigSummary = {
  target?: string;
  current_datasource?: string;
  home?: string;
};

type SelectOption = {
  value: string;
  label: string;
};

type ConnectionState = "idle" | "checking" | "online" | "offline";

type SseEvent = {
  id?: string;
  event?: string;
  data?: unknown;
};

type CatalogRecord = Record<string, unknown>;

const defaultApiBase = import.meta.env.VITE_DATUS_API_BASE ?? "";

function normalizeBaseUrl(value: string) {
  return value.trim().replace(/\/+$/, "");
}

async function requestJson<T>(baseUrl: string, path: string, init?: RequestInit): Promise<T> {
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

function extractResultData<T>(payload: unknown): T | null {
  if (payload && typeof payload === "object" && "success" in payload) {
    const result = payload as { success?: boolean; data?: T };
    return result.success ? (result.data ?? null) : null;
  }
  return payload as T;
}

function uniqueOptions(options: SelectOption[]) {
  const seen = new Set<string>();
  return options.filter((option) => {
    if (!option.value || seen.has(option.value)) return false;
    seen.add(option.value);
    return true;
  });
}

function databaseNameFromCatalog(item: CatalogRecord) {
  const name = stringifyContent(item.name);
  const schemaName = stringifyContent(item.schema_name);
  if (name && schemaName && name.endsWith(`.${schemaName}`)) {
    return name.slice(0, -schemaName.length - 1);
  }
  return name;
}

function schemaNameFromCatalog(item: CatalogRecord) {
  return stringifyContent(item.schema_name);
}

function schemaOptionsForDatabase(entries: CatalogRecord[], databaseName: string) {
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

function stringifyContent(value: unknown): string {
  if (typeof value === "string") return value;
  if (value == null) return "";
  return JSON.stringify(value, null, 2);
}

function blockquote(value: string) {
  return value
    .split("\n")
    .map((line) => `> ${line}`)
    .join("\n");
}

function contentFromPayloadBlocks(
  content: Array<{ type?: string; payload?: Record<string, unknown> }> = [],
  operation: MessageOperation = "createMessage"
) {
  const blocks: MessageBlock[] = [];

  for (const item of content) {
      const payload = item.payload ?? {};
      const type = item.type ?? "markdown";

      if (type === "markdown") blocks.push({ type: "markdown", content: stringifyContent(payload.content) });
      if (type === "thinking") {
        const text = stringifyContent(payload.content);
        blocks.push({ type: "markdown", content: operation === "appendMessage" ? text : `**Thinking**\n\n${blockquote(text)}` });
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

function parseSseBuffer(buffer: string): { events: SseEvent[]; rest: string } {
  const parts = buffer.split(/\r?\n\r?\n/);
  const rest = parts.pop() ?? "";
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

function messageFromEvent(event: SseEvent): ParsedMessage | null {
  const data = event.data as
    | {
        type?: MessageOperation;
        payload?: {
          message_id?: string | number;
          role?: Role;
          content?: Array<{ type?: string; payload?: Record<string, unknown> }>;
          depth?: number;
        };
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
  if (!payload || !payload.role) return null;

  const operation = data.type ?? "createMessage";
  const { text: content, blocks } = contentFromPayloadBlocks(payload.content, operation);
  if (!content) return null;

  return {
    operation,
    message: {
      id: String(payload.message_id ?? event.id ?? crypto.randomUUID()),
      role: payload.role,
      content,
      blocks,
      depth: payload.depth
    }
  };
}

function mergeMessage(messages: ChatMessage[], incoming: ParsedMessage) {
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

function MarkdownMessage({ content }: { content: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        a: ({ children, ...props }) => (
          <a {...props} target="_blank" rel="noreferrer">
            {children}
          </a>
        )
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

function MessageContent({ message }: { message: ChatMessage }) {
  const blocks = message.blocks?.length ? message.blocks : [{ type: "markdown" as const, content: message.content }];
  return (
    <div className="messageBlocks">
      {blocks.map((block, index) => {
        if (block.type === "tool-call") {
          return <ToolCard key={index} mode="call" toolName={block.toolName} value={block.params} />;
        }
        if (block.type === "tool-result") {
          return (
            <ToolCard
              key={index}
              mode="result"
              toolName={block.toolName}
              value={block.result}
              duration={block.duration}
              shortDesc={block.shortDesc}
            />
          );
        }
        return (
          <div className="markdownBody" key={index}>
            <MarkdownMessage content={block.content} />
          </div>
        );
      })}
    </div>
  );
}

function ToolCard({
  mode,
  toolName,
  value,
  duration,
  shortDesc
}: {
  mode: "call" | "result";
  toolName: string;
  value: unknown;
  duration?: number;
  shortDesc?: string;
}) {
  const hasValue = value !== undefined && value !== null && stringifyContent(value) !== "";
  return (
    <details className={`toolCard ${mode}`} open={mode === "call"}>
      <summary>
        <span className="toolChevron">
          <ChevronDown size={15} />
        </span>
        <span className="toolBadge">{mode === "call" ? "调用" : "结果"}</span>
        <span className="toolName">{toolName}</span>
        {duration !== undefined && <span className="toolMeta">{duration.toFixed(2)}s</span>}
      </summary>
      {shortDesc && <div className="toolSummary">{shortDesc}</div>}
      {hasValue && <pre className="toolPayload">{stringifyContent(value)}</pre>}
    </details>
  );
}

function App() {
  const [apiBase, setApiBase] = useState(defaultApiBase);
  const [connection, setConnection] = useState<ConnectionState>("idle");
  const [config, setConfig] = useState<ConfigSummary | null>(null);
  const [agents, setAgents] = useState<AgentOption[]>([]);
  const [modelOptions, setModelOptions] = useState<SelectOption[]>([]);
  const [databaseOptions, setDatabaseOptions] = useState<SelectOption[]>([]);
  const [schemaOptions, setSchemaOptions] = useState<SelectOption[]>([]);
  const [catalogEntries, setCatalogEntries] = useState<CatalogRecord[]>([]);
  const [isLoadingOptions, setIsLoadingOptions] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [model, setModel] = useState("");
  const [database, setDatabase] = useState("");
  const [schema, setSchema] = useState("");
  const [language, setLanguage] = useState("zh");
  const [permissionMode, setPermissionMode] = useState("normal");
  const [planMode, setPlanMode] = useState(false);
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const resolvedBase = useMemo(() => normalizeBaseUrl(apiBase), [apiBase]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, isStreaming]);

  const checkConnection = useCallback(async () => {
    setConnection("checking");
    setError("");
    try {
      await requestJson(resolvedBase, "/health", { headers: { Accept: "application/json" } });
      setIsLoadingOptions(true);
      const [configPayload, agentPayload, modelsPayload, databasePayload] = await Promise.all([
        requestJson<unknown>(resolvedBase, "/api/v1/config/agent").catch(() => null),
        requestJson<unknown>(resolvedBase, "/api/v1/agent/list").catch(() => null),
        requestJson<unknown>(resolvedBase, "/api/v1/models").catch(() => null),
        requestJson<unknown>(resolvedBase, "/api/v1/catalog/list").catch(() => null)
      ]);

      const configData = extractResultData<ConfigSummary>(configPayload);
      setConfig(configData);

      const agentData = extractResultData<Record<string, unknown>>(agentPayload);
      const rawAgents = Array.isArray(agentData?.agents) ? agentData.agents : [];
      setAgents(
        rawAgents
          .map((agent) => {
            const item = agent as Record<string, unknown>;
            return {
              id: String(item.id ?? item.agent_id ?? item.name ?? ""),
              name: String(item.name ?? item.id ?? item.agent_id ?? "未命名 Agent"),
              type: typeof item.type === "string" ? item.type : undefined
            };
          })
          .filter((agent) => agent.id)
      );

      const modelsData = extractResultData<Record<string, unknown>>(modelsPayload);
      const rawModels = Array.isArray(modelsData?.models) ? modelsData.models : [];
      const modelList = uniqueOptions(
        rawModels.map((entry) => {
          const item = entry as Record<string, unknown>;
          const provider = stringifyContent(item.provider);
          const id = stringifyContent(item.id ?? item.model);
          const value = provider && id ? `${provider}/${id}` : "";
          const name = stringifyContent(item.name);
          return {
            value,
            label: name && name !== id ? `${name} (${value})` : value
          };
        })
      );
      setModelOptions(modelList);
      const currentModel = stringifyContent(modelsData?.current_model);
      if (!model && currentModel && modelList.some((option) => option.value === currentModel)) {
        setModel(currentModel);
      }

      const dbData = extractResultData<Record<string, unknown>>(databasePayload);
      const rawDatabases = (Array.isArray(dbData?.databases) ? dbData.databases : []) as CatalogRecord[];
      const dbList = uniqueOptions(
        rawDatabases.map((entry) => {
          const name = databaseNameFromCatalog(entry);
          const catalogName = stringifyContent(entry.catalog_name);
          return {
            value: name,
            label: catalogName ? `${name} (${catalogName})` : name
          };
        })
      );
      const schemaList = schemaOptionsForDatabase(rawDatabases, database);
      setCatalogEntries(rawDatabases);
      setDatabaseOptions(dbList);
      setSchemaOptions(schemaList);
      if (schema && !schemaList.some((option) => option.value === schema)) setSchema("");
      setConnection("online");
    } catch (err) {
      setConnection("offline");
      setError(err instanceof Error ? err.message : "无法连接后端服务");
    } finally {
      setIsLoadingOptions(false);
    }
  }, [model, resolvedBase]);

  useEffect(() => {
    void checkConnection();
  }, [checkConnection]);

  useEffect(() => {
    setSchema("");

    if (!database) {
      setSchemaOptions(schemaOptionsForDatabase(catalogEntries, ""));
      return;
    }

    let ignore = false;
    const localSchemas = schemaOptionsForDatabase(catalogEntries, database);
    setSchemaOptions(localSchemas);

    const loadSchemas = async () => {
      const query = new URLSearchParams({ database_name: database });
      const payload = await requestJson<unknown>(resolvedBase, `/api/v1/catalog/list?${query.toString()}`).catch(
        () => null
      );
      if (ignore || !payload) return;
      const data = extractResultData<Record<string, unknown>>(payload);
      const rawDatabases = (Array.isArray(data?.databases) ? data.databases : []) as CatalogRecord[];
      const normalized = rawDatabases.filter((entry) => databaseNameFromCatalog(entry) === database);
      const scopedEntries = normalized.length > 0 ? normalized : rawDatabases;
      setSchemaOptions(schemaOptionsForDatabase(scopedEntries, database));
    };

    void loadSchemas();
    return () => {
      ignore = true;
    };
  }, [catalogEntries, database, resolvedBase]);

  const sendMessage = async () => {
    const text = message.trim();
    if (!text || isStreaming) return;

    const controller = new AbortController();
    abortRef.current = controller;
    setIsStreaming(true);
    setError("");
    setMessage("");
    setMessages((current) => [
      ...current,
      {
        id: `local-${Date.now()}`,
        role: "user",
        content: text
      }
    ]);

    try {
      const response = await fetch(`${resolvedBase}/api/v1/chat/stream`, {
        method: "POST",
        signal: controller.signal,
        headers: {
          Accept: "text/event-stream",
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          message: text,
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
        })
      });

      if (!response.ok || !response.body) {
        throw new Error(await response.text());
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parsed = parseSseBuffer(buffer);
        buffer = parsed.rest;

        for (const sse of parsed.events) {
          const data = sse.data as { session_id?: string } | undefined;
          if (data?.session_id) setSessionId(data.session_id);

          const nextMessage = messageFromEvent(sse);
          if (nextMessage) {
            setMessages((current) => mergeMessage(current, nextMessage));
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        const textError = err instanceof Error ? err.message : "请求失败";
        setError(textError);
        setMessages((current) => [
          ...current,
          {
            id: `request-error-${Date.now()}`,
            role: "system",
            content: textError
          }
        ]);
      }
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
    }
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    void sendMessage();
  };

  const stopSession = async () => {
    abortRef.current?.abort();
    if (!sessionId) {
      setIsStreaming(false);
      return;
    }
    await requestJson(resolvedBase, "/api/v1/chat/stop", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId })
    }).catch((err) => setError(err instanceof Error ? err.message : "停止会话失败"));
    setIsStreaming(false);
  };

  const connectionLabel = {
    idle: "未检测",
    checking: "检测中",
    online: "已连接",
    offline: "未连接"
  }[connection];

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brandMark">
            <Sparkles size={22} />
          </div>
          <div>
            <h1>Datus Agent</h1>
            <p>前端控制台</p>
          </div>
        </div>

        <section className="panel">
          <div className="panelTitle">
            <Server size={16} />
            <span>服务连接</span>
          </div>
          <label>
            API 地址
            <input value={apiBase} onChange={(event) => setApiBase(event.target.value)} placeholder="同源代理或 http://localhost:8000" />
          </label>
          <button className="secondaryButton" onClick={checkConnection} type="button">
            {connection === "checking" ? <Loader2 className="spin" size={16} /> : <RefreshCw size={16} />}
            {connectionLabel}
          </button>
          {error && <p className="errorText">{error}</p>}
        </section>

        <section className="panel">
          <div className="panelTitle">
            <Settings2 size={16} />
            <span>运行参数</span>
          </div>
          <label>
            子 Agent
            <select value={selectedAgent} onChange={(event) => setSelectedAgent(event.target.value)}>
              <option value="">默认 chat</option>
              {agents.map((agent) => (
                <option key={agent.id} value={agent.id}>
                  {agent.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            会话 ID
            <input value={sessionId} onChange={(event) => setSessionId(event.target.value)} placeholder="自动生成或粘贴已有会话" />
          </label>
          <label>
            模型覆盖
            <select value={model} onChange={(event) => setModel(event.target.value)} disabled={isLoadingOptions}>
              <option value="">使用默认模型</option>
              {model && !modelOptions.some((option) => option.value === model) && <option value={model}>{model}</option>}
              {modelOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <div className="twoCols">
            <label>
              数据库
              <select
                value={database}
                onChange={(event) => {
                  setDatabase(event.target.value);
                  setSchema("");
                }}
                disabled={isLoadingOptions}
              >
                <option value="">不指定</option>
                {database && !databaseOptions.some((option) => option.value === database) && <option value={database}>{database}</option>}
                {databaseOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Schema
              <select value={schema} onChange={(event) => setSchema(event.target.value)} disabled={isLoadingOptions}>
                <option value="">不指定</option>
                {schema && !schemaOptions.some((option) => option.value === schema) && <option value={schema}>{schema}</option>}
                {schemaOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="twoCols">
            <label>
              语言
              <select value={language} onChange={(event) => setLanguage(event.target.value)}>
                <option value="zh">中文</option>
                <option value="en">English</option>
              </select>
            </label>
            <label>
              权限
              <select value={permissionMode} onChange={(event) => setPermissionMode(event.target.value)}>
                <option value="normal">normal</option>
                <option value="auto">auto</option>
                <option value="dangerous">dangerous</option>
              </select>
            </label>
          </div>
          <label className="checkRow">
            <input type="checkbox" checked={planMode} onChange={(event) => setPlanMode(event.target.checked)} />
            Plan mode
          </label>
        </section>

        <section className="panel summaryPanel">
          <div className="panelTitle">
            <Database size={16} />
            <span>当前配置</span>
          </div>
          <dl>
            <dt>模型</dt>
            <dd>{config?.target || "-"}</dd>
            <dt>数据源</dt>
            <dd>{config?.current_datasource || "-"}</dd>
            <dt>Home</dt>
            <dd title={config?.home}>{config?.home || "-"}</dd>
          </dl>
        </section>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">
              {connection === "online" ? <CheckCircle2 size={14} /> : <WifiOff size={14} />}
              {connectionLabel}
            </p>
            <h2>Agent 对话</h2>
          </div>
          <div className="toolbar">
            <button className="iconButton" type="button" title="清空消息" onClick={() => setMessages([])}>
              <Trash2 size={17} />
            </button>
            <button className="stopButton" type="button" onClick={stopSession} disabled={!isStreaming && !sessionId}>
              <CircleStop size={16} />
              停止
            </button>
          </div>
        </header>

        <div className="messages" ref={scrollRef}>
          {messages.length === 0 ? (
            <div className="emptyState">
              <TerminalSquare size={34} />
              <h3>输入问题开始接入测试</h3>
              <p>页面会通过 SSE 读取 `/api/v1/chat/stream` 的实时响应。</p>
            </div>
          ) : (
            messages.map((item) => (
              <article key={`${item.role}-${item.id}`} className={`message ${item.role}`} style={{ marginLeft: item.depth ? item.depth * 18 : 0 }}>
                <div className="avatar">{item.role === "assistant" ? <Bot size={17} /> : item.role === "user" ? <Send size={16} /> : <Activity size={16} />}</div>
                <div className="bubble">
                  <MessageContent message={item} />
                </div>
              </article>
            ))
          )}
          {isStreaming && (
            <div className="streaming">
              <Loader2 className="spin" size={16} />
              正在生成响应
            </div>
          )}
        </div>

        <form className="composer" onSubmit={submit}>
          <textarea
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder="输入要交给 Datus Agent 处理的问题..."
            rows={3}
            onKeyDown={(event) => {
              if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
                event.preventDefault();
                void sendMessage();
              }
            }}
          />
          <button className="primaryButton" type="submit" disabled={!message.trim() || isStreaming}>
            {isStreaming ? <Loader2 className="spin" size={17} /> : <Play size={17} />}
            发送
          </button>
        </form>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
