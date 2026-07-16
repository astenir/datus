<script setup lang="ts">
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Textarea } from "@/components/ui/textarea"
import type { AgentManagerController } from "@/composables/useAgentManager"

const props = defineProps<{
  manager: AgentManagerController
  readonly: boolean
}>()
</script>

<template>
  <div class="flex flex-col gap-5">
    <div>
      <h2 class="text-lg font-semibold">提示与约束</h2>
      <p class="mt-1 text-sm text-muted-foreground">定义 Agent 的系统指令和必须遵守的执行规则。</p>
    </div>

    <FieldGroup class="gap-5">
      <Field>
        <FieldLabel for="agent-prompt">系统提示词</FieldLabel>
        <Textarea
          id="agent-prompt"
          v-model="props.manager.form.value.promptTemplate"
          class="min-h-64 font-mono text-xs leading-6"
          :readonly="props.readonly"
          spellcheck="false"
          placeholder="描述 Agent 的角色、目标和执行方式"
        />
        <FieldDescription>提示词会作为该 Agent 的主要行为指令。</FieldDescription>
      </Field>

      <Field>
        <FieldLabel for="agent-rules">规则</FieldLabel>
        <Textarea
          id="agent-rules"
          v-model="props.manager.form.value.rulesText"
          class="min-h-32 font-mono text-xs leading-6"
          :readonly="props.readonly"
          placeholder="仅查询授权数据源"
        />
        <FieldDescription>支持英文逗号或换行分隔。</FieldDescription>
      </Field>
    </FieldGroup>
  </div>
</template>
