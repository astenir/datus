<script setup lang="ts">
import { Activity, CircleStop, Loader2, MessageSquare, PanelLeft, RefreshCw, Trash2 } from "@lucide/vue";

import Button from "@/components/ui/Button.vue";
import Tooltip from "@/components/ui/Tooltip.vue";
import TooltipTrigger from "@/components/ui/TooltipTrigger.vue";
import TooltipContent from "@/components/ui/TooltipContent.vue";
import { sessionUserQueryText } from "@/lib/chat";
import type { ChatSessionOption, ConnectionState } from "@/types";

defineProps<{
  connection: ConnectionState;
  isStreaming: boolean;
  selectedSession?: ChatSessionOption;
  sessionId: string;
}>();

const emit = defineEmits<{
  "clear-messages": [];
  "open-mobile-sessions": [];
  "refresh-connection": [];
  "stop-session": [];
}>();
</script>

<template>
  <header class="topbar">
    <div class="conversationTitle">
      <p class="eyebrow">
        <Activity v-if="selectedSession?.is_active" :size="14" />
        <MessageSquare v-else :size="14" />
        {{ sessionId ? '历史会话' : '新会话' }}
      </p>
      <h2>{{ selectedSession ? (sessionUserQueryText(selectedSession) || sessionId || 'Agent 对话') : (sessionId || 'Agent 对话') }}</h2>
    </div>
    <div class="toolbar">
      <Tooltip>
        <TooltipTrigger as-child>
          <Button class="iconButton mobileSessionButton" variant="ghost" size="icon" aria-label="打开会话历史" @click="emit('open-mobile-sessions')">
            <PanelLeft :size="17" />
          </Button>
        </TooltipTrigger>
        <TooltipContent>会话历史</TooltipContent>
      </Tooltip>
      <Tooltip>
        <TooltipTrigger as-child>
          <Button class="iconButton" variant="ghost" size="icon" aria-label="刷新连接" @click="emit('refresh-connection')">
            <Loader2 v-if="connection === 'checking'" class="spin" :size="16" />
            <RefreshCw v-else :size="16" />
          </Button>
        </TooltipTrigger>
        <TooltipContent>刷新连接</TooltipContent>
      </Tooltip>
      <Tooltip>
        <TooltipTrigger as-child>
          <Button class="iconButton" variant="ghost" size="icon" aria-label="清空消息" @click="emit('clear-messages')">
            <Trash2 :size="17" />
          </Button>
        </TooltipTrigger>
        <TooltipContent>清空消息</TooltipContent>
      </Tooltip>
      <Button class="stopButton" variant="outline" @click="emit('stop-session')" :disabled="!isStreaming && !sessionId">
        <CircleStop :size="16" />
        停止
      </Button>
    </div>
  </header>
</template>
