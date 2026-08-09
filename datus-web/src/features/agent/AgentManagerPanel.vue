<script setup lang="ts">
import { computed, onMounted, shallowRef } from "vue"
import {
  BotIcon,
  BracesIcon,
  ListChecksIcon,
  LoaderCircleIcon,
  PencilIcon,
  PlusIcon,
  RefreshCwIcon,
  StarIcon,
  Trash2Icon,
  WrenchIcon,
} from "@lucide/vue"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Spinner } from "@/components/ui/spinner"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useAgentManager } from "@/composables/useAgentManager"
import AgentFormDialog from "@/features/agent/AgentFormDialog.vue"
import {
  filterAgentsBySource,
  type AgentSourceFilter,
} from "@/features/agent/agent-source-filter"
import PageHeaderToolbar from "@/features/shared/PageHeaderToolbar.vue"
import PanelCardHeader from "@/features/shared/PanelCardHeader.vue"
import { cn, formatDate } from "@/lib/utils"

const manager = useAgentManager()
type AgentRow = (typeof manager.agents.value)[number]

const agentStatusOptions = [
  { value: "draft", label: "草稿" },
  { value: "published", label: "已发布" },
  { value: "disabled", label: "已停用" },
  { value: "archived", label: "已归档" },
] as const

const deleteTarget = shallowRef<AgentRow | null>(null)
const formDialogOpen = shallowRef(false)
const agentSourceFilter = shallowRef<AgentSourceFilter>("all")
const mobileWorkspaceTab = shallowRef("agents")
const toolWorkspaceTab = shallowRef("catalog")

const visibleAgents = computed(() =>
  filterAgentsBySource(manager.agents.value, agentSourceFilter.value)
)
const builtinAgentCount = computed(() =>
  manager.agents.value.filter((agent) => agent.source === "builtin").length
)
const customAgentCount = computed(() => manager.agents.value.length - builtinAgentCount.value)
const emptyAgentListMessage = computed(() => {
  if (agentSourceFilter.value === "custom") {
    return "暂无自定义 Agent。点击新建创建第一个可复用 Agent。"
  }
  if (agentSourceFilter.value === "builtin") return "暂无系统内置 Agent。"
  return "暂无 Agent。点击新建创建第一个可复用 Agent。"
})
const agentListLoadingLabel = computed(() =>
  manager.agents.value.length > 0 ? "正在刷新 Agent..." : "正在加载 Agent..."
)
const toolCatalogEntries = computed(() => manager.toolCatalogEntries())
const useToolTypeEntries = computed(() => manager.useToolTypeEntries())
const defaultUseTools = computed(() => manager.selectedUseTools.value?.default_tools ?? [])
const configuredTools = computed(() => manager.selectedConfiguredTools.value)
const toolPanelDescription = computed(() => {
  const selectedName = manager.selectedAgentName.value
  if (manager.detailLoading.value && selectedName) return `正在加载 ${selectedName} 的工具配置...`
  if (manager.selectedAgent.value) {
    return `${selectedName ?? "当前 Agent"} · ${manager.selectedAgent.value.node_class || "gen_sql"} · 已配置与节点参考`
  }
  return "点击左侧 Agent 查看已配置工具和节点默认工具。"
})
const deleteDialogOpen = computed({
  get: () => deleteTarget.value !== null,
  set: (value: boolean) => {
    if (!value) deleteTarget.value = null
  },
})

function systemPromptSummary(agent: AgentRow) {
  const text = agent.description || ""
  return text.trim() || "-"
}

function updateAgentSourceFilter(value: unknown) {
  if (value === "all" || value === "custom" || value === "builtin") {
    agentSourceFilter.value = value
  }
}

function isDefaultAgent(agent: AgentRow) {
  return manager.enterpriseDefaultAgentId.value === agent.agent_id
}

function canSetDefaultAgent(agent: AgentRow) {
  return agent.status === "published"
}

function defaultAgentActionLabel(agent: AgentRow) {
  if (isDefaultAgent(agent)) return `${agent.name} 已是企业默认 Agent，点击清除`
  return `将 ${agent.name} 设为企业默认 Agent`
}

function agentEditActionLabel(agent: AgentRow) {
  return agent.source === "builtin" ? `查看 ${agent.name}` : `编辑 ${agent.name}`
}

async function setDefaultAgent(agent: AgentRow) {
  await manager.setEnterpriseDefault(isDefaultAgent(agent) ? null : agent.agent_id)
}

