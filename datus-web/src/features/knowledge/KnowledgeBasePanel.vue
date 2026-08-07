<script setup lang="ts">
import { computed, onMounted, ref, shallowRef, watch } from "vue"
import { toast } from "vue-sonner"
import {
  BookMarkedIcon,
  DatabaseIcon,
  GitBranchIcon,
  RefreshCwIcon,
  Table2Icon,
} from "@lucide/vue"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import {
  Dialog,
  DialogDescription,
  DialogHeader,
  DialogScrollContent,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useConnection } from "@/composables/useConnection"
import { useSemanticWorkbench } from "@/composables/useSemanticWorkbench"
import type { ChatWorkspace } from "@/composables/useChatWorkspace"
import KnowledgeBootstrapPanel from "@/features/knowledge/KnowledgeBootstrapPanel.vue"
import KnowledgeDetailPanel from "@/features/knowledge/KnowledgeDetailPanel.vue"
import PageHeaderToolbar from "@/features/shared/PageHeaderToolbar.vue"
import PanelCardHeader from "@/features/shared/PanelCardHeader.vue"
import CatalogTree from "@/features/workspace/CatalogTree.vue"
import SubjectTree from "@/features/workspace/SubjectTree.vue"
import { subjectApi } from "@/lib/api"
import { catalogSchemaRows, catalogTableRows } from "@/lib/catalog-tree"
import { selectedOptionLabel } from "@/lib/datasource-display"
import type { MetricDimensionsData, MetricInfo, ReferenceSQLInfo, SubjectNode } from "@/types"
import type { SubjectTreeNode } from "@/lib/subject-tree"

type KnowledgeTreeMode = "catalog" | "subject"

const props = defineProps<{
  workspace: ChatWorkspace
  selectedTable?: string | null
  canViewSubjectTree?: boolean
}>()

const emit = defineEmits<{
  updateTable: [table: string]
}>()

const connection = useConnection()
const semantic = useSemanticWorkbench({
  currentDatasource: () => props.workspace.currentDatasource.value,
})

const treeMode = shallowRef<KnowledgeTreeMode>("catalog")
const buildDialogOpen = shallowRef(false)
const mobileDetailOpen = shallowRef(false)
const subjects = ref<SubjectNode[]>([])
const loadingSubjects = shallowRef(false)
const selectedSubject = shallowRef<SubjectTreeNode | null>(null)
const metricInfo = ref<MetricInfo | null>(null)
const metricDimensions = ref<MetricDimensionsData | null>(null)
const referenceSql = ref<ReferenceSQLInfo | null>(null)
const loadingSubjectDetail = shallowRef(false)
let subjectListRequestId = 0
let subjectDetailRequestId = 0

const selectedTable = computed(() => props.selectedTable?.trim() ?? "")
const currentDatasource = computed(() => props.workspace.currentDatasource.value.trim())
const schemaRows = computed(() => catalogSchemaRows(props.workspace.catalogEntries.value))
const tableRows = computed(() => catalogTableRows(props.workspace.catalogEntries.value))
const currentDatasourceLabel = computed(() =>
  selectedOptionLabel(props.workspace.currentDatasource.value, props.workspace.visibleDatasourceOptions.value) || "未选择"
)
const canUseSubjectTree = computed(() => props.canViewSubjectTree !== false)
const selectedTableRow = computed(() =>
  tableRows.value.find((row) => row.fullName === selectedTable.value) ?? null,
)
const selectedSubjectPath = computed(() => selectedSubject.value?.path ?? null)
const currentKnowledgeContextLabel = computed(() => {
  if (treeMode.value === "subject") {
    return selectedSubject.value
      ? selectedSubject.value.subjectPath.join(" / ")
      : "未选择主题"
  }

  return selectedTable.value || "未选择表"
})
const treePanelDescription = computed(() =>
  treeMode.value === "catalog"
    ? "点击表节点加载结构和语义 YAML。"
    : "点击主题、指标或参考 SQL 查看详情。",
)
const treeRefreshing = computed(() =>
  treeMode.value === "catalog" ? props.workspace.isLoadingCatalog.value : loadingSubjects.value,
)
const detailLoading = computed(() =>
  treeMode.value === "subject" ? loadingSubjectDetail.value : semantic.loadingTable.value,
)
const detailLoadingLabel = computed(() =>
  treeMode.value === "subject" ? "正在加载主题详情..." : "正在加载表详情...",
)
const tableDetailTitle = computed(() => {
  if (semantic.loadingTable.value) return selectedTable.value || "正在加载表"
  return semantic.tableDetail.value?.name || selectedTable.value || "未加载表"
})
const tableDetailDescription = computed(() =>
  selectedTableRow.value
    ? `${selectedTableRow.value.database || "-"} / ${selectedTableRow.value.schema || "-"}`
    : "选择左侧表后加载结构与语义模型"
)
const mobileDetailTitle = computed(() =>
  treeMode.value === "subject"
    ? selectedSubject.value?.name || "主题详情"
    : tableDetailTitle.value
)
const mobileDetailDescription = computed(() =>
  treeMode.value === "subject"
    ? selectedSubject.value?.subjectPath.join(" / ") || "查看主题节点详情"
    : tableDetailDescription.value
)

