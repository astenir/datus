<script setup lang="ts">
import { computed, shallowRef, watch } from "vue"
import { ChevronDownIcon, ChevronUpIcon, WrenchIcon } from "@lucide/vue"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Confirmation,
  ConfirmationAction,
  ConfirmationActions,
  ConfirmationRequest,
  ConfirmationTitle,
} from "@/components/ai-elements/confirmation"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import PermissionRequestDetails from "@/features/chat/PermissionRequestDetails.vue"
import { parsePermissionRequest } from "@/lib/interaction-display"
import type { ActiveUserInteraction, UserInteractionRequest } from "@/types"

const props = withDefaults(defineProps<{
  interaction: ActiveUserInteraction | null
  disabled?: boolean
}>(), {
  disabled: false,
})

const emit = defineEmits<{
  submit: [interactionKey: string, answers: string[][]]
}>()

const detailsOpen = shallowRef(false)

const approval = computed(() =>
  props.interaction ? { id: props.interaction.interactionKey } : undefined,
)

const sourceLabel = computed(() =>
  props.interaction?.depth && props.interaction.depth > 0 ? "来自子 Agent 执行" : "当前对话",
)

const singleRequest = computed(() => {
  const requests = props.interaction?.block.requests ?? []
  return requests.length === 1 ? requests[0] : null
})

const permissionRequest = computed(() => {
  const request = singleRequest.value
  return request ? parsePermissionRequest(request.content) : null
})

const canUseCompactLayout = computed(() => Boolean(
  props.interaction &&
    singleRequest.value &&
    permissionRequest.value &&
    !singleRequest.value.allowFreeText &&
    !singleRequest.value.multiSelect &&
    singleRequest.value.options.length > 0,
))

const requestLabel = computed(() => {
  const request = props.interaction?.block.requests[0]
  if (!request) return "用户交互"

  return permissionRequest.value?.operationName ??
    permissionRequest.value?.toolName ??
    request.title ??
    request.content
})

const requestSummary = computed(() => {
  const rows = permissionRequest.value?.argsRows ?? []
  const firstRow = rows[0]
  if (firstRow) return `${firstRow.key}: ${firstRow.value}`

  const request = singleRequest.value
  return request?.content ?? ""
})

function submitOption(key: string) {
  const interactionKey = props.interaction?.interactionKey
  if (!interactionKey || props.disabled) return

  emit("submit", interactionKey, [[key]])
}

function normalizeKey(value: string) {
  return value.trim().toLowerCase()
}

function isNegativeOption(option: UserInteractionRequest["options"][number]) {
  const key = normalizeKey(option.key)
  const title = normalizeKey(option.title)
  return ["n", "no", "false", "cancel", "deny", "reject"].includes(key) ||
    ["no", "cancel", "deny", "reject", "取消", "拒绝"].includes(title)
}

watch(
  () => props.interaction?.interactionKey,
  () => {
    detailsOpen.value = false
  },
)
</script>

<template>
  <Confirmation
    v-if="canUseCompactLayout && interaction && singleRequest && permissionRequest"
    :approval="approval"
    state="approval-requested"
    class="mb-3 overflow-hidden rounded-lg bg-background p-0 shadow-lg shadow-muted/50"
    aria-live="polite"
    aria-label="待处理工具权限请求"
  >
    <Collapsible
      v-model:open="detailsOpen"
      class="overflow-hidden rounded-lg bg-background"
    >
      <ConfirmationRequest>
        <div class="flex min-w-0 flex-col gap-3 p-3 sm:flex-row sm:items-center">
          <ConfirmationTitle class="min-w-0 flex-1 text-foreground">
            <div class="flex min-w-0 flex-wrap items-center gap-2">
              <Badge variant="secondary">
                <WrenchIcon data-icon="inline-start" />
                等待确认
              </Badge>
              <span class="min-w-0 truncate text-sm font-medium text-foreground">
                {{ requestLabel }}
              </span>
              <span class="text-xs text-muted-foreground">
                {{ sourceLabel }}
              </span>
            </div>

            <p class="mt-1 truncate text-xs text-muted-foreground">
              {{ requestSummary }}
            </p>
          </ConfirmationTitle>

          <ConfirmationActions class="flex shrink-0 flex-wrap items-center justify-start gap-2 self-start sm:justify-end sm:self-center">
            <CollapsibleTrigger
              v-if="permissionRequest"
              as-child
            >
              <Button
                type="button"
                variant="ghost"
                size="sm"
              >
                <ChevronUpIcon
                  v-if="detailsOpen"
                  data-icon="inline-start"
                />
                <ChevronDownIcon
                  v-else
                  data-icon="inline-start"
                />
                详情
              </Button>
            </CollapsibleTrigger>

            <ConfirmationAction
              v-for="option in singleRequest.options"
              :key="option.key"
              :variant="isNegativeOption(option) ? 'outline' : 'default'"
              :disabled="disabled"
              @click="submitOption(option.key)"
            >
              {{ option.title }}
            </ConfirmationAction>
          </ConfirmationActions>
        </div>
      </ConfirmationRequest>

      <CollapsibleContent
        v-if="permissionRequest"
        class="border-t bg-muted/20 p-3"
      >
        <PermissionRequestDetails :request="permissionRequest" />
      </CollapsibleContent>
    </Collapsible>

  </Confirmation>
</template>
