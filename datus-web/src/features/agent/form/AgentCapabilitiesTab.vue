<script setup lang="ts">
import { computed } from "vue"
import {
  BotIcon,
  CheckCircle2Icon,
  ListChecksIcon,
  LoaderCircleIcon,
  PlusIcon,
} from "@lucide/vue"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import type { AgentManagerController } from "@/composables/useAgentManager"
import SearchableMultiSelect from "@/features/shared/SearchableMultiSelect.vue"

const props = defineProps<{
  manager: AgentManagerController
  readonly: boolean
}>()

const customSkillInput = defineModel<string>("customSkillInput", { required: true })

const defaultUseTools = computed(() => props.manager.selectedUseTools.value?.default_tools ?? [])
const mcpServerOptions = computed(() => props.manager.mcpServerOptions.value)
const policyModeLabel = computed(() =>
  props.manager.form.value.toolPolicyMode === "allowlist" ? "仅允许所选工具" : "继承节点工具"
)
const personalMcpModeLabel = computed(() =>
  props.manager.form.value.personalMcpMode === "selectable"
    ? "允许用户在新会话选择"
    : "禁用"
)
const selectedMcpList = computed(() =>
  props.manager.form.value.mcpText
    .split(/[\n,]/)
    .map(item => item.trim())
    .filter(Boolean)
)

function addCustomSkill() {
  const value = customSkillInput.value.trim()
  if (!value) return

  props.manager.addListFieldValue("skillsText", value)
  customSkillInput.value = ""
}
</script>

