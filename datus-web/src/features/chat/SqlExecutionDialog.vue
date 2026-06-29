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
import { Textarea } from "@/components/ui/textarea"
import { useSqlExecution } from "@/composables/useSqlExecution"

const props = defineProps<{
  initialSql: string
  databaseName?: string
}>()

const open = defineModel<boolean>("open", { default: false })
const execution = useSqlExecution()
const sqlDraft = shallowRef(props.initialSql)

const canExecute = computed(() => Boolean(sqlDraft.value.trim()) && !execution.running.value)
const showResultTable = computed(() => execution.columns.value.length > 0)
const showRawResult = computed(() => Boolean(execution.rawResult.value) && !showResultTable.value)
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
    return
  }

  execution.reset()
})

onBeforeUnmount(() => {
  execution.reset()
})

async function execute() {
  await execution.executeSql(sqlDraft.value, {
    databaseName: props.databaseName,
  })
}

function handleOpenUpdate(value: boolean) {
  open.value = value
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
          在当前数据源上下文中执行这段 read_query SQL，并查看返回结果。
        </DialogDescription>
      </DialogHeader>

      <div class="flex min-h-0 min-w-0 flex-col gap-4 overflow-y-auto px-2 pb-2">
        <FieldGroup>
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
            <FieldDescription>
              {{ databaseName ? `Database: ${databaseName}` : "使用后端当前数据库上下文" }}
            </FieldDescription>
          </Field>
        </FieldGroup>

        <div class="flex flex-wrap items-center gap-2">
          <Badge variant="outline">
            <DatabaseIcon data-icon="inline-start" />
            {{ databaseName || "默认数据库" }}
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
          <AlertDescription>{{ execution.error.value }}</AlertDescription>
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
