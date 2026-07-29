<script setup lang="ts">
import { computed } from "vue"
import { Message, MessageContent, MessageResponse } from "@/components/ai-elements/message"
import { Badge } from "@/components/ui/badge"
import ChatBlockRenderer from "@/features/chat/ChatBlockRenderer.vue"
import type { ChatDisplayMessage, SelectOption, SuccessStorySource } from "@/types"

const props = defineProps<{
  message: ChatDisplayMessage
  streaming?: boolean
  executionActive?: boolean
  interactionDisabled?: boolean
  activeInteractionKey?: string | null
  dockedInteractionKey?: string | null
  datasourceName?: string
  datasourceOptions?: readonly SelectOption[]
  databaseName?: string
  successStorySessionId?: string
  successStorySessionLink?: string
  canSaveSuccessStory?: boolean
  successStoryVersion?: number
  isSuccessStorySaving?: (source: SuccessStorySource) => boolean
  isSuccessStorySaved?: (source: SuccessStorySource) => boolean
}>()

const emit = defineEmits<{
  submitInteraction: [interactionKey: string, answers: string[][]]
  openArtifact: [kind: string, slug: string]
  saveSuccessStory: [source: SuccessStorySource]
}>()

const isUserMessage = computed(() => props.message.role === "user")
const isSystemMessage = computed(() => props.message.role === "system")
const hasErrorBlock = computed(() => props.message.blocks?.some((block) => block.type === "error") ?? false)
const messageFrom = computed(() => isUserMessage.value ? "user" : "assistant")
const messageClass = computed(() =>
  hasErrorBlock.value
    ? "mx-auto w-full !max-w-3xl justify-center"
    : isSystemMessage.value
      ? "mx-auto !max-w-3xl justify-center"
      : "mx-auto !max-w-3xl",
)
const contentClass = computed(() =>
  hasErrorBlock.value
    ? "w-full overflow-visible text-sm leading-6"
    : isSystemMessage.value
      ? "w-fit rounded-full bg-muted px-3 py-1 text-xs text-muted-foreground"
      : isUserMessage.value
        ? "w-auto rounded-2xl bg-muted px-4 py-3 text-sm leading-6"
        : "w-full overflow-visible text-sm leading-7 text-foreground",
)

function submitInteraction(interactionKey: string, answers: string[][]) {
  emit("submitInteraction", interactionKey, answers)
}

function openArtifact(kind: string, slug: string) {
  emit("openArtifact", kind, slug)
}

function saveSuccessStory(source: SuccessStorySource) {
  emit("saveSuccessStory", source)
}
</script>

<template>
  <Message
    :from="messageFrom"
    :class="messageClass"
  >
    <MessageContent :class="contentClass">
      <div
        v-if="message.depth && !isUserMessage && !isSystemMessage"
        class="mb-3"
      >
        <Badge variant="outline">
          子 Agent 执行
        </Badge>
      </div>

      <div class="flex flex-col gap-3">
        <template v-if="message.blocks?.length">
          <ChatBlockRenderer
            v-for="(block, index) in message.blocks"
            :key="`${message.id}-${index}`"
            :block="block"
            :streaming="streaming"
            :execution-active="executionActive"
            :interaction-disabled="interactionDisabled"
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
        </template>
        <MessageResponse
          v-else
          :content="message.content"
          :streaming="streaming"
        />
      </div>
    </MessageContent>
  </Message>
</template>
