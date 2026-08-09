<script setup lang="ts">
import { computed } from "vue"
import { CheckCircle2Icon, WrenchIcon } from "@lucide/vue"
import { Badge } from "@/components/ui/badge"
import UserInteractionBlock from "@/features/chat/UserInteractionBlock.vue"
import { parsePermissionRequest } from "@/lib/interaction-display"
import type { MessageDisplayBlock } from "@/types"

type UserInteractionBlockData = Extract<MessageDisplayBlock, { type: "user-interaction" }>

const props = defineProps<{
  block: UserInteractionBlockData
  interactionDisabled?: boolean
  activeInteractionKey?: string | null
  dockedInteractionKey?: string | null
  executionActive?: boolean
}>()

const emit = defineEmits<{
  submit: [interactionKey: string, answers: string[][]]
}>()

const isDockedInteraction = computed(() => (
  Boolean(props.dockedInteractionKey) && props.block.interactionKey === props.dockedInteractionKey
))

const isReadOnlyInteraction = computed(() => (
  props.block.interactionKey !== props.activeInteractionKey
))

const interactionSummary = computed(() => {
  const request = props.block.requests[0]
  if (!request) return "用户交互"

  const permissionRequest = parsePermissionRequest(request.content)
  return permissionRequest?.operationName ?? permissionRequest?.toolName ?? request.title ?? request.content
})

const readOnlyInteractionDescription = computed(() => (
  props.executionActive ? "已提交，工具调用继续执行中" : "此交互请求已处理或已失效"
))

const interactionDisabled = computed(() => (
  props.interactionDisabled || isReadOnlyInteraction.value
))

function submitInteraction(interactionKey: string, answers: string[][]) {
  emit("submit", interactionKey, answers)
}
</script>

<template>
  <div
    v-if="isDockedInteraction"
    class="flex min-w-0 items-start gap-3 rounded-md border border-dashed bg-muted/20 p-3"
    data-testid="chat-interaction-docked"
  >
    <Badge
      variant="secondary"
      class="shrink-0"
    >
      <WrenchIcon data-icon="inline-start" />
      等待确认
    </Badge>
    <div class="min-w-0 flex-1">
      <p class="truncate text-sm font-medium text-foreground">
        {{ interactionSummary }}
      </p>
      <p class="text-xs text-muted-foreground">
        请在输入框上方处理此工具权限请求
      </p>
    </div>
  </div>

  <div
    v-else-if="isReadOnlyInteraction"
    class="flex min-w-0 items-start gap-3 rounded-md border border-dashed bg-muted/20 p-3"
    data-testid="chat-interaction-read-only"
  >
    <Badge
      variant="secondary"
      class="shrink-0"
    >
      <CheckCircle2Icon data-icon="inline-start" />
      已处理
    </Badge>
    <div class="min-w-0 flex-1">
      <p class="truncate text-sm font-medium text-foreground">
        {{ interactionSummary }}
      </p>
      <p class="text-xs text-muted-foreground">
        {{ readOnlyInteractionDescription }}
      </p>
    </div>
  </div>

  <UserInteractionBlock
    v-else
    :block="block"
    :disabled="interactionDisabled"
    @submit="submitInteraction"
  />
</template>
