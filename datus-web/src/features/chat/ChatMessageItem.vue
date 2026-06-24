<script setup lang="ts">
import { computed } from "vue"
import { Message, MessageContent, MessageResponse } from "@/components/ai-elements/message"
import ChatBlockRenderer from "@/features/chat/ChatBlockRenderer.vue"
import type { ChatDisplayMessage } from "@/types"

const props = defineProps<{
  message: ChatDisplayMessage
  streaming?: boolean
  interactionDisabled?: boolean
}>()

const emit = defineEmits<{
  submitInteraction: [interactionKey: string, answers: string[][]]
  openArtifact: [kind: string, slug: string]
}>()

const isUserMessage = computed(() => props.message.role === "user")
const isSystemMessage = computed(() => props.message.role === "system")
const messageFrom = computed(() => isUserMessage.value ? "user" : "assistant")
const messageClass = computed(() =>
  isSystemMessage.value
    ? "mx-auto !max-w-3xl justify-center"
    : "mx-auto !max-w-3xl",
)
const contentClass = computed(() =>
  isSystemMessage.value
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
</script>

<template>
  <Message
    :from="messageFrom"
    :class="messageClass"
  >
    <MessageContent :class="contentClass">
      <div
        v-if="message.depth && !isUserMessage && !isSystemMessage"
        class="mb-3 text-sm text-muted-foreground"
      >
        depth {{ message.depth }}
      </div>

      <div class="flex flex-col gap-3">
        <template v-if="message.blocks?.length">
          <ChatBlockRenderer
            v-for="(block, index) in message.blocks"
            :key="`${message.id}-${index}`"
            :block="block"
            :streaming="streaming"
            :interaction-disabled="interactionDisabled"
            @submit-interaction="submitInteraction"
            @open-artifact="openArtifact"
          />
        </template>
        <MessageResponse
          v-else
          :content="message.content"
        />
      </div>
    </MessageContent>
  </Message>
</template>
