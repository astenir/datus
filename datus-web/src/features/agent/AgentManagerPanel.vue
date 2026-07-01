<script setup lang="ts">
import { computed, onMounted, shallowRef } from "vue"
import {
  BotIcon,
  BracesIcon,
  CheckCircle2Icon,
  ListChecksIcon,
  LoaderCircleIcon,
  PlusIcon,
  RefreshCwIcon,
  SaveIcon,
  Trash2Icon,
  WrenchIcon,
} from "@lucide/vue"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { useAgentManager } from "@/composables/useAgentManager"
import { formatDate } from "@/lib/utils"

const manager = useAgentManager()
type AgentRow = (typeof manager.agents.value)[number]

const deleteTarget = shallowRef<AgentRow | null>(null)
const formDialogOpen = shallowRef(false)

const selectedTitle = computed(() => manager.selectedAgentName.value ?? "新建 Agent")
const selectedTypeLabel = computed(() => manager.selectedAgent.value?.node_class || manager.form.value.nodeClass || "未指定")
const toolCatalogEntries = computed(() => manager.toolCatalogEntries())
const useToolTypeEntries = computed(() => manager.useToolTypeEntries())
const defaultUseTools = computed(() => manager.selectedUseTools.value?.default_tools ?? [])
const deleteDialogOpen = computed({
  get: () => deleteTarget.value !== null,
  set: (value: boolean) => {
    if (!value) deleteTarget.value = null
  },
})
const formModeLabel = computed(() => manager.formMode.value === "edit" ? "编辑" : "新建")
const saveLabel = computed(() => manager.formMode.value === "edit" ? "保存 Agent" : "创建 Agent")
const formDialogDescription = computed(() => {
  return manager.formMode.value === "edit"
    ? "编辑当前 Agent 的节点类型、工具、约束和作用域，保存后会同步到企业 Agent 接口。"
    : "创建新的可复用 Agent；列表字段支持英文逗号或换行分隔。"
})

function systemPromptSummary(agent: AgentRow) {
  const text = agent.description || ""
  return text.trim() || "-"
}

async function selectAgent(agent: AgentRow) {
  await manager.selectAgent(agent.agent_id)
  formDialogOpen.value = true
}

function startCreate() {
  manager.startCreate()
  formDialogOpen.value = true
}

async function submitForm() {
  const saved = await manager.saveForm()
  if (saved) {
    formDialogOpen.value = false
  }
}

async function refreshAll() {
  await Promise.all([
    manager.loadAgents(),
    manager.loadToolCatalog(),
  ])
}

async function confirmDelete() {
  const target = deleteTarget.value
  if (!target) return

  await manager.deleteAgent(target.agent_id)
  deleteTarget.value = null
}

onMounted(() => {
  void refreshAll()
})
</script>

