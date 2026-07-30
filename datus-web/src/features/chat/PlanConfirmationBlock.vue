<script setup lang="ts">
import { computed, shallowRef } from "vue"
import {
  CheckCircle2Icon,
  CheckIcon,
  CircleAlertIcon,
  MessageSquareTextIcon,
  SendHorizontalIcon,
  XCircleIcon,
  XIcon,
} from "@lucide/vue"
import {
  Plan,
  PlanAction,
  PlanContent,
  PlanDescription,
  PlanFooter,
  PlanHeader,
  PlanTitle,
  PlanTrigger,
} from "@/components/ai-elements/plan"
import { MessageResponse } from "@/components/ai-elements/message"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Field, FieldLabel } from "@/components/ui/field"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"
import type { PlanConfirmationDisplayBlock } from "@/types"

const props = withDefaults(defineProps<{
  block: PlanConfirmationDisplayBlock
  active?: boolean
  pending?: boolean
}>(), {
  active: true,
  pending: false,
})

const emit = defineEmits<{
  submit: [interactionKey: string, answers: string[][]]
}>()

const feedback = shallowRef("")
const interactionKey = computed(() => props.block.interaction?.interactionKey ?? "")
const canSubmitFeedback = computed(() => feedback.value.trim().length > 0)
const canInteract = computed(() => Boolean(props.active && props.block.interaction && !props.block.outcome))
const outcomeMeta = computed(() => {
  const outcome = props.block.outcome
  if (outcome?.status === "confirmed") {
    return {
      title: "执行计划",
      description: "计划已确认，执行队列正在启动。",
      badge: "已确认",
      variant: "secondary" as const,
      icon: CheckCircle2Icon,
    }
  }
  if (outcome?.status === "cancelled") {
    return {
      title: "执行计划",
      description: "规划已取消，不会执行其中步骤。",
      badge: "已取消",
      variant: "outline" as const,
      icon: XCircleIcon,
    }
  }
  if (outcome?.status === "feedback") {
    return {
      title: "执行计划",
      description: "已提交修改意见，正在等待修订后的计划。",
      badge: "待修订",
      variant: "secondary" as const,
      icon: MessageSquareTextIcon,
    }
  }
  if (outcome?.status === "error") {
    return {
      title: "执行计划",
      description: outcome.error || "计划确认失败，请重试。",
      badge: "确认失败",
      variant: "destructive" as const,
      icon: CircleAlertIcon,
    }
  }
  if (!canInteract.value) {
    return {
      title: "执行计划",
      description: "此计划确认已失效，请以最新计划或当前执行队列为准。",
      badge: "已失效",
      variant: "outline" as const,
      icon: CircleAlertIcon,
    }
  }
  return null
})
const planTitle = computed(() => outcomeMeta.value?.title ?? "计划待确认")
const planDescription = computed(() => outcomeMeta.value?.description ?? "审阅执行步骤；可以确认执行、取消规划，或提交修改意见。")

function submitChoice(choice: "confirm" | "cancel") {
  if (!canInteract.value || props.pending || !interactionKey.value) return
  emit("submit", interactionKey.value, [[choice]])
}

function submitFeedback() {
  const value = feedback.value.trim()
  if (!canInteract.value || props.pending || !interactionKey.value || !value) return
  emit("submit", interactionKey.value, [[value]])
}
</script>

<template>
  <Plan default-open>
    <PlanHeader>
      <div class="flex min-w-0 flex-col gap-1">
        <div class="flex min-w-0 flex-wrap items-center gap-2">
          <PlanTitle>{{ planTitle }}</PlanTitle>
          <Badge
            v-if="outcomeMeta"
            :variant="outcomeMeta.variant"
            role="status"
          >
            <component
              :is="outcomeMeta.icon"
              class="size-3"
              aria-hidden="true"
            />
            {{ outcomeMeta.badge }}
          </Badge>
        </div>
        <PlanDescription>{{ planDescription }}</PlanDescription>
      </div>
      <PlanAction>
        <PlanTrigger />
      </PlanAction>
    </PlanHeader>

    <PlanContent>
      <MessageResponse :content="block.content" />
    </PlanContent>

    <PlanFooter
      v-if="canInteract || (block.outcome?.status === 'feedback' && block.outcome.feedback)"
      class="flex flex-col items-stretch gap-3 border-t"
    >
      <template v-if="canInteract">
        <div
          v-if="pending"
          class="flex items-center gap-2 rounded-md bg-muted px-3 py-2 text-sm text-muted-foreground"
          role="status"
          aria-live="polite"
        >
          <Spinner aria-hidden="true" />
          正在提交计划决定…
        </div>

        <Field class="gap-2">
          <FieldLabel :for="`${interactionKey}-feedback`">
            修改意见
          </FieldLabel>
          <Textarea
            :id="`${interactionKey}-feedback`"
            v-model="feedback"
            class="min-h-20"
            :disabled="pending"
            placeholder="例如：补充风险检查，或调整执行顺序"
          />
        </Field>

        <div class="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:justify-end">
          <Button
            type="button"
            variant="outline"
            class="w-full sm:w-auto"
            :disabled="pending"
            @click="submitChoice('cancel')"
          >
            <XIcon data-icon="inline-start" />
            取消规划
          </Button>
          <Button
            type="button"
            variant="secondary"
            class="w-full sm:w-auto"
            :disabled="pending || !canSubmitFeedback"
            @click="submitFeedback"
          >
            <SendHorizontalIcon data-icon="inline-start" />
            提交修改意见
          </Button>
          <Button
            type="button"
            class="w-full sm:w-auto"
            :disabled="pending"
            @click="submitChoice('confirm')"
          >
            <CheckIcon data-icon="inline-start" />
            确认并执行
          </Button>
        </div>
      </template>

      <div
        v-else-if="block.outcome?.status === 'feedback' && block.outcome.feedback"
        class="flex min-w-0 items-start gap-2 text-sm leading-6"
      >
        <MessageSquareTextIcon
          class="mt-1 size-4 shrink-0"
          aria-hidden="true"
        />
        <p class="min-w-0 rounded-md bg-muted px-3 py-2 text-foreground">
          {{ block.outcome.feedback }}
        </p>
      </div>
    </PlanFooter>
  </Plan>
</template>