<template>
  <div class="flex flex-col gap-5">
    <div>
      <h2 class="text-lg font-semibold">工具与扩展能力</h2>
      <p class="mt-1 text-sm text-muted-foreground">
        配置 Agent 可以调用的工具、MCP Server 和 Skill，并定义工具的允许与拒绝策略。
      </p>
    </div>

    <FieldGroup class="grid gap-5 md:grid-cols-2">
      <Field class="md:col-span-2">
        <FieldLabel for="agent-tool-policy-mode">工具策略</FieldLabel>
        <Select v-model="props.manager.form.value.toolPolicyMode">
          <SelectTrigger id="agent-tool-policy-mode" class="w-full">
            <SelectValue>{{ policyModeLabel }}</SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              <SelectItem value="allowlist">仅允许所选工具</SelectItem>
              <SelectItem value="inherit">继承节点工具</SelectItem>
            </SelectGroup>
          </SelectContent>
        </Select>
        <FieldDescription>建议企业自定义 Chat 使用允许列表。</FieldDescription>
      </Field>

      <Field>
        <div class="flex items-center justify-between gap-2">
          <FieldLabel>工具</FieldLabel>
          <Button
            type="button"
            size="sm"
            variant="outline"
            :disabled="props.readonly || defaultUseTools.length === 0"
            @click="props.manager.applyDefaultTools"
          >
            <ListChecksIcon data-icon="inline-start" />
            使用默认值
          </Button>
        </div>
        <SearchableMultiSelect
          :options="props.manager.toolOptions.value"
          :selected-values="props.manager.selectedTools.value"
          :disabled="props.readonly || props.manager.toolsLoading.value"
          placeholder="选择工具"
          search-placeholder="搜索工具或分类"
          empty-text="未选择工具；保存时后端会按节点类型使用默认行为。"
          @toggle="props.manager.toggleListFieldValue('toolsText', $event)"
        />
        <FieldDescription v-if="props.manager.form.value.toolPolicyMode === 'allowlist'">
          允许列表模式下，未选中的工具不会暴露给模型。
        </FieldDescription>
        <FieldDescription v-else>
          继承模式下，所选工具仍决定实际加载的工具集；留空时按节点类型加载默认工具。
        </FieldDescription>
        <FieldDescription>
          目录未返回精确项的节点默认工具标记为“默认”；其他已保存值标记为“当前配置”。
        </FieldDescription>
      </Field>

      <Field>
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
          拒绝规则在所有执行上下文生效（含本地/CLI 会话）；Web 与企业会话的服务端 Bash 由后端强制禁用，无法通过本页重新启用。其他工具仍遵循拒绝优先。
        </FieldDescription>
      </Field>

      <Field>
        <FieldLabel>Skills</FieldLabel>
        <SearchableMultiSelect
          :options="props.manager.skillOptions.value"
          :selected-values="props.manager.selectedSkills.value"
          :disabled="props.readonly || props.manager.skillOptions.value.length === 0"
          placeholder="选择 Skill"
          search-placeholder="搜索 Skill"
          empty-text="未选择 Skill。"
          @toggle="props.manager.toggleListFieldValue('skillsText', $event)"
        />
        <div class="flex flex-col gap-2 sm:flex-row">
          <Input
            v-model="customSkillInput"
            :readonly="props.readonly"
            placeholder="添加自定义 Skill"
            @keydown.enter.prevent="addCustomSkill"
          />
          <Button
            type="button"
            variant="outline"
            :disabled="props.readonly || !customSkillInput.trim()"
            @click="addCustomSkill"
          >
            <PlusIcon data-icon="inline-start" />
            添加
          </Button>
        </div>
        <FieldDescription>
          当前后端未提供全量 Skill 目录，可按标签添加项目内已有 Skill。
        </FieldDescription>
      </Field>

      <Field>
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
          这里仅开放选择能力，不绑定任何个人资源。用户在 Chat 新会话中选择自己的 MCP；企业 MCP 绑定见下方区块。
        </FieldDescription>
      </Field>
    </FieldGroup>

    <FieldGroup class="gap-5">
      <Alert v-if="!props.manager.selectedNodeSupportsMcp.value">
        <BotIcon />
        <AlertTitle>当前节点类型不支持 MCP</AlertTitle>
        <AlertDescription>
          已保存的残留绑定不会进入运行时；切换到“通用聊天”或“SQL 分析”后才能配置 MCP Server。
        </AlertDescription>
      </Alert>

      <Field v-else>
        <FieldLabel>MCP</FieldLabel>
        <div class="rounded-lg border bg-muted/20 p-3">
          <div class="mb-3 flex flex-wrap items-center gap-2">
            <Badge variant="outline">{{ mcpServerOptions.length }} 个 Server</Badge>
            <Badge variant="secondary">{{ props.manager.selectedMcpCount.value }} 已选</Badge>
            <Badge variant="outline">{{ props.manager.selectedMcpToolCount.value }} 个工具</Badge>
            <Badge
              v-if="props.manager.mcpCatalogLoading.value"
              variant="outline"
            >
              <LoaderCircleIcon
                class="animate-spin"
                data-icon="inline-start"
              />
              加载中
            </Badge>
          </div>

          <Alert
            v-if="props.manager.mcpCatalogError.value"
            variant="destructive"
          >
            <BotIcon />
            <AlertTitle>读取 MCP 失败</AlertTitle>
            <AlertDescription>{{ props.manager.mcpCatalogError.value }}</AlertDescription>
          </Alert>

          <div
            v-else-if="mcpServerOptions.length === 0 && !props.manager.mcpCatalogLoading.value"
            class="rounded-md border bg-background p-3 text-sm text-muted-foreground"
          >
            暂无 MCP Server。
          </div>

          <div
            v-else
            class="grid gap-2 lg:grid-cols-2"
          >
            <Button
              v-for="server in mcpServerOptions"
              :key="server.name"
              type="button"
              :variant="server.missing ? 'destructive' : server.selected ? 'secondary' : 'outline'"
              class="h-auto min-h-16 justify-start px-3 py-2 text-left"
              :aria-pressed="server.selected"
              :disabled="props.readonly"
              @click="props.manager.toggleMcpServer(server.name)"
            >
              <span class="flex min-w-0 flex-1 flex-col gap-1.5">
                <span class="flex min-w-0 items-center gap-2">
                  <CheckCircle2Icon
                    v-if="server.selected"
                    class="shrink-0"
                    data-icon="inline-start"
                  />
                  <span class="truncate text-sm font-medium">{{ server.name }}</span>
                  <Badge
                    :variant="server.missing ? 'destructive' : 'outline'"
                    class="shrink-0"
                  >
                    {{ server.missing ? "已失效" : server.type }}
                  </Badge>
                </span>
                <span class="truncate text-xs text-muted-foreground">{{ server.target }}</span>
                <span class="flex flex-wrap gap-1">
                  <Badge
                    v-for="tool in server.tools.slice(0, 4)"
                    :key="`${server.name}:${tool}`"
                    variant="secondary"
                  >
                    {{ tool }}
                  </Badge>
                  <Badge
                    v-if="server.tools.length > 4"
                    variant="outline"
                  >
                    +{{ server.tools.length - 4 }}
                  </Badge>
                </span>
              </span>
            </Button>
          </div>

          <div
            v-if="selectedMcpList.length > 0"
            class="mt-3 flex flex-wrap gap-1.5"
          >
            <Badge
              v-for="serverName in selectedMcpList"
              :key="serverName"
              variant="outline"
            >
              {{ serverName }}
            </Badge>
          </div>
          <FieldDescription>
            “已失效”的 Server 已不在 MCP 配置中，点击可解除残留绑定。
          </FieldDescription>
        </div>
      </Field>
    </FieldGroup>
  </div>
</template>
