<script setup lang="ts">
import { computed } from "vue"
import {
  CheckCircle2Icon,
  CircleAlertIcon,
  MessageSquareTextIcon,
  XCircleIcon,
} from "@lucide/vue"
import { MessageResponse } from "@/components/ai-elements/message"
import { Badge } from "@/components/ui/badge"
import type {
  InteractionSummaryAnswer,
  InteractionSummaryStatus,
  MessageBlock,
  UserInteractionRequest,
} from "@/types"

type InteractionSummaryBlockData = Extract<MessageBlock, { type: "interaction-summary" }>
type SummaryEntry = {
  id: string
  request: UserInteractionRequest
  answer?: InteractionSummaryAnswer
}

const props = defineProps<{
  block: InteractionSummaryBlockData
}>()

const statusMeta = computed(() => statusDetails(props.block.status))
const hasRequests = computed(() => props.block.requests.length > 0)
const summaryEntries = computed<SummaryEntry[]>(() =>
  props.block.requests.map((request, index) => ({
    id: `${index}-${request.title ?? request.content}`,
    request,
    answer: answerForRequest(request) ?? props.block.answers[index],
  })),
)
const usedAnswers = computed(() => {
  const answers = summaryEntries.value
    .map((entry) => entry.answer)
    .filter((answer): answer is InteractionSummaryAnswer => Boolean(answer))
  return new Set(answers)
})
const looseAnswers = computed(() =>
  props.block.answers.filter((answer) => {
    if (!hasRequests.value) return true
    return !usedAnswers.value.has(answer)
  }),
)

function statusDetails(status: InteractionSummaryStatus) {
  if (status === "answered") {
    return {
      label: "已回答",
      description: "Answered",
      icon: CheckCircle2Icon,
      variant: "secondary" as const,
    }
  }
  if (status === "cancelled") {
    return {
      label: "已取消",
      description: "Cancelled",
      icon: XCircleIcon,
      variant: "outline" as const,
    }
  }
  if (status === "failed") {
    return {
      label: "失败",
      description: "Failed",
      icon: CircleAlertIcon,
      variant: "destructive" as const,
    }
  }
  return {
    label: "Interaction",
    description: "Interaction",
    icon: MessageSquareTextIcon,
    variant: "outline" as const,
  }
}

function isMarkdown(request: UserInteractionRequest) {
  return request.contentType?.toLowerCase() === "markdown"
}

function requestTitle(request: UserInteractionRequest, index: number) {
  return request.title || (props.block.requests.length > 1 ? `Question ${index + 1}` : "Interaction")
}

function requestContent(request: UserInteractionRequest) {
  return request.content || request.title || "Interaction"
}

function optionTitle(request: UserInteractionRequest, key: string) {
  return request.options.find((option) => option.key === key)?.title ?? key
}

function isDefaultChoice(request: UserInteractionRequest, key: string) {
  return Boolean(request.defaultChoice && request.defaultChoice === key)
}

function isAnswerForRequest(answer: InteractionSummaryAnswer, request: UserInteractionRequest) {
  const question = answer.question.trim()
  return Boolean(question && (question === request.content || question === request.title))
}

function answerForRequest(request: UserInteractionRequest) {
  return props.block.answers.find((answer) => isAnswerForRequest(answer, request))
}

function answerValues(answer: InteractionSummaryAnswer | undefined) {
  if (!answer) return []
  return Array.isArray(answer.answer) ? answer.answer : [answer.answer]
}

function answerLabel(answer: InteractionSummaryAnswer | undefined, request?: UserInteractionRequest) {
  const values = answerValues(answer).filter(Boolean)
  if (values.length === 0) return ""
  if (!request) return values.join("、")
  return values.map((value) => optionTitle(request, value)).join("、")
}
</script>

<template>
  <div class="flex flex-col gap-4 rounded-lg border bg-muted/20 p-3">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <div class="flex min-w-0 items-center gap-2">
        <component
          :is="statusMeta.icon"
          class="size-4 shrink-0 text-muted-foreground"
          aria-hidden="true"
        />
        <div class="min-w-0">
          <div class="truncate text-sm font-medium text-foreground">
            {{ hasRequests ? "交互历史" : "Interaction" }}
          </div>
          <div class="truncate text-xs text-muted-foreground">
            {{ block.actionType || "interaction" }}
          </div>
        </div>
      </div>
      <Badge :variant="statusMeta.variant">
        {{ statusMeta.label }}
      </Badge>
    </div>

    <div
      v-if="hasRequests"
      class="flex flex-col gap-4"
    >
      <section
        v-for="(entry, index) in summaryEntries"
        :key="entry.id"
        class="flex flex-col gap-3 border-t border-border/70 pt-3 first:border-t-0 first:pt-0"
      >
        <div class="flex flex-col gap-1">
          <div class="text-xs font-medium text-muted-foreground">
            {{ requestTitle(entry.request, index) }}
          </div>
          <MessageResponse
            v-if="isMarkdown(entry.request)"
            :content="requestContent(entry.request)"
            class="text-sm leading-6 text-foreground [&_p]:text-foreground [&_strong]:font-semibold [&_strong]:text-foreground"
          />
          <p
            v-else
            class="text-sm leading-6 text-foreground"
          >
            {{ requestContent(entry.request) }}
          </p>
        </div>

        <div
          v-if="entry.request.options.length"
          class="flex flex-wrap gap-2"
        >
          <Badge
            v-for="option in entry.request.options"
            :key="option.key"
            variant="outline"
            class="max-w-full whitespace-normal text-left"
          >
            <span class="truncate">{{ option.title || option.key }}</span>
            <span
              v-if="isDefaultChoice(entry.request, option.key)"
              class="text-muted-foreground"
            >
              默认
            </span>
          </Badge>
        </div>

        <div
          v-if="answerLabel(entry.answer, entry.request)"
          class="rounded-md bg-background/70 px-3 py-2 text-sm leading-6"
        >
          <span class="font-medium text-muted-foreground">回答：</span>
          <span class="text-foreground">{{ answerLabel(entry.answer, entry.request) }}</span>
        </div>
      </section>
    </div>

    <div
      v-else
      class="text-sm leading-6 text-muted-foreground"
    >
      {{ statusMeta.description }}
    </div>

    <div
      v-if="looseAnswers.length"
      class="flex flex-col gap-2 border-t border-border/70 pt-3"
    >
      <div class="text-xs font-medium text-muted-foreground">
        Answers
      </div>
      <div
        v-for="(answer, answerIndex) in looseAnswers"
        :key="`${answer.question}-${answerIndex}`"
        class="rounded-md bg-background/70 px-3 py-2 text-sm leading-6"
      >
        <span class="font-medium text-muted-foreground">{{ answer.question }}：</span>
        <span class="text-foreground">{{ answerLabel(answer) || "未记录" }}</span>
      </div>
    </div>

    <p
      v-if="block.error"
      class="rounded-md bg-destructive/10 px-3 py-2 text-sm leading-6 text-destructive"
    >
      {{ block.error }}
    </p>
  </div>
</template>
