<script setup lang="ts">
import { computed, watch } from "vue"
import {
  CheckCircle2Icon,
  SaveIcon,
  Table2Icon,
  XCircleIcon,
} from "@lucide/vue"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
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
import type { ChatWorkspace } from "@/composables/useChatWorkspace"
import CatalogTree from "@/features/workspace/CatalogTree.vue"

const props = defineProps<{
  workspace: ChatWorkspace
  selectedTable?: string | null
}>()

const emit = defineEmits<{
  updateTable: [table: string]
}>()

const workbench = useSemanticWorkbench()

const tableColumnCount = computed(() => workbench.tableDetail.value?.columns.length ?? 0)
const tableIndexCount = computed(() => workbench.tableDetail.value?.indexes.length ?? 0)
const tableRowCount = computed(() => formatRows(workbench.tableDetail.value?.rows))
function formatRows(value: number | undefined) {
  if (typeof value !== "number") return "-"
  return value.toLocaleString("zh-CN")
}

function requestTableLoad(value: string) {
  const target = value.trim()
  if (!target) {
    void workbench.loadTableDetails()
    return
  }

  if (target === selectedTable.value) {
    void workbench.loadTableDetails(target)
    return
  }

  emit("updateTable", target)
}

const selectedTable = computed(() => props.selectedTable?.trim() ?? "")

watch(
  selectedTable,
  (table) => {
    if (!table || table === workbench.tableName.value.trim()) return
    void workbench.loadTableDetails(table)
  },
  { immediate: true },
)
</script>

<template>
  <section class="min-h-0 flex-1 overflow-y-auto p-4">
    <div class="flex flex-col gap-4">
      <div class="flex flex-wrap items-center gap-3">
        <div class="min-w-0 flex-1">
          <h1 class="text-lg font-semibold">语义模型工作台</h1>
          <p class="text-sm text-muted-foreground">
            维护表级语义 YAML 与字段说明。
          </p>
        </div>
      </div>

      <div class="grid gap-3 md:grid-cols-4">
        <Card>
          <CardHeader class="pb-2">
            <CardTitle class="text-sm">当前表</CardTitle>
          </CardHeader>
          <CardContent class="flex items-end justify-between gap-3">
            <span class="min-w-0 truncate text-lg font-semibold">{{ workbench.tableDetail.value?.name || "-" }}</span>
            <Table2Icon class="text-muted-foreground" />
          </CardContent>
        </Card>
        <Card>
          <CardHeader class="pb-2">
            <CardTitle class="text-sm">列数</CardTitle>
          </CardHeader>
          <CardContent class="flex items-end justify-between gap-3">
            <span class="text-lg font-semibold">{{ tableColumnCount }}</span>
            <span class="text-xs text-muted-foreground">Columns</span>
          </CardContent>
        </Card>
        <Card>
          <CardHeader class="pb-2">
            <CardTitle class="text-sm">索引</CardTitle>
          </CardHeader>
          <CardContent class="flex items-end justify-between gap-3">
            <span class="text-lg font-semibold">{{ tableIndexCount }}</span>
            <span class="text-xs text-muted-foreground">Indexes</span>
          </CardContent>
        </Card>
        <Card>
          <CardHeader class="pb-2">
            <CardTitle class="text-sm">行数</CardTitle>
          </CardHeader>
          <CardContent class="flex items-end justify-between gap-3">
            <span class="text-lg font-semibold">{{ tableRowCount }}</span>
            <span class="text-xs text-muted-foreground">Rows</span>
          </CardContent>
        </Card>
      </div>

      <div class="grid gap-4 xl:grid-cols-[24rem_minmax(0,1fr)]">
        <CatalogTree
          :entries="workspace.catalogEntries.value"
          :selected-table="selectedTable"
          :loading="workspace.isLoadingCatalog.value"
          title="语义模型目录"
          description="点击表节点加载结构和语义 YAML。"
          @refresh="workspace.loadCatalog()"
          @select-table="requestTableLoad"
        />

        <div class="flex flex-col gap-4">
          <Card>
            <CardHeader class="flex flex-row items-center justify-between gap-3">
              <div>
                <CardTitle class="text-lg">表结构</CardTitle>
                <CardDescription class="text-sm">
                  {{ workbench.tableDetail.value?.name || "未加载表" }}
                </CardDescription>
              </div>
              <Badge variant="outline">索引 {{ tableIndexCount }}</Badge>
            </CardHeader>
            <CardContent>
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
                      v-for="column in workbench.tableDetail.value?.columns ?? []"
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
                    <TableRow v-if="(workbench.tableDetail.value?.columns ?? []).length === 0">
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
              <div class="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
                <span>行数 {{ tableRowCount }}</span>
                <span>列数 {{ tableColumnCount }}</span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle class="text-lg">语义 YAML</CardTitle>
              <CardDescription class="text-sm">
                表级语义定义。
              </CardDescription>
            </CardHeader>
            <CardContent class="flex flex-col gap-4">
              <Textarea
                v-model="workbench.semanticYaml.value"
                class="min-h-96 font-mono text-xs leading-6"
                spellcheck="false"
                placeholder="加载表后显示语义模型 YAML"
              />
              <div class="flex flex-wrap items-center justify-between gap-3">
                <Badge :variant="workbench.validation.value?.valid ? 'secondary' : workbench.validation.value ? 'destructive' : 'outline'">
                  <CheckCircle2Icon
                    v-if="workbench.validation.value?.valid"
                    data-icon="inline-start"
                  />
                  <XCircleIcon
                    v-else-if="workbench.validation.value"
                    data-icon="inline-start"
                  />
                  {{ workbench.validation.value?.valid ? "校验通过" : workbench.validation.value ? "校验失败" : "未校验" }}
                </Badge>
                <div class="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    :disabled="workbench.validating.value"
                    @click="workbench.validateSemanticModel"
                  >
                    <CheckCircle2Icon data-icon="inline-start" />
                    校验
                  </Button>
                  <Button
                    size="sm"
                    :disabled="workbench.savingSemantic.value"
                    @click="workbench.saveSemanticModel"
                  >
                    <SaveIcon data-icon="inline-start" />
                    保存
                  </Button>
                </div>
              </div>
              <div
                v-if="workbench.semanticInvalidMessages.value.length > 0"
                class="rounded-md border p-3 text-sm text-destructive"
              >
                <div
                  v-for="message in workbench.semanticInvalidMessages.value"
                  :key="message"
                >
                  {{ message }}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  </section>
</template>
