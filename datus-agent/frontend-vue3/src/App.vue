<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted } from "vue";

import ChatComposer from "@/components/chat/ChatComposer.vue";
import ConversationToolbar from "@/components/chat/ConversationToolbar.vue";
import MessageList from "@/components/chat/MessageList.vue";
import Sidebar from "@/components/layout/Sidebar.vue";
import SettingsDrawer from "@/components/settings/SettingsDrawer.vue";
import TooltipProvider from "@/components/ui/TooltipProvider.vue";
import { useChatAutoScroll } from "@/composables/useChatAutoScroll";
import { useTheme } from "@/composables/useTheme";
import Alert from "@/components/ui/Alert.vue";
import AlertDescription from "@/components/ui/AlertDescription.vue";
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

import { Splitpanes, Pane } from "splitpanes";
import "splitpanes/dist/splitpanes.css";

const defaultApiBase = import.meta.env.VITE_DATUS_API_BASE ?? "";

// State
const apiBase = ref(defaultApiBase);
const connection = ref<ConnectionState>("idle");
const config = ref<ConfigSummary | null>(null);
const agents = ref<AgentOption[]>([]);
const sessionOptions = ref<ChatSessionOption[]>([]);
const modelOptions = ref<SelectOption[]>([]);
const databaseOptions = ref<SelectOption[]>([]);
const catalogEntries = ref<CatalogRecord[]>([]);
const isLoadingOptions = ref(false);
const isLoadingSessions = ref(false);
const selectedAgent = ref("");
const sessionId = ref("");
const model = ref("");
const database = ref("");
const schema = ref("");
const language = ref("zh");
const permissionMode = ref("normal");
const planMode = ref(false);
const isSettingsOpen = ref(false);
const isDatabasePickerOpen = ref(false);
const isMobileSidebarOpen = ref(false);
const expandedDatabases = ref<Set<string>>(new Set());
const sidebarCollapsed = ref(false);
const message = ref("");
const messages = ref<ChatMessage[]>([]);
const isStreaming = ref(false);
const error = ref("");
let abortController: AbortController | null = null;
const scrollRef = ref<HTMLDivElement | null>(null);

const { theme, toggleTheme } = useTheme();

// Computed
const resolvedBase = computed(() => normalizeBaseUrl(apiBase.value));

const connectionLabel = computed(() => ({
  idle: "未检测",
  checking: "检测中",
  online: "已连接",
  offline: "未连接"
}[connection.value]));

const selectedSession = computed(() =>
  sessionOptions.value.find((s) => s.session_id === sessionId.value)
);

const selectedDatabaseLabel = computed(() => {
  if (!database.value) return "不指定";
  const label = databaseOptions.value.find((o) => o.value === database.value)?.label ?? database.value;
  return schema.value ? `${label} / ${schema.value}` : `${label} / 不指定 schema`;
});

const agentSelectOptions = computed(() => [
  { value: "", label: "默认 chat" },
  ...agents.value.map((a) => ({ value: a.id, label: a.name }))
]);

const modelSelectOptions = computed(() => [
  { value: "", label: "默认模型" },
  ...(model.value && !modelOptions.value.some((o) => o.value === model.value) ? [{ value: model.value, label: model.value }] : []),
  ...modelOptions.value
]);

// Auto-scroll
useChatAutoScroll(scrollRef, messages, isStreaming);

// Sidebar resize
watch(sidebarCollapsed, async () => {
  await nextTick();
  // Splitpanes handles resize via its own API
});

// Methods
const loadSessions = async () => {
  isLoadingSessions.value = true;
  try {
    const payload = await requestJson<unknown>(resolvedBase.value, chatSessionsPath());
    const data = extractResultData<Record<string, unknown>>(payload);
    const sessions = (Array.isArray(data?.sessions) ? data.sessions : []) as ChatSessionOption[];
    sessionOptions.value = sessions.filter((s) => s.session_id);
  } catch (err) {
    sessionOptions.value = [];
    error.value = err instanceof Error ? err.message : "会话列表加载失败";
  } finally {
    isLoadingSessions.value = false;
  }
};

const loadSessionHistory = async (nextSessionId: string) => {
  sessionId.value = nextSessionId;
  error.value = "";

  if (!nextSessionId) {
    messages.value = [];
    return;
  }

  try {
    const query = new URLSearchParams({ session_id: nextSessionId });
    const payload = await requestJson<unknown>(resolvedBase.value, `/api/v1/chat/history?${query.toString()}`);
    const data = extractResultData<Record<string, unknown>>(payload);
    const history = (Array.isArray(data?.messages) ? data.messages : []) as SseMessagePayload[];
    messages.value = history
      .map((item, index) => messageFromPayload(item, "createMessage", `history-${index}`))
      .filter((item): item is ChatMessage => Boolean(item));
  } catch (err) {
    messages.value = [];
    error.value = err instanceof Error ? err.message : "会话历史加载失败";
  }
};