function agentStatusToneClass(status: string | null | undefined) {
  switch (status?.trim().toLowerCase() || "draft") {
    case "published":
      return "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
    case "draft":
      return "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300"
    case "disabled":
      return "border-destructive/30 bg-destructive/10 text-destructive"
    case "archived":
      return "border-slate-500/30 bg-slate-500/10 text-slate-700 dark:text-slate-300"
    default:
      return "bg-muted text-muted-foreground"
  }
}

function agentStatusLabel(status: string | null | undefined) {
  const normalizedStatus = status?.trim().toLowerCase() || "draft"
  return agentStatusOptions.find(option => option.value === normalizedStatus)?.label ?? normalizedStatus
}

function inspectAgent(agent: AgentRow) {
  mobileWorkspaceTab.value = "tools"
  toolWorkspaceTab.value = "selection"
  void manager.inspectAgent(agent.agent_id)
}

function openAgentEditor(agent: AgentRow) {
  formDialogOpen.value = true
  void manager.openAgentEditor(agent.agent_id)
}

async function selectInitialAgent() {
  const currentAgent = manager.selectedAgentId.value
    ? manager.agents.value.find(agent => agent.agent_id === manager.selectedAgentId.value)
    : undefined
  const nextAgent = currentAgent
    ?? visibleAgents.value.find(agent => agent.agent_id === manager.enterpriseDefaultAgentId.value)
    ?? visibleAgents.value[0]

  if (!nextAgent) {
    if (manager.selectedAgentId.value) await manager.inspectAgent(null)
    return
  }

  if (manager.selectedAgentId.value !== nextAgent.agent_id || !manager.selectedAgent.value) {
    toolWorkspaceTab.value = "selection"
    await manager.inspectAgent(nextAgent.agent_id)
  }
}

function startCreate() {
  manager.startCreate()
  formDialogOpen.value = true
}