function showMobileDetail() {
  if (typeof window !== "undefined" && window.matchMedia("(max-width: 1279px)").matches) {
    mobileDetailOpen.value = true
  }
}

function switchTreeMode(mode: unknown) {
  if (mode !== "catalog" && mode !== "subject") return
  if (mode === "subject" && !canUseSubjectTree.value) return

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

  if (!canUseSubjectTree.value) return

  void loadSubjects()
}

function requestTableLoad(value: string) {
  const target = value.trim()
  if (!target) {
    void semantic.loadTableDetails()
    return
  }

  treeMode.value = "catalog"
  showMobileDetail()
  if (target === selectedTable.value) {
    void semantic.loadTableDetails(target)
    return
  }

  emit("updateTable", target)
}

async function loadSubjects() {
  if (!canUseSubjectTree.value) return

  const requestId = ++subjectListRequestId
  loadingSubjects.value = true
  try {
    const result = await subjectApi.list(connection.effectiveBase(), currentDatasource.value)
    if (requestId !== subjectListRequestId) return
    subjects.value = result?.subjects ?? []
  } catch (error) {
    if (requestId !== subjectListRequestId) return
    console.error("加载主题树失败:", error)
    toast.error("加载主题树失败")
  } finally {
    if (requestId === subjectListRequestId) {
      loadingSubjects.value = false
    }
  }
}

async function selectSubject(node: SubjectTreeNode) {
  const requestId = ++subjectDetailRequestId
  selectedSubject.value = node
  metricInfo.value = null
  metricDimensions.value = null
  referenceSql.value = null
  loadingSubjectDetail.value = false

  if (node.type === "directory") return

  showMobileDetail()

  loadingSubjectDetail.value = true
  try {
    if (node.type === "metric") {
      const [metric, dimensions] = await Promise.all([
        subjectApi.getMetric(connection.effectiveBase(), node.subjectPath, currentDatasource.value),
        subjectApi.getMetricDimensions(connection.effectiveBase(), node.subjectPath, currentDatasource.value),
      ])
      if (requestId !== subjectDetailRequestId) return
      metricInfo.value = metric
      metricDimensions.value = dimensions
      return
    }

    if (node.type === "reference_sql") {
      const result = await subjectApi.getReferenceSql(
        connection.effectiveBase(),
        node.subjectPath,
        currentDatasource.value,
      )
      if (requestId !== subjectDetailRequestId) return
      referenceSql.value = result
    }
  } catch (error) {
    if (requestId !== subjectDetailRequestId) return
    console.error("加载主题详情失败:", error)
    toast.error("加载主题详情失败")
  } finally {
    if (requestId === subjectDetailRequestId) {
      loadingSubjectDetail.value = false
    }
  }
}

function clearSubjectSelection() {
  subjectDetailRequestId += 1
  selectedSubject.value = null
  metricInfo.value = null
  metricDimensions.value = null
  referenceSql.value = null
  loadingSubjectDetail.value = false
}

watch(
  canUseSubjectTree,
  (canView) => {
    if (canView || treeMode.value !== "subject") return
    subjectListRequestId += 1
    loadingSubjects.value = false
    treeMode.value = "catalog"
    subjects.value = []
    clearSubjectSelection()
  },
)

watch(currentDatasource, () => {
  subjectListRequestId += 1
  loadingSubjects.value = false
  subjects.value = []
  mobileDetailOpen.value = false
  clearSubjectSelection()
  if (canUseSubjectTree.value) {
    void loadSubjects()
  }
})

watch(
  selectedTable,
  (table) => {
    if (!table || table === semantic.tableName.value.trim()) return
    void semantic.loadTableDetails(table)
  },
  { immediate: true },
)

onMounted(() => {
  if (canUseSubjectTree.value) {
    void loadSubjects()
  }
})
</script>

