<script setup lang="ts">
import { computed } from "vue"
import type { AgentManagerController } from "@/composables/useAgentManager"
import { promptSourceLabel } from "@/features/agent/form/promptSource"
import { formatDate } from "@/lib/utils"

const props = defineProps<{
  manager: AgentManagerController
}>()

function agentSourceLabel(source: string | null | undefined) {
  if (source === "builtin") return "系统内置"
  if (source === "enterprise") return "企业自定义"
  return source?.trim() || "-"
}

function listSummary(items: readonly string[] | null | undefined) {
  return items?.length ? items.join(", ") : "-"
}

function formatAcl(
  acl: {
    visibility?: string | null
    allowed_roles?: readonly string[]
    allowed_user_ids?: readonly string[]
  } | null | undefined,
) {
  if (!acl) return "-"

  const roles = listSummary(acl.allowed_roles)
  const users = listSummary(acl.allowed_user_ids)
  return `${acl.visibility || "private"} / roles: ${roles} / users: ${users}`
}

function formatJson(value: Record<string, unknown> | null | undefined) {
  if (!value || Object.keys(value).length === 0) return "-"
  return JSON.stringify(value, null, 2)
}

const detailRows = computed(() => {
  const agent = props.manager.selectedAgent.value
  if (!agent) return []

  return [
    ["Agent ID", agent.agent_id],
    ["来源", agentSourceLabel(agent.source)],
    ["所有者", agent.owner_user_id],
    ["数据源", agent.datasource_id],
    ["Artifact", agent.artifact_slug],
    ["创建时间", formatDate(agent.created_at) || null],
    ["更新时间", formatDate(agent.updated_at) || null],
    ["模板", agent.prompt_template_name],
    ["提示词来源", promptSourceLabel(agent.prompt_source)],
    ["配置版本", agent.configured_prompt_version],
    ["生效版本", agent.resolved_prompt_version ?? agent.prompt_version],
    ["激活版本 ID", agent.active_prompt_version_id],
    ["正文修订", agent.prompt_revision],
    ["语言", agent.prompt_language],
    ["MCP", listSummary(agent.mcp)],
    ["Skills", listSummary(agent.skills)],
  ] satisfies Array<[string, string | null | undefined]>
})

const aclText = computed(() => formatAcl(props.manager.selectedAgent.value?.acl))
const scopedContextText = computed(() => formatJson(props.manager.selectedAgent.value?.scoped_context))
</script>

<template>
  <div class="flex flex-col gap-5">
    <div>
      <h2 class="text-lg font-semibold">元数据</h2>
      <p class="mt-1 text-sm text-muted-foreground">查看后端保存的标识、模板、ACL 和原始作用域信息。</p>
    </div>

    <dl
      v-if="props.manager.selectedAgent.value"
      class="grid gap-x-6 gap-y-4 md:grid-cols-2"
    >
      <div
        v-for="[label, value] in detailRows"
        :key="label"
        class="min-w-0"
      >
        <dt class="text-xs font-medium text-muted-foreground">{{ label }}</dt>
        <dd class="mt-1 whitespace-pre-wrap break-words text-sm leading-6">{{ value || "-" }}</dd>
      </div>
      <div class="min-w-0 md:col-span-2">
        <dt class="text-xs font-medium text-muted-foreground">ACL</dt>
        <dd class="mt-1 whitespace-pre-wrap break-words text-sm leading-6">{{ aclText }}</dd>
      </div>
      <div class="min-w-0 md:col-span-2">
        <dt class="text-xs font-medium text-muted-foreground">Scoped Context</dt>
        <dd>
          <pre class="mt-1 max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-md bg-muted p-3 text-xs leading-5">{{ scopedContextText }}</pre>
        </dd>
      </div>
    </dl>

    <p
      v-else
      class="text-sm text-muted-foreground"
    >
      创建 Agent 后将生成标识、所有者、时间和模板元数据。
    </p>
  </div>
</template>
