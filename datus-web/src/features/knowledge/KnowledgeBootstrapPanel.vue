<script setup lang="ts">
import { computed } from "vue"
import {
  BookMarkedIcon,
  CheckCircle2Icon,
  CircleHelpIcon,
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
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { useKnowledgeBootstrap } from "@/composables/useKnowledgeBootstrap"
import KnowledgeUploadField from "@/features/knowledge/KnowledgeUploadField.vue"
import type {
  BootstrapBuildMode,
  BootstrapComponent,
  BootstrapStrategy,
  KnowledgeBootstrapStatus,
} from "@/types"

type BadgeVariant = "default" | "secondary" | "destructive" | "outline"

const props = defineProps<{
  datasource?: string | null
}>()

const manager = useKnowledgeBootstrap({ currentDatasource: () => props.datasource })

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

const buildModeOptions: ReadonlyArray<{ value: BootstrapBuildMode; label: string }> = [
  { value: "overwrite", label: "覆盖" },
  { value: "check", label: "检查" },
]

const successStoryAccept = ".csv,text/csv,application/vnd.ms-excel"
const referenceSqlAccept = ".sql,text/plain,application/sql"
const docsAccept = ".md,.markdown,.txt,.rst,.html,.htm,.json,.yaml,.yml,text/plain,text/markdown,text/html,application/json"

const statusLabel = computed(() => statusText(manager.status.value))
const activeModeLabel = computed(() => manager.activeMode.value === "kb" ? "业务知识库" : "平台文档")
const streamLabel = computed(() => manager.activeStreamId.value || "等待事件流")
const terminalText = computed(() => manager.terminalOutput.value || "等待构建事件...")
const currentDatasourceLabel = computed(() => props.datasource?.trim() || "后端默认数据源")
const usesSuccessStoryFields = computed(() => {
  const component = manager.forms.value.kb.component
  return component === "semantic_model" || component === "metrics"
})
const usesReferenceSqlFields = computed(() => manager.forms.value.kb.component === "reference_sql")
const usesSubjectTreeField = computed(() => {
  const component = manager.forms.value.kb.component
  return component === "metrics" || component === "reference_sql"
})
const selectedKbComponent = computed(() =>
  kbComponentOptions.find((option) => option.value === manager.forms.value.kb.component) ?? kbComponentOptions[0],
)
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

function updateKbComponent(value: unknown) {
  if (value === "metadata" || value === "semantic_model" || value === "metrics" || value === "reference_sql") {
    manager.forms.value.kb.component = value
  }
}

function updateStrategy(value: unknown) {
  if (value === "overwrite" || value === "check" || value === "incremental") {
    manager.forms.value.kb.strategy = value
  }
}

function updateBuildMode(value: unknown) {
  if (value === "overwrite" || value === "check") {
    manager.forms.value.docs.buildMode = value
  }
}
</script>

<template>
  <section class="min-h-0 flex-1 overflow-visible">
    <TooltipProvider>
      <div class="flex flex-col gap-4">
      <div class="flex flex-wrap items-center gap-2 rounded-md border bg-muted/30 px-3 py-2 text-sm">
        <Badge :variant="statusBadgeVariant(manager.status.value)">
          <component
            :is="statusIcon"
            :class="{ 'animate-spin': manager.status.value === 'running' }"
            data-icon="inline-start"
          />
          {{ statusLabel }}
        </Badge>
        <Badge variant="outline">{{ activeModeLabel }}</Badge>
        <span class="min-w-0 truncate text-xs text-muted-foreground">
          {{ streamLabel }}
        </span>
        <div class="ml-auto flex shrink-0 items-center gap-2">
          <span class="text-xs text-muted-foreground">日志 {{ manager.logs.value.length }}</span>
          <Button
            variant="outline"
            size="sm"
            :disabled="manager.logs.value.length === 0 || manager.isRunning.value"
            @click="manager.clearLogs"
          >
            <RotateCcwIcon data-icon="inline-start" />
            清空
          </Button>
        </div>
      </div>

      <div class="grid gap-4 xl:grid-cols-[minmax(0,1fr)_28rem]">
        <Tabs
          default-value="kb"
          class="flex flex-col gap-4"
        >
          <TabsList class="flex h-auto !flex-row flex-wrap justify-start">
            <TabsTrigger value="kb">业务知识库</TabsTrigger>
            <TabsTrigger value="docs">平台文档</TabsTrigger>
          </TabsList>

          <TabsContent value="kb">
            <Card size="sm">
              <CardHeader class="!flex flex-row items-center justify-between gap-3">
                <CardTitle class="text-lg">业务知识库构建</CardTitle>
                <Tooltip>
                  <TooltipTrigger as-child>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      class="size-6"
                      aria-label="业务知识库构建说明"
                    >
                      <CircleHelpIcon />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="left">
                    调用 `/api/v1/kb/bootstrap`，每次只构建一个知识组件。
                  </TooltipContent>
                </Tooltip>
              </CardHeader>
              <CardContent class="flex flex-col gap-3">
                <div class="grid gap-3 md:grid-cols-3">
                  <Field>
                    <div class="flex items-center gap-2">
                      <FieldLabel for="kb-component">构建类型</FieldLabel>
                      <Tooltip>
                        <TooltipTrigger as-child>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            class="size-5"
                            aria-label="当前构建类型说明"
                          >
                            <CircleHelpIcon />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>
                          {{ selectedKbComponent.description }}
                        </TooltipContent>
                      </Tooltip>
                    </div>
                    <Select
                      :model-value="manager.forms.value.kb.component"
                      @update:model-value="updateKbComponent"
                    >
                      <SelectTrigger id="kb-component">
                        <SelectValue placeholder="选择构建类型" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectGroup>
                          <SelectItem
                            v-for="option in kbComponentOptions"
                            :key="option.value"
                            :value="option.value"
                            :title="option.description"
                          >
                            {{ option.label }}
                          </SelectItem>
                        </SelectGroup>
                      </SelectContent>
                    </Select>
                  </Field>
                  <Field :data-disabled="true">
                    <FieldLabel for="kb-datasource">数据源</FieldLabel>
                    <Input
                      id="kb-datasource"
                      :model-value="currentDatasourceLabel"
                      disabled
                    />
                  </Field>
                  <Field>
                    <FieldLabel for="kb-strategy">更新策略</FieldLabel>
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
                </div>

                <div class="grid gap-3 lg:grid-cols-2">
                  <FieldGroup class="gap-3">
                    <div class="flex flex-wrap items-center justify-between gap-2">
                      <div class="flex items-center gap-2">
                        <span class="text-sm font-medium">历史 SQL</span>
                        <Tooltip>
                          <TooltipTrigger as-child>
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              class="size-5"
                              aria-label="历史 SQL 说明"
                            >
                              <CircleHelpIcon />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>
                            语义模型和指标构建需要上传 CSV，提交时使用 upload_id。
                          </TooltipContent>
                        </Tooltip>
                      </div>
                      <Badge :variant="usesSuccessStoryFields ? 'secondary' : 'outline'">
                        {{ usesSuccessStoryFields ? "可用" : "当前不可选" }}
                      </Badge>
                    </div>
                    <KnowledgeUploadField
                      id="kb-success-story-upload"
                      label="上传历史 SQL CSV"
                      :accept="successStoryAccept"
                      :files="manager.selectedUploadFiles.value.successStory"
                      :upload="manager.uploads.value.successStory"
                      :uploading="manager.uploadPending.value.successStory"
                      :disabled="manager.isRunning.value || !usesSuccessStoryFields"
                      @files-change="manager.setUploadFiles('successStory', $event)"
                      @upload="manager.uploadFiles('successStory')"
                      @clear="manager.clearUpload('successStory')"
                    />
                  </FieldGroup>

                  <FieldGroup class="gap-3">
                    <div class="flex flex-wrap items-center justify-between gap-2">
                      <div class="flex items-center gap-2">
                        <span class="text-sm font-medium">参考 SQL</span>
                        <Tooltip>
                          <TooltipTrigger as-child>
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              class="size-5"
                              aria-label="参考 SQL 说明"
                            >
                              <CircleHelpIcon />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>
                            参考 SQL 构建可上传多个 .sql 文件。
                          </TooltipContent>
                        </Tooltip>
                      </div>
                      <Badge :variant="usesReferenceSqlFields ? 'secondary' : 'outline'">
                        {{ usesReferenceSqlFields ? "可用" : "当前不可选" }}
                      </Badge>
                    </div>
                    <KnowledgeUploadField
                      id="kb-reference-sql-upload"
                      label="上传参考 SQL"
                      :accept="referenceSqlAccept"
                      multiple
                      :files="manager.selectedUploadFiles.value.referenceSql"
                      :upload="manager.uploads.value.referenceSql"
                      :uploading="manager.uploadPending.value.referenceSql"
                      :disabled="manager.isRunning.value || !usesReferenceSqlFields"
                      @files-change="manager.setUploadFiles('referenceSql', $event)"
                      @upload="manager.uploadFiles('referenceSql')"
                      @clear="manager.clearUpload('referenceSql')"
                    />
                  </FieldGroup>

                  <Field
                    class="lg:col-span-2"
                    :data-disabled="!usesSubjectTreeField ? true : undefined"
                  >
                    <div class="flex flex-wrap items-center justify-between gap-2">
                      <div class="flex items-center gap-2">
                        <FieldLabel for="kb-subject-tree">预定义主题树分类</FieldLabel>
                        <Tooltip>
                          <TooltipTrigger as-child>
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              class="size-5"
                              aria-label="预定义主题树分类说明"
                            >
                              <CircleHelpIcon />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>
                            指标和参考 SQL 构建可使用；留空时后端复用或学习已有分类。
                          </TooltipContent>
                        </Tooltip>
                      </div>
                      <Badge :variant="usesSubjectTreeField ? 'secondary' : 'outline'">
                        {{ usesSubjectTreeField ? "可用" : "当前不可选" }}
                      </Badge>
                    </div>
                    <Textarea
                      id="kb-subject-tree"
                      v-model="manager.forms.value.kb.subjectTreeText"
                      class="min-h-20 text-sm leading-6"
                      :disabled="!usesSubjectTreeField"
                      placeholder="每行一个主题路径"
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
            <Card size="sm">
              <CardHeader class="!flex flex-row items-center justify-between gap-3">
                <CardTitle class="text-lg">平台文档构建</CardTitle>
                <Tooltip>
                  <TooltipTrigger as-child>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      class="size-6"
                      aria-label="平台文档构建说明"
                    >
                      <CircleHelpIcon />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="left">
                    调用 `/api/v1/kb/bootstrap-docs`，构建平台文档检索知识库。
                  </TooltipContent>
                </Tooltip>
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
                  <KnowledgeUploadField
                    id="docs-upload"
                    label="上传平台文档"
                    :accept="docsAccept"
                    multiple
                    :files="manager.selectedUploadFiles.value.docs"
                    :upload="manager.uploads.value.docs"
                    :uploading="manager.uploadPending.value.docs"
                    :disabled="manager.isRunning.value"
                    @files-change="manager.setUploadFiles('docs', $event)"
                    @upload="manager.uploadFiles('docs')"
                    @clear="manager.clearUpload('docs')"
                  />
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

        <Terminal
          :output="terminalText"
          :is-streaming="manager.isRunning.value"
          class="min-h-[28rem]"
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
          <TerminalContent class="min-h-96 text-xs leading-6" />
        </Terminal>
      </div>
      </div>
    </TooltipProvider>
  </section>
</template>
