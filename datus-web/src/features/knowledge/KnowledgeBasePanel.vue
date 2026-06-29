<script setup lang="ts">
import { computed, onMounted, ref, shallowRef, watch } from "vue"
import { toast } from "vue-sonner"
import {
  BookMarkedIcon,
  CheckCircle2Icon,
  DatabaseIcon,
  GitBranchIcon,
  RefreshCwIcon,
  SaveIcon,
  Table2Icon,
  XCircleIcon,
} from "@lucide/vue"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ButtonGroup } from "@/components/ui/button-group"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogDescription,
  DialogHeader,
  DialogScrollContent,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Textarea } from "@/components/ui/textarea"
import { useConnection } from "@/composables/useConnection"
import { useSemanticWorkbench } from "@/composables/useSemanticWorkbench"
import type { ChatWorkspace } from "@/composables/useChatWorkspace"
import KnowledgeBootstrapPanel from "@/features/knowledge/KnowledgeBootstrapPanel.vue"
import CatalogTree from "@/features/workspace/CatalogTree.vue"
import SubjectTree from "@/features/workspace/SubjectTree.vue"
import { subjectApi } from "@/lib/api"
import { catalogSchemaRows, catalogTableRows } from "@/lib/catalog-tree"
import type { MetricDimensionsData, MetricInfo, ReferenceSQLInfo, SubjectNode } from "@/types"
import type { SubjectTreeNode } from "@/lib/subject-tree"

type KnowledgeTreeMode = "catalog" | "subject"

const props = defineProps<{
  workspace: ChatWorkspace
  selectedTable?: string | null
}>()

const emit = defineEmits<{
  updateTable: [table: string]
}>()

const connection = useConnection()
const semantic = useSemanticWorkbench()

const treeMode = shallowRef<KnowledgeTreeMode>("catalog")
const buildDialogOpen = shallowRef(false)
const subjects = ref<SubjectNode[]>([])
const loadingSubjects = shallowRef(false)
const selectedSubject = shallowRef<SubjectTreeNode | null>(null)
const metricInfo = ref<MetricInfo | null>(null)
const metricDimensions = ref<MetricDimensionsData | null>(null)
const referenceSql = ref<ReferenceSQLInfo | null>(null)
const loadingSubjectDetail = shallowRef(false)

const selectedTable = computed(() => props.selectedTable?.trim() ?? "")
const tableColumnCount = computed(() => semantic.tableDetail.value?.columns.length ?? 0)
const tableIndexCount = computed(() => semantic.tableDetail.value?.indexes.length ?? 0)
const tableRowCount = computed(() => formatRows(semantic.tableDetail.value?.rows))
const schemaRows = computed(() => catalogSchemaRows(props.workspace.catalogEntries.value))
const tableRows = computed(() => catalogTableRows(props.workspace.catalogEntries.value))
const selectedTableRow = computed(() =>
  tableRows.value.find((row) => row.fullName === selectedTable.value) ?? null,
)
const selectedSubjectPath = computed(() => selectedSubject.value?.path ?? null)
const currentKnowledgeContextLabel = computed(() => {
  if (treeMode.value === "subject") {
    return selectedSubject.value
      ? selectedSubject.value.subjectPath.join(" / ")
      : "未选择 Subject"
  }

  return selectedTable.value || "未选择表"
})
const subjectTypeLabel = computed(() => {
  if (!selectedSubject.value) return "未选择"
  if (selectedSubject.value.type === "metric") return "指标"
  if (selectedSubject.value.type === "reference_sql") return "参考 SQL"
  return "主题目录"
})
const treePanelDescription = computed(() =>
  treeMode.value === "catalog"
    ? "点击表节点加载结构和语义 YAML。"
    : "点击主题、指标或参考 SQL 查看详情。",
)
const treeRefreshing = computed(() =>
  treeMode.value === "catalog" ? props.workspace.isLoadingCatalog.value : loadingSubjects.value,
)

function formatRows(value: number | undefined) {
  if (typeof value !== "number") return "-"
  return value.toLocaleString("zh-CN")
}

function switchTreeMode(mode: KnowledgeTreeMode) {
  treeMode.value = mode
  if (mode === "subject" && subjects.value.length === 0 && !loadingSubjects.value) {
    void loadSubjects()
  }
}

function refreshTree() {
  if (treeMode.value === "catalog") {
    void props.workspace.loadCatalog()
    return
  }

  void loadSubjects()
}

function requestTableLoad(value: string) {
  const target = value.trim()
  if (!target) {
    void semantic.loadTableDetails()
    return
  }

  treeMode.value = "catalog"
  if (target === selectedTable.value) {
    void semantic.loadTableDetails(target)
    return
  }

  emit("updateTable", target)
}