<template>
  <section class="flex min-h-0 flex-1 overflow-hidden p-4">
    <div class="flex min-h-0 flex-1 flex-col gap-4">
      <Tabs
        :model-value="treeMode"
        class="flex min-h-0 flex-1 flex-col gap-4"
        @update:model-value="switchTreeMode"
      >
        <PageHeaderToolbar
          title="知识库"
          description="浏览数据目录、主题树，并运行知识构建任务。"
          aria-label="知识库页头工具栏"
        >
          <template #leading>
            <BookMarkedIcon />
          </template>

          <template #meta>
            <div class="flex min-w-0 items-center gap-2">
              <DatabaseIcon class="size-4 shrink-0 text-muted-foreground" />
              <span class="text-xs text-muted-foreground">数据源</span>
              <span class="max-w-48 truncate font-medium">
                {{ currentDatasourceLabel }}
              </span>
            </div>
            <Badge variant="secondary">模式 {{ schemaRows.length }}</Badge>
            <Badge variant="secondary">表 {{ tableRows.length }}</Badge>
            <Badge
              v-if="canUseSubjectTree"
              variant="secondary"
            >
              主题 {{ subjects.length }}
            </Badge>
            <div class="flex min-w-0 max-w-48 items-center gap-2 text-xs text-muted-foreground">
              <Table2Icon
                v-if="treeMode === 'catalog'"
                class="size-4 shrink-0"
              />
              <GitBranchIcon
                v-else
                class="size-4 shrink-0"
              />
              <span class="truncate">{{ currentKnowledgeContextLabel }}</span>
            </div>
          </template>

          <template #navigation>
            <TabsList class="flex h-auto max-w-full !flex-row flex-nowrap justify-start">
              <TabsTrigger value="catalog">
                <Table2Icon data-icon="inline-start" />
                目录树
              </TabsTrigger>
              <TabsTrigger
                v-if="canUseSubjectTree"
                value="subject"
              >
                <GitBranchIcon data-icon="inline-start" />
                主题树
              </TabsTrigger>
            </TabsList>
          </template>

          <template #actions>
            <Button
              variant="outline"
              size="sm"
              :disabled="treeRefreshing"
              @click="refreshTree"
            >
              <RefreshCwIcon
                data-icon="inline-start"
                :class="treeRefreshing && 'animate-spin'"
              />
              刷新
            </Button>
            <Button
              size="sm"
              @click="buildDialogOpen = true"
            >
              <BookMarkedIcon data-icon="inline-start" />
              知识构建
            </Button>
          </template>
        </PageHeaderToolbar>

        <div class="-m-3 grid min-h-0 flex-1 grid-rows-[minmax(0,1fr)] gap-4 overflow-hidden p-3 xl:grid-cols-[24rem_minmax(0,1fr)]">
          <Card class="flex min-h-0 min-w-0 flex-col gap-4">
            <PanelCardHeader
              :title="treeMode === 'catalog' ? '目录树' : '主题树'"
              :description="treePanelDescription"
            >
              <template #icon>
                <Table2Icon
                  v-if="treeMode === 'catalog'"
                  aria-hidden="true"
                />
                <GitBranchIcon
                  v-else
                  aria-hidden="true"
                />
              </template>
            </PanelCardHeader>
            <CardContent class="flex min-h-0 flex-1 flex-col">
              <TabsContent
                value="catalog"
                class="flex min-h-0 flex-1 flex-col"
              >
                <CatalogTree
                  class="min-h-0 flex-1"
                  embedded
                  :entries="workspace.catalogEntries.value"
                  :selected-table="selectedTable"
                  :loading="workspace.isLoadingCatalog.value"
                  @refresh="workspace.loadCatalog()"
                  @select-table="requestTableLoad"
                />
              </TabsContent>
              <TabsContent
                value="subject"
                class="flex min-h-0 flex-1 flex-col"
              >
                <SubjectTree
                  v-if="canUseSubjectTree"
                  class="min-h-0 flex-1"
                  embedded
                  :subjects="subjects"
                  :selected-path="selectedSubjectPath"
                  :loading="loadingSubjects"
                  @refresh="loadSubjects"
                  @select-subject="selectSubject"
                />
              </TabsContent>
            </CardContent>
          </Card>

          <KnowledgeDetailPanel
            class="hidden xl:flex"
            :tree-mode="treeMode"
            :selected-subject="selectedSubject"
            :detail-loading="detailLoading"
            :detail-loading-label="detailLoadingLabel"
            :metric-info="metricInfo"
            :metric-dimensions="metricDimensions"
            :reference-sql="referenceSql"
            :table-detail-title="tableDetailTitle"
            :table-detail-description="tableDetailDescription"
            :semantic="semantic"
          />
        </div>
      </Tabs>
    </div>

    <Sheet v-model:open="mobileDetailOpen">
      <SheetContent
        side="right"
        class="gap-0 data-[side=right]:w-full sm:data-[side=right]:max-w-2xl xl:hidden"
      >
        <SheetHeader class="border-b">
          <SheetTitle>{{ mobileDetailTitle }}</SheetTitle>
          <SheetDescription>{{ mobileDetailDescription }}</SheetDescription>
        </SheetHeader>
        <KnowledgeDetailPanel
          class="min-h-0 flex-1 rounded-none border-0 shadow-none"
          :tree-mode="treeMode"
          :selected-subject="selectedSubject"
          :detail-loading="detailLoading"
          :detail-loading-label="detailLoadingLabel"
          :metric-info="metricInfo"
          :metric-dimensions="metricDimensions"
          :reference-sql="referenceSql"
          :table-detail-title="tableDetailTitle"
          :table-detail-description="tableDetailDescription"
          :semantic="semantic"
          :show-header="false"
        />
      </SheetContent>
    </Sheet>

    <Dialog v-model:open="buildDialogOpen">
      <DialogScrollContent class="max-w-6xl">
        <DialogHeader>
          <DialogTitle>知识构建</DialogTitle>
          <DialogDescription>
            运行业务知识库和平台文档构建任务。
          </DialogDescription>
        </DialogHeader>
        <KnowledgeBootstrapPanel :datasource="workspace.currentDatasource.value" />
      </DialogScrollContent>
    </Dialog>
  </section>
</template>
