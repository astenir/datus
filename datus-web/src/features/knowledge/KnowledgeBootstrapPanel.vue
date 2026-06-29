<script setup lang="ts">
import { computed } from "vue"
import {
  BookMarkedIcon,
  CheckCircle2Icon,
  DatabaseIcon,
  FileTextIcon,
  LoaderCircleIcon,
  PlayIcon,
  RotateCcwIcon,
  SquareIcon,
  XCircleIcon,
} from "@lucide/vue"
import {
  Terminal,
  TerminalActions,
  TerminalClearButton,
  TerminalContent,
  TerminalCopyButton,
  TerminalHeader,
  TerminalStatus,
  TerminalTitle,
} from "@/components/ai-elements/terminal"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Field, FieldDescription, FieldGroup, FieldLabel, FieldLegend, FieldSet } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { useKnowledgeBootstrap } from "@/composables/useKnowledgeBootstrap"
import { stringifyContent } from "@/lib/chat"
import type {
  BootstrapBuildMode,
  BootstrapComponent,
  BootstrapStrategy,
  KnowledgeBootstrapLogEntry,
  KnowledgeBootstrapLogLevel,
  KnowledgeBootstrapStatus,
} from "@/types"

type BadgeVariant = "default" | "secondary" | "destructive" | "outline"

const manager = useKnowledgeBootstrap()

const kbComponentOptions: ReadonlyArray<{ value: BootstrapComponent; label: string; description: string }> = [
  { value: "metadata", label: "元数据", description: "表、字段和目录索引" },
  { value: "semantic_model", label: "语义模型", description: "表级语义 YAML" },
  { value: "metrics", label: "指标", description: "指标定义和维度" },
  { value: "reference_sql", label: "参考 SQL", description: "可复用查询样例" },
]

const strategyOptions: ReadonlyArray<{ value: BootstrapStrategy; label: string }> = [
  { value: "incremental", label: "增量" },
  { value: "check", label: "检查" },
  { value: "overwrite", label: "覆盖" },
]

const schemaLinkingOptions = [
  { value: "full", label: "完整" },
  { value: "table", label: "表" },
  { value: "view", label: "视图" },
  { value: "mv", label: "物化视图" },
] as const

const buildModeOptions: ReadonlyArray<{ value: BootstrapBuildMode; label: string }> = [
  { value: "overwrite", label: "覆盖" },
  { value: "check", label: "检查" },
]

const recentLogs = computed(() => manager.logs.value.slice(-6).reverse())
const statusLabel = computed(() => statusText(manager.status.value))
const activeModeLabel = computed(() => manager.activeMode.value === "kb" ? "业务知识库" : "平台文档")
const streamLabel = computed(() => manager.activeStreamId.value || "等待事件流")
const terminalText = computed(() => manager.terminalOutput.value || "等待构建事件...")
const statusIcon = computed(() => {
  if (manager.status.value === "running") return LoaderCircleIcon
  if (manager.status.value === "completed") return CheckCircle2Icon
  if (manager.status.value === "error") return XCircleIcon
  if (manager.status.value === "cancelled") return SquareIcon
  return BookMarkedIcon
})

function statusText(status: KnowledgeBootstrapStatus) {
  switch (status) {
    case "running":
      return "运行中"
    case "completed":
      return "已完成"
    case "cancelled":
      return "已取消"
    case "error":
      return "失败"
    default:
      return "未运行"
  }
}

function statusBadgeVariant(status: KnowledgeBootstrapStatus): BadgeVariant {
  if (status === "completed") return "secondary"
  if (status === "error") return "destructive"
  if (status === "running") return "default"
  return "outline"
}

function logBadgeVariant(level: KnowledgeBootstrapLogLevel): BadgeVariant {
  if (level === "success") return "secondary"
  if (level === "error") return "destructive"
  return "outline"
}

function payloadText(entry: KnowledgeBootstrapLogEntry) {
  const text = stringifyContent(entry.payload).trim()
  return text.length > 180 ? `${text.slice(0, 180)}...` : text
}

function updateStrategy(value: unknown) {
  if (value === "overwrite" || value === "check" || value === "incremental") {
    manager.forms.value.kb.strategy = value
  }
}

