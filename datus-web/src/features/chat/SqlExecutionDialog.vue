<script setup lang="ts">
import { computed, onBeforeUnmount, shallowRef, watch } from "vue"
import { DatabaseIcon, Loader2Icon, PlayIcon, SquareIcon } from "@lucide/vue"
import {
  Dialog,
  DialogClose,
  DialogFooter,
  DialogHeader,
  DialogScrollContent,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Field, FieldContent, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field"
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
import SqlExecutionResult from "@/features/chat/SqlExecutionResult.vue"
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
const showExecutionResult = computed(() =>
  execution.running.value || Boolean(execution.error.value) || Boolean(execution.result.value),
)

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

      <div class="flex min-h-0 min-w-0 flex-col gap-5 overflow-y-auto px-2 pb-2">
        <FieldGroup class="gap-4">
          <Field>
            <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <FieldLabel for="read-query-sql" class="pt-2">SQL</FieldLabel>
              <Field
                orientation="horizontal"
                class="flex-col items-stretch gap-2 sm:w-auto sm:flex-row sm:items-start"
              >
                <FieldLabel
                  for="read-query-datasource"
                  class="shrink-0 text-xs text-muted-foreground sm:pt-2"
                >
                  执行数据源
                </FieldLabel>
                <FieldContent class="min-w-0 w-full sm:w-72 sm:flex-none">
                  <Select
                    v-if="hasDatasourceOptions"
                    v-model="selectedDatasource"
                    :disabled="execution.running.value"
                  >
                    <SelectTrigger
                      id="read-query-datasource"
                      class="w-full"
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
                  <Badge
                    v-else
                    id="read-query-datasource"
                    variant="secondary"
                    class="max-w-full justify-start"
                    :title="executionDatasourceLabel"
                  >
                    <DatabaseIcon data-icon="inline-start" />
                    <span class="truncate">{{ executionDatasourceLabel }}</span>
                  </Badge>
                  <FieldDescription v-if="executionDatabaseName" class="text-xs">
                    数据库：{{ executionDatabaseName }}
                  </FieldDescription>
                </FieldContent>
              </Field>
            </div>
            <Textarea
              id="read-query-sql"
              v-model="sqlDraft"
              class="min-h-52 max-h-[40vh] overflow-auto px-4 font-mono text-xs leading-6"
              spellcheck="false"
            />
          </Field>
        </FieldGroup>

        <SqlExecutionResult
          v-if="showExecutionResult"
          :running="execution.running.value"
          :error="execution.error.value"
          :context-label="executionContextLabel"
          :columns="execution.columns.value"
          :rows="execution.displayRows.value"
          :raw-result="execution.rawResult.value"
          :has-result="Boolean(execution.result.value)"
          :row-count-label="rowCountLabel"
          :execution-time-label="executionTimeLabel"
        />
      </div>

      <DialogFooter class="w-full min-w-0 gap-2">
        <DialogClose as-child>
          <Button
            type="button"
            variant="outline"
            class="w-full sm:w-auto"
          >
            取消
          </Button>
        </DialogClose>
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
          <template v-if="execution.running.value">
            <Loader2Icon data-icon="inline-start" class="animate-spin" />
            执行中
          </template>
          <template v-else>
            <PlayIcon data-icon="inline-start" />
            执行
          </template>
        </Button>
      </DialogFooter>
    </DialogScrollContent>
  </Dialog>
</template>