<template>
  <section class="flex min-h-0 flex-1 overflow-hidden p-3">
    <div class="flex min-h-0 flex-1 flex-col gap-3">
      <div class="flex shrink-0 flex-wrap items-center gap-3">
        <div class="min-w-0 flex-1">
          <h1 class="text-lg font-semibold">Agent 管理</h1>
          <div class="mt-1 flex flex-wrap items-center gap-2">
            <Badge variant="secondary">{{ manager.agentCount.value }} 个 Agent</Badge>
            <Badge variant="outline">{{ manager.toolCategoryCount.value }} 类 / {{ manager.toolCount.value }} 个工具</Badge>
            <span class="min-w-0 truncate text-xs text-muted-foreground">
              当前：<span class="font-medium text-foreground">{{ selectedTitle }}</span>
            </span>
            <Badge variant="outline">{{ selectedTypeLabel }}</Badge>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            :disabled="manager.loading.value || manager.toolsLoading.value"
            @click="refreshAll"
          >
            <RefreshCwIcon data-icon="inline-start" />
            刷新
          </Button>
          <Button
            size="sm"
            @click="startCreate"
          >
            <PlusIcon data-icon="inline-start" />
            新建 Agent
          </Button>
        </div>
      </div>

      <Alert
        v-if="manager.enterpriseRoutesUnavailable.value"
        variant="destructive"
        class="shrink-0"
      >
        <BotIcon />
        <AlertTitle>企业 Agent 管理接口不可用</AlertTitle>
        <AlertDescription>
          当前页面已切换到 `/api/v1/admin/agents*` 企业接口。请确认后端企业 Agent 管理路由已启用，且当前用户具备对应管理权限。
        </AlertDescription>
      </Alert>

      <div class="grid min-h-0 flex-1 auto-cols-[calc(100vw-1.5rem)] grid-flow-col gap-3 overflow-x-auto xl:auto-cols-auto xl:grid-flow-row xl:grid-cols-[minmax(28rem,1fr)_minmax(22rem,0.6fr)] xl:overflow-visible">
        <Card
          size="sm"
          class="min-h-0 min-w-0"
        >
          <CardHeader class="shrink-0">
            <div class="flex flex-wrap items-start gap-3">
              <div class="min-w-0 flex-1">
                <CardTitle class="text-lg">Agent 列表</CardTitle>
                <CardDescription class="text-sm">选择一行查看详情并编辑。</CardDescription>
              </div>
              <Badge
                v-if="manager.loading.value"
                variant="outline"
              >
                <LoaderCircleIcon
                  class="animate-spin"
                  data-icon="inline-start"
                />
                加载中
              </Badge>
            </div>
          </CardHeader>
          <CardContent class="flex min-h-0 flex-1 flex-col gap-3">
            <Alert
              v-if="manager.error.value"
              variant="destructive"
            >
              <BotIcon />
              <AlertTitle>读取失败</AlertTitle>
              <AlertDescription>{{ manager.error.value }}</AlertDescription>
            </Alert>

            <ScrollArea class="min-h-0 flex-1 rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Agent</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead class="w-12 text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow
                    v-for="agent in manager.agents.value"
                    :key="agent.agent_id"
                    class="cursor-pointer"
                    @click="selectAgent(agent)"
                  >
                    <TableCell>
                      <div class="flex min-w-0 flex-col gap-1">
                        <div class="flex min-w-0 items-center gap-2 font-medium">
                          <CheckCircle2Icon
                            v-if="agent.agent_id === manager.selectedAgentId.value"
                            class="shrink-0 text-primary"
                          />
                          <span class="truncate">{{ agent.name }}</span>
                        </div>
                        <div class="flex min-w-0 flex-wrap items-center gap-1.5">
                          <Badge variant="secondary">{{ agent.node_class || "gen_sql" }}</Badge>
                          <span class="min-w-0 truncate text-xs text-muted-foreground">{{ systemPromptSummary(agent) }}</span>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div class="flex flex-col items-start gap-1">
                        <Badge variant="outline">{{ agent.status || "draft" }}</Badge>
                        <span class="text-xs text-muted-foreground">{{ formatDate(agent.created_at) || "-" }}</span>
                      </div>
                    </TableCell>
                    <TableCell class="text-right">
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label="删除 Agent"
                        @click.stop="deleteTarget = agent"
                      >
                        <Trash2Icon data-icon="inline-start" />
                      </Button>
                    </TableCell>
                  </TableRow>
                  <TableRow v-if="manager.agents.value.length === 0">
                    <TableCell
                      colspan="3"
                      class="h-24 text-center text-sm text-muted-foreground"
                    >
                      暂无 Agent。点击新建创建第一个可复用 Agent。
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </ScrollArea>
          </CardContent>
        </Card>

        <Card
          size="sm"
          class="min-h-0 min-w-0"
        >
          <CardHeader class="shrink-0">
            <div class="flex flex-wrap items-start gap-3">
              <div class="min-w-0 flex-1">
                <CardTitle class="text-lg">工具</CardTitle>
                <CardDescription class="text-sm">目录与当前 Agent 默认工具。</CardDescription>
              </div>
              <Badge variant="outline">{{ manager.selectedUseToolCount.value }}</Badge>
            </div>
          </CardHeader>
          <CardContent class="min-h-0 flex-1">
            <Tabs
              default-value="catalog"
              class="flex h-full min-h-0 flex-col gap-3"
            >
              <TabsList class="grid h-auto shrink-0 grid-cols-2">
                <TabsTrigger value="catalog">工具目录</TabsTrigger>
                <TabsTrigger value="selection">当前工具</TabsTrigger>
              </TabsList>

              <TabsContent
                value="catalog"
                class="m-0 min-h-0"
              >
                <ScrollArea class="h-full min-h-0">
                  <div class="flex flex-col gap-3 pr-3">
                    <div
                      v-for="[category, tools] in toolCatalogEntries"
                      :key="category"
                      class="rounded-lg border bg-muted/20 p-3"
                    >
                      <div class="mb-2 flex items-center justify-between gap-2">
                        <div class="flex min-w-0 items-center gap-2">
                          <WrenchIcon class="shrink-0 text-muted-foreground" />
                          <span class="truncate text-sm font-medium">{{ category }}</span>
                        </div>
                        <Badge variant="outline">{{ tools.length }}</Badge>
                      </div>
                      <div class="flex flex-wrap gap-1.5">
                        <Badge
                          v-for="tool in tools"
                          :key="tool"
                          variant="secondary"
                        >
                          {{ tool }}
                        </Badge>
                      </div>
                    </div>
                    <Alert v-if="toolCatalogEntries.length === 0">
                      <BracesIcon />
                      <AlertTitle>暂无工具目录</AlertTitle>
                      <AlertDescription>后端没有返回可配置工具，或当前用户没有读取权限。</AlertDescription>
                    </Alert>
                  </div>
                </ScrollArea>
              </TabsContent>

              <TabsContent
                value="selection"
                class="m-0 min-h-0"
              >
                <ScrollArea class="h-full min-h-0">
                  <div class="flex flex-col gap-3 pr-3">
                    <div class="rounded-lg border bg-muted/20 p-3">
                      <div class="mb-2 flex items-center gap-2">
                        <ListChecksIcon class="text-muted-foreground" />
                        <span class="text-sm font-medium">默认工具</span>
                        <Badge variant="outline">{{ defaultUseTools.length }}</Badge>
                      </div>
                      <div class="flex flex-wrap gap-1.5">
                        <Badge
                          v-for="tool in defaultUseTools"
                          :key="tool"
                          variant="secondary"
                        >
                          {{ tool }}
                        </Badge>
                        <span
                          v-if="defaultUseTools.length === 0"
                          class="text-sm text-muted-foreground"
                        >
                          未返回默认工具。
                        </span>
                      </div>
                    </div>

                    <div
                      v-for="[category, tools] in useToolTypeEntries"
                      :key="category"
                      class="rounded-lg border bg-muted/20 p-3"
                    >
                      <div class="mb-2 flex items-center justify-between gap-2">
                        <span class="truncate text-sm font-medium">{{ category }}</span>
                        <Badge variant="outline">{{ tools.length }}</Badge>
                      </div>
                      <div class="flex flex-wrap gap-1.5">
                        <Badge
                          v-for="tool in tools"
                          :key="tool"
                          variant="secondary"
                        >
                          {{ tool }}
                        </Badge>
                      </div>
                    </div>
                  </div>
                </ScrollArea>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </div>

    </div>

    <Dialog v-model:open="formDialogOpen">
      <DialogContent class="max-h-[calc(100vh-2rem)] grid-rows-[auto_minmax(0,1fr)] sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>{{ formModeLabel }} Agent</DialogTitle>
          <DialogDescription>{{ formDialogDescription }}</DialogDescription>
        </DialogHeader>

        <form
          class="flex min-h-0 flex-col gap-4"
          @submit.prevent="submitForm"
        >
          <ScrollArea class="min-h-0 flex-1">
            <FieldGroup class="gap-4 pr-3">
              <div class="grid gap-4 md:grid-cols-2">
                <Field>
                  <FieldLabel for="agent-name">名称</FieldLabel>
                  <Input
                    id="agent-name"
                    v-model="manager.form.value.name"
                    placeholder="fund_research"
                  />
                </Field>

                <Field>
                  <FieldLabel for="agent-type">节点类型</FieldLabel>
                  <Input
                    id="agent-type"
                    v-model="manager.form.value.nodeClass"
                    placeholder="gen_sql"
                  />
                </Field>
              </div>

              <div class="grid gap-4 md:grid-cols-2">
                <Field>
                  <FieldLabel for="agent-status">状态</FieldLabel>
                  <Select v-model="manager.form.value.status">
                    <SelectTrigger id="agent-status">
                      <SelectValue placeholder="选择状态" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        <SelectItem value="draft">draft</SelectItem>
                        <SelectItem value="published">published</SelectItem>
                        <SelectItem value="disabled">disabled</SelectItem>
                        <SelectItem value="archived">archived</SelectItem>
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                </Field>

                <Field>
                  <FieldLabel for="agent-max-turns">最大轮次</FieldLabel>
                  <Input
                    id="agent-max-turns"
                    v-model="manager.form.value.maxTurns"
                    inputmode="numeric"
                    placeholder="8"
                  />
                </Field>
              </div>

              <Field>
                <FieldLabel for="agent-description">描述</FieldLabel>
                <Textarea
                  id="agent-description"
                  v-model="manager.form.value.description"
                  class="min-h-16"
                  placeholder="这个 Agent 的职责范围"
                />
              </Field>

              <Field>
                <FieldLabel for="agent-prompt">系统提示词</FieldLabel>
                <Textarea
                  id="agent-prompt"
                  v-model="manager.form.value.promptTemplate"
                  class="min-h-32 font-mono text-xs leading-6"
                  spellcheck="false"
                />
              </Field>

              <div class="grid gap-4 md:grid-cols-2">
                <Field>
                  <FieldLabel for="agent-tools">工具</FieldLabel>
                  <Textarea
                    id="agent-tools"
                    v-model="manager.form.value.toolsText"
                    class="min-h-24 font-mono text-xs leading-6"
                    placeholder="read_query"
                  />
                </Field>
                <Field>
                  <FieldLabel for="agent-rules">规则</FieldLabel>
                  <Textarea
                    id="agent-rules"
                    v-model="manager.form.value.rulesText"
                    class="min-h-24 font-mono text-xs leading-6"
                    placeholder="仅查询授权数据源"
                  />
                </Field>
              </div>

              <div class="grid gap-4 md:grid-cols-2">
                <Field>
                  <FieldLabel for="agent-catalogs">数据目录</FieldLabel>
                  <Input
                    id="agent-catalogs"
                    v-model="manager.form.value.catalogsText"
                    placeholder="fund, market"
                  />
                </Field>
                <Field>
                  <FieldLabel for="agent-subjects">主题域</FieldLabel>
                  <Input
                    id="agent-subjects"
                    v-model="manager.form.value.subjectsText"
                    placeholder="portfolio, risk"
                  />
                </Field>
              </div>
            </FieldGroup>
          </ScrollArea>

          <DialogFooter class="shrink-0">
            <Button
              variant="outline"
              type="button"
              :disabled="manager.saving.value"
              @click="formDialogOpen = false"
            >
              取消
            </Button>
            <Button
              type="submit"
              :disabled="!manager.canSubmitForm.value"
            >
              <SaveIcon data-icon="inline-start" />
              {{ saveLabel }}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>

    <Dialog v-model:open="deleteDialogOpen">
      <DialogContent>
        <DialogHeader>
          <DialogTitle>删除 Agent</DialogTitle>
          <DialogDescription>
            删除后聊天工作区将不再显示该 Agent，后端配置也会同步移除。
          </DialogDescription>
        </DialogHeader>
        <div class="rounded-lg bg-muted px-3 py-2 text-sm font-medium">
          {{ deleteTarget?.name }}
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            :disabled="manager.deleting.value"
            @click="deleteTarget = null"
          >
            取消
          </Button>
          <Button
            variant="destructive"
            :disabled="manager.deleting.value"
            @click="confirmDelete"
          >
            <Trash2Icon data-icon="inline-start" />
            删除
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </section>
</template>
