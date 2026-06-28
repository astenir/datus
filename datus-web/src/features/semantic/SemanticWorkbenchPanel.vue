<script setup lang="ts">
import { computed, watch } from "vue"
import {
  CheckCircle2Icon,
  DatabaseIcon,
  SaveIcon,
  Table2Icon,
  XCircleIcon,
} from "@lucide/vue"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
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
import type { CatalogRecord } from "@/types"

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
const catalogRows = computed(() => props.workspace.catalogEntries.value.slice(0, 8).map((entry) => ({
  key: catalogKey(entry),
  database: stringField(entry.database_name ?? entry.name ?? entry.catalog_name),
  schema: stringField(entry.schema_name ?? entry.schema),
  tables: catalogTableNames(entry),
  raw: entry,
})))

function stringField(value: unknown) {
  return typeof value === "string" ? value : ""
}

function catalogKey(entry: CatalogRecord) {
  return [
    stringField(entry.database_name ?? entry.name ?? entry.catalog_name),
    stringField(entry.schema_name ?? entry.schema),
    catalogTableNames(entry).join(","),
  ].filter(Boolean).join(":") || JSON.stringify(entry)
}

function catalogTableNames(entry: CatalogRecord) {
  const tables = Array.isArray(entry.tables) ? entry.tables : []
  return tables.map((item) => {
    if (typeof item === "string") return item
    if (typeof item === "object" && item !== null && "name" in item) {
      return stringField((item as { name?: unknown }).name)
    }
    return ""
  }).filter(Boolean)
}

function formatRows(value: number | undefined) {
  if (typeof value !== "number") return "-"
  return value.toLocaleString("zh-CN")
}

function loadTable() {
  requestTableLoad(workbench.tableName.value)
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

function useCatalogTable(entry: CatalogRecord) {
  const tableName = workbench.useCatalogTable(entry)
  if (tableName) {
    emit("updateTable", tableName)
  }
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

      <div class="grid gap-4 xl:grid-cols-[26rem_minmax(0,1fr)]">
        <div class="flex flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle class="text-lg">加载表</CardTitle>
              <CardDescription class="text-sm">
                表结构与语义 YAML。
              </CardDescription>
            </CardHeader>
            <CardContent class="flex flex-col gap-4">
              <FieldGroup>
                <Field>
                  <FieldLabel for="semantic-table-name">表名</FieldLabel>
                  <Input
                    id="semantic-table-name"
                    v-model="workbench.tableName.value"
                    placeholder="database.schema.table"
                    @keydown.enter.prevent="loadTable"
                  />
                </Field>
              </FieldGroup>
              <Button
                :disabled="!workbench.canLoadTable.value || workbench.loadingTable.value"
                @click="loadTable"
              >
                <DatabaseIcon data-icon="inline-start" />
                加载表
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle class="text-lg">目录快捷入口</CardTitle>
              <CardDescription class="text-sm">
                最近加载的数据目录表。
              </CardDescription>
            </CardHeader>
            <CardContent class="flex flex-col gap-2">
              <div
                v-for="entry in catalogRows"
                :key="entry.key"
                class="flex items-center gap-3 rounded-md border p-2"
              >
                <div class="min-w-0 flex-1">
                  <div class="truncate text-sm font-medium">{{ entry.database || "-" }}</div>
                  <div class="truncate text-xs text-muted-foreground">
                    {{ entry.schema || "默认 schema" }} · 表 {{ entry.tables.length }}
                  </div>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  :disabled="entry.tables.length === 0"
                  @click="useCatalogTable(entry.raw)"
                >
                  <Table2Icon data-icon="inline-start" />
                  使用
                </Button>
              </div>
              <div
                v-if="catalogRows.length === 0"
                class="rounded-md border p-4 text-sm text-muted-foreground"
              >
                当前目录没有可用表，先在数据目录中刷新。
              </div>
            </CardContent>
          </Card>
        </div>

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