async function loadSubjects() {
  loadingSubjects.value = true
  try {
    const result = await subjectApi.list(connection.effectiveBase())
    subjects.value = result?.subjects ?? []
  } catch (error) {
    console.error("加载 Subject Tree 失败:", error)
    toast.error("加载 Subject Tree 失败")
  } finally {
    loadingSubjects.value = false
  }
}

async function selectSubject(node: SubjectTreeNode) {
  selectedSubject.value = node
  metricInfo.value = null
  metricDimensions.value = null
  referenceSql.value = null

  if (node.type === "directory") return

  loadingSubjectDetail.value = true
  try {
    if (node.type === "metric") {
      const [metric, dimensions] = await Promise.all([
        subjectApi.getMetric(connection.effectiveBase(), node.subjectPath),
        subjectApi.getMetricDimensions(connection.effectiveBase(), node.subjectPath),
      ])
      metricInfo.value = metric
      metricDimensions.value = dimensions
      return
    }

    if (node.type === "reference_sql") {
      referenceSql.value = await subjectApi.getReferenceSql(connection.effectiveBase(), node.subjectPath)
    }
  } catch (error) {
    console.error("加载 Subject 详情失败:", error)
    toast.error("加载 Subject 详情失败")
  } finally {
    loadingSubjectDetail.value = false
  }
}

watch(
  selectedTable,
  (table) => {
    if (!table || table === semantic.tableName.value.trim()) return
    void semantic.loadTableDetails(table)
  },
  { immediate: true },
)

onMounted(() => {
  void loadSubjects()
})
</script>

