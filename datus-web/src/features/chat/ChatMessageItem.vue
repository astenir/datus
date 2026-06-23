<script setup lang="ts">
import { computed } from "vue"
import { Message, MessageContent, MessageResponse } from "@/components/ai-elements/message"
import { Badge } from "@/components/ui/badge"
import ChatBlockRenderer from "@/features/chat/ChatBlockRenderer.vue"
import type { ChatDisplayMessage } from "@/types"

const props = defineProps<{
  message: ChatDisplayMessage
  streaming?: boolean
  interactionDisabled?: boolean
}>()

const emit = defineEmits<{
  submitInteraction: [interactionKey: string, answers: string[][]]
}>()

const roleLabel = computed(() => {
  if (props.message.role === "assistant") return "Datus"
  if (props.message.role === "user") return "You"
  return "System"
})

function submitInteraction(interactionKey: string, answers: string[][]) {
  emit("submitInteraction", interactionKey, answers)
}
</script>

<template>
  <Message
    :from="message.role === 'user' ? 'user' : 'assistant'"
    class="max-w-full"
  >
    <MessageContent class="w-full">
      <div class="mb-2 flex items-center gap-2">
        <Badge variant="secondary">{{ roleLabel }}</Badge>
        <span
          v-if="message.depth"
          class="text-xs text-muted-foreground"
        >
          depth {{ message.depth }}
        </span>
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