function updateSchemaLinkingType(value: unknown) {
  if (value === "table" || value === "view" || value === "mv" || value === "full") {
    manager.forms.value.kb.schemaLinkingType = value
  }
}

function updateBuildMode(value: unknown) {
  if (value === "overwrite" || value === "check") {
    manager.forms.value.docs.buildMode = value
  }
}

function updateComponent(component: BootstrapComponent, value: boolean) {
  manager.toggleKbComponent(component, value)
}
</script>

<template>
  <section class="min-h-0 flex-1 overflow-y-auto p-4">
    <div class="flex flex-col gap-4">
      <div class="flex flex-wrap items-center gap-3">
        <div class="min-w-0 flex-1">
          <h1 class="text-lg font-semibold">知识构建</h1>
          <p class="text-sm text-muted-foreground">
            运行业务知识库和平台文档的后端构建任务，事件流会实时写入右侧日志。
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          :disabled="manager.logs.value.length === 0 || manager.isRunning.value"
          @click="manager.clearLogs"
        >
          <RotateCcwIcon data-icon="inline-start" />
          清空日志
        </Button>
      </div>

      <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardHeader class="pb-2">
            <CardTitle class="text-sm">任务状态</CardTitle>
          </CardHeader>
          <CardContent class="flex items-end justify-between gap-3">
            <Badge :variant="statusBadgeVariant(manager.status.value)">
              <component
                :is="statusIcon"
                :class="{ 'animate-spin': manager.status.value === 'running' }"
                data-icon="inline-start"
              />
              {{ statusLabel }}
            </Badge>
            <span class="text-xs text-muted-foreground">{{ activeModeLabel }}</span>
          </CardContent>
        </Card>
        <Card>
          <CardHeader class="pb-2">
            <CardTitle class="text-sm">事件流</CardTitle>
          </CardHeader>
          <CardContent class="flex min-w-0 items-end justify-between gap-3">
            <span class="min-w-0 truncate text-lg font-semibold">{{ streamLabel }}</span>
            <span class="text-xs text-muted-foreground">事件流 ID</span>
          </CardContent>
        </Card>
        <Card>
          <CardHeader class="pb-2">
            <CardTitle class="text-sm">构建组件</CardTitle>
          </CardHeader>
          <CardContent class="flex items-end justify-between gap-3">
            <span class="text-lg font-semibold">{{ manager.kbComponentCount.value }}</span>
            <span class="text-xs text-muted-foreground">业务知识库</span>
          </CardContent>
        </Card>
        <Card>
          <CardHeader class="pb-2">
            <CardTitle class="text-sm">日志</CardTitle>
          </CardHeader>
          <CardContent class="flex items-end justify-between gap-3">
            <span class="text-lg font-semibold">{{ manager.logs.value.length }}</span>
            <span class="text-xs text-muted-foreground">事件记录</span>
          </CardContent>
        </Card>
      </div>

      <div class="grid gap-4 xl:grid-cols-[minmax(0,1fr)_29rem]">
        <Tabs
          default-value="kb"
          class="flex flex-col gap-4"
        >
          <TabsList class="flex h-auto !flex-row flex-wrap justify-start">
            <TabsTrigger value="kb">业务知识库</TabsTrigger>
            <TabsTrigger value="docs">平台文档</TabsTrigger>
          </TabsList>

          <TabsContent value="kb">
            <Card>
              <CardHeader>
                <CardTitle class="text-lg">业务知识库构建</CardTitle>
                <CardDescription class="text-sm">
                  提交后端 `/api/v1/kb/bootstrap`，可按目录、库名和构建策略控制范围。
                </CardDescription>
              </CardHeader>
              <CardContent class="flex flex-col gap-4">
                <FieldSet>
                  <FieldLegend>组件</FieldLegend>
                  <div class="grid gap-3 md:grid-cols-2">
                    <Field
                      v-for="component in kbComponentOptions"
                      :key="component.value"
                      class="rounded-lg border bg-muted/20 p-3"
                    >
                      <div class="flex items-start justify-between gap-3">
                        <div class="min-w-0">
                          <FieldLabel :for="`kb-component-${component.value}`">{{ component.label }}</FieldLabel>
                          <FieldDescription>{{ component.description }}</FieldDescription>
                        </div>
                        <Switch
                          :id="`kb-component-${component.value}`"
                          size="sm"
                          :model-value="manager.forms.value.kb.components.includes(component.value)"
                          :aria-label="`切换 ${component.label}`"
                          @update:model-value="updateComponent(component.value, $event)"
                        />
                      </div>
                    </Field>
                  </div>
                </FieldSet>

                <div class="grid gap-4 md:grid-cols-2">
                  <FieldGroup>
                    <Field>
                      <FieldLabel for="kb-strategy">策略</FieldLabel>
                      <Select
                        :model-value="manager.forms.value.kb.strategy"
                        @update:model-value="updateStrategy"
                      >
                        <SelectTrigger id="kb-strategy">
                          <SelectValue placeholder="选择策略" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectGroup>
                            <SelectItem
                              v-for="option in strategyOptions"
                              :key="option.value"
                              :value="option.value"
                            >
                              {{ option.label }}
                            </SelectItem>
                          </SelectGroup>
                        </SelectContent>
                      </Select>
                    </Field>
                    <Field>
                      <FieldLabel for="kb-schema-linking">模式链接类型</FieldLabel>
                      <Select
                        :model-value="manager.forms.value.kb.schemaLinkingType"
                        @update:model-value="updateSchemaLinkingType"
                      >
                        <SelectTrigger id="kb-schema-linking">
                          <SelectValue placeholder="选择链接类型" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectGroup>
                            <SelectItem
                              v-for="option in schemaLinkingOptions"
                              :key="option.value"
                              :value="option.value"
                            >
                              {{ option.label }}
                            </SelectItem>
                          </SelectGroup>
                        </SelectContent>
                      </Select>
                    </Field>
                  </FieldGroup>

                  <FieldGroup>
                    <Field>
                      <FieldLabel for="kb-catalog">目录名</FieldLabel>
                      <Input
                        id="kb-catalog"
                        v-model="manager.forms.value.kb.catalog"
                        placeholder="main"
                      />
                    </Field>
                    <Field>
                      <FieldLabel for="kb-database">数据库</FieldLabel>
                      <Input
                        id="kb-database"
                        v-model="manager.forms.value.kb.databaseName"
                        placeholder="fund"
                      />
                    </Field>
                  </FieldGroup>
                </div>

                <FieldGroup>
                  <Field>
                    <FieldLabel for="kb-subject-tree">主题树</FieldLabel>
                    <Textarea
                      id="kb-subject-tree"
                      v-model="manager.forms.value.kb.subjectTreeText"
                      class="min-h-24 text-sm leading-6"
                      placeholder="每行一个主题路径"
                    />
                    <FieldDescription>留空时由后端使用默认范围。</FieldDescription>
                  </Field>
                  <div class="grid gap-4 md:grid-cols-2">
                    <Field>
                      <FieldLabel for="kb-success-story">成功案例</FieldLabel>
                      <Input
                        id="kb-success-story"
                        v-model="manager.forms.value.kb.successStory"
                        placeholder="可选 CSV 或目录"
                      />
                    </Field>
                    <Field>
                      <FieldLabel for="kb-sql-dir">SQL 目录</FieldLabel>
                      <Input
                        id="kb-sql-dir"
                        v-model="manager.forms.value.kb.sqlDir"
                        placeholder="可选"
                      />
                    </Field>
                  </div>
                </FieldGroup>

                <div class="flex flex-wrap justify-end gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    :disabled="!manager.canCancel.value"
                    @click="manager.cancelActiveBootstrap"
                  >
                    <SquareIcon data-icon="inline-start" />
                    取消
                  </Button>
                  <Button
                    size="sm"
                    :disabled="manager.isRunning.value"
                    @click="manager.startKbBootstrap"
                  >
                    <PlayIcon data-icon="inline-start" />
                    开始构建
                  </Button>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="docs">
            <Card>
              <CardHeader>
                <CardTitle class="text-lg">平台文档构建</CardTitle>
                <CardDescription class="text-sm">
                  提交后端 `/api/v1/kb/bootstrap-docs`，用于构建平台文档检索知识库。
                </CardDescription>
              </CardHeader>
              <CardContent class="flex flex-col gap-4">
                <div class="grid gap-4 md:grid-cols-3">
                  <Field>
                    <FieldLabel for="docs-platform">平台</FieldLabel>
                    <Input
                      id="docs-platform"
                      v-model="manager.forms.value.docs.platform"
                      placeholder="datus"
                    />
                  </Field>
                  <Field>
                    <FieldLabel for="docs-build-mode">模式</FieldLabel>
                    <Select
                      :model-value="manager.forms.value.docs.buildMode"
                      @update:model-value="updateBuildMode"
                    >
                      <SelectTrigger id="docs-build-mode">
                        <SelectValue placeholder="选择模式" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectGroup>
                          <SelectItem
                            v-for="option in buildModeOptions"
                            :key="option.value"
                            :value="option.value"
                          >
                            {{ option.label }}
                          </SelectItem>
                        </SelectGroup>
                      </SelectContent>
                    </Select>
                  </Field>
                  <Field>
                    <FieldLabel for="docs-pool-size">并发</FieldLabel>
                    <Input
                      id="docs-pool-size"
                      v-model.number="manager.forms.value.docs.poolSize"
                      type="number"
                      min="1"
                      max="16"
                    />
                  </Field>
                </div>

                <div class="grid gap-4 md:grid-cols-2">
                  <Field>
                    <FieldLabel for="docs-source-type">来源类型</FieldLabel>
                    <Input
                      id="docs-source-type"
                      v-model="manager.forms.value.docs.sourceType"
                      placeholder="github / local / url"
                    />
                  </Field>
                  <Field>
                    <FieldLabel for="docs-source">来源</FieldLabel>
                    <Input
                      id="docs-source"
                      v-model="manager.forms.value.docs.source"
                      placeholder="仓库、目录或 URL"
                    />
                  </Field>
                  <Field>
                    <FieldLabel for="docs-version">版本</FieldLabel>
                    <Input
                      id="docs-version"
                      v-model="manager.forms.value.docs.version"
                      placeholder="v1"
                    />
                  </Field>
                  <Field>
                    <FieldLabel for="docs-github-ref">GitHub 引用</FieldLabel>
                    <Input
                      id="docs-github-ref"
                      v-model="manager.forms.value.docs.githubRef"
                      placeholder="main"
                    />
                  </Field>
                  <Field class="md:col-span-2">
                    <FieldLabel for="docs-github-token">GitHub 令牌</FieldLabel>
                    <Input
                      id="docs-github-token"
                      v-model="manager.forms.value.docs.githubToken"
                      type="password"
                      autocomplete="off"
                      placeholder="仅本次请求使用"
                    />
                    <FieldDescription>不会写入浏览器存储，日志输出会脱敏 token 字段。</FieldDescription>
                  </Field>
                </div>

                <div class="grid gap-4 md:grid-cols-3">
                  <Field>
                    <FieldLabel for="docs-chunk-size">分块大小</FieldLabel>
                    <Input
                      id="docs-chunk-size"
                      v-model="manager.forms.value.docs.chunkSize"
                      inputmode="numeric"
                      placeholder="可选"
                    />
                  </Field>
                  <Field>
                    <FieldLabel for="docs-max-depth">最大深度</FieldLabel>
                    <Input
                      id="docs-max-depth"
                      v-model="manager.forms.value.docs.maxDepth"
                      inputmode="numeric"
                      placeholder="可选"
                    />
                  </Field>
                  <Field>
                    <FieldLabel for="docs-paths">路径</FieldLabel>
                    <Textarea
                      id="docs-paths"
                      v-model="manager.forms.value.docs.pathsText"
                      class="min-h-24 text-sm leading-6"
                      placeholder="每行一个路径"
                    />
                  </Field>
                </div>

                <div class="grid gap-4 md:grid-cols-2">
                  <Field>
                    <FieldLabel for="docs-include">包含规则</FieldLabel>
                    <Textarea
                      id="docs-include"
                      v-model="manager.forms.value.docs.includePatternsText"
                      class="min-h-24 text-sm leading-6"
                      placeholder="每行一个包含规则"
                    />
                  </Field>
                  <Field>
                    <FieldLabel for="docs-exclude">排除规则</FieldLabel>
                    <Textarea
                      id="docs-exclude"
                      v-model="manager.forms.value.docs.excludePatternsText"
                      class="min-h-24 text-sm leading-6"
                      placeholder="每行一个排除规则"
                    />
                  </Field>
                </div>

                <div class="flex flex-wrap justify-end gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    :disabled="!manager.canCancel.value"
                    @click="manager.cancelActiveBootstrap"
                  >
                    <SquareIcon data-icon="inline-start" />
                    取消
                  </Button>
                  <Button
                    size="sm"
                    :disabled="manager.isRunning.value"
                    @click="manager.startDocsBootstrap"
                  >
                    <PlayIcon data-icon="inline-start" />
                    开始构建文档
                  </Button>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        <div class="flex flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle class="text-lg">最近事件</CardTitle>
              <CardDescription class="text-sm">
                {{ manager.latestLog.value?.message || "暂无构建事件" }}
              </CardDescription>
            </CardHeader>
            <CardContent class="flex flex-col gap-3">
              <div
                v-if="recentLogs.length === 0"
                class="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground"
              >
                启动构建后显示事件摘要
              </div>
              <div
                v-for="entry in recentLogs"
                :key="entry.id"
                class="flex flex-col gap-2 rounded-lg border bg-muted/20 p-3"
              >
                <div class="flex min-w-0 items-center gap-2">
                  <Badge
                    :variant="logBadgeVariant(entry.level)"
                    class="shrink-0"
                  >
                    {{ entry.event }}
                  </Badge>
                  <span class="min-w-0 flex-1 truncate text-sm font-medium">{{ entry.message }}</span>
                </div>
                <div class="flex flex-wrap gap-2 text-xs text-muted-foreground">
                  <span>{{ entry.mode === "kb" ? "业务知识库" : "平台文档" }}</span>
                  <span v-if="entry.component">{{ entry.component }}</span>
                  <span v-if="entry.streamId">{{ entry.streamId }}</span>
                </div>
                <p
                  v-if="payloadText(entry)"
                  class="line-clamp-2 text-xs leading-5 text-muted-foreground"
                >
                  {{ payloadText(entry) }}
                </p>
              </div>
            </CardContent>
          </Card>

          <Terminal
            :output="terminalText"
            :is-streaming="manager.isRunning.value"
            class="min-h-96"
            @clear="manager.clearLogs"
          >
            <TerminalHeader>
              <TerminalTitle>构建事件流</TerminalTitle>
              <div class="flex items-center gap-2">
                <TerminalStatus />
                <TerminalActions>
                  <TerminalCopyButton />
                  <TerminalClearButton />
                </TerminalActions>
              </div>
            </TerminalHeader>
            <TerminalContent class="min-h-80 text-xs leading-6" />
          </Terminal>
        </div>
      </div>

      <div class="grid gap-3 md:grid-cols-2">
        <Card>
          <CardHeader class="pb-3">
            <CardTitle class="flex items-center gap-2 text-sm">
              <DatabaseIcon data-icon="inline-start" />
              业务知识范围
            </CardTitle>
          </CardHeader>
          <CardContent class="text-sm text-muted-foreground">
            当前表单会提交组件、策略、目录名、数据库名、主题树、成功案例和 SQL 目录。
          </CardContent>
        </Card>
        <Card>
          <CardHeader class="pb-3">
            <CardTitle class="flex items-center gap-2 text-sm">
              <FileTextIcon data-icon="inline-start" />
              文档知识范围
            </CardTitle>
          </CardHeader>
          <CardContent class="text-sm text-muted-foreground">
            当前表单会提交平台、构建模式、来源、路径、分块和 GitHub 引用；敏感令牌只随请求发送。
          </CardContent>
        </Card>
      </div>
    </div>
  </section>
</template>
