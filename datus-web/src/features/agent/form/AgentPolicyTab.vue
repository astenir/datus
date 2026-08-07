<script setup lang="ts">
import { computed } from "vue"
import { ShieldCheckIcon } from "@lucide/vue"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import type { AgentManagerController } from "@/composables/useAgentManager"
import SearchableMultiSelect from "@/features/shared/SearchableMultiSelect.vue"

const props = defineProps<{
  manager: AgentManagerController
}>()

const policyModeLabel = computed(() =>
  props.manager.form.value.toolPolicyMode === "allowlist" ? "仅允许所选工具" : "继承节点全部工具"
)
const personalMcpModeLabel = computed(() =>
  props.manager.form.value.personalMcpMode === "selectable"
    ? "允许用户在新会话选择"
    : "禁用"
)
</script>

<template>
  <div class="flex flex-col gap-5">
    <div>
      <h2 class="text-lg font-semibold">运行与工具策略</h2>
      <p class="mt-1 text-sm text-muted-foreground">
        这些限制由服务端在工具暴露和调用前同时执行，适用于内置与自定义 Agent。
      </p>
    </div>

    <Alert>
      <ShieldCheckIcon />
      <AlertTitle>服务端 Bash 已禁用</AlertTitle>
      <AlertDescription>
        Web 和企业会话不会加载服务端 Bash 工具，下方策略不能重新启用 Bash。其他工具仍遵循拒绝优先；关闭委派后 task 工具也会被移除。
      </AlertDescription>
    </Alert>

    <FieldGroup class="grid gap-5 md:grid-cols-2">
      <Field class="md:col-span-2">
        <FieldLabel for="agent-personal-mcp-mode">个人 MCP</FieldLabel>
        <Select v-model="props.manager.form.value.personalMcpMode">
          <SelectTrigger id="agent-personal-mcp-mode" class="w-full">
            <SelectValue>{{ personalMcpModeLabel }}</SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              <SelectItem value="disabled">禁用</SelectItem>
              <SelectItem value="selectable">允许用户在新会话选择</SelectItem>
            </SelectGroup>
          </SelectContent>
        </Select>
        <FieldDescription>
          这里仅开放选择能力，不绑定任何个人资源。用户在 Chat 新会话中选择自己的 MCP；企业 MCP 仍在“扩展能力”中静态绑定。
        </FieldDescription>
      </Field>

      <Field class="md:col-span-2">
        <FieldLabel for="agent-tool-policy-mode">工具策略</FieldLabel>
        <Select v-model="props.manager.form.value.toolPolicyMode">
          <SelectTrigger
            id="agent-tool-policy-mode"
            class="w-full"
          >
            <SelectValue>{{ policyModeLabel }}</SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              <SelectItem value="allowlist">仅允许所选工具</SelectItem>
              <SelectItem value="inherit">继承节点全部工具</SelectItem>
            </SelectGroup>
          </SelectContent>
        </Select>
        <FieldDescription>建议企业自定义 Chat 使用允许列表。</FieldDescription>
      </Field>

      <Field
        v-if="props.manager.form.value.toolPolicyMode === 'allowlist'"
        class="md:col-span-2"
      >
        <FieldLabel>允许工具</FieldLabel>
        <SearchableMultiSelect
          :options="props.manager.toolOptions.value"
          :selected-values="props.manager.selectedTools.value"
          placeholder="选择 Agent 可以调用的工具"
          search-placeholder="搜索工具名称或分类..."
          empty-text="未允许任何工具"
          no-results-text="没有匹配工具"
          @toggle="props.manager.toggleListFieldValue('toolsText', $event)"
        />
        <FieldDescription>允许列表模式下，未选中的工具不会暴露给模型。</FieldDescription>
      </Field>

      <Field class="md:col-span-2">
        <FieldLabel>拒绝工具</FieldLabel>
        <SearchableMultiSelect
          :options="props.manager.deniedToolOptions.value"
          :selected-values="props.manager.deniedTools.value"
          placeholder="选择必须禁止的工具"
          search-placeholder="搜索工具名称或分类..."
          empty-text="未设置额外拒绝规则"
          no-results-text="没有匹配工具"
          @toggle="props.manager.toggleListFieldValue('deniedToolsText', $event)"
        />
        <FieldDescription>
          可使用分类通配规则，例如 filesystem_tools.* 或 bash_tools.*；Web 和企业会话即使移除 Bash 拒绝规则仍保持禁用。
        </FieldDescription>
      </Field>

      <Field
        orientation="horizontal"
        class="md:col-span-2"
      >
        <div class="flex-1">
          <FieldLabel for="agent-subagent-delegation">允许委派其他 Agent</FieldLabel>
          <FieldDescription>关闭后服务端会移除 task 工具，避免通过子 Agent 绕过当前策略。</FieldDescription>
        </div>
        <Switch
          id="agent-subagent-delegation"
          v-model="props.manager.form.value.allowSubagentDelegation"
        />
      </Field>

      <Field
        v-if="props.manager.form.value.allowSubagentDelegation"
        class="md:col-span-2"
      >
        <FieldLabel>允许委派的 Agent</FieldLabel>
        <SearchableMultiSelect
          :options="props.manager.subagentOptions.value"
          :selected-values="props.manager.form.value.allowedSubagentIds"
          placeholder="选择可委派的 Agent"
          search-placeholder="搜索 Agent..."
          empty-text="未设置精确白名单"
          no-results-text="没有匹配 Agent"
          @toggle="props.manager.toggleAllowedSubagent"
        />
        <FieldDescription>被委派 Agent 仍会再次检查自己的 ACL 和工具策略。</FieldDescription>
      </Field>
    </FieldGroup>
  </div>
</template>
