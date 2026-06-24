<script setup lang="ts">
import { computed, onMounted, shallowRef } from "vue"
import {
  BotIcon,
  PlusIcon,
  RefreshCwIcon,
  Trash2Icon,
} from "@lucide/vue"
import { toast } from "vue-sonner"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Textarea } from "@/components/ui/textarea"
import { useAgents } from "@/composables/useAgents"
import { formatDate } from "@/lib/utils"
import type { AgentInfo, CreateAgentInput } from "@/types"

const agentManager = useAgents()

const isLoading = shallowRef(false)
const isCreating = shallowRef(false)
const isDeleting = shallowRef(false)
const agentName = shallowRef("")
const agentType = shallowRef("")
const description = shallowRef("")
const promptTemplate = shallowRef("")
const tools = shallowRef("")
const catalogs = shallowRef("")
const subjects = shallowRef("")
const selectedDeleteAgent = shallowRef<AgentInfo | null>(null)

const agents = computed(() => {
  return [...agentManager.agents.value].sort((left, right) => left.name.localeCompare(right.name))
})
const agentCountLabel = computed(() => String(agents.value.length))
const createDisabled = computed(() => isCreating.value || agentName.value.trim().length === 0)
const deleteDialogOpen = computed({
  get: () => selectedDeleteAgent.value !== null,
  set: (value: boolean) => {
    if (!value) selectedDeleteAgent.value = null
  },
})

function parseList(value: string): string[] | undefined {
  const items = value
    .split(",")
    .map(item => item.trim())
    .filter(Boolean)

  return items.length > 0 ? items : undefined
}

function resetForm() {
  agentName.value = ""
  agentType.value = ""
  description.value = ""
  promptTemplate.value = ""
  tools.value = ""
  catalogs.value = ""
  subjects.value = ""
}

function agentPromptSummary(agent: AgentInfo): string {
  return agent.system_prompt || agent.config_yaml || "-"
}

async function refreshAgents() {
  isLoading.value = true
  try {
    await agentManager.loadAgents()
  } finally {
    isLoading.value = false
  }
}

async function createAgent() {
  const name = agentName.value.trim()
  if (!name) return

  const input: CreateAgentInput = {
    name,
    type: agentType.value.trim() || undefined,
    description: description.value.trim() || undefined,
    prompt_template: promptTemplate.value.trim() || undefined,
    tools: parseList(tools.value),
    catalogs: parseList(catalogs.value),
    subjects: parseList(subjects.value),
  }

  isCreating.value = true
  try {
    await agentManager.createAgent(input)
    resetForm()
    toast.success("Agent 已创建")
  } catch (error) {
    toast.error(`创建 Agent 失败：${error instanceof Error ? error.message : String(error)}`)
  } finally {
    isCreating.value = false
  }
}

async function deleteSelectedAgent() {
  const agent = selectedDeleteAgent.value
  if (!agent) return

  isDeleting.value = true
  try {
    await agentManager.deleteAgent(agent.name)
    selectedDeleteAgent.value = null
    toast.success("Agent 已删除")
  } catch (error) {
    toast.error(`删除 Agent 失败：${error instanceof Error ? error.message : String(error)}`)
  } finally {
    isDeleting.value = false
  }
}

onMounted(() => {
  void refreshAgents()
})
</script>

