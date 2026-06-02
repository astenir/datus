<script setup lang="ts">
import {
  CheckCircle2,
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
  WifiOff
} from "@lucide/vue";

import Badge from "@/components/ui/Badge.vue";
import Button from "@/components/ui/Button.vue";
import ScrollArea from "@/components/ui/ScrollArea.vue";
import Skeleton from "@/components/ui/Skeleton.vue";
import Tooltip from "@/components/ui/Tooltip.vue";
import TooltipTrigger from "@/components/ui/TooltipTrigger.vue";
import TooltipContent from "@/components/ui/TooltipContent.vue";
import SidebarRoot from "@/components/ui/Sidebar.vue";
import SidebarGroup from "@/components/ui/SidebarGroup.vue";
import SidebarGroupContent from "@/components/ui/SidebarGroupContent.vue";
import SidebarGroupHeader from "@/components/ui/SidebarGroupHeader.vue";
import SidebarHeader from "@/components/ui/SidebarHeader.vue";
import { formatSessionTime, sessionTitle, sessionUserQueryText } from "@/lib/chat";
import type { ChatSessionOption, ConnectionState } from "@/types";

defineProps<{
  connection: ConnectionState;
  connectionLabel: string;
  sessions: ChatSessionOption[];
  sessionId: string;
  isLoadingSessions: boolean;
  isStreaming: boolean;
  collapsed: boolean;
  theme: "light" | "dark";
}>();

const emit = defineEmits<{
  "toggle-collapse": [];
  "toggle-theme": [];
  "open-settings": [];
  "new-session": [];
  "refresh-sessions": [];
  "select-session": [sessionId: string];
}>();
</script>

<template>
  <SidebarRoot :class="`sidebar ${collapsed ? 'collapsed' : ''}`">
    <div>
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
                :aria-label="collapsed ? '展开侧栏' : '收起侧栏'"
                @click="emit('toggle-collapse')"
              >
                <PanelLeftOpen v-if="collapsed" :size="17" />
                <PanelLeftClose v-else :size="17" />
              </Button>
            </TooltipTrigger>
            <TooltipContent :side="collapsed ? 'right' : 'bottom'">{{ collapsed ? '展开侧栏' : '收起侧栏' }}</TooltipContent>
          </Tooltip>
        </div>
      </SidebarHeader>
    </div>

    <SidebarGroup>
      <SidebarGroupHeader>
        <div>
          <h2>会话</h2>
          <p>{{ sessions.length }} 个会话</p>
        </div>
        <div class="sessionActions">
          <Tooltip>
            <TooltipTrigger as-child>
              <Button class="iconButton" variant="ghost" size="icon" aria-label="新会话" :disabled="isStreaming" @click="emit('new-session')">
                <Plus :size="17" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>新会话</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger as-child>
              <Button class="iconButton" variant="ghost" size="icon" aria-label="刷新会话" :disabled="isLoadingSessions" @click="emit('refresh-sessions')">
                <Loader2 v-if="isLoadingSessions" class="spin" :size="16" />
                <RefreshCw v-else :size="16" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>刷新会话</TooltipContent>
          </Tooltip>
        </div>
      </SidebarGroupHeader>

      <button :class="`sessionItem ${!sessionId ? 'active' : ''}`" type="button" :disabled="isStreaming" @click="emit('new-session')">
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
            <template v-if="isLoadingSessions">
              <div v-for="i in 5" :key="`skeleton-${i}`" class="skeletonSessionItem">
                <Skeleton class="skeletonSessionIcon" />
                <div class="skeletonSessionLine">
                  <Skeleton class="skeletonSessionLineShort" />
                  <Skeleton class="skeletonSessionLineLong" />
                </div>
              </div>
            </template>
            <template v-else>
              <button
                v-for="session in sessions"
                :key="session.session_id"
                :class="`sessionItem ${session.session_id === sessionId ? 'active' : ''}`"
                type="button"
                :title="sessionTitle(session)"
                :disabled="isStreaming"
                @click="emit('select-session', session.session_id)"
              >
                <span class="sessionIcon">
                  <MessageSquare :size="16" />
                </span>
                <span class="sessionText">
                  <strong>{{ sessionUserQueryText(session) || session.session_id }}</strong>
                  <small>
                    {{ formatSessionTime(session.last_updated || session.created_at) || session.session_id }}
                    <template v-if="typeof session.total_turns === 'number' && session.total_turns > 0"> · {{ session.total_turns }} turns</template>
                  </small>
                </span>
              </button>
            </template>
          </div>
        </ScrollArea>
      </SidebarGroupContent>
    </SidebarGroup>

    <div class="sidebarFooter">
      <Badge
        :variant="connection === 'online' ? 'success' : connection === 'offline' ? 'destructive' : connection === 'checking' ? 'secondary' : 'outline'"
        class="connectionPill"
      >
        <CheckCircle2 v-if="connection === 'online'" :size="14" />
        <Loader2 v-else-if="connection === 'checking'" class="spin" :size="14" />
        <WifiOff v-else :size="14" />
        {{ connectionLabel }}
      </Badge>
      <div class="sidebarFooterActions">
        <Tooltip>
          <TooltipTrigger as-child>
            <Button class="sidebarThemeBtn" variant="ghost" size="icon" aria-label="切换主题" @click="emit('toggle-theme')">
              <Sun v-if="theme === 'dark'" :size="17" />
              <Moon v-else :size="17" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>切换主题</TooltipContent>
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

    <div class="sidebarActionsStack">
      <Tooltip>
        <TooltipTrigger as-child>
          <Button class="sidebarThemeBtn" variant="ghost" size="icon" aria-label="切换主题" @click="emit('toggle-theme')">
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
          <Button class="iconButton" variant="ghost" size="icon" aria-label="新会话" :disabled="isStreaming" @click="emit('new-session')">
            <Plus :size="17" />
          </Button>
        </TooltipTrigger>
        <TooltipContent side="right">新会话</TooltipContent>
      </Tooltip>
    </div>
  </SidebarRoot>
</template>
