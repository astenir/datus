<script setup lang="ts">
import { computed, defineAsyncComponent, nextTick, watch, useTemplateRef, type PropType } from "vue";
import { Activity, Bot, Loader2, Send, TerminalSquare } from "@lucide/vue";

import ErrorBoundary from "@/components/ErrorBoundary.vue";
import Avatar from "@/components/ui/Avatar.vue";
import AvatarFallback from "@/components/ui/AvatarFallback.vue";
import type { ChatMessage } from "@/types";

const MessageContent = defineAsyncComponent(() => import("@/components/chat/MessageContent.vue"));

const props = defineProps({
  messages: {
    type: Array as PropType<ChatMessage[]>,
    required: true
  },
  isStreaming: {
    type: Boolean,
    required: true
  },
  sessionId: {
    type: String as PropType<string | null>,
    default: null
  }
});

const scrollContainer = useTemplateRef<HTMLDivElement>("scrollContainer");

// Hide streaming indicator when the last block is a user-interaction (backend is waiting for input)
const showStreaming = computed(() => {
  if (!props.isStreaming) return false;
  const last = props.messages[props.messages.length - 1];
  if (!last?.blocks?.length) return true;
  const lastBlock = last.blocks[last.blocks.length - 1];
  return lastBlock?.type !== "user-interaction";
});

function scrollToBottom() {
  const el = scrollContainer.value;
  if (el) {
    el.scrollTop = el.scrollHeight;
  }
}

watch(
  () => props.messages.length,
  () => {
    nextTick(scrollToBottom);
  }
);

watch(
  () => {
    if (!props.isStreaming || props.messages.length === 0) return null;
    const last = props.messages[props.messages.length - 1];
    return last?.content;
  },
  (content) => {
    if (content !== null) {
      nextTick(scrollToBottom);
    }
  }
);
</script>

<template>
  <div ref="scrollContainer" class="messages">
    <div v-if="messages.length === 0" class="emptyState">
      <TerminalSquare :size="34" />
      <h3>开始新的分析</h3>
      <p>Datus Agent</p>
    </div>
    <template v-else>
      <article
        v-for="item in messages"
        :key="`${item.role}-${item.id}`"
        :class="`message ${item.role}`"
        :style="{ marginLeft: item.depth ? item.depth * 18 + 'px' : '0' }"
      >
        <Avatar class="avatar">
          <AvatarFallback>
            <Bot v-if="item.role === 'assistant'" :size="17" />
            <Send v-else-if="item.role === 'user'" :size="16" />
            <Activity v-else :size="16" />
          </AvatarFallback>
        </Avatar>
        <div class="bubble">
          <ErrorBoundary :fallback-text="item.content">
            <Suspense>
              <template #default>
                <MessageContent :message="item" :session-id="sessionId ?? undefined" :is-streaming="isStreaming" />
              </template>
              <template #fallback>
                <div class="markdownBody">{{ item.content }}</div>
              </template>
            </Suspense>
          </ErrorBoundary>
        </div>
      </article>
    </template>
    <div v-if="showStreaming" class="streaming">
      <Loader2 class="spin" :size="16" />
      正在生成响应
    </div>
  </div>
</template>