async function refreshAll(options: { force?: boolean } = {}) {
  await Promise.all([
    manager.loadAgents(),
    manager.loadEnterpriseDefault(),
    manager.loadNodeTypes(),
    manager.loadToolCatalog(),
    manager.loadMcpCatalog(options),
    manager.loadResourceCatalogs(),
    manager.loadAclDirectory(),
  ])
  await selectInitialAgent()
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
  <section class="flex min-h-0 flex-1 overflow-hidden p-4">
    <div class="flex min-h-0 flex-1 flex-col gap-4">
      <PageHeaderToolbar
        title="Agent 管理"
        description="配置企业 Agent、访问范围与运行工具。"
        aria-label="Agent 管理页头工具栏"
      >
        <template #leading>
          <BotIcon />
        </template>

        <template #meta>
          <Badge variant="secondary">{{ manager.agentCount.value }} 个 Agent</Badge>
          <Badge variant="outline">{{ manager.toolCategoryCount.value }} 类 / {{ manager.toolCount.value }} 个工具</Badge>
        </template>

        <template #actions>
          <Button
            variant="outline"
            size="sm"
            :disabled="manager.loading.value || manager.toolsLoading.value"
            @click="refreshAll({ force: true })"
          >
            <RefreshCwIcon
              data-icon="inline-start"
              :class="(manager.loading.value || manager.toolsLoading.value) && 'animate-spin'"
            />
            刷新
          </Button>
          <Button
            size="sm"
            @click="startCreate"
          >
            <PlusIcon data-icon="inline-start" />
            新建 Agent
          </Button>
        </template>
      </PageHeaderToolbar>

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

      <Tabs
        v-model="mobileWorkspaceTab"
        class="flex min-h-0 flex-1 flex-col gap-3"
      >
        <TabsList class="grid h-auto shrink-0 grid-cols-2 xl:hidden">
          <TabsTrigger value="agents">Agent 列表</TabsTrigger>
          <TabsTrigger value="tools">工具参考</TabsTrigger>
        </TabsList>

        <div class="grid min-h-0 flex-1 gap-4 xl:grid-cols-[minmax(28rem,1fr)_minmax(22rem,0.6fr)]">
          <TabsContent
            value="agents"
            force-mount
            class="m-0 flex min-h-0 min-w-0 data-[state=inactive]:hidden xl:data-[state=inactive]:flex"
          >
            <Card
              size="default"
              class="h-full w-full min-h-0 min-w-0 gap-4"
            >
          <PanelCardHeader
            title="Agent 列表"
            description="点击 Agent 查看工具，使用操作按钮编辑或管理。"
          >
            <template #meta>
              <Tabs
                :model-value="agentSourceFilter"
                class="shrink-0"
                @update:model-value="updateAgentSourceFilter"
              >
                <TabsList
                  aria-label="按 Agent 来源过滤"
                  class="grid h-auto shrink-0 grid-cols-3"
                >
                  <TabsTrigger value="all">全部 {{ manager.agentCount.value }}</TabsTrigger>
                  <TabsTrigger value="custom">自定义 {{ customAgentCount }}</TabsTrigger>
                  <TabsTrigger value="builtin">系统内置 {{ builtinAgentCount }}</TabsTrigger>
                </TabsList>
              </Tabs>
            </template>
            <template #action>
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
            </template>
          </PanelCardHeader>
          <CardContent class="flex min-h-0 flex-1 flex-col gap-3">
            <Alert
              v-if="manager.error.value"
              variant="destructive"
            >
              <BotIcon />
              <AlertTitle>读取失败</AlertTitle>
              <AlertDescription>{{ manager.error.value }}</AlertDescription>
            </Alert>

            <ScrollArea class="min-h-0 flex-1 rounded-lg border [&_[data-slot=table-container]]:overflow-x-hidden">
              <Table class="table-fixed">
                <TableHeader>
                  <TableRow>
                    <TableHead>Agent</TableHead>
                    <TableHead class="w-28">状态</TableHead>
                    <TableHead class="w-32 text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody :aria-busy="manager.loading.value">
                  <TableRow
                    v-for="agent in visibleAgents"
                    :key="agent.agent_id"
                    :aria-selected="manager.selectedAgentId.value === agent.agent_id"
                    :class="cn(manager.selectedAgentId.value === agent.agent_id && 'bg-muted/60')"
                  >
                    <TableCell class="min-w-0 overflow-hidden whitespace-normal">
                      <Button
                        variant="ghost"
                        class="h-auto w-full min-w-0 justify-start px-2 py-1 text-left"
                        :aria-label="`选择 ${agent.name}`"
                        :aria-pressed="manager.selectedAgentId.value === agent.agent_id"
                        @click="inspectAgent(agent)"
                      >
                        <div class="flex min-w-0 flex-col gap-1">
                          <div class="flex min-w-0 items-center gap-1.5">
                            <span class="min-w-0 flex-1 truncate font-medium">{{ agent.name }}</span>
                            <Badge
                              class="shrink-0"
                              variant="secondary"
                            >
                              {{ agent.node_class || "gen_sql" }}
                            </Badge>
                            <Badge
                              v-if="agent.source === 'builtin'"
                              class="shrink-0"
                              variant="outline"
                            >
                              系统内置
                            </Badge>
                            <Badge
                              v-if="isDefaultAgent(agent)"
                              class="shrink-0"
                              variant="outline"
                            >
                              企业默认
                            </Badge>
                          </div>
                          <span class="block min-w-0 truncate text-xs text-muted-foreground">{{ systemPromptSummary(agent) }}</span>
                        </div>
                      </Button>
                    </TableCell>
                    <TableCell>
                      <div class="flex flex-col items-start gap-1">
                        <Badge
                          :class="agentStatusToneClass(agent.status)"
                          variant="outline"
                        >
                          {{ agentStatusLabel(agent.status) }}
                        </Badge>
                        <span class="text-xs text-muted-foreground">{{ formatDate(agent.created_at) || "-" }}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div class="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          :disabled="manager.defaultPolicyLoading.value || !canSetDefaultAgent(agent)"
                          :aria-label="defaultAgentActionLabel(agent)"
                          :aria-pressed="isDefaultAgent(agent)"
                          :title="defaultAgentActionLabel(agent)"
                          @click="setDefaultAgent(agent)"
                        >
                          <StarIcon
                            data-icon="inline-start"
                            :class="cn(isDefaultAgent(agent) && 'fill-yellow-400 text-yellow-500')"
                          />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          :aria-label="agentEditActionLabel(agent)"
                          :title="agentEditActionLabel(agent)"
                          @click="openAgentEditor(agent)"
                        >
                          <PencilIcon data-icon="inline-start" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          :disabled="agent.source === 'builtin' || manager.deleting.value"
                          aria-label="删除 Agent"
                          @click="deleteTarget = agent"
                        >
                          <Trash2Icon data-icon="inline-start" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                  <TableRow v-if="manager.loading.value && visibleAgents.length === 0">
                    <TableCell
                      colspan="3"
                      class="h-24 text-center text-sm text-muted-foreground"
                    >
                      <div
                        role="status"
                        aria-live="polite"
                        class="flex items-center justify-center gap-2"
                      >
                        <Spinner aria-hidden="true" />
                        {{ agentListLoadingLabel }}
                      </div>
                    </TableCell>
                  </TableRow>
                  <TableRow v-else-if="visibleAgents.length === 0">
                    <TableCell
                      colspan="3"
                      class="h-24 text-center text-sm text-muted-foreground"
                    >
                      {{ emptyAgentListMessage }}
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </ScrollArea>
          </CardContent>
            </Card>
          </TabsContent>

          <TabsContent
            value="tools"
            force-mount
            class="m-0 flex min-h-0 min-w-0 data-[state=inactive]:hidden xl:data-[state=inactive]:flex"
          >
            <Card
              size="default"
              class="h-full w-full min-h-0 min-w-0 gap-4"
            >
          <PanelCardHeader
            title="Agent 工具"
            :description="toolPanelDescription"
          >
            <template #meta>
              <Badge variant="outline">{{ manager.selectedConfiguredToolCount.value }} 个已配置</Badge>
            </template>
          </PanelCardHeader>
          <CardContent class="min-h-0 flex-1">
            <Tabs
              v-model="toolWorkspaceTab"
              class="flex h-full min-h-0 flex-col gap-3"
            >
              <TabsList class="grid h-auto shrink-0 grid-cols-2">
                <TabsTrigger value="catalog">工具目录</TabsTrigger>
                <TabsTrigger value="selection">Agent 配置</TabsTrigger>
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
                    <div
                      v-if="manager.detailLoading.value"
                      class="flex min-h-24 items-center justify-center gap-2 text-sm text-muted-foreground"
                      role="status"
                      aria-live="polite"
                    >
                      <Spinner aria-hidden="true" />
                      正在加载 Agent 工具...
                    </div>

                    <Alert v-else-if="manager.detailError.value" variant="destructive">
                      <BotIcon />
                      <AlertTitle>读取 Agent 工具失败</AlertTitle>
                      <AlertDescription>
                        {{ manager.detailError.value }}
                        <Button
                          v-if="manager.selectedAgentId.value"
                          variant="outline"
                          size="sm"
                          class="mt-2"
                          @click="manager.inspectAgent(manager.selectedAgentId.value)"
                        >
                          重试
                        </Button>
                      </AlertDescription>
                    </Alert>

                    <Alert v-else-if="!manager.selectedAgent.value">
                      <ListChecksIcon />
                      <AlertTitle>请选择 Agent</AlertTitle>
                      <AlertDescription>点击左侧 Agent 后，这里会显示已配置工具和节点工具参考。</AlertDescription>
                    </Alert>

                    <template v-else>
                      <div class="rounded-lg border bg-muted/20 p-3">
                        <div class="mb-2 flex items-center gap-2">
                          <ListChecksIcon class="text-muted-foreground" />
                          <span class="text-sm font-medium">已配置工具</span>
                          <Badge variant="outline">{{ configuredTools.length }}</Badge>
                        </div>
                        <div class="flex flex-wrap gap-1.5">
                          <Badge
                            v-for="tool in configuredTools"
                            :key="tool"
                            variant="secondary"
                          >
                            {{ tool }}
                          </Badge>
                          <span
                            v-if="configuredTools.length === 0"
                            class="text-sm text-muted-foreground"
                          >
                            未配置显式工具，运行时可能使用节点默认工具。
                          </span>
                        </div>
                      </div>

                      <div class="rounded-lg border bg-muted/20 p-3">
                        <div class="mb-2 flex items-center gap-2">
                          <ListChecksIcon class="text-muted-foreground" />
                          <span class="text-sm font-medium">节点默认工具</span>
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
                            未返回节点默认工具。
                          </span>
                        </div>
                      </div>

                      <div
                        v-for="[category, tools] in useToolTypeEntries"
                        :key="category"
                        class="rounded-lg border bg-muted/20 p-3"
                      >
                        <div class="mb-2 flex items-center justify-between gap-2">
                          <span class="truncate text-sm font-medium">可选工具 · {{ category }}</span>
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
                    </template>
                  </div>
                </ScrollArea>
              </TabsContent>
            </Tabs>
          </CardContent>
            </Card>
          </TabsContent>
        </div>
      </Tabs>

    </div>

    <AgentFormDialog
      v-model:open="formDialogOpen"
      :manager="manager"
    />

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
