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
import AgentMultiOptionPicker from "@/features/agent/AgentMultiOptionPicker.vue"

const props = defineProps<{
  manager: AgentManagerController
}>()

const policyModeLabel = computed(() =>
  props.manager.form.value.toolPolicyMode === "allowlist" ? "仅允许所选工具" : "继承节点全部工具"
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
      <AlertTitle>拒绝规则优先</AlertTitle>
      <AlertDescription>
        即使工具同时出现在允许列表中，拒绝列表仍会阻止调用；关闭委派后 task 工具也会被移除。
      </AlertDescription>
    </Alert>

    <FieldGroup class="grid gap-5 md:grid-cols-2">
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
        <AgentMultiOptionPicker
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
        <AgentMultiOptionPicker
          :options="props.manager.toolOptions.value"
          :selected-values="props.manager.deniedTools.value"
          placeholder="选择必须禁止的工具"
          search-placeholder="搜索工具名称或分类..."
          empty-text="未设置额外拒绝规则"
          no-results-text="没有匹配工具"
          @toggle="props.manager.toggleListFieldValue('deniedToolsText', $event)"
        />
        <FieldDescription>可使用分类通配规则，例如 filesystem_tools.* 或 bash_tools.*。</FieldDescription>
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
        <AgentMultiOptionPicker
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