<template>
  <section class="min-h-0 flex-1 overflow-y-auto p-4">
    <div class="mx-auto flex max-w-6xl flex-col gap-4">
      <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div class="min-w-0">
          <div class="flex items-center gap-2">
            <BotIcon class="text-muted-foreground" />
            <h1 class="truncate text-lg font-semibold">Agent 管理</h1>
            <Badge variant="outline">{{ agentCountLabel }}</Badge>
          </div>
          <p class="mt-1 text-sm text-muted-foreground">创建和维护可在对话中选择的 Agent。</p>
        </div>
        <Button
          variant="outline"
          size="sm"
          :disabled="isLoading"
          @click="refreshAgents"
        >
          <RefreshCwIcon data-icon="inline-start" />
          刷新
        </Button>
      </div>

      <div class="grid gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
        <Card>
          <CardHeader>
            <CardTitle>新建 Agent</CardTitle>
            <CardDescription>基础信息会提交到当前后端 Agent 配置。</CardDescription>
          </CardHeader>
          <CardContent>
            <form
              class="flex flex-col gap-4"
              @submit.prevent="createAgent"
            >
              <FieldGroup>
                <Field>
                  <FieldLabel for="agent-name">名称</FieldLabel>
                  <Input
                    id="agent-name"
                    v-model="agentName"
                    placeholder="例如：fund_research"
                  />
                </Field>

                <Field>
                  <FieldLabel for="agent-type">类型</FieldLabel>
                  <Input
                    id="agent-type"
                    v-model="agentType"
                    placeholder="例如：analytics"
                  />
                </Field>

                <Field>
                  <FieldLabel for="agent-description">描述</FieldLabel>
                  <Textarea
                    id="agent-description"
                    v-model="description"
                    class="min-h-20"
                    placeholder="这个 Agent 负责的工作范围"
                  />
                </Field>

                <Field>
                  <FieldLabel for="agent-prompt">Prompt 模板</FieldLabel>
                  <Textarea
                    id="agent-prompt"
                    v-model="promptTemplate"
                    class="min-h-28 font-mono text-xs"
                    placeholder="输入系统提示词或任务模板"
                  />
                </Field>

                <Field>
                  <FieldLabel for="agent-tools">工具</FieldLabel>
                  <Input
                    id="agent-tools"
                    v-model="tools"
                    placeholder="read_query, search_table"
                  />
                  <FieldDescription>多个值用英文逗号分隔。</FieldDescription>
                </Field>

                <Field>
                  <FieldLabel for="agent-catalogs">数据目录</FieldLabel>
                  <Input
                    id="agent-catalogs"
                    v-model="catalogs"
                    placeholder="catalog_a, catalog_b"
                  />
                </Field>

                <Field>
                  <FieldLabel for="agent-subjects">主题域</FieldLabel>
                  <Input
                    id="agent-subjects"
                    v-model="subjects"
                    placeholder="fund, holdings"
                  />
                </Field>
              </FieldGroup>

              <div class="flex items-center justify-end gap-2">
                <Button
                  variant="ghost"
                  type="button"
                  :disabled="isCreating"
                  @click="resetForm"
                >
                  清空
                </Button>
                <Button
                  type="submit"
                  :disabled="createDisabled"
                >
                  <PlusIcon data-icon="inline-start" />
                  创建
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        <Card class="min-w-0">
          <CardHeader>
            <CardTitle>Agent 列表</CardTitle>
            <CardDescription>聊天输入栏中的 Agent 选项来自这里。</CardDescription>
          </CardHeader>
          <CardContent class="min-w-0">
            <Alert
              v-if="agents.length === 0"
              class="mb-4"
            >
              <BotIcon />
              <AlertTitle>暂无 Agent</AlertTitle>
              <AlertDescription>创建后会出现在聊天输入栏的 Agent 下拉选择中。</AlertDescription>
            </Alert>

            <div class="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>名称</TableHead>
                    <TableHead>类型</TableHead>
                    <TableHead>提示词</TableHead>
                    <TableHead>创建时间</TableHead>
                    <TableHead class="w-20 text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow
                    v-for="agent in agents"
                    :key="agent.name"
                  >
                    <TableCell class="font-medium">{{ agent.name }}</TableCell>
                    <TableCell>
                      <Badge variant="secondary">{{ agent.type || "default" }}</Badge>
                    </TableCell>
                    <TableCell class="max-w-md">
                      <span class="line-clamp-2 text-muted-foreground">{{ agentPromptSummary(agent) }}</span>
                    </TableCell>
                    <TableCell>{{ formatDate(agent.created_at) || "-" }}</TableCell>
                    <TableCell class="text-right">
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label="删除 Agent"
                        @click="selectedDeleteAgent = agent"
                      >
                        <Trash2Icon data-icon="inline-start" />
                      </Button>
                    </TableCell>
                  </TableRow>
                  <TableRow v-if="agents.length === 0">
                    <TableCell
                      colspan="5"
                      class="h-24 text-center text-muted-foreground"
                    >
                      没有可显示的 Agent
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>

    <Dialog v-model:open="deleteDialogOpen">
      <DialogContent>
        <DialogHeader>
          <DialogTitle>删除 Agent</DialogTitle>
          <DialogDescription>
            删除后聊天输入栏将不再显示该 Agent。
          </DialogDescription>
        </DialogHeader>
        <div class="rounded-2xl bg-muted px-3 py-2 text-sm font-medium">
          {{ selectedDeleteAgent?.name }}
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            :disabled="isDeleting"
            @click="selectedDeleteAgent = null"
          >
            取消
          </Button>
          <Button
            variant="destructive"
            :disabled="isDeleting"
            @click="deleteSelectedAgent"
          >
            删除
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </section>
</template>
