<script setup lang="ts">
import { computed } from "vue"
import { BracesIcon, Columns3Icon, KeyRoundIcon } from "@lucide/vue"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useSemanticWorkbench } from "@/composables/useSemanticWorkbench"
import KnowledgeSchemaPanel from "@/features/knowledge/KnowledgeSchemaPanel.vue"
import KnowledgeSubjectOverview from "@/features/knowledge/KnowledgeSubjectOverview.vue"
import KnowledgeTableOverview from "@/features/knowledge/KnowledgeTableOverview.vue"
import MetricDetailWorkbench from "@/features/knowledge/MetricDetailWorkbench.vue"
import ReferenceSqlDetailWorkbench from "@/features/knowledge/ReferenceSqlDetailWorkbench.vue"
import SemanticModelEditor from "@/features/knowledge/SemanticModelEditor.vue"
import DetailLoadingIndicator from "@/features/workspace/DetailLoadingIndicator.vue"
import type { SubjectTreeNode } from "@/lib/subject-tree"
import type { MetricDimensionsData, MetricInfo, ReferenceSQLInfo } from "@/types"

type KnowledgeTreeMode = "catalog" | "subject"
type SemanticWorkbench = ReturnType<typeof useSemanticWorkbench>

const props = withDefaults(defineProps<{
  treeMode: KnowledgeTreeMode
  selectedSubject: SubjectTreeNode | null
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
        class="shrink-0"
      >
        <KnowledgeSubjectOverview
          :subject="selectedSubject"
          :loading="detailLoading"
        />
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
        v-else-if="treeMode === 'subject' && (!selectedSubject || selectedSubject.type === 'directory')"
        class="h-full overflow-hidden px-4 pb-4 sm:px-6 sm:pb-6"
      >
        <div class="rounded-md border p-4 text-sm text-muted-foreground">
          {{ selectedSubject ? "当前节点是主题目录，继续展开或选择子节点。" : "选择左侧主题节点后查看指标、维度或参考 SQL。" }}
        </div>
      </ScrollArea>

      <MetricDetailWorkbench
        v-else-if="treeMode === 'subject' && selectedSubject?.type === 'metric'"
        :metric="metricInfo"
        :dimensions="metricDimensions"
      />

      <ReferenceSqlDetailWorkbench
        v-else-if="treeMode === 'subject' && selectedSubject?.type === 'reference_sql'"
        :reference-sql="referenceSql"
      />

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