const checkConnection = async () => {
  connection.value = "checking";
  error.value = "";
  try {
    isLoadingOptions.value = true;
    const configPayloadRaw = await requestJson<unknown>(resolvedBase.value, "/api/v1/config/agent");
    const [configPayload, agentPayload, modelsPayload, databasePayload] = await Promise.all([
      Promise.resolve(configPayloadRaw),
      requestJson<unknown>(resolvedBase.value, "/api/v1/agent/list").catch(() => null),
      requestJson<unknown>(resolvedBase.value, "/api/v1/models").catch(() => null),
      requestJson<unknown>(resolvedBase.value, "/api/v1/catalog/list").catch(() => null)
    ]);

    const configData = extractResultData<ConfigSummary>(configPayload);
    config.value = configData;

    const agentData = extractResultData<Record<string, unknown>>(agentPayload);
    const rawAgents = Array.isArray(agentData?.agents) ? agentData.agents : [];
    agents.value = rawAgents
      .map((agent) => {
        const item = agent as Record<string, unknown>;
        return {
          id: String(item.id ?? item.agent_id ?? item.name ?? ""),
          name: String(item.name ?? item.id ?? item.agent_id ?? "未命名 Agent"),
          type: typeof item.type === "string" ? item.type : undefined
        };
      })
      .filter((a) => a.id);

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
    modelOptions.value = modelList;
    const currentModel = stringifyContent(modelsData?.current_model);
    if (!model.value && currentModel && modelList.some((o) => o.value === currentModel)) {
      model.value = currentModel;
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
    catalogEntries.value = rawDatabases;
    databaseOptions.value = dbList;
    connection.value = "online";
  } catch (err) {
    connection.value = "offline";
    error.value = err instanceof Error ? err.message : "无法连接后端服务";
  } finally {
    isLoadingOptions.value = false;
  }
};

// Auto-load on mount
onMounted(() => {
  void checkConnection();
});

// Load sessions when connected
watch(connection, (state) => {
  if (state === "online") void loadSessions();
});

// Auto-expand database when selected
watch(database, (db) => {
  if (!db) return;
  if (!expandedDatabases.value.has(db)) {
    expandedDatabases.value = new Set([...expandedDatabases.value, db]);
  }
});

// Load schemas when database changes
watch(database, async (db) => {
  if (!db) return;
  const query = new URLSearchParams({ database_name: db });
  const payload = await requestJson<unknown>(resolvedBase.value, `/api/v1/catalog/list?${query.toString()}`).catch(() => null);
  if (!payload) return;
  const data = extractResultData<Record<string, unknown>>(payload);
  const rawDatabases = (Array.isArray(data?.databases) ? data.databases : []) as CatalogRecord[];
  const normalized = rawDatabases.filter((entry) => databaseNameFromCatalog(entry) === db);
  const scopedEntries = normalized.length > 0 ? normalized : rawDatabases;
  const others = catalogEntries.value.filter((entry) => databaseNameFromCatalog(entry) !== db);
  catalogEntries.value = [...others, ...scopedEntries];
});

const sendMessage = async () => {
  const text = message.value.trim();
  if (!text || isStreaming.value) return;

  const controller = new AbortController();
  abortController = controller;
  isStreaming.value = true;
  error.value = "";
  message.value = "";
  messages.value = [
    ...messages.value,
    {
      id: `local-${Date.now()}`,
      role: "user",
      content: text
    }
  ];

  try {
    const response = await fetch(`${resolvedBase.value}/api/v1/chat/stream`, {
      method: "POST",
      signal: controller.signal,
      headers: {
        Accept: "text/event-stream",
        "Content-Type": "application/json"
      },
      body: JSON.stringify(
        buildChatStreamRequest({
          message: text,
          sessionId: sessionId.value,
          selectedAgent: selectedAgent.value,
          model: model.value,
          database: database.value,
          schema: schema.value,
          language: language.value,
          planMode: planMode.value,
          permissionMode: permissionMode.value
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
        if (data?.session_id) sessionId.value = data.session_id;

        const nextMessage = messageFromEvent(sse);
        if (nextMessage) {
          messages.value = mergeMessage(messages.value, nextMessage);
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
      error.value = textError;
      messages.value = [
        ...messages.value,
        {
          id: `request-error-${Date.now()}`,
          role: "system",
          content: textError
        }
      ];
    }
  } finally {
    isStreaming.value = false;
    abortController = null;
    void loadSessions();
  }
};

const selectDatabaseSchema = (databaseName: string, schemaName: string, closePicker = true) => {
  database.value = databaseName;
  schema.value = schemaName;
  if (databaseName) {
    expandedDatabases.value = new Set([...expandedDatabases.value, databaseName]);
  }
  if (closePicker) isDatabasePickerOpen.value = false;
};

const toggleDatabaseExpansion = (databaseName: string) => {
  const next = new Set(expandedDatabases.value);
  if (next.has(databaseName)) next.delete(databaseName);
  else next.add(databaseName);
  expandedDatabases.value = next;
  selectDatabaseSchema(databaseName, "", false);
};

const stopSession = async () => {
  abortController?.abort();
  if (!sessionId.value) {
    isStreaming.value = false;
    return;
  }
  await requestJson(resolvedBase.value, "/api/v1/chat/stop", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId.value })
  }).catch((err) => {
    error.value = err instanceof Error ? err.message : "停止会话失败";
  });
  isStreaming.value = false;
};

const onPaneResized = (payload: { panes: Array<{ size: number }> }) => {
  // panes[0] is the sidebar pane
  if (payload.panes.length > 0) {
    const sidebarSize = payload.panes[0].size;
    sidebarCollapsed.value = sidebarSize < 10;
  }
};
</script>

<template>
  <TooltipProvider>
  <main class="shell" :class="{ mobileSidebarOpen: isMobileSidebarOpen }">
    <button
      class="mobileSidebarBackdrop"
      type="button"
      aria-label="关闭会话历史"
      @click="isMobileSidebarOpen = false"
    />
    <Splitpanes class="shellPanels" style="flex: 1" @resized="onPaneResized">
      <Pane
        id="sidebar"
        :size="sidebarCollapsed ? 5 : 25"
        :min-size="sidebarCollapsed ? 5 : 18"
        :max-size="sidebarCollapsed ? 5 : 35"
        class="sidebarPanel"
        :class="{ collapsed: sidebarCollapsed }"
      >
        <Sidebar
          :connection="connection"
          :connection-label="connectionLabel"
          :sessions="sessionOptions"
          :session-id="sessionId"
          :is-loading-sessions="isLoadingSessions"
          :is-streaming="isStreaming"
          :collapsed="sidebarCollapsed"
          :theme="theme"
          @toggle-collapse="sidebarCollapsed = !sidebarCollapsed"
          @toggle-theme="toggleTheme"
          @open-settings="isSettingsOpen = true"
          @new-session="isMobileSidebarOpen = false; loadSessionHistory('')"
          @refresh-sessions="loadSessions()"
          @select-session="(id) => { isMobileSidebarOpen = false; loadSessionHistory(id) }"
        />
      </Pane>
      <Pane min-size="35" class="workspacePanel">
        <section class="workspace">
          <ConversationToolbar
            :connection="connection"
            :is-streaming="isStreaming"
            :selected-session="selectedSession ?? undefined"
            :session-id="sessionId"
            @clear-messages="messages = []"
            @open-mobile-sessions="sidebarCollapsed = false; isMobileSidebarOpen = true"
            @refresh-connection="checkConnection()"
            @stop-session="stopSession()"
          />

          <Alert v-if="error" variant="destructive" class="errorBanner">
            <AlertDescription>{{ error }}</AlertDescription>
          </Alert>

          <MessageList :messages="messages" :is-streaming="isStreaming" :scroll-ref="scrollRef" />

          <ChatComposer
            :agent-options="agentSelectOptions"
            :catalog-entries="catalogEntries"
            :database="database"
            :database-options="databaseOptions"
            :expanded-databases="expandedDatabases"
            :is-database-picker-open="isDatabasePickerOpen"
            :is-loading-options="isLoadingOptions"
            :is-streaming="isStreaming"
            :message="message"
            :model="model"
            :model-options="modelSelectOptions"
            :plan-mode="planMode"
            :schema="schema"
            :selected-agent="selectedAgent"
            :selected-database-label="selectedDatabaseLabel"
            @database-picker-open-change="isDatabasePickerOpen = $event"
            @message-change="message = $event"
            @model-change="model = $event"
            @plan-mode-change="planMode = $event"
            @select-agent="(v) => { selectedAgent = v; if (shouldResetConversationOnAgentChange()) { sessionId = ''; messages = [] } }"
            @select-database-schema="selectDatabaseSchema"
            @submit="sendMessage()"
            @toggle-database-expansion="toggleDatabaseExpansion"
          />
        </section>
      </Pane>
    </Splitpanes>

    <SettingsDrawer
      v-if="isSettingsOpen"
      :api-base="apiBase"
      :connection="connection"
      :connection-label="connectionLabel"
      :config="config"
      :language="language"
      :permission-mode="permissionMode"
      :plan-mode="planMode"
      @api-base-change="apiBase = $event"
      @check-connection="checkConnection()"
      @language-change="language = $event"
      @permission-mode-change="permissionMode = $event"
      @plan-mode-change="planMode = $event"
      @close="isSettingsOpen = false"
    />
  </main>
  </TooltipProvider>
</template>
