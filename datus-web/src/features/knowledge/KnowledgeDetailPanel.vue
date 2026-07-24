<script setup lang="ts">
import { computed } from "vue"
import { BracesIcon, Columns3Icon, KeyRoundIcon } from "@lucide/vue"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
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
import { useSemanticWorkbench } from "@/composables/useSemanticWorkbench"
import KnowledgeSchemaPanel from "@/features/knowledge/KnowledgeSchemaPanel.vue"
import KnowledgeTableOverview from "@/features/knowledge/KnowledgeTableOverview.vue"
import SemanticModelEditor from "@/features/knowledge/SemanticModelEditor.vue"
import DetailLoadingIndicator from "@/features/workspace/DetailLoadingIndicator.vue"
import type { SubjectTreeNode } from "@/lib/subject-tree"
import type { MetricDimensionsData, MetricInfo, ReferenceSQLInfo } from "@/types"

type KnowledgeTreeMode = "catalog" | "subject"
type SemanticWorkbench = ReturnType<typeof useSemanticWorkbench>

const props = withDefaults(defineProps<{
  treeMode: KnowledgeTreeMode
  selectedSubject: SubjectTreeNode | null
  loadingSubjectDetail: boolean
  subjectTypeLabel: string
  detailLoading: boolean
  detailLoadingLabel: string
  metricInfo: MetricInfo | null
  metricDimensions: MetricDimensionsData | null
  referenceSql: ReferenceSQLInfo | null
  tableDetailTitle: string
  tableDetailDescription: string
  semantic: SemanticWorkbench
  showHeader?: boolean
}>(), {
  showHeader: true,
})

const semanticTabStatus = computed(() => {
  if (props.semantic.validating.value) return "校验中"
  if (props.semantic.isValidationCurrent.value && props.semantic.validation.value?.valid) {
    return props.semantic.isSemanticDirty.value ? "待保存" : "已通过"
  }
  if (props.semantic.isValidationCurrent.value && props.semantic.validation.value) return "失败"
  return props.semantic.isSemanticDirty.value ? "已修改" : "未校验"
})

const semanticTabVariant = computed<"secondary" | "destructive" | "outline">(() => {
  if (props.semantic.isValidationCurrent.value && props.semantic.validation.value && !props.semantic.validation.value.valid) {
    return "destructive"
  }
  if (props.semantic.isValidationCurrent.value && props.semantic.validation.value?.valid) return "secondary"
  return "outline"
})
</script>

<template>
  <Card
    class="flex min-h-0 min-w-0 flex-col"
    :aria-busy="detailLoading"
  >
    <template v-if="showHeader">
      <CardHeader
        v-if="treeMode === 'subject'"
        class="flex shrink-0 flex-row items-start justify-between gap-3"
      >
        <div class="min-w-0">
          <CardTitle class="truncate text-lg">
            {{ selectedSubject?.name || "未选择主题" }}
          </CardTitle>
          <CardDescription class="text-sm">
            {{ selectedSubject ? selectedSubject.subjectPath.join(" / ") : "从主题树选择节点后浏览详情" }}
          </CardDescription>
        </div>
        <Badge variant="outline">{{ loadingSubjectDetail ? "加载中" : subjectTypeLabel }}</Badge>
      </CardHeader>
      <CardHeader
        v-else
        class="shrink-0"
      >
        <KnowledgeTableOverview
          :title="tableDetailTitle"
          :path="tableDetailDescription"
          :detail="semantic.tableDetail.value"
          :loading="semantic.loadingTable.value"
        />
      </CardHeader>
    </template>

    <CardContent class="flex min-h-0 flex-1 flex-col p-0">
      <div
        v-if="detailLoading"
        class="px-4 pb-4 sm:px-6 sm:pb-6"
      >
        <DetailLoadingIndicator :label="detailLoadingLabel" />
      </div>

      <ScrollArea
        v-else-if="treeMode === 'subject'"
        class="h-full overflow-hidden px-4 pb-4 sm:px-6 sm:pb-6"
      >
        <div class="flex min-w-0 flex-col gap-4">
          <div
            v-if="!selectedSubject"
            class="rounded-md border p-4 text-sm text-muted-foreground"
          >
            选择左侧主题节点后查看指标、维度或参考 SQL。
          </div>

          <template v-else-if="selectedSubject.type === 'metric'">
            <div class="overflow-x-auto rounded-md border">
              <Table class="table-fixed [&_td]:break-all [&_td]:whitespace-normal [&_th]:whitespace-normal">
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
              aria-label="指标 YAML"
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
              aria-label="参考 SQL"
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
        </div>
      </ScrollArea>

      <Tabs
        v-else
        default-value="structure"
        class="min-h-0 min-w-0 flex-1 px-4 pb-4 sm:px-6 sm:pb-6"
      >
        <TabsList
          class="flex h-auto w-full shrink-0 !flex-row justify-start overflow-x-auto"
        >
          <TabsTrigger value="structure">
            <Columns3Icon aria-hidden="true" />
            表结构
            <Badge variant="outline">{{ semantic.tableDetail.value?.columns.length ?? 0 }}</Badge>
          </TabsTrigger>
          <TabsTrigger value="indexes">
            <KeyRoundIcon aria-hidden="true" />
            索引
            <Badge variant="outline">{{ semantic.tableDetail.value?.indexes.length ?? 0 }}</Badge>
          </TabsTrigger>
          <TabsTrigger value="semantic">
            <BracesIcon aria-hidden="true" />
            语义模型
            <Badge :variant="semanticTabVariant">{{ semanticTabStatus }}</Badge>
          </TabsTrigger>
        </TabsList>

        <ScrollArea class="min-h-0 flex-1 overflow-hidden">
          <TabsContent value="structure" class="m-0 pt-3">
            <KnowledgeSchemaPanel
              :detail="semantic.tableDetail.value"
              mode="columns"
            />
          </TabsContent>
          <TabsContent value="indexes" class="m-0 pt-3">
            <KnowledgeSchemaPanel
              :detail="semantic.tableDetail.value"
              mode="indexes"
            />
          </TabsContent>
          <TabsContent value="semantic" class="m-0 pt-3">
            <SemanticModelEditor
              :model-value="semantic.semanticYaml.value"
              :validation="semantic.validation.value"
              :validation-current="semantic.isValidationCurrent.value"
              :dirty="semantic.isSemanticDirty.value"
              :validating="semantic.validating.value"
              :saving="semantic.savingSemantic.value"
              @update:model-value="semantic.semanticYaml.value = $event"
              @validate="semantic.validateSemanticModel"
              @save="semantic.saveSemanticModel"
            />
          </TabsContent>
        </ScrollArea>
      </Tabs>
    </CardContent>
  </Card>
</template>
