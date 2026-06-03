<script setup lang="ts">
import {
  Bot,
  CheckCircle2,
  Database,
  Loader2,
  MessageSquare,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  RefreshCw,
  Settings2,
  Sparkles,
  Sun,
  Terminal,
  WifiOff,
  Wrench,
} from "@lucide/vue";

import Badge from "@/components/ui/Badge.vue";
import Button from "@/components/ui/Button.vue";
import ScrollArea from "@/components/ui/ScrollArea.vue";
import Tooltip from "@/components/ui/Tooltip.vue";
import TooltipTrigger from "@/components/ui/TooltipTrigger.vue";
import TooltipContent from "@/components/ui/TooltipContent.vue";
import SidebarRoot from "@/components/ui/SidebarRoot.vue";
import SidebarGroup from "@/components/ui/SidebarGroup.vue";
import SidebarGroupContent from "@/components/ui/SidebarGroupContent.vue";
import SidebarGroupHeader from "@/components/ui/SidebarGroupHeader.vue";
import SidebarHeader from "@/components/ui/SidebarHeader.vue";
import { formatSessionTime, sessionTitle, sessionUserQueryText } from "@/lib/chat";
import { CONNECTION_LABELS } from "@/lib/constants";
import { ref } from "vue";
import { useTheme } from "@/composables/useTheme";
import type { ChatSessionOption, ConnectionState, ViewType } from "@/types";

const props = defineProps<{
  connection: ConnectionState;
  sessions: ChatSessionOption[];
  selectedSession: string | null;
  activeView: ViewType;
  collapsed: boolean;
}>();

const emit = defineEmits<{
  toggle: [];
  "refresh-connection": [];
  "select-session": [sessionId: string];
  "new-session": [];
  "open-settings": [];
  "open-agent-manager": [];
  "update:active-view": [view: ViewType];
  "delete-session": [sessionId: string];
  "compact-session": [sessionId: string];
}>();

const { theme, toggleTheme } = useTheme();

const navItems: Array<{ view: ViewType; label: string; icon: typeof MessageSquare }> = [
  { view: "chat", label: "对话", icon: MessageSquare },
  { view: "knowledge", label: "知识库", icon: Database },
  { view: "mcp", label: "MCP", icon: Wrench },
  { view: "sql", label: "SQL", icon: Terminal },
];

const contextMenuSession = ref<string | null>(null);
const contextMenuPos = ref({ x: 0, y: 0 });

function onSessionContext(e: MouseEvent, sessionId: string) {
  e.preventDefault();
  contextMenuSession.value = sessionId;
  contextMenuPos.value = { x: e.clientX, y: e.clientY };
}

function closeContextMenu() {
  contextMenuSession.value = null;
}

function handleDelete() {
  if (contextMenuSession.value) {
    emit("delete-session", contextMenuSession.value);
    closeContextMenu();
  }
}

function handleCompact() {
  if (contextMenuSession.value) {
    emit("compact-session", contextMenuSession.value);
    closeContextMenu();
  }
}
</script>

