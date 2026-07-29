<script setup lang="ts">
import { computed, shallowRef } from "vue"
import { CheckIcon, SendHorizontalIcon, XIcon } from "@lucide/vue"
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
import { Textarea } from "@/components/ui/textarea"
import type { PlanConfirmationDisplayBlock } from "@/types"

const props = withDefaults(defineProps<{
  block: PlanConfirmationDisplayBlock
  disabled?: boolean
}>(), {
  disabled: false,
})

const emit = defineEmits<{
  submit: [interactionKey: string, answers: string[][]]
}>()

const feedback = shallowRef("")
const interactionKey = computed(() => props.block.interaction.interactionKey)
const canSubmitFeedback = computed(() => feedback.value.trim().length > 0)

function submitChoice(choice: "confirm" | "cancel") {
  if (props.disabled) return
  emit("submit", interactionKey.value, [[choice]])
}

function submitFeedback() {
  const value = feedback.value.trim()
  if (props.disabled || !value) return
  emit("submit", interactionKey.value, [[value]])
}
</script>

<template>
  <Plan default-open>
    <PlanHeader>
      <div class="flex min-w-0 flex-col gap-1">
        <PlanTitle>计划待确认</PlanTitle>
        <PlanDescription>审阅执行步骤；可以确认执行、取消规划，或提交修改意见。</PlanDescription>
      </div>
      <PlanAction>
        <PlanTrigger />
      </PlanAction>
    </PlanHeader>

    <PlanContent>
      <MessageResponse :content="block.content" />
    </PlanContent>

    <PlanFooter class="flex flex-col items-stretch gap-3 border-t">
      <template v-if="!disabled">
        <Field class="gap-2">
          <FieldLabel :for="`${interactionKey}-feedback`">
            修改意见
          </FieldLabel>
          <Textarea
            :id="`${interactionKey}-feedback`"
            v-model="feedback"
            class="min-h-20"
            placeholder="例如：补充风险检查，或调整执行顺序"
          />
        </Field>

        <div class="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:justify-end">
          <Button
            type="button"
            variant="outline"
            class="w-full sm:w-auto"
            @click="submitChoice('cancel')"
          >
            <XIcon data-icon="inline-start" />
            取消规划
          </Button>
          <Button
            type="button"
            variant="secondary"
            class="w-full sm:w-auto"
            :disabled="!canSubmitFeedback"
            @click="submitFeedback"
          >
            <SendHorizontalIcon data-icon="inline-start" />
            提交修改意见
          </Button>
          <Button
            type="button"
            class="w-full sm:w-auto"
            @click="submitChoice('confirm')"
          >
            <CheckIcon data-icon="inline-start" />
            确认并执行
          </Button>
        </div>
      </template>

      <Badge
        v-else
        variant="secondary"
        class="self-start"
      >
        已处理
      </Badge>
    </PlanFooter>
  </Plan>
</template>
