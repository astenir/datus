<script setup lang="ts">
import { computed } from "vue"
import { Badge } from "@/components/ui/badge"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import type { AgentManagerController } from "@/composables/useAgentManager"
import AgentPromptVersionControl from "@/features/agent/form/AgentPromptVersionControl.vue"
import { promptSourceLabel } from "@/features/agent/form/promptSource"

const props = defineProps<{
  manager: AgentManagerController
  readonly: boolean
}>()

const isBuiltin = computed(() => props.manager.selectedIsBuiltin.value)
const isCreate = computed(() => props.manager.formMode.value === "create")
const sourceLabel = computed(() =>
  isCreate.value
    ? "企业自定义"
    : promptSourceLabel(props.manager.selectedAgent.value?.prompt_source)
)
const promptDescription = computed(() => {
  if (isCreate.value) return "提示词会作为该 Agent 的主要行为指令；创建后将保存为首个不可变版本。"
  if (!isBuiltin.value) return "历史版本保持只读；如需修改正文，请基于当前预览内容新建版本。"

  const source = props.manager.selectedAgent.value?.prompt_source
  if (source === "user_override") {
    return "当前原始模板来自运行时 agent.home/template 的同名用户覆盖；内置 Agent 定义仍为只读。"
  }
  if (source === "runtime") {
    return "当前原始模板来自运行时 Agent 配置；内置 Agent 定义仍为只读。"
  }
  return "当前原始模板由当前部署的仓库内置版本提供；如需定制，请复制为企业 Agent。"
})
const displayedPrompt = computed(() =>
  props.manager.promptVersions.selectedVersion.value?.prompt_template
  ?? props.manager.form.value.promptTemplate
)
</script>

<template>
  <div class="flex flex-col gap-5">
    <div>
      <h2 class="text-lg font-semibold">提示与约束</h2>
      <p class="mt-1 text-sm text-muted-foreground">定义 Agent 的系统指令和必须遵守的执行规则。</p>
    </div>

    <FieldGroup class="gap-5">
      <Field>
        <div class="flex flex-wrap items-center gap-2">
          <FieldLabel for="agent-prompt">系统提示词</FieldLabel>
          <Badge v-if="isBuiltin || isCreate" :variant="isBuiltin ? 'outline' : 'secondary'">
            {{ sourceLabel }}
          </Badge>
          <Badge v-if="isBuiltin" variant="outline">v{{ props.manager.form.value.promptVersion }}</Badge>
          <Input
            v-else-if="isCreate"
            id="agent-prompt-version"
            v-model="props.manager.form.value.promptVersion"
            aria-label="提示词版本标识"
            class="h-7 w-32 text-xs"
            maxlength="40"
            placeholder="1.0"
          />
        </div>
        <AgentPromptVersionControl
          v-if="!isBuiltin && !isCreate"
          :versions="props.manager.promptVersions.versions.value"
          :active-version-id="props.manager.promptVersions.activeVersionId.value"
          :selected-version-id="props.manager.promptVersions.selectedVersionId.value"
          :selected-version="props.manager.promptVersions.selectedVersion.value"
          :active-version="props.manager.promptVersions.activeVersion.value"
          :loading="props.manager.promptVersions.loading.value"
          :detail-loading="props.manager.promptVersions.detailLoading.value"
          :creating="props.manager.promptVersions.creating.value"
          :activating="props.manager.promptVersions.activating.value"
          :error="props.manager.promptVersions.error.value"
          :prompt-source="props.manager.selectedAgent.value?.prompt_source"
          :base-prompt-content="props.manager.form.value.promptTemplate"
          :base-prompt-language="props.manager.selectedAgent.value?.prompt_language ?? 'en'"
          :base-prompt-version="props.manager.selectedAgent.value?.resolved_prompt_version ?? props.manager.form.value.promptVersion"
          :base-prompt-revision="props.manager.selectedAgent.value?.prompt_revision"
          @select="props.manager.selectPromptVersion"
          @create="props.manager.createPromptVersion"
          @activate="props.manager.activatePromptVersion"
        />
        <Textarea
          v-if="isCreate"
          id="agent-prompt"
          v-model="props.manager.form.value.promptTemplate"
          class="min-h-64 font-mono text-xs leading-6"
          :readonly="props.readonly"
          spellcheck="false"
          placeholder="描述 Agent 的角色、目标和执行方式"
        />
        <Textarea
          v-else
          id="agent-prompt"
          :model-value="displayedPrompt"
          class="min-h-64 font-mono text-xs leading-6"
          readonly
          spellcheck="false"
        />
        <FieldDescription>
          {{ promptDescription }}
        </FieldDescription>
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