<template>
  <SidebarRoot :class="`sidebar ${collapsed ? 'collapsed' : ''}`">
    <!-- Header: only visible when expanded -->
    <div v-if="!collapsed" class="sidebarHeaderWrap">
      <SidebarHeader>
        <div class="brand">
          <div class="brandMark">
            <Sparkles :size="22" />
          </div>
          <div>
            <h1>Datus Agent</h1>
            <p>Chat Console</p>
          </div>
        </div>
        <div class="sidebarActions">
          <Tooltip>
            <TooltipTrigger as-child>
              <Button
                class="iconButton sidebarCollapseBtn"
                variant="ghost"
                size="icon"
                aria-label="收起侧栏"
                @click="emit('toggle')"
              >
                <PanelLeftClose :size="17" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom">收起侧栏</TooltipContent>
          </Tooltip>
        </div>
      </SidebarHeader>
    </div>

    <!-- Navigation tabs -->
    <div class="navTabs">
      <!-- Collapse/expand button: same navTab style when collapsed -->
      <button
        v-if="collapsed"
        class="navTab"
        type="button"
        title="展开侧栏"
        @click="emit('toggle')"
      >
        <PanelLeftOpen :size="16" />
      </button>
      <button
        v-for="item in navItems"
        :key="item.view"
        :class="`navTab ${activeView === item.view ? 'active' : ''}`"
        type="button"
        :title="item.label"
        @click="emit('update:active-view', item.view)"
      >
        <component :is="item.icon" :size="16" />
        <span v-if="!collapsed">{{ item.label }}</span>
      </button>
    </div>

    <!-- Session list (only shown in chat view) -->
    <SidebarGroup v-if="activeView === 'chat'">
      <SidebarGroupHeader>
        <div>
          <h2>会话</h2>
          <p>{{ sessions.length }} 个会话</p>
        </div>
        <div class="sessionActions">
          <Tooltip>
            <TooltipTrigger as-child>
              <Button class="iconButton" variant="ghost" size="icon" aria-label="新会话" @click="emit('new-session')">
                <Plus :size="17" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>新会话</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger as-child>
              <Button class="iconButton" variant="ghost" size="icon" aria-label="刷新会话" @click="emit('refresh-connection')">
                <RefreshCw :size="16" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>刷新会话</TooltipContent>
          </Tooltip>
        </div>
      </SidebarGroupHeader>

      <button :class="`sessionItem ${!selectedSession ? 'active' : ''}`" type="button" @click="emit('new-session')">
        <span class="sessionIcon">
          <Plus :size="16" />
        </span>
        <span class="sessionText">
          <strong>新会话</strong>
          <small>自动生成 ID</small>
        </span>
      </button>

      <SidebarGroupContent class="sessionListFrame">
        <ScrollArea class="sessionList">
          <div class="sessionListInner">
            <button
              v-for="session in sessions"
              :key="session.session_id"
              :class="`sessionItem ${session.session_id === selectedSession ? 'active' : ''}`"
              type="button"
              :title="sessionTitle(session)"
              @click="emit('select-session', session.session_id)"
              @contextmenu="onSessionContext($event, session.session_id)"
            >
              <span class="sessionIcon">
                <MessageSquare :size="16" />
              </span>
              <span class="sessionText">
                <strong>{{ sessionUserQueryText(session) || '新会话' }}</strong>
                <small>
                  {{ formatSessionTime(session.last_updated || session.created_at) }}
                  <template v-if="typeof session.total_turns === 'number' && session.total_turns > 0"> · {{ session.total_turns }} turns</template>
                </small>
              </span>
            </button>
          </div>
        </ScrollArea>
      </SidebarGroupContent>
    </SidebarGroup>

    <!-- Context menu -->
    <Teleport to="body">
      <div
        v-if="contextMenuSession"
        class="sessionContextMenu"
        :style="{ left: contextMenuPos.x + 'px', top: contextMenuPos.y + 'px' }"
        @click="closeContextMenu"
        @contextmenu.prevent="closeContextMenu"
      >
        <button type="button" @click="handleCompact">压缩历史</button>
        <button type="button" class="destructive" @click="handleDelete">删除会话</button>
      </div>
    </Teleport>

    <div v-if="!collapsed" class="sidebarFooter">
      <Badge
        :variant="connection === 'online' ? 'success' : connection === 'offline' ? 'destructive' : connection === 'checking' ? 'secondary' : 'outline'"
        class="connectionPill"
      >
        <CheckCircle2 v-if="connection === 'online'" :size="14" />
        <Loader2 v-else-if="connection === 'checking'" class="spin" :size="14" />
        <WifiOff v-else :size="14" />
        {{ CONNECTION_LABELS[connection] }}
      </Badge>
      <div class="sidebarFooterActions">
        <Tooltip>
          <TooltipTrigger as-child>
            <Button class="sidebarThemeBtn" variant="ghost" size="icon" aria-label="切换主题" @click="toggleTheme">
              <Sun v-if="theme === 'dark'" :size="17" />
              <Moon v-else :size="17" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>切换主题</TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger as-child>
            <Button class="iconButton" variant="ghost" size="icon" aria-label="Agent 管理" @click="emit('open-agent-manager')">
              <Bot :size="17" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Agent 管理</TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger as-child>
            <Button class="iconButton" variant="ghost" size="icon" aria-label="打开设置" @click="emit('open-settings')">
              <Settings2 :size="17" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>设置</TooltipContent>
        </Tooltip>
      </div>
    </div>

    <div v-if="collapsed" class="sidebarActionsStack">
      <Tooltip>
        <TooltipTrigger as-child>
          <Button class="sidebarThemeBtn" variant="ghost" size="icon" aria-label="切换主题" @click="toggleTheme">
            <Sun v-if="theme === 'dark'" :size="17" />
            <Moon v-else :size="17" />
          </Button>
        </TooltipTrigger>
        <TooltipContent side="right">切换主题</TooltipContent>
      </Tooltip>
      <Tooltip>
        <TooltipTrigger as-child>
          <Button class="iconButton" variant="ghost" size="icon" aria-label="打开设置" @click="emit('open-settings')">
            <Settings2 :size="17" />
          </Button>
        </TooltipTrigger>
        <TooltipContent side="right">设置</TooltipContent>
      </Tooltip>
      <Tooltip>
        <TooltipTrigger as-child>
          <Button class="iconButton" variant="ghost" size="icon" aria-label="新会话" @click="emit('new-session')">
            <Plus :size="17" />
          </Button>
        </TooltipTrigger>
        <TooltipContent side="right">新会话</TooltipContent>
      </Tooltip>
    </div>
  </SidebarRoot>
</template>
