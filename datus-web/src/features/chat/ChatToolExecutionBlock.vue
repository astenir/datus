<script setup lang="ts">
import { computed } from "vue"
import { MessageResponse } from "@/components/ai-elements/message"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import TodoQueueBlock from "@/features/chat/TodoQueueBlock.vue"
import ToolExecutionCard from "@/features/chat/ToolExecutionCard.vue"
import ToolPayloadView from "@/features/chat/ToolPayloadView.vue"
import { todoQueueFromToolResult } from "@/lib/todo-queue"
import {
  type ToolDisplayBlock,
  toolPresentation,
  visibleToolChildMessages,
} from "@/lib/tool-presentation"
import { isSuccessStoryEligibleToolExecution } from "@/lib/tool-display"
import type { MessageDisplayBlock, SelectOption, SuccessStorySource, ToolChildMessage } from "@/types"

const props = defineProps<{
  block: ToolDisplayBlock
  defaultOpen?: boolean
  streaming?: boolean
  executionActive?: boolean
  datasourceName?: string
  datasourceOptions?: readonly SelectOption[]
  databaseName?: string
  successStorySessionId?: string
  successStorySessionLink?: string
  canSaveSuccessStory?: boolean
  isSuccessStorySaving?: (source: SuccessStorySource) => boolean
  isSuccessStorySaved?: (source: SuccessStorySource) => boolean
}>()

const emit = defineEmits<{
  saveSuccessStory: [source: SuccessStorySource]
}>()

defineSlots<{
  "child-block": (props: { block: MessageDisplayBlock }) => unknown
}>()

const currentToolPresentation = computed(() => toolPresentation(props.block, {
  isActive: props.executionActive !== false,
}))

const toolChildMessages = computed(() => visibleToolChildMessages(
  "childMessages" in props.block ? props.block.childMessages : undefined,
))

const hasToolInput = computed(() => props.block.type === "tool-call" || props.block.type === "tool-execution")
const hasToolOutput = computed(() => props.block.type === "tool-result" || props.block.type === "tool-execution")
const showToolOutput = computed(() => hasToolOutput.value && !currentToolPresentation.value.isSubagent)

const toolInputValue = computed(() => (
  props.block.type === "tool-result" ? undefined : props.block.params
))

const toolOutputValue = computed(() => (
  props.block.type === "tool-call" ? undefined : props.block.result
))

const toolErrorText = computed(() => (
  props.block.type === "tool-call" ? undefined : props.block.errorText
))

const currentSuccessStorySource = computed(() => {
  if (props.block.type !== "tool-execution") return undefined
  if (!props.canSaveSuccessStory || !props.successStorySessionId || !props.block.callToolId) return undefined
  if (!isSuccessStoryEligibleToolExecution(props.block.toolName, props.block.resultStatus, props.block.errorText)) {
    return undefined
  }

  return {
    sessionId: props.successStorySessionId,
    callToolId: props.block.callToolId,
    ...(props.successStorySessionLink ? { sessionLink: props.successStorySessionLink } : {}),
  }
})

const todoQueue = computed(() => {
  if (props.block.type === "tool-call") return null
  if (props.block.errorText || props.block.resultStatus === "error") return null
  return todoQueueFromToolResult(props.block.toolName, props.block.result)
})

function saveSuccessStory(source: SuccessStorySource) {
  emit("saveSuccessStory", source)
}

function successStorySaving(source?: SuccessStorySource) {
  return source ? props.isSuccessStorySaving?.(source) === true : false
}

function successStorySaved(source?: SuccessStorySource) {
  return source ? props.isSuccessStorySaved?.(source) === true : false
}

function childMessageSourceLabel(message: ToolChildMessage) {
  if (message.role === "system") return "系统事件"
  if (message.role === "user") return "用户输入"
  return undefined
}
</script>

<template>
  <TodoQueueBlock
    v-if="todoQueue"
    :queue="todoQueue"
    :duration="block.type === 'tool-result' || block.type === 'tool-execution' ? block.duration : undefined"
  />

  <ToolExecutionCard
    v-else
    :presentation="currentToolPresentation"
    :default-open="defaultOpen"
  >
    <ToolPayloadView
      v-if="hasToolInput"
      mode="input"
      :tool-name="block.toolName"
      :value="toolInputValue"
      :datasource-name="datasourceName"
      :datasource-options="datasourceOptions"
      :database-name="databaseName"
      :success-story-source="currentSuccessStorySource"
      :success-story-saving="successStorySaving(currentSuccessStorySource)"
      :success-story-saved="successStorySaved(currentSuccessStorySource)"
      @save-success-story="saveSuccessStory"
    />

    <template v-if="toolChildMessages.length">
      <Separator />
      <div class="flex flex-col gap-3 p-4">
        <div class="flex min-w-0 items-center justify-between gap-3">
          <h4 class="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            执行过程
          </h4>
          <Badge variant="outline">
            {{ toolChildMessages.length }} 项
          </Badge>
        </div>

        <div
          v-for="child in toolChildMessages"
          :key="child.id"
          class="flex min-w-0 flex-col gap-2"
          data-testid="subagent-process-item"
        >
          <div
            v-if="childMessageSourceLabel(child)"
            class="text-xs font-medium text-muted-foreground"
          >
            {{ childMessageSourceLabel(child) }}
          </div>
          <div class="flex min-w-0 flex-col gap-2 text-sm leading-6">
            <template v-if="child.blocks?.length">
              <template
                v-for="(childBlock, index) in child.blocks"
                :key="`${child.id}-${index}`"
              >
                <slot
                  name="child-block"
                  :block="childBlock"
                />
              </template>
            </template>
            <MessageResponse
              v-else
              :content="child.content"
              :streaming="streaming"
            />
          </div>
        </div>
      </div>
    </template>

    <template v-if="showToolOutput">
      <Separator />
      <ToolPayloadView
        mode="output"
        :tool-name="block.toolName"
        :value="toolOutputValue"
        :error-text="toolErrorText"
        :datasource-name="datasourceName"
        :datasource-options="datasourceOptions"
        :database-name="databaseName"
      />
    </template>
  </ToolExecutionCard>
</template>
