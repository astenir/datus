<script setup lang="ts">
import { computed, ref } from "vue"
import { CheckIcon, SendHorizontalIcon } from "@lucide/vue"
import {
  Confirmation,
  ConfirmationAction,
  ConfirmationActions,
  ConfirmationRequest,
  ConfirmationTitle,
} from "@/components/ai-elements/confirmation"
import { Suggestion, Suggestions } from "@/components/ai-elements/suggestion"
import { Button } from "@/components/ui/button"
import { Field, FieldLabel } from "@/components/ui/field"
import { Textarea } from "@/components/ui/textarea"
import type { MessageBlock, UserInteractionRequest } from "@/types"

type UserInteractionBlockData = Extract<MessageBlock, { type: "user-interaction" }>
type UserInteractionOption = UserInteractionRequest["options"][number]

const props = withDefaults(defineProps<{
  block: UserInteractionBlockData
  disabled?: boolean
}>(), {
  disabled: false,
})

const emit = defineEmits<{
  submit: [interactionKey: string, answers: string[][]]
}>()

const selectedAnswers = ref<Record<number, readonly string[]>>({})
const freeTextAnswers = ref<Record<number, string>>({})

const approval = computed(() => ({ id: props.block.interactionKey }))
const singleRequest = computed(() => props.block.requests[0] ?? null)
const hasRequests = computed(() => props.block.requests.length > 0)
const isQuickConfirm = computed(() => {
  const request = singleRequest.value
  return Boolean(
    request &&
      props.block.requests.length === 1 &&
      !request.allowFreeText &&
      !request.multiSelect &&
      request.options.length > 0 &&
      (props.block.actionType.toLowerCase() === "confirm" || hasYesNoOptions(request.options)),
  )
})
const isQuickSingleChoice = computed(() => {
  const request = singleRequest.value
  return Boolean(
    request &&
      props.block.requests.length === 1 &&
      !isQuickConfirm.value &&
      !request.allowFreeText &&
      !request.multiSelect &&
      request.options.length > 0,
  )
})
const canSubmitAll = computed(() =>
  hasRequests.value &&
  props.block.requests.every((request, index) => answerForRequest(index, request).length > 0),
)

function normalizeKey(value: string) {
  return value.trim().toLowerCase()
}

function hasYesNoOptions(options: readonly UserInteractionOption[]) {
  if (options.length !== 2) return false

  return options.some((option) => isPositiveOption(option)) &&
    options.some((option) => isNegativeOption(option))
}

function isPositiveOption(option: UserInteractionOption) {
  const key = normalizeKey(option.key)
  const title = normalizeKey(option.title)
  return ["y", "yes", "true", "ok", "confirm", "approve", "allow", "accept"].includes(key) ||
    ["yes", "ok", "confirm", "approve", "allow", "accept", "确认", "同意", "允许"].includes(title)
}

function isNegativeOption(option: UserInteractionOption) {
  const key = normalizeKey(option.key)
  const title = normalizeKey(option.title)
  return ["n", "no", "false", "cancel", "deny", "reject"].includes(key) ||
    ["no", "cancel", "deny", "reject", "取消", "拒绝"].includes(title)
}

function selectedFor(index: number) {
  return selectedAnswers.value[index] ?? []
}

function isSelected(index: number, key: string) {
  return selectedFor(index).includes(key)
}

function setSingle(index: number, key: string) {
  selectedAnswers.value = { ...selectedAnswers.value, [index]: [key] }
}

function toggleMulti(index: number, key: string) {
  const current = selectedFor(index)
  const next = current.includes(key)
    ? current.filter((item) => item !== key)
    : [...current, key]
  selectedAnswers.value = { ...selectedAnswers.value, [index]: next }
}

function setFreeText(index: number, value: string | number) {
  freeTextAnswers.value = { ...freeTextAnswers.value, [index]: String(value) }
}

function answerForRequest(index: number, request: UserInteractionRequest) {
  const selected = selectedFor(index)
  const freeText = request.allowFreeText ? freeTextAnswers.value[index]?.trim() : ""

  return freeText ? [...selected, freeText] : [...selected]
}

function submitOption(key: string) {
  if (props.disabled) return
  emit("submit", props.block.interactionKey, [[key]])
}

function submitAll() {
  if (props.disabled || !canSubmitAll.value) return

  const answers = props.block.requests.map((request, index) => answerForRequest(index, request))
  emit("submit", props.block.interactionKey, answers)
}
</script>

<template>
  <Confirmation
    v-if="isQuickConfirm && singleRequest"
    :approval="approval"
    state="approval-requested"
  >
    <ConfirmationRequest>
      <ConfirmationTitle>{{ singleRequest.content }}</ConfirmationTitle>
    </ConfirmationRequest>
    <ConfirmationActions>
      <ConfirmationAction
        v-for="option in singleRequest.options"
        :key="option.key"
        :disabled="disabled"
        :variant="isNegativeOption(option) ? 'outline' : 'default'"
        @click="submitOption(option.key)"
      >
        {{ option.title }}
      </ConfirmationAction>
    </ConfirmationActions>
  </Confirmation>

  <div
    v-else-if="isQuickSingleChoice && singleRequest"
    class="flex flex-col gap-2 rounded-lg border bg-muted/20 p-3"
  >
    <p class="text-sm leading-6 text-foreground">
      {{ singleRequest.content }}
    </p>
    <Suggestions>
      <Suggestion
        v-for="option in singleRequest.options"
        :key="option.key"
        :suggestion="option.title"
        :disabled="disabled"
        @click="submitOption(option.key)"
      />
    </Suggestions>
  </div>

  <div
    v-else-if="hasRequests"
    class="flex flex-col gap-4 rounded-lg border bg-muted/20 p-3"
  >
    <div
      v-for="(request, requestIndex) in block.requests"
      :key="`${block.interactionKey}-${requestIndex}`"
      class="flex flex-col gap-3"
    >
      <p class="text-sm leading-6 text-foreground">
        {{ request.content }}
      </p>

      <div
        v-if="request.options.length"
        class="flex flex-wrap gap-2"
      >
        <Button
          v-for="option in request.options"
          :key="option.key"
          type="button"
          size="sm"
          :variant="isSelected(requestIndex, option.key) ? 'default' : 'outline'"
          :disabled="disabled"
          @click="request.multiSelect ? toggleMulti(requestIndex, option.key) : setSingle(requestIndex, option.key)"
        >
          <CheckIcon
            v-if="isSelected(requestIndex, option.key)"
            data-icon="inline-start"
          />
          {{ option.title }}
        </Button>
      </div>

      <Field
        v-if="request.allowFreeText"
        class="gap-2"
      >
        <FieldLabel :for="`${block.interactionKey}-${requestIndex}-free-text`">
          补充输入
        </FieldLabel>
        <Textarea
          :id="`${block.interactionKey}-${requestIndex}-free-text`"
          :model-value="freeTextAnswers[requestIndex] ?? ''"
          :disabled="disabled"
          class="min-h-20"
          placeholder="输入内容"
          @update:model-value="(value) => setFreeText(requestIndex, value)"
        />
      </Field>
    </div>

    <div class="flex justify-end">
      <Button
        type="button"
        size="sm"
        :disabled="disabled || !canSubmitAll"
        @click="submitAll"
      >
        <SendHorizontalIcon data-icon="inline-start" />
        提交
      </Button>
    </div>
  </div>
</template>
