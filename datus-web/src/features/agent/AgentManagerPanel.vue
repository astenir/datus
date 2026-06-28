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
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
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
import type { AgentInfo } from "@/types"

const manager = useAgentManager()
const deleteTarget = shallowRef<AgentInfo | null>(null)

const selectedTitle = computed(() => manager.selectedAgentName.value ?? "新建 Agent")
const selectedTypeLabel = computed(() => manager.selectedAgent.value?.type || manager.form.value.type || "未指定")
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

function systemPromptSummary(agent: AgentInfo) {
  const text = agent.system_prompt || agent.config_yaml || ""
  return text.trim() || "-"
}

function selectAgent(agent: AgentInfo) {
  void manager.selectAgent(agent.name)
}

function startCreate() {
  manager.startCreate()
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

  await manager.deleteAgent(target.name)
  deleteTarget.value = null
}

onMounted(() => {
  void refreshAll()
})
</script>

<template>
  <section class="min-h-0 flex-1 overflow-y-auto p-4">
    <div class="flex flex-col gap-4">
      <div class="flex flex-wrap items-center gap-3">
        <div class="min-w-0 flex-1">
          <h1 class="text-lg font-semibold">Agent 管理</h1>
          <p class="text-sm text-muted-foreground">
            管理后端 Agent、可用工具目录和默认工具组合，聊天工作区会复用这些配置。
          </p>
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
            新建
          </Button>
        </div>
      </div>

      <Alert
        v-if="manager.legacyRoutesDisabled.value"
        variant="destructive"
      >
        <BotIcon />
        <AlertTitle>企业模式已禁用 Agent 配置接口</AlertTitle>
        <AlertDescription>
          当前 `/api/v1/agent/*` 路由是 legacy Agent 配置面，企业后端会通过 `agent.config_legacy` 保护关闭它。此页面保留 OpenAPI 对齐和本地兼容能力，生产企业环境需要接入新的企业 Agent 管理接口后再启用编辑操作。
        </AlertDescription>
      </Alert>

      <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardHeader class="pb-2">
            <CardTitle class="text-sm">Agent</CardTitle>
          </CardHeader>
          <CardContent class="flex items-end justify-between gap-3">
            <span class="text-lg font-semibold">{{ manager.agentCount.value }}</span>
            <BotIcon class="shrink-0 text-muted-foreground" />
          </CardContent>
        </Card>
        <Card>
          <CardHeader class="pb-2">
            <CardTitle class="text-sm">工具分类</CardTitle>
          </CardHeader>
          <CardContent class="flex items-end justify-between gap-3">
            <span class="text-lg font-semibold">{{ manager.toolCategoryCount.value }}</span>
            <span class="text-xs text-muted-foreground">共 {{ manager.toolCount.value }} 个工具</span>
          </CardContent>
        </Card>
        <Card>
          <CardHeader class="pb-2">
            <CardTitle class="text-sm">当前选择</CardTitle>
          </CardHeader>
          <CardContent class="flex min-w-0 items-end justify-between gap-3">
            <span class="min-w-0 truncate text-lg font-semibold">{{ selectedTitle }}</span>
            <Badge variant="outline">{{ selectedTypeLabel }}</Badge>
          </CardContent>
        </Card>
        <Card>
          <CardHeader class="pb-2">
            <CardTitle class="text-sm">可用工具</CardTitle>
          </CardHeader>
          <CardContent class="flex items-end justify-between gap-3">
            <span class="text-lg font-semibold">{{ manager.selectedUseToolCount.value }}</span>
            <span class="text-xs text-muted-foreground">当前 Agent</span>
          </CardContent>
        </Card>
      </div>

      <div class="grid gap-4 xl:grid-cols-[minmax(0,1fr)_28rem]">
        <Card class="min-w-0">
          <CardHeader>
            <div class="flex flex-wrap items-start gap-3">
              <div class="min-w-0 flex-1">
                <CardTitle class="text-lg">Agent 列表</CardTitle>
                <CardDescription class="text-sm">
                  选择一行查看详情并编辑；删除操作会立即同步到后端配置。
                </CardDescription>
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
          <CardContent class="min-w-0">
            <Alert
              v-if="manager.error.value"
              variant="destructive"
              class="mb-4"
            >
              <BotIcon />
              <AlertTitle>读取失败</AlertTitle>
              <AlertDescription>{{ manager.error.value }}</AlertDescription>
            </Alert>

            <div class="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>名称</TableHead>
                    <TableHead>类型</TableHead>
                    <TableHead>提示词</TableHead>
                    <TableHead>创建时间</TableHead>
                    <TableHead class="w-24 text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow
                    v-for="agent in manager.agents.value"
                    :key="agent.name"
                    class="cursor-pointer"
                    @click="selectAgent(agent)"
                  >
                    <TableCell class="font-medium">
                      <div class="flex min-w-0 items-center gap-2">
                        <CheckCircle2Icon
                          v-if="agent.name === manager.selectedAgentName.value"
                          class="shrink-0 text-primary"
                        />
                        <span class="truncate">{{ agent.name }}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary">{{ agent.type || "default" }}</Badge>
                    </TableCell>
                    <TableCell class="max-w-md">
                      <span class="line-clamp-2 text-sm text-muted-foreground">{{ systemPromptSummary(agent) }}</span>
                    </TableCell>
                    <TableCell class="text-sm text-muted-foreground">{{ formatDate(agent.created_at) || "-" }}</TableCell>
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
                      colspan="5"
                      class="h-24 text-center text-sm text-muted-foreground"
                    >
                      暂无 Agent。点击新建创建第一个可复用 Agent。
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle class="text-lg">{{ formModeLabel }} Agent</CardTitle>
            <CardDescription class="text-sm">
              列表字段支持英文逗号或换行分隔；编辑时会使用后端 `system_prompt` 字段保存提示词。
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form
              class="flex flex-col gap-4"
              @submit.prevent="manager.saveForm"
            >
              <FieldGroup>
                <Field>
                  <FieldLabel for="agent-name">名称</FieldLabel>
                  <Input
                    id="agent-name"
                    v-model="manager.form.value.name"
                    placeholder="fund_research"
                  />
                </Field>

                <Field>
                  <FieldLabel for="agent-type">类型</FieldLabel>
                  <Input
                    id="agent-type"
                    v-model="manager.form.value.type"
                    placeholder="analytics"
                    :disabled="manager.formMode.value === 'edit'"
                  />
                  <FieldDescription>编辑接口不支持修改类型；需要更换类型时请新建 Agent。</FieldDescription>
                </Field>

                <Field>
                  <FieldLabel for="agent-description">描述</FieldLabel>
                  <Textarea
                    id="agent-description"
                    v-model="manager.form.value.description"
                    class="min-h-20"
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

                <div class="grid gap-4 md:grid-cols-2">
                  <Field>
                    <FieldLabel for="agent-max-turns">最大轮次</FieldLabel>
                    <Input
                      id="agent-max-turns"
                      v-model="manager.form.value.maxTurns"
                      inputmode="numeric"
                      placeholder="8"
                    />
                  </Field>
                  <Field>
                    <FieldLabel for="agent-workspace-root">工作目录</FieldLabel>
                    <Input
                      id="agent-workspace-root"
                      v-model="manager.form.value.workspaceRoot"
                      placeholder="/srv/datus/workspaces/fund"
                    />
                  </Field>
                </div>
              </FieldGroup>

              <div class="flex flex-wrap justify-end gap-2">
                <Button
                  variant="outline"
                  type="button"
                  :disabled="manager.saving.value"
                  @click="startCreate"
                >
                  <PlusIcon data-icon="inline-start" />
                  重置新建
                </Button>
                <Button
                  type="submit"
                  :disabled="!manager.canSubmitForm.value"
                >
                  <SaveIcon data-icon="inline-start" />
                  {{ saveLabel }}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>

      <Tabs
        default-value="catalog"
        class="flex flex-col gap-4"
      >
        <TabsList class="flex h-auto !flex-row flex-wrap justify-start">
          <TabsTrigger value="catalog">工具目录</TabsTrigger>
          <TabsTrigger value="selection">当前 Agent 工具</TabsTrigger>
        </TabsList>

        <TabsContent value="catalog">
          <Card>
            <CardHeader>
              <CardTitle class="text-lg">可配置工具</CardTitle>
              <CardDescription class="text-sm">
                来自 `/api/v1/agent/tools`，用于判断创建或编辑 Agent 时可绑定哪些工具。
              </CardDescription>
            </CardHeader>
            <CardContent class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
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
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="selection">
          <Card>
            <CardHeader>
              <CardTitle class="text-lg">当前 Agent 可用工具</CardTitle>
              <CardDescription class="text-sm">
                来自 `/api/v1/agent/use_tools`，展示后端按 Agent 类型解析后的默认工具和分类工具。
              </CardDescription>
            </CardHeader>
            <CardContent class="flex flex-col gap-4">
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

              <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
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
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>

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
