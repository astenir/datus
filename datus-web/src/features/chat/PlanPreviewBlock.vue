<script setup lang="ts">
import {
  Plan,
  PlanAction,
  PlanContent,
  PlanDescription,
  PlanHeader,
  PlanTitle,
  PlanTrigger,
} from "@/components/ai-elements/plan"
import { MessageResponse } from "@/components/ai-elements/message"

defineProps<{
  content: string
}>()
</script>

<template>
  <Plan default-open>
    <PlanHeader>
      <div class="flex min-w-0 flex-col gap-1">
        <PlanTitle>规划方案</PlanTitle>
        <PlanDescription>本次规划生成的执行步骤</PlanDescription>
      </div>
      <PlanAction>
        <PlanTrigger />
      </PlanAction>
    </PlanHeader>
    <PlanContent>
      <MessageResponse :content="content" />
    </PlanContent>
  </Plan>
</template>
