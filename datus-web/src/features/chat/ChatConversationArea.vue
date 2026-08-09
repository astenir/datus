<script setup lang="ts">
import { defineAsyncComponent } from "vue"
import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from "@/components/ai-elements/conversation"
import { Suggestion, Suggestions } from "@/components/ai-elements/suggestion"
import ChatActivityStatus from "@/features/chat/ChatActivityStatus.vue"
import type {
  ChatDisplayMessage,
  ChatStreamActivity,
  SelectOption,
  SuccessStorySource,
} from "@/types"
import type { TodoExecutionState } from "@/lib/todo-execution"

defineProps<{
  displayMessages: readonly ChatDisplayMessage[]
  isStreaming: boolean
  streamingMessageId: string | null
  interactionPending: boolean
  activeInteractionKey: string | null
  dockedInteractionKey: string | null
  datasourceName: string
  datasourceOptions: readonly SelectOption[]
  databaseName: string
  successStorySessionId?: string
  successStorySessionLink?: string
  canSaveSuccessStory: boolean
  successStoryVersion: number
  isSuccessStorySaving: (source: SuccessStorySource) => boolean
  isSuccessStorySaved: (source: SuccessStorySource) => boolean
  activeTodoExecution: TodoExecutionState | null
  streamActivity: ChatStreamActivity
}>()

const emit = defineEmits<{
  sendSuggestion: [suggestion: string]
  submitInteraction: [interactionKey: string, answers: string[][]]
  openArtifact: [kind: string, slug: string]
  saveSuccessStory: [source: SuccessStorySource]
  stop: []
}>()

const ChatMessageItem = defineAsyncComponent(() => import("@/features/chat/ChatMessageItem.vue"))

const promptSuggestions = [
  "帮我分析基金持仓的关键变化",
  "列出当前数据源有哪些表",
  "运行 SQL 查询近 10 条记录",
  "查看 MCP 工具连接状态",
  "生成一份数据质量检查思路",
  "帮我总结这个会话的重点",
]

function submitInteraction(interactionKey: string, answers: string[][]) {
  emit("submitInteraction", interactionKey, answers)
}

function openArtifact(kind: string, slug: string) {
  emit("openArtifact", kind, slug)
}

function saveSuccessStory(source: SuccessStorySource) {
  emit("saveSuccessStory", source)
}

function sendSuggestion(suggestion: string) {
  emit("sendSuggestion", suggestion)
}

function stop() {
  emit("stop")
}
</script>

<template>
  <div class="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
    <div
      v-if="displayMessages.length === 0"
      class="flex min-h-0 w-full min-w-0 flex-1 flex-col items-center justify-center px-4 pb-28 pt-12 text-center md:pb-36"
    >
      <h1 class="max-w-full text-3xl font-bold leading-tight text-foreground md:text-4xl">
        有什么我能帮你的吗？
      </h1>

      <Suggestions class="mx-auto mt-8 flex w-full max-w-5xl flex-wrap justify-center gap-2 whitespace-normal px-1">
        <Suggestion
          v-for="(suggestion, index) in promptSuggestions"
          :key="suggestion"
          :suggestion="suggestion"
          variant="secondary"
          size="lg"
          :class="[
            'h-auto min-h-10 max-w-full rounded-2xl border-transparent bg-muted px-5 py-2.5 text-sm text-foreground hover:bg-muted/80 md:min-h-11',
            index > 1 ? 'hidden sm:inline-flex' : '',
          ]"
          @click="sendSuggestion"
        />
      </Suggestions>
    </div>

    <Conversation
      v-else
      class="min-h-0"
    >
      <ConversationContent class="gap-5 px-4 py-6 md:px-8">
        <ChatMessageItem
          v-for="message in displayMessages"
          :key="message.id"
          v-memo="[message, message.id === streamingMessageId, isStreaming, interactionPending, activeInteractionKey, datasourceName, databaseName, successStorySessionId, canSaveSuccessStory, successStoryVersion]"
          :message="message"
          :streaming="message.id === streamingMessageId"
          :execution-active="isStreaming"
          :interaction-disabled="interactionPending"
          :active-interaction-key="activeInteractionKey"
          :docked-interaction-key="dockedInteractionKey"
          :datasource-name="datasourceName"
          :datasource-options="datasourceOptions"
          :database-name="databaseName"
          :success-story-session-id="successStorySessionId"
          :success-story-session-link="successStorySessionLink"
          :can-save-success-story="canSaveSuccessStory"
          :success-story-version="successStoryVersion"
          :is-success-story-saving="isSuccessStorySaving"
          :is-success-story-saved="isSuccessStorySaved"
          @submit-interaction="submitInteraction"
          @open-artifact="openArtifact"
          @save-success-story="saveSuccessStory"
        />
        <ChatActivityStatus
          v-if="isStreaming && !activeTodoExecution"
          :activity="streamActivity"
          @stop="stop"
        />
      </ConversationContent>
      <ConversationScrollButton />
    </Conversation>
  </div>
</template>
