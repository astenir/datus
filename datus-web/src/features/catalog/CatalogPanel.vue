<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { toast } from "vue-sonner"
import {
  CheckCircle2Icon,
  DatabaseIcon,
  RefreshCwIcon,
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
import type { ChatWorkspace } from "@/composables/useChatWorkspace"
import { useConnection } from "@/composables/useConnection"
import CatalogTree from "@/features/workspace/CatalogTree.vue"
import { tableApi } from "@/lib/api"
import { catalogSchemaRows, catalogTableRows } from "@/lib/catalog-tree"
import type { TableDetail } from "@/types"

const props = defineProps<{
  workspace: ChatWorkspace
  selectedTable?: string | null
}>()

const emit = defineEmits<{
  updateTable: [table: string]
}>()

const connection = useConnection()
const loadingDetail = ref(false)
const tableDetail = ref<TableDetail | null>(null)

const selectedTableName = computed(() => props.selectedTable?.trim() ?? "")
const schemaRows = computed(() => catalogSchemaRows(props.workspace.catalogEntries.value))
const tableRows = computed(() => catalogTableRows(props.workspace.catalogEntries.value))
const selectedTableRow = computed(() =>
  tableRows.value.find((row) => row.fullName === selectedTableName.value) ?? null,
)
const detailRowCount = computed(() => formatCount(tableDetail.value?.rows))
const detailColumnCount = computed(() => tableDetail.value?.columns.length ?? 0)
const detailIndexCount = computed(() => tableDetail.value?.indexes.length ?? 0)
const displayedDetailName = computed(() => tableDetail.value?.name || selectedTableName.value || "未选择表")

function formatCount(value: number | undefined) {
  return typeof value === "number" ? value.toLocaleString("zh-CN") : "-"
}

async function loadTableDetail(table: string) {
  const target = table.trim()
  if (!target) {
    tableDetail.value = null
    return
  }

  loadingDetail.value = true
  try {
    const detail = await tableApi.detail(connection.effectiveBase(), target)
    tableDetail.value = detail?.table ?? null
    if (!tableDetail.value) {
      toast.error("未获取到表结构详情")
    }
  } catch (error) {
    console.error("加载表详情失败:", error)
    toast.error("加载表详情失败")
    tableDetail.value = null
  } finally {
    loadingDetail.value = false
  }
}

function selectTable(table: string) {
  if (selectedTableName.value === table) {
    void loadTableDetail(table)
    return
  }

  emit("updateTable", table)
}

watch(
  selectedTableName,
  (table) => {
    void loadTableDetail(table)
  },
  { immediate: true },
)
</script>

<template>
  <section class="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4">
    <div class="flex flex-wrap items-center gap-3">
      <div class="min-w-0 flex-1">
        <h1 class="text-lg font-semibold">数据目录</h1>
        <p class="text-sm text-muted-foreground">
          浏览当前数据源中的数据库、Schema 和表结构。
        </p>
      </div>
      <Button
        variant="outline"
        size="sm"
        :disabled="workspace.isLoadingCatalog.value"
        @click="workspace.loadCatalog()"
      >
        <RefreshCwIcon data-icon="inline-start" />
        刷新目录
      </Button>
    </div>

    <div class="grid gap-3 md:grid-cols-3">
      <Card>
        <CardHeader class="pb-2">
          <CardTitle class="text-sm">目录范围</CardTitle>
        </CardHeader>
        <CardContent class="flex items-end justify-between gap-3">
          <span class="min-w-0 truncate text-lg font-semibold">
            {{ workspace.currentDatasource.value || "未选择" }}
          </span>
          <DatabaseIcon class="text-muted-foreground" />
        </CardContent>
      </Card>
      <Card>
        <CardHeader class="pb-2">
          <CardTitle class="text-sm">Schema</CardTitle>
        </CardHeader>
        <CardContent class="flex items-end justify-between gap-3">
          <span class="text-lg font-semibold">{{ schemaRows.length }}</span>
          <span class="text-xs text-muted-foreground">可见范围</span>
        </CardContent>
      </Card>
      <Card>
        <CardHeader class="pb-2">
          <CardTitle class="text-sm">Tables</CardTitle>
        </CardHeader>
        <CardContent class="flex items-end justify-between gap-3">
          <span class="text-lg font-semibold">{{ tableRows.length }}</span>
          <span class="text-xs text-muted-foreground">可浏览表</span>
        </CardContent>
      </Card>
    </div>

    <div class="grid min-h-0 gap-4 xl:grid-cols-[24rem_minmax(0,1fr)]">
      <CatalogTree
        :entries="workspace.catalogEntries.value"
        :selected-table="selectedTableName"
        :loading="workspace.isLoadingCatalog.value"
        title="数据目录树"
        description="点击表节点查看字段、索引和行数。"
        @refresh="workspace.loadCatalog()"
        @select-table="selectTable"
      />

      <Card class="min-w-0">
        <CardHeader class="flex flex-row items-start justify-between gap-3">
          <div class="min-w-0">
            <CardTitle class="truncate text-lg">{{ displayedDetailName }}</CardTitle>
            <CardDescription class="text-sm">
              {{ selectedTableRow ? `${selectedTableRow.database || "-"} / ${selectedTableRow.schema || "-"}` : "选择左侧表后加载详情" }}
            </CardDescription>
          </div>
          <Badge :variant="tableDetail ? 'secondary' : 'outline'">
            <CheckCircle2Icon
              v-if="tableDetail"
              data-icon="inline-start"
            />
            {{ tableDetail ? "已加载" : loadingDetail ? "加载中" : "未加载" }}
          </Badge>
        </CardHeader>
        <CardContent class="flex flex-col gap-4">
          <div class="grid gap-2 sm:grid-cols-3">
            <div class="rounded-md border p-3">
              <div class="text-xs text-muted-foreground">Rows</div>
              <div class="mt-1 text-lg font-semibold">{{ detailRowCount }}</div>
            </div>
            <div class="rounded-md border p-3">
              <div class="text-xs text-muted-foreground">Columns</div>
              <div class="mt-1 text-lg font-semibold">{{ detailColumnCount }}</div>
            </div>
            <div class="rounded-md border p-3">
              <div class="text-xs text-muted-foreground">Indexes</div>
              <div class="mt-1 text-lg font-semibold">{{ detailIndexCount }}</div>
            </div>
          </div>

          <div
            v-if="loadingDetail"
            class="rounded-md border p-4 text-sm text-muted-foreground"
          >
            正在加载表结构...
          </div>

          <div
            v-else-if="!selectedTableName"
            class="rounded-md border p-4 text-sm text-muted-foreground"
          >
            从目录列表选择一个表，或访问带有 <span class="font-mono text-xs">table</span> 查询参数的目录链接。
          </div>

          <template v-else>
            <div class="overflow-x-auto rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Column</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Nullable</TableHead>
                    <TableHead>Default</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow
                    v-for="column in tableDetail?.columns ?? []"
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
                  <TableRow v-if="(tableDetail?.columns ?? []).length === 0">
                    <TableCell
                      class="h-20 text-center text-sm text-muted-foreground"
                      colspan="4"
                    >
                      暂无字段信息
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </div>

            <div class="rounded-md border p-3">
              <div class="mb-2 text-sm font-medium">索引</div>
              <div
                v-if="(tableDetail?.indexes ?? []).length === 0"
                class="text-sm text-muted-foreground"
              >
                暂无索引信息
              </div>
              <div
                v-for="index in tableDetail?.indexes ?? []"
                :key="index.name"
                class="flex items-center justify-between gap-3 border-t py-2 first:border-t-0 first:pt-0 last:pb-0"
              >
                <div class="min-w-0">
                  <div class="truncate text-sm font-medium">{{ index.name }}</div>
                  <div class="truncate text-xs text-muted-foreground">
                    {{ index.columns.join(", ") || "-" }}
                  </div>
                </div>
                <Badge variant="outline">{{ index.type || "index" }}</Badge>
              </div>
            </div>
          </template>
        </CardContent>
      </Card>
    </div>

    <Card>
      <CardHeader class="flex-row items-center justify-between">
        <div>
          <CardTitle class="text-lg">Schema 汇总</CardTitle>
          <CardDescription class="text-sm">
            当前目录响应中的数据库和 Schema 分布。
          </CardDescription>
        </div>
        <Button
          variant="outline"
          size="sm"
          :disabled="workspace.isLoadingCatalog.value"
          @click="workspace.loadCatalog()"
        >
          <RefreshCwIcon data-icon="inline-start" />
          刷新
        </Button>
      </CardHeader>
      <CardContent>
        <div class="overflow-x-auto rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Database</TableHead>
                <TableHead>Schema</TableHead>
                <TableHead>Type</TableHead>
                <TableHead class="text-right">Tables</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow
                v-for="row in schemaRows"
                :key="row.key"
              >
                <TableCell class="font-medium">{{ row.database }}</TableCell>
                <TableCell>{{ row.schema || "-" }}</TableCell>
                <TableCell>{{ row.type || "-" }}</TableCell>
                <TableCell class="text-right">{{ row.tableCount }}</TableCell>
              </TableRow>
              <TableRow v-if="schemaRows.length === 0">
                <TableCell
                  class="h-24 text-center text-muted-foreground"
                  colspan="4"
                >
                  暂无目录数据
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  </section>
</template>
