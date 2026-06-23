<script setup lang="ts">
import {
  Reasoning,
  ReasoningContent,
  ReasoningTrigger,
} from "@/components/ai-elements/reasoning"
import {
  Tool,
  ToolContent,
  ToolHeader,
  ToolInput,
  ToolOutput,
} from "@/components/ai-elements/tool"
import { MessageResponse } from "@/components/ai-elements/message"
import UserInteractionBlock from "@/features/chat/UserInteractionBlock.vue"
import type { MessageDisplayBlock } from "@/types"

defineProps<{
  block: MessageDisplayBlock
  streaming?: boolean
  interactionDisabled?: boolean
}>()

const emit = defineEmits<{
  submitInteraction: [interactionKey: string, answers: string[][]]
}>()

function submitInteraction(interactionKey: string, answers: string[][]) {
  emit("submitInteraction", interactionKey, answers)
}
</script>

<template>
  <MessageResponse
    v-if="block.type === 'markdown'"
    :content="block.content"
  />

  <Reasoning
    v-else-if="block.type === 'thinking'"
    :is-streaming="streaming"
  >
    <ReasoningTrigger />
    <ReasoningContent :content="block.content" />
  </Reasoning>

  <Tool
    v-else-if="block.type === 'tool-call'"
    default-open
  >
    <ToolHeader
      :type="`tool-${block.toolName}` as never"
      state="input-available"
      :title="block.toolName"
    />
    <ToolContent>
      <ToolInput :input="block.params as never" />
    </ToolContent>
  </Tool>

  <Tool
    v-else-if="block.type === 'tool-result'"
    default-open
  >
    <ToolHeader
      :type="`tool-${block.toolName}` as never"
      state="output-available"
      :title="block.toolName"
    />
    <ToolContent>
      <ToolOutput
        :output="block.result as never"
        :error-text="undefined"
      />
    </ToolContent>
  </Tool>

  <Tool
    v-else-if="block.type === 'tool-execution'"
    default-open
  >
    <ToolHeader
      :type="`tool-${block.toolName}` as never"
      state="output-available"
      :title="block.toolName"
    />
    <ToolContent>
      <ToolInput :input="block.params as never" />
      <ToolOutput
        :output="block.result as never"
        :error-text="undefined"
      />
    </ToolContent>
  </Tool>

  <MessageResponse
    v-else-if="block.type === 'artifact'"
    :content="`**${block.name}**\n\n${block.description ?? block.kind}`"
  />

  <UserInteractionBlock
    v-else-if="block.type === 'user-interaction'"
    :block="block"
    :disabled="interactionDisabled"
    @submit="submitInteraction"
  />
</template>
