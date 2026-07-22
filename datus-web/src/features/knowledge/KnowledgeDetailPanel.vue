<script setup lang="ts">
import { CheckCircle2Icon, SaveIcon, XCircleIcon } from "@lucide/vue"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
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
import { Textarea } from "@/components/ui/textarea"
import { useSemanticWorkbench } from "@/composables/useSemanticWorkbench"
import DetailLoadingIndicator from "@/features/workspace/DetailLoadingIndicator.vue"
import type { SubjectTreeNode } from "@/lib/subject-tree"
import type { MetricDimensionsData, MetricInfo, ReferenceSQLInfo } from "@/types"

type KnowledgeTreeMode = "catalog" | "subject"
type SemanticWorkbench = ReturnType<typeof useSemanticWorkbench>

withDefaults(defineProps<{
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
  tableIndexCount: number
  semantic: SemanticWorkbench
  showHeader?: boolean
}>(), {
  showHeader: true,
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
        class="flex shrink-0 flex-row items-center justify-between gap-3"
      >
        <div class="min-w-0">
          <CardTitle class="truncate text-lg">
            {{ tableDetailTitle }}
          </CardTitle>
          <CardDescription class="text-sm">
            {{ tableDetailDescription }}
          </CardDescription>
        </div>
        <Badge variant="outline">
          {{ semantic.loadingTable.value ? "加载中" : `索引 ${tableIndexCount}` }}
        </Badge>
      </CardHeader>
    </template>

    <CardContent class="min-h-0 flex-1 p-0">
      <ScrollArea class="h-full overflow-hidden px-4 pb-4 sm:px-6 sm:pb-6">
        <div class="flex min-w-0 flex-col gap-4">
          <DetailLoadingIndicator
            v-if="detailLoading"
            :label="detailLoadingLabel"
          />

          <template v-else-if="treeMode === 'subject'">
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
          </template>

          <template v-else>
            <div class="overflow-x-auto rounded-md border">
              <Table class="table-fixed [&_td]:break-all [&_td]:whitespace-normal [&_th]:whitespace-normal">
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
                        主键
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
                aria-label="语义 YAML"
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
</template>
