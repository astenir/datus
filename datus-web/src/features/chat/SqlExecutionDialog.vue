<script setup lang="ts">
import { computed, onBeforeUnmount, shallowRef, watch } from "vue"
import { AlertCircleIcon, DatabaseIcon, Loader2Icon, PlayIcon, SquareIcon } from "@lucide/vue"
import {
  Dialog,
  DialogFooter,
  DialogHeader,
  DialogScrollContent,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { useSqlExecution } from "@/composables/useSqlExecution"
import type { SelectOption } from "@/types"

const props = defineProps<{
  initialSql: string
  datasourceName?: string
  datasourceOptions?: readonly SelectOption[]
  databaseName?: string
}>()

const open = defineModel<boolean>("open", { default: false })
const execution = useSqlExecution()
const sqlDraft = shallowRef(props.initialSql)
const selectedDatasource = shallowRef("")

const canExecute = computed(() => Boolean(sqlDraft.value.trim()) && !execution.running.value)
const showResultTable = computed(() => execution.columns.value.length > 0)
const showRawResult = computed(() => Boolean(execution.rawResult.value) && !showResultTable.value)
const datasourceOptions = computed(() => props.datasourceOptions ?? [])
const normalizedDatasourceName = computed(() => props.datasourceName?.trim() ?? "")
const hasDatasourceOptions = computed(() => datasourceOptions.value.length > 0)
const executionDatasourceName = computed(() => selectedDatasource.value.trim() || normalizedDatasourceName.value)
const executionDatabaseName = computed(() => {
  const selected = executionDatasourceName.value
  if (selected && selected !== normalizedDatasourceName.value) return ""
  return props.databaseName?.trim() ?? ""
})
const executionDatasourceLabel = computed(() =>
  optionLabel(executionDatasourceName.value, datasourceOptions.value) || executionDatasourceName.value || "后端默认数据源",
)
const executionContextLabel = computed(() => {
  const parts = [`数据源 ${executionDatasourceLabel.value}`]
  if (executionDatabaseName.value) {
    parts.push(`数据库 ${executionDatabaseName.value}`)
  }
  return parts.join(" / ")
})
const rowCountLabel = computed(() => {
  if (!execution.result.value) return "尚未执行"
  if (typeof execution.result.value.row_count === "number") return `${execution.result.value.row_count} 行`
  return `${execution.displayRows.value.length} 行`
})
const executionTimeLabel = computed(() => {
  const seconds = execution.result.value?.execution_time
  return typeof seconds === "number" ? `${seconds.toFixed(2)}s` : ""
})

watch(
  () => props.initialSql,
  (sql) => {
    if (!open.value) {
      sqlDraft.value = sql
    }
  },
)

watch(open, (isOpen) => {
  if (isOpen) {
    sqlDraft.value = props.initialSql
    selectedDatasource.value = normalizedDatasourceName.value
    return
  }

  execution.reset()
})

watch(
  () => props.datasourceName,
  () => {
    if (!open.value) {
      selectedDatasource.value = normalizedDatasourceName.value
    }
  },
)

onBeforeUnmount(() => {
  execution.reset()
})

async function execute() {
  await execution.executeSql(sqlDraft.value, {
    datasourceName: executionDatasourceName.value,
    databaseName: executionDatabaseName.value,
  })
}

function handleOpenUpdate(value: boolean) {
  open.value = value
}

function optionLabel(value: string, options: readonly SelectOption[]) {
  if (!value) return ""
  return options.find((option) => option.value === value)?.label ?? value
}
</script>

<template>
  <Dialog
    :open="open"
    @update:open="handleOpenUpdate"
  >
    <DialogScrollContent class="max-h-[88vh] w-[calc(100vw-2rem)] min-w-0 grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden sm:max-w-5xl">
      <DialogHeader>
        <DialogTitle>执行 SQL</DialogTitle>
        <DialogDescription>
          在选定数据源上下文中执行 SQL 并查看返回结果。
        </DialogDescription>
      </DialogHeader>

      <div class="flex min-h-0 min-w-0 flex-col gap-4 overflow-y-auto px-2 pb-2">
        <FieldGroup>
          <Field>
            <FieldLabel for="read-query-datasource">执行数据源</FieldLabel>
            <Select
              v-if="hasDatasourceOptions"
              v-model="selectedDatasource"
              :disabled="execution.running.value"
            >
              <SelectTrigger
                id="read-query-datasource"
                class="h-11 w-full border-primary/40 bg-primary/5"
              >
                <SelectValue placeholder="选择数据源" />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  <SelectItem
                    v-for="option in datasourceOptions"
                    :key="option.value"
                    :value="option.value"
                  >
                    {{ option.label }}
                  </SelectItem>
                </SelectGroup>
              </SelectContent>
            </Select>
            <div
              v-else
              id="read-query-datasource"
              class="flex h-11 min-w-0 items-center gap-2 rounded-md border border-primary/40 bg-primary/5 px-3 text-sm font-medium text-foreground"
            >
              <DatabaseIcon data-icon="inline-start" />
              <span class="truncate">{{ executionDatasourceLabel }}</span>
            </div>
          </Field>

          <Field>
            <FieldLabel for="read-query-sql">SQL</FieldLabel>
            <div class="px-1 pb-1">
              <Textarea
                id="read-query-sql"
                v-model="sqlDraft"
                class="min-h-44 overflow-auto px-4 font-mono text-xs leading-6"
                spellcheck="false"
              />
            </div>
            <FieldDescription v-if="executionDatabaseName">
              Database: {{ executionDatabaseName }}
            </FieldDescription>
          </Field>
        </FieldGroup>

        <div class="flex flex-wrap items-center gap-2">
          <Badge
            v-if="execution.result.value || execution.running.value || execution.error.value"
            variant="default"
          >
            <DatabaseIcon data-icon="inline-start" />
            {{ executionDatasourceLabel }}
          </Badge>
          <Badge
            v-if="executionDatabaseName"
            variant="outline"
          >
            <DatabaseIcon data-icon="inline-start" />
            {{ executionDatabaseName }}
          </Badge>
          <Badge
            v-if="execution.running.value"
            variant="secondary"
          >
            执行中
          </Badge>
          <Badge
            v-if="execution.result.value"
            variant="secondary"
          >
            {{ rowCountLabel }}
          </Badge>
          <Badge
            v-if="executionTimeLabel"
            variant="outline"
          >
            {{ executionTimeLabel }}
          </Badge>
        </div>

        <Alert
          v-if="execution.error.value"
          variant="destructive"
        >
          <AlertCircleIcon />
          <AlertTitle>执行失败</AlertTitle>
          <AlertDescription class="flex flex-col gap-1">
            <span>{{ execution.error.value }}</span>
            <span class="text-xs opacity-90">执行上下文：{{ executionContextLabel }}</span>
          </AlertDescription>
        </Alert>

        <div
          v-if="showResultTable"
          class="min-w-0 shrink-0 overflow-hidden rounded-md border bg-background"
        >
          <Table class="min-w-max">
            <TableHeader>
              <TableRow>
                <TableHead
                  v-for="column in execution.columns.value"
                  :key="column"
                  class="h-9 text-xs"
                >
                  {{ column }}
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow
                v-for="(row, rowIndex) in execution.displayRows.value"
                :key="`${rowIndex}-${row.join('|')}`"
              >
                <TableCell
                  v-for="(cell, cellIndex) in row"
                  :key="`${rowIndex}-${execution.columns.value[cellIndex] ?? cellIndex}`"
                  class="max-w-sm whitespace-normal break-words py-2 align-top text-xs leading-6"
                >
                  {{ cell }}
                </TableCell>
              </TableRow>
              <TableRow v-if="execution.displayRows.value.length === 0">
                <TableCell
                  :colspan="Math.max(execution.columns.value.length, 1)"
                  class="h-20 text-center text-xs text-muted-foreground"
                >
                  执行完成，无数据
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </div>

        <pre
          v-else-if="showRawResult"
          class="max-h-96 max-w-full overflow-auto rounded-md bg-muted p-3 font-mono text-xs leading-6 text-muted-foreground"
        >{{ execution.rawResult.value }}</pre>

        <p
          v-else-if="execution.result.value"
          class="rounded-md border bg-background p-3 text-sm text-muted-foreground"
        >
          执行完成，后端没有返回可展示的结果。
        </p>
      </div>

      <DialogFooter class="w-full min-w-0 gap-2">
        <Button
          v-if="execution.running.value"
          type="button"
          variant="outline"
          class="w-full sm:w-auto"
          @click="execution.stopRunning"
        >
          <SquareIcon data-icon="inline-start" />
          停止
        </Button>
        <Button
          type="button"
          class="w-full sm:w-auto"
          :disabled="!canExecute"
          @click="execute"
        >
          <Loader2Icon
            v-if="execution.running.value"
            data-icon="inline-start"
            class="animate-spin"
          />
          <PlayIcon
            v-else
            data-icon="inline-start"
          />
          执行
        </Button>
      </DialogFooter>
    </DialogScrollContent>
  </Dialog>
</template>