<template>
  <section class="flex min-h-0 flex-1 overflow-hidden p-4">
    <div class="flex min-h-0 flex-1 flex-col gap-4">
      <div class="flex shrink-0 flex-wrap items-center gap-2 rounded-md border bg-muted/30 px-3 py-2 text-sm">
        <div class="flex min-w-0 flex-1 flex-wrap items-center gap-2">
          <div class="flex min-w-0 items-center gap-2">
            <DatabaseIcon class="shrink-0 text-muted-foreground" />
            <span class="text-xs text-muted-foreground">数据源</span>
            <span class="max-w-48 truncate font-medium">
              {{ workspace.currentDatasource.value || "未选择" }}
            </span>
          </div>
          <Badge variant="secondary">Schema {{ schemaRows.length }}</Badge>
          <Badge variant="secondary">Tables {{ tableRows.length }}</Badge>
          <Badge variant="secondary">Subjects {{ subjects.length }}</Badge>
          <Badge variant="outline">
            {{ treeMode === "catalog" ? "目录 Tree" : "Subject Tree" }}
          </Badge>
          <div class="flex min-w-0 flex-1 items-center gap-2 text-xs text-muted-foreground">
            <Table2Icon
              v-if="treeMode === 'catalog'"
              class="shrink-0"
            />
            <GitBranchIcon
              v-else
              class="shrink-0"
            />
            <span class="truncate">{{ currentKnowledgeContextLabel }}</span>
          </div>
        </div>
        <Button
          class="ml-auto shrink-0"
          size="sm"
          @click="buildDialogOpen = true"
        >
          <BookMarkedIcon data-icon="inline-start" />
          知识构建
        </Button>
      </div>

      <div class="grid min-h-0 flex-1 grid-rows-[minmax(0,1fr)_minmax(0,1fr)] gap-4 overflow-hidden xl:grid-cols-[24rem_minmax(0,1fr)] xl:grid-rows-1">
        <Card class="flex min-h-0 min-w-0 flex-col">
          <CardHeader class="shrink-0">
            <div class="flex flex-col gap-3">
              <div class="min-w-0">
                <CardTitle class="text-lg">
                  {{ treeMode === "catalog" ? "目录 Tree" : "Subject Tree" }}
                </CardTitle>
                <CardDescription class="text-sm">
                  {{ treePanelDescription }}
                </CardDescription>
              </div>
              <div class="flex shrink-0 flex-wrap items-center gap-2">
                <ButtonGroup orientation="horizontal">
                  <Button
                    size="sm"
                    :variant="treeMode === 'catalog' ? 'default' : 'outline'"
                    @click="switchTreeMode('catalog')"
                  >
                    <Table2Icon data-icon="inline-start" />
                    目录 Tree
                  </Button>
                  <Button
                    size="sm"
                    :variant="treeMode === 'subject' ? 'default' : 'outline'"
                    @click="switchTreeMode('subject')"
                  >
                    <GitBranchIcon data-icon="inline-start" />
                    Subject Tree
                  </Button>
                </ButtonGroup>
                <Button
                  variant="outline"
                  size="sm"
                  :disabled="treeRefreshing"
                  @click="refreshTree"
                >
                  <RefreshCwIcon data-icon="inline-start" />
                  刷新
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent class="min-h-0 flex-1">
            <CatalogTree
              v-if="treeMode === 'catalog'"
              class="min-h-0 flex-1"
              embedded
              :entries="workspace.catalogEntries.value"
              :selected-table="selectedTable"
              :loading="workspace.isLoadingCatalog.value"
              @refresh="workspace.loadCatalog()"
              @select-table="requestTableLoad"
            />
            <SubjectTree
              v-else
              class="min-h-0 flex-1"
              embedded
              :subjects="subjects"
              :selected-path="selectedSubjectPath"
              :loading="loadingSubjects"
              @refresh="loadSubjects"
              @select-subject="selectSubject"
            />
          </CardContent>
        </Card>

        <Card class="flex min-h-0 min-w-0 flex-col">
          <CardHeader
            v-if="treeMode === 'subject'"
            class="flex shrink-0 flex-row items-start justify-between gap-3"
          >
            <div class="min-w-0">
              <CardTitle class="truncate text-lg">
                {{ selectedSubject?.name || "未选择 Subject" }}
              </CardTitle>
              <CardDescription class="text-sm">
                {{ selectedSubject ? selectedSubject.subjectPath.join(" / ") : "从 Subject Tree 选择节点后浏览详情" }}
              </CardDescription>
            </div>
            <Badge variant="outline">{{ loadingSubjectDetail ? "加载中" : subjectTypeLabel }}</Badge>
          </CardHeader>
          <CardHeader
            v-else
            class="flex shrink-0 flex-row items-center justify-between gap-3"
          >
            <div class="min-w-0">
              <CardTitle class="truncate text-lg">
                {{ semantic.tableDetail.value?.name || selectedTable || "未加载表" }}
              </CardTitle>
              <CardDescription class="text-sm">
                {{ selectedTableRow ? `${selectedTableRow.database || "-"} / ${selectedTableRow.schema || "-"}` : "选择左侧表后加载结构与语义模型" }}
              </CardDescription>
            </div>
            <Badge variant="outline">索引 {{ tableIndexCount }}</Badge>
          </CardHeader>
          <CardContent class="min-h-0 flex-1 p-0">
            <ScrollArea class="h-full px-6 pb-6">
              <div class="flex min-w-0 flex-col gap-4">
                <template v-if="treeMode === 'subject'">
                  <div
                    v-if="!selectedSubject"
                    class="rounded-md border p-4 text-sm text-muted-foreground"
                  >
                    选择左侧 Subject 节点后查看指标、维度或参考 SQL。
                  </div>

                  <template v-else-if="selectedSubject.type === 'metric'">
                    <div class="rounded-md border">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>维度</TableHead>
                            <TableHead>类型</TableHead>
                            <TableHead>主键</TableHead>
                            <TableHead>说明</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          <TableRow
                            v-for="dimension in metricDimensions?.dimensions ?? []"
                            :key="dimension.name"
                          >
                            <TableCell class="font-medium">{{ dimension.name }}</TableCell>
                            <TableCell>{{ dimension.type || "-" }}</TableCell>
                            <TableCell>{{ dimension.is_primary_key ? "是" : "否" }}</TableCell>
                            <TableCell>{{ dimension.description || "-" }}</TableCell>
                          </TableRow>
                          <TableRow v-if="(metricDimensions?.dimensions ?? []).length === 0">
                            <TableCell
                              colspan="4"
                              class="h-24 text-center text-sm text-muted-foreground"
                            >
                              暂无维度信息
                            </TableCell>
                          </TableRow>
                        </TableBody>
                      </Table>
                    </div>
                    <Textarea
                      :model-value="metricInfo?.yaml ?? ''"
                      readonly
                      class="min-h-72 font-mono text-xs leading-6"
                      placeholder="暂无指标 YAML"
                    />
                  </template>

                  <template v-else-if="selectedSubject.type === 'reference_sql'">
                    <div class="grid gap-3 md:grid-cols-2">
                      <div class="rounded-md border p-3">
                        <div class="text-xs text-muted-foreground">名称</div>
                        <div class="mt-1 truncate text-sm font-medium">{{ referenceSql?.name || "-" }}</div>
                      </div>
                      <div class="rounded-md border p-3">
                        <div class="text-xs text-muted-foreground">摘要</div>
                        <div class="mt-1 truncate text-sm font-medium">{{ referenceSql?.summary || "-" }}</div>
                      </div>
                    </div>
                    <Textarea
                      :model-value="referenceSql?.sql ?? ''"
                      readonly
                      class="min-h-72 font-mono text-xs leading-6"
                      placeholder="暂无参考 SQL"
                    />
                    <div class="rounded-md border p-3 text-sm text-muted-foreground">
                      {{ referenceSql?.search_text || "暂无检索文本" }}
                    </div>
                  </template>

                  <div
                    v-else
                    class="rounded-md border p-4 text-sm text-muted-foreground"
                  >
                    当前节点是主题目录，继续展开或选择子节点。
                  </div>
                </template>

                <template v-else>
                  <div class="grid gap-2 sm:grid-cols-3">
                    <div class="rounded-md border p-3">
                      <div class="text-xs text-muted-foreground">Rows</div>
                      <div class="mt-1 text-lg font-semibold">{{ tableRowCount }}</div>
                    </div>
                    <div class="rounded-md border p-3">
                      <div class="text-xs text-muted-foreground">Columns</div>
                      <div class="mt-1 text-lg font-semibold">{{ tableColumnCount }}</div>
                    </div>
                    <div class="rounded-md border p-3">
                      <div class="text-xs text-muted-foreground">Indexes</div>
                      <div class="mt-1 text-lg font-semibold">{{ tableIndexCount }}</div>
                    </div>
                  </div>

                  <div class="rounded-md border">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>列</TableHead>
                          <TableHead>类型</TableHead>
                          <TableHead>可空</TableHead>
                          <TableHead>默认值</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        <TableRow
                          v-for="column in semantic.tableDetail.value?.columns ?? []"
                          :key="column.name"
                        >
                          <TableCell class="font-medium">
                            {{ column.name }}
                            <Badge
                              v-if="column.pk"
                              variant="secondary"
                              class="ml-2"
                            >
                              PK
                            </Badge>
                          </TableCell>
                          <TableCell>{{ column.type }}</TableCell>
                          <TableCell>{{ column.nullable ? "是" : "否" }}</TableCell>
                          <TableCell>{{ column.default_value || "-" }}</TableCell>
                        </TableRow>
                        <TableRow v-if="(semantic.tableDetail.value?.columns ?? []).length === 0">
                          <TableCell
                            colspan="4"
                            class="h-24 text-center text-sm text-muted-foreground"
                          >
                            暂无表结构
                          </TableCell>
                        </TableRow>
                      </TableBody>
                    </Table>
                  </div>

                  <div class="flex flex-col gap-3">
                    <div>
                      <div class="text-lg font-semibold">语义 YAML</div>
                      <div class="text-sm text-muted-foreground">表级语义定义。</div>
                    </div>
                    <Textarea
                      v-model="semantic.semanticYaml.value"
                      class="min-h-96 font-mono text-xs leading-6"
                      spellcheck="false"
                      placeholder="加载表后显示语义模型 YAML"
                    />
                    <div class="flex flex-wrap items-center justify-between gap-3">
                      <Badge :variant="semantic.validation.value?.valid ? 'secondary' : semantic.validation.value ? 'destructive' : 'outline'">
                        <CheckCircle2Icon
                          v-if="semantic.validation.value?.valid"
                          data-icon="inline-start"
                        />
                        <XCircleIcon
                          v-else-if="semantic.validation.value"
                          data-icon="inline-start"
                        />
                        {{ semantic.validation.value?.valid ? "校验通过" : semantic.validation.value ? "校验失败" : "未校验" }}
                      </Badge>
                      <div class="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          :disabled="semantic.validating.value"
                          @click="semantic.validateSemanticModel"
                        >
                          <CheckCircle2Icon data-icon="inline-start" />
                          校验
                        </Button>
                        <Button
                          size="sm"
                          :disabled="semantic.savingSemantic.value"
                          @click="semantic.saveSemanticModel"
                        >
                          <SaveIcon data-icon="inline-start" />
                          保存
                        </Button>
                      </div>
                    </div>
                    <div
                      v-if="semantic.semanticInvalidMessages.value.length > 0"
                      class="rounded-md border p-3 text-sm text-destructive"
                    >
                      <div
                        v-for="message in semantic.semanticInvalidMessages.value"
                        :key="message"
                      >
                        {{ message }}
                      </div>
                    </div>
                  </div>
                </template>
              </div>
            </ScrollArea>
          </CardContent>
        </Card>
      </div>
    </div>

    <Dialog v-model:open="buildDialogOpen">
      <DialogScrollContent class="max-w-6xl">
        <DialogHeader>
          <DialogTitle>知识构建</DialogTitle>
          <DialogDescription>
            运行业务知识库和平台文档构建任务。
          </DialogDescription>
        </DialogHeader>
        <KnowledgeBootstrapPanel />
      </DialogScrollContent>
    </Dialog>
  </section>
</template>
