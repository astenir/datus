import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import { ChatComposer } from "@/components/chat/chat-composer";
import { ConversationToolbar } from "@/components/chat/conversation-toolbar";
import { MessageList } from "@/components/chat/message-list";
import { Sidebar } from "@/components/layout/sidebar";
import { useChatAutoScroll } from "@/hooks/use-chat-auto-scroll";
import { useTheme } from "@/hooks/use-theme";
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable";
import { SettingsDrawer } from "@/components/settings/settings-drawer";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  chatSessionsPath,
  buildChatStreamRequest,
  databaseNameFromCatalog,
  extractResultData,
  messageFromEvent,
  messageFromPayload,
  mergeMessage,
  normalizeBaseUrl,
  parseSseBuffer,
  requestJson,
  schemaOptionsForDatabase,
  shouldResetConversationOnAgentChange,
  stringifyContent,
  uniqueOptions
} from "@/lib/chat";
import type { AgentOption, CatalogRecord, ChatMessage, ChatSessionOption, ConfigSummary, ConnectionState, SelectOption, SseMessagePayload } from "@/types";
import type { PanelImperativeHandle } from "react-resizable-panels";

const defaultApiBase = import.meta.env.VITE_DATUS_API_BASE ?? "";
export function App() {
  const [apiBase, setApiBase] = useState(defaultApiBase);
  const [connection, setConnection] = useState<ConnectionState>("idle");
  const [config, setConfig] = useState<ConfigSummary | null>(null);
  const [agents, setAgents] = useState<AgentOption[]>([]);
  const [sessionOptions, setSessionOptions] = useState<ChatSessionOption[]>([]);
  const [modelOptions, setModelOptions] = useState<SelectOption[]>([]);
  const [databaseOptions, setDatabaseOptions] = useState<SelectOption[]>([]);
  const [catalogEntries, setCatalogEntries] = useState<CatalogRecord[]>([]);
  const [isLoadingOptions, setIsLoadingOptions] = useState(false);
  const [isLoadingSessions, setIsLoadingSessions] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [model, setModel] = useState("");
  const [database, setDatabase] = useState("");
  const [schema, setSchema] = useState("");
  const [language, setLanguage] = useState("zh");
  const [permissionMode, setPermissionMode] = useState("normal");
  const [planMode, setPlanMode] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isDatabasePickerOpen, setIsDatabasePickerOpen] = useState(false);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const [expandedDatabases, setExpandedDatabases] = useState<Set<string>>(new Set());
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const { theme, toggleTheme } = useTheme();
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const sidebarPanelRef = useRef<PanelImperativeHandle | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const resolvedBase = useMemo(() => normalizeBaseUrl(apiBase), [apiBase]);

  useLayoutEffect(() => {
    sidebarPanelRef.current?.resize(sidebarCollapsed ? "64px" : "304px");
  }, [sidebarCollapsed]);

  useChatAutoScroll(scrollRef, [messages], isStreaming);

  const loadSessions = useCallback(async () => {
    setIsLoadingSessions(true);
    try {
      const payload = await requestJson<unknown>(resolvedBase, chatSessionsPath());
      const data = extractResultData<Record<string, unknown>>(payload);
      const sessions = (Array.isArray(data?.sessions) ? data.sessions : []) as ChatSessionOption[];
      setSessionOptions(sessions.filter((session) => session.session_id));
    } catch (err) {
      setSessionOptions([]);
      setError(err instanceof Error ? err.message : "会话列表加载失败");
    } finally {
      setIsLoadingSessions(false);
    }
  }, [resolvedBase]);

  const loadSessionHistory = useCallback(
    async (nextSessionId: string) => {
      setSessionId(nextSessionId);
      setError("");

      if (!nextSessionId) {
        setMessages([]);
        return;
      }

      try {
        const query = new URLSearchParams({ session_id: nextSessionId });
        const payload = await requestJson<unknown>(resolvedBase, `/api/v1/chat/history?${query.toString()}`);
        const data = extractResultData<Record<string, unknown>>(payload);
        const history = (Array.isArray(data?.messages) ? data.messages : []) as SseMessagePayload[];
        setMessages(
          history
            .map((item, index) => messageFromPayload(item, "createMessage", `history-${index}`))
            .filter((item): item is ChatMessage => Boolean(item))
        );
      } catch (err) {
        setMessages([]);
        setError(err instanceof Error ? err.message : "会话历史加载失败");
      }
    },
    [resolvedBase]
  );

  const checkConnection = useCallback(async () => {
    setConnection("checking");
    setError("");
    try {
      setIsLoadingOptions(true);
      const configPayloadRaw = await requestJson<unknown>(resolvedBase, "/api/v1/config/agent");
      const [configPayload, agentPayload, modelsPayload, databasePayload] = await Promise.all([
        Promise.resolve(configPayloadRaw),
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
      setModel((current) => current || (currentModel && modelList.some((option) => option.value === currentModel) ? currentModel : current));

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
      setCatalogEntries(rawDatabases);
      setDatabaseOptions(dbList);
      setConnection("online");
    } catch (err) {
      setConnection("offline");
      setError(err instanceof Error ? err.message : "无法连接后端服务");
    } finally {
      setIsLoadingOptions(false);
    }
  }, [resolvedBase]);

  useEffect(() => {
    void checkConnection();
  }, [checkConnection]);

  useEffect(() => {
    if (connection === "online") void loadSessions();
  }, [connection, loadSessions]);

  useEffect(() => {
    if (!database) return;
    setExpandedDatabases((current) => {
      if (current.has(database)) return current;
      const next = new Set(current);
      next.add(database);
      return next;
    });
  }, [database]);

  useEffect(() => {
    if (!database) return;

    let ignore = false;
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
      setCatalogEntries((current) => {
        const others = current.filter((entry) => databaseNameFromCatalog(entry) !== database);
        return [...others, ...scopedEntries];
      });
    };

    void loadSchemas();
    return () => {
      ignore = true;
    };
  }, [database, resolvedBase]);

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
        body: JSON.stringify(
          buildChatStreamRequest({
            message: text,
            sessionId,
            selectedAgent,
            model,
            database,
            schema,
            language,
            planMode,
            permissionMode
          })
        )
      });

      if (!response.ok || !response.body) {
        throw new Error(await response.text());
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      const applySseEvents = (events: ReturnType<typeof parseSseBuffer>["events"]) => {
        for (const sse of events) {
          const data = sse.data as { session_id?: string } | undefined;
          if (data?.session_id) setSessionId(data.session_id);

          const nextMessage = messageFromEvent(sse);
          if (nextMessage) {
            setMessages((current) => mergeMessage(current, nextMessage));
          }
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parsed = parseSseBuffer(buffer);
        buffer = parsed.rest;
        applySseEvents(parsed.events);
      }

      buffer += decoder.decode();
      const finalParsed = parseSseBuffer(buffer, { flush: true });
      applySseEvents(finalParsed.events);
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
      void loadSessions();
    }
  };

  const selectDatabaseSchema = (databaseName: string, schemaName: string, closePicker = true) => {
    setDatabase(databaseName);
    setSchema(schemaName);
    if (databaseName) {
      setExpandedDatabases((current) => {
        const next = new Set(current);
        next.add(databaseName);
        return next;
      });
    }
    if (closePicker) setIsDatabasePickerOpen(false);
  };

  const toggleDatabaseExpansion = (databaseName: string) => {
    setExpandedDatabases((current) => {
      const next = new Set(current);
      if (next.has(databaseName)) next.delete(databaseName);
      else next.add(databaseName);
      return next;
    });
    selectDatabaseSchema(databaseName, "", false);
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

  const selectedSession = sessionOptions.find((session) => session.session_id === sessionId);
  const selectedDatabaseLabel = database
    ? `${databaseOptions.find((option) => option.value === database)?.label ?? database}${schema ? ` / ${schema}` : " / 不指定 schema"}`
    : "不指定";
  const agentSelectOptions = [
    { value: "", label: "默认 chat" },
    ...agents.map((agent) => ({ value: agent.id, label: agent.name }))
  ];
  const modelSelectOptions = [
    { value: "", label: "默认模型" },
    ...(model && !modelOptions.some((option) => option.value === model) ? [{ value: model, label: model }] : []),
    ...modelOptions
  ];

  return (
    <main className={`shell ${isMobileSidebarOpen ? "mobileSidebarOpen" : ""}`}>
      <button
        className="mobileSidebarBackdrop"
        type="button"
        aria-label="关闭会话历史"
        onClick={() => setIsMobileSidebarOpen(false)}
      />
      <ResizablePanelGroup orientation="horizontal" className="shellPanels">
        <ResizablePanel
          id="sidebar"
          panelRef={sidebarPanelRef}
          defaultSize={sidebarCollapsed ? "64px" : "304px"}
          minSize={sidebarCollapsed ? "64px" : "220px"}
          maxSize={sidebarCollapsed ? "64px" : "420px"}
          groupResizeBehavior="preserve-pixel-size"
          className={`sidebarPanel ${sidebarCollapsed ? "collapsed" : ""}`}
        >
          <Sidebar
            connection={connection}
            connectionLabel={connectionLabel}
            sessions={sessionOptions}
            sessionId={sessionId}
            isLoadingSessions={isLoadingSessions}
            isStreaming={isStreaming}
            collapsed={sidebarCollapsed}
            theme={theme}
            onToggleCollapse={() => setSidebarCollapsed((prev) => !prev)}
            onToggleTheme={toggleTheme}
            onOpenSettings={() => setIsSettingsOpen(true)}
            onNewSession={() => {
              setIsMobileSidebarOpen(false);
              void loadSessionHistory("");
            }}
            onRefreshSessions={() => void loadSessions()}
            onSelectSession={(nextSessionId) => {
              setIsMobileSidebarOpen(false);
              void loadSessionHistory(nextSessionId);
            }}
          />
        </ResizablePanel>
        <ResizableHandle withHandle={!sidebarCollapsed} className="sidebarResizeHandle" />
        <ResizablePanel id="workspace" minSize="420px" className="workspacePanel">
          <section className="workspace">
            <ConversationToolbar
              connection={connection}
              isStreaming={isStreaming}
              selectedSession={selectedSession}
              sessionId={sessionId}
              onClearMessages={() => setMessages([])}
              onOpenMobileSessions={() => {
                setSidebarCollapsed(false);
                setIsMobileSidebarOpen(true);
              }}
              onRefreshConnection={checkConnection}
              onStopSession={() => void stopSession()}
            />

            {error && <Alert variant="destructive" className="errorBanner"><AlertDescription>{error}</AlertDescription></Alert>}

            <MessageList messages={messages} isStreaming={isStreaming} scrollRef={scrollRef} />

            <ChatComposer
              agentOptions={agentSelectOptions}
              catalogEntries={catalogEntries}
              database={database}
              databaseOptions={databaseOptions}
              expandedDatabases={expandedDatabases}
              isDatabasePickerOpen={isDatabasePickerOpen}
              isLoadingOptions={isLoadingOptions}
              isStreaming={isStreaming}
              message={message}
              model={model}
              modelOptions={modelSelectOptions}
              planMode={planMode}
              schema={schema}
              selectedAgent={selectedAgent}
              selectedDatabaseLabel={selectedDatabaseLabel}
              onDatabasePickerOpenChange={setIsDatabasePickerOpen}
              onMessageChange={setMessage}
              onModelChange={setModel}
              onPlanModeChange={setPlanMode}
              onSelectAgent={(nextAgent) => {
                setSelectedAgent(nextAgent);
                if (shouldResetConversationOnAgentChange()) {
                  setSessionId("");
                  setMessages([]);
                }
              }}
              onSelectDatabaseSchema={selectDatabaseSchema}
              onSubmit={() => void sendMessage()}
              onToggleDatabaseExpansion={toggleDatabaseExpansion}
            />
          </section>
        </ResizablePanel>
      </ResizablePanelGroup>

      {isSettingsOpen && (
        <SettingsDrawer
          apiBase={apiBase}
          connection={connection}
          connectionLabel={connectionLabel}
          config={config}
          language={language}
          permissionMode={permissionMode}
          planMode={planMode}
          onApiBaseChange={setApiBase}
          onCheckConnection={checkConnection}
          onLanguageChange={setLanguage}
          onPermissionModeChange={setPermissionMode}
          onPlanModeChange={setPlanMode}
          onClose={() => setIsSettingsOpen(false)}
        />
      )}
    </main>
  );
}
