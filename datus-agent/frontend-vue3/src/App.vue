<script setup lang="ts">
import { ref, onMounted, watch } from "vue";
import { Splitpanes, Pane } from "splitpanes";
import { TooltipProvider } from "reka-ui";
import "splitpanes/dist/splitpanes.css";

import Sidebar from "@/components/layout/Sidebar.vue";
import ChatComposer from "@/components/chat/ChatComposer.vue";
import ConversationToolbar from "@/components/chat/ConversationToolbar.vue";
import MessageList from "@/components/chat/MessageList.vue";
import SettingsDrawer from "@/components/settings/SettingsDrawer.vue";

import { useTheme } from "@/composables/useTheme";
import { useChatSettings } from "@/composables/useChatSettings";
import { useConnection } from "@/composables/useConnection";
import { useChatState } from "@/composables/useChatState";
import { useAgents } from "@/composables/useAgents";
import { useModels } from "@/composables/useModels";
import { useCatalog } from "@/composables/useCatalog";

import type { ViewType } from "@/types";

// ─── Composables ─────────────────────────────────────────────────────────────

useTheme();
const { language, permissionMode, planMode } = useChatSettings();
const { apiBase, connection, config, effectiveBase, checkConnection, setApiBase } = useConnection();
const { messages, sessions, selectedSession, isStreaming, loadSessions, selectSession, sendMessage, stopSession, deleteSession, compactSession, resumeSession, clearMessages } = useChatState();
const { agents, loadAgents } = useAgents();
const { modelOptions, loadModels } = useModels();
const { catalogEntries, databaseOptions, database, schema, schemaOptions, loadCatalog, resetCatalog } = useCatalog();

// ─── Navigation ──────────────────────────────────────────────────────────────

const activeView = ref<ViewType>("chat");

// ─── Settings drawer ─────────────────────────────────────────────────────────

const settingsOpen = ref(false);

function openSettings() {
  settingsOpen.value = true;
}

// ─── Agent options for ChatComposer ──────────────────────────────────────────

const agentOptions = ref<Array<{ value: string; label: string }>>([]);
watch(agents, (list) => {
  agentOptions.value = list.map((a) => ({ value: a.name, label: a.name }));
});

const selectedAgent = ref("");

// ─── Sidebar collapse ────────────────────────────────────────────────────────

const sidebarCollapsed = ref(false);

function onSidebarToggle() {
  sidebarCollapsed.value = !sidebarCollapsed.value;
}

function onPaneResized(payload: { panes: Array<{ size: number }> }) {
  if (payload.panes.length > 0) {
    sidebarCollapsed.value = payload.panes[0].size < 10;
  }
}

// ─── Chat actions ────────────────────────────────────────────────────────────

function handleSend(message: string) {
  sendMessage({
    message,
    selectedAgent: selectedAgent.value,
    model: "",
    database: database.value,
    schema: schema.value,
  });
}

function handleRefreshConnection() {
  checkConnection();
}

// ─── Bootstrap ───────────────────────────────────────────────────────────────

async function initialize() {
  await checkConnection();
  await Promise.all([loadSessions(), loadAgents(), loadModels(), loadCatalog()]);
}

onMounted(initialize);

// Reload sessions when subagent changes
watch(selectedAgent, () => {
  loadSessions(selectedAgent.value || undefined);
});

// Reload schemas when database changes
watch(database, (db) => {
  if (db) {
    loadCatalog(db);
  }
});
</script>

<template>
  <TooltipProvider :delay-duration="300">
    <div class="shell">
      <div class="workspace">
        <Splitpanes vertical :style="{ height: '100%' }" @resized="onPaneResized">
          <Pane :size="sidebarCollapsed ? 0 : 20" :min-size="sidebarCollapsed ? 0 : 14" max-size="34">
            <div id="sidebar">
              <Sidebar
                :connection="connection"
                :sessions="sessions"
                :selected-session="selectedSession"
                :active-view="activeView"
                :collapsed="sidebarCollapsed"
                @toggle="onSidebarToggle"
                @refresh-connection="handleRefreshConnection"
                @select-session="selectSession"
                @new-session="clearMessages"
                @open-settings="openSettings"
                @update:active-view="activeView = $event"
                @delete-session="deleteSession"
                @compact-session="compactSession"
              />
            </div>
          </Pane>

          <Pane :size="sidebarCollapsed ? 100 : 80" :min-size="42">
            <!-- Chat view -->
            <div v-if="activeView === 'chat'" class="chatView">
              <div class="chatShell">
                <ConversationToolbar
                  :selected-session="selectedSession"
                  :connection="connection"
                  :is-streaming="isStreaming"
                  @refresh-connection="handleRefreshConnection"
                  @clear-messages="clearMessages"
                  @stop-session="stopSession"
                  @resume-session="resumeSession()"
                />
                <MessageList :messages="messages" :is-streaming="isStreaming" :session-id="selectedSession" />
              </div>
              <ChatComposer
                :connection="connection"
                :is-streaming="isStreaming"
                :agent-options="agentOptions"
                :model-options="modelOptions"
                :database-options="databaseOptions"
                :schema-options="schemaOptions"
                :catalog-entries="catalogEntries"
                :selected-agent="selectedAgent"
                :database="database"
                :schema="schema"
                :plan-mode="planMode"
                @update:selected-agent="selectedAgent = $event"
                @update:database="database = $event"
                @update:schema="schema = $event"
                @update:plan-mode="planMode = $event"
                @send="handleSend"
                @stop="stopSession"
              />
            </div>

            <!-- Knowledge Explorer view -->
            <div v-else-if="activeView === 'knowledge'" class="moduleView">
              <div class="modulePlaceholder">
                <h2>知识库 Explorer</h2>
                <p>Subject 树浏览和知识管理 — 即将实现</p>
              </div>
            </div>

            <!-- MCP Manager view -->
            <div v-else-if="activeView === 'mcp'" class="moduleView">
              <div class="modulePlaceholder">
                <h2>MCP 服务器管理</h2>
                <p>MCP 服务器 CRUD 和工具调用 — 即将实现</p>
              </div>
            </div>

            <!-- SQL Console view -->
            <div v-else-if="activeView === 'sql'" class="moduleView">
              <div class="modulePlaceholder">
                <h2>SQL 控制台</h2>
                <p>直接 SQL 查询执行 — 即将实现</p>
              </div>
            </div>
          </Pane>
        </Splitpanes>
      </div>

      <SettingsDrawer
        :open="settingsOpen"
        :connection="connection"
        :config="config"
        :api-base="apiBase"
        :language="language"
        :permission-mode="permissionMode"
        :plan-mode="planMode"
        @update:open="settingsOpen = $event"
        @update:api-base="setApiBase"
        @update:language="language = $event"
        @update:permission-mode="permissionMode = $event"
        @update:plan-mode="planMode = $event"
        @refresh-connection="handleRefreshConnection"
      />
    </div>
  </TooltipProvider>
</template>
