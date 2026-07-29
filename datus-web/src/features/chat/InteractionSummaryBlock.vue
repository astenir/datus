<script setup lang="ts">
import { computed } from "vue"
import {
  CheckCircle2Icon,
  ChevronDownIcon,
  CircleAlertIcon,
  MessageSquareTextIcon,
  XCircleIcon,
} from "@lucide/vue"
import { MessageResponse } from "@/components/ai-elements/message"
import { Badge } from "@/components/ui/badge"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { Separator } from "@/components/ui/separator"
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
const firstEntry = computed(() => summaryEntries.value[0])
const summaryPrompt = computed(() => {
  const entry = firstEntry.value
  return entry ? requestContent(entry.request) : statusMeta.value.description
})
const summaryAnswer = computed(() => {
  const entry = firstEntry.value
  return entry ? answerLabel(entry.answer, entry.request) : ""
})

function statusDetails(status: InteractionSummaryStatus) {
  if (status === "answered") {
    return {
      label: "已回答",
      description: "本次交互已提交回答",
      icon: CheckCircle2Icon,
      variant: "secondary" as const,
    }
  }
  if (status === "cancelled") {
    return {
      label: "已取消",
      description: "本次交互已取消",
      icon: XCircleIcon,
      variant: "outline" as const,
    }
  }
  if (status === "failed") {
    return {
      label: "失败",
      description: "本次交互未完成",
      icon: CircleAlertIcon,
      variant: "destructive" as const,
    }
  }
  return {
    label: "状态未知",
    description: "未记录本次交互的最终状态",
    icon: MessageSquareTextIcon,
    variant: "outline" as const,
  }
}

function isMarkdown(request: UserInteractionRequest) {
  return request.contentType?.toLowerCase() === "markdown"
}

function requestTitle(request: UserInteractionRequest, index: number) {
  return request.title || (props.block.requests.length > 1 ? `问题 ${index + 1}` : "交互请求")
}

function requestContent(request: UserInteractionRequest) {
  return request.content || request.title || "交互请求"
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
  <Collapsible
    class="group overflow-hidden rounded-lg border"
    data-testid="interaction-summary"
  >
    <CollapsibleTrigger
      class="grid w-full min-w-0 grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-1 px-3 py-2.5 text-left"
      data-testid="interaction-summary-trigger"
    >
      <div
        class="col-start-1 row-start-1 flex min-w-0 items-center gap-2"
        data-testid="interaction-summary-primary-row"
      >
        <MessageSquareTextIcon
          class="size-4 shrink-0 text-muted-foreground"
          data-testid="interaction-summary-leading-icon"
          aria-hidden="true"
        />
        <span
          class="min-w-0 truncate text-sm font-medium text-foreground"
          data-testid="interaction-summary-title"
        >
          补充信息
        </span>
        <Badge :variant="statusMeta.variant">
          <component
            :is="statusMeta.icon"
            aria-hidden="true"
          />
          {{ statusMeta.label }}
        </Badge>
      </div>

      <ChevronDownIcon
        class="col-start-2 row-start-1 size-4 self-center text-muted-foreground transition-transform group-data-[state=open]:rotate-180 motion-reduce:transition-none"
        aria-hidden="true"
      />

      <p
        class="col-start-1 row-start-2 line-clamp-2 pl-6 text-xs leading-5 text-muted-foreground"
        data-testid="interaction-summary-description"
      >
        {{ summaryPrompt }}
      </p>
      <p
        v-if="summaryAnswer"
        class="col-start-1 row-start-3 truncate pl-6 text-xs text-foreground"
      >
        <span class="text-muted-foreground">回答：</span>{{ summaryAnswer }}
      </p>
    </CollapsibleTrigger>

    <CollapsibleContent>
      <Separator />
      <div class="flex flex-col gap-4 p-3">
        <div class="flex min-w-0 items-center gap-2 text-xs text-muted-foreground">
          <component
            :is="statusMeta.icon"
            class="size-4 shrink-0 text-muted-foreground"
            aria-hidden="true"
          />
          {{ statusMeta.description }}
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
          v-if="looseAnswers.length"
          class="flex flex-col gap-2 border-t border-border/70 pt-3"
        >
          <div class="text-xs font-medium text-muted-foreground">
            补充回答
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
    </CollapsibleContent>
  </Collapsible>
</template>
