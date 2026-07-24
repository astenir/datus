<script setup lang="ts">
import type { BundledLanguage } from "shiki"
import { computed, shallowRef } from "vue"
import { BookmarkPlusIcon, CheckIcon, Loader2Icon, PlayIcon } from "@lucide/vue"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import {
  CodeBlock,
  CodeBlockActions,
  CodeBlockHeader,
  CodeBlockTitle,
} from "@/components/ai-elements/code-block"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import ChatCodeBlockCopyButton from "@/features/chat/ChatCodeBlockCopyButton.vue"
import SqlExecutionDialog from "@/features/chat/SqlExecutionDialog.vue"
import {
  displayValueForTool,
  isSqlExecutionTool,
  sqlExecutionContextFromToolValue,
  sqlFromToolValue,
  sqlKeys,
  summarizeValue,
  tableFromToolValue,
} from "@/lib/tool-display"
import type { SelectOption, SuccessStorySource } from "@/types"

const MAX_VISIBLE_ROWS = 50

const props = defineProps<{
  mode: "input" | "output"
  toolName: string
  value?: unknown
  errorText?: string
  datasourceName?: string
  datasourceOptions?: readonly SelectOption[]
  databaseName?: string
  successStorySource?: SuccessStorySource
  successStorySaving?: boolean
  successStorySaved?: boolean
}>()

const emit = defineEmits<{
  saveSuccessStory: [source: SuccessStorySource]
}>()

const sqlDialogOpen = shallowRef(false)

const title = computed(() => {
  if (props.errorText) return "错误"
  return props.mode === "input" ? "参数" : "结果"
})

const displayValue = computed(() => (
  props.mode === "output"
    ? displayValueForTool("result", props.value)
    : props.value
))

const sql = computed(() => sqlFromToolValue(displayValue.value))

const sqlOmitKeys = computed(() => {
  const value = displayValue.value
  if (!sql.value || !isPlainRecord(value)) return []
  return sqlKeys.filter((key) => value[key] === sql.value)
})

const table = computed(() => tableFromToolValue(displayValue.value, {
  omitKeys: sqlOmitKeys.value,
}))

const visibleRows = computed(() => table.value?.rows.slice(0, MAX_VISIBLE_ROWS) ?? [])

const hiddenRowCount = computed(() => Math.max((table.value?.rows.length ?? 0) - MAX_VISIBLE_ROWS, 0))

const showTable = computed(() => Boolean(table.value && (table.value.rows.length > 0 || table.value.columns.length > 0)))

const showFallback = computed(() => {
  if (props.errorText) return false
  if (showTable.value) return false
  if (sql.value && sqlOmitKeys.value.length > 0) return false
  return displayValue.value !== undefined && displayValue.value !== null && displayValue.value !== ""
})

const fallbackCode = computed(() => formatCode(displayValue.value))
const fallbackLanguage = computed<BundledLanguage>(() => "json")
const valueSummary = computed(() => table.value?.sourceLabel ?? summarizeValue(displayValue.value))
const canExecuteSql = computed(() => (
  props.mode === "input"
    && isSqlExecutionTool(props.toolName)
    && Boolean(sql.value)
))
const sqlExecutionContext = computed(() => sqlExecutionContextFromToolValue(displayValue.value))
const sqlExecutionDatasourceName = computed(() => sqlExecutionContext.value.datasourceName ?? props.datasourceName)
const sqlExecutionDatabaseName = computed(() => {
  const toolDatabaseName = sqlExecutionContext.value.databaseName
  if (toolDatabaseName) return toolDatabaseName

  const toolDatasourceName = sqlExecutionContext.value.datasourceName
  if (toolDatasourceName && toolDatasourceName !== props.datasourceName?.trim()) return undefined

  return props.databaseName
})

function formatCode(value: unknown): string {
  if (typeof value === "string") return value
  return JSON.stringify(value, null, 2)
}

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value)
}

function saveSuccessStory() {
  if (!props.successStorySource || props.successStorySaving || props.successStorySaved) return
  emit("saveSuccessStory", props.successStorySource)
}

</script>

<template>
  <div class="flex flex-col gap-3 p-4">
    <div class="flex min-w-0 flex-wrap items-center gap-2">
      <h4 class="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {{ title }}
      </h4>
      <Badge
        v-if="!errorText"
        variant="outline"
      >
        {{ valueSummary }}
      </Badge>
    </div>

    <div
      v-if="errorText"
      class="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm leading-6 text-destructive"
    >
      {{ errorText }}
    </div>

    <CodeBlock
      v-if="sql"
      :code="sql"
      language="sql"
    >
      <CodeBlockHeader class="px-2 py-1">
        <CodeBlockTitle>SQL</CodeBlockTitle>
        <CodeBlockActions>
          <TooltipProvider v-if="successStorySource">
            <Tooltip>
              <TooltipTrigger as-child>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  :disabled="successStorySaving || successStorySaved"
                  :aria-label="successStorySaved ? '已保存为成功案例' : '保存为成功案例'"
                  @click="saveSuccessStory"
                >
                  <Loader2Icon
                    v-if="successStorySaving"
                    data-icon="inline-start"
                    class="animate-spin"
                  />
                  <CheckIcon
                    v-else-if="successStorySaved"
                    data-icon="inline-start"
                  />
                  <BookmarkPlusIcon
                    v-else
                    data-icon="inline-start"
                  />
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                <p>{{ successStorySaved ? "已保存为成功案例" : "保存为成功案例" }}</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
          <TooltipProvider v-if="canExecuteSql">
            <Tooltip>
              <TooltipTrigger as-child>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label="执行 SQL"
                  @click="sqlDialogOpen = true"
                >
                  <PlayIcon data-icon="inline-start" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                <p>执行 SQL</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
          <ChatCodeBlockCopyButton :code="sql" />
        </CodeBlockActions>
      </CodeBlockHeader>
    </CodeBlock>

    <SqlExecutionDialog
      v-if="sql && canExecuteSql"
      v-model:open="sqlDialogOpen"
      :initial-sql="sql"
      :datasource-name="sqlExecutionDatasourceName"
      :datasource-options="datasourceOptions"
      :database-name="sqlExecutionDatabaseName"
    />

    <div
      v-if="showTable && table"
      class="overflow-hidden rounded-md border bg-background"
    >
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead
              v-for="(column, columnIndex) in table.columns"
              :key="`${column}-${columnIndex}`"
              class="h-9 text-xs"
            >
              {{ column }}
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow
            v-for="(row, rowIndex) in visibleRows"
            :key="`${rowIndex}-${row.join('|')}`"
          >
            <TableCell
              v-for="(cell, cellIndex) in row"
              :key="`${rowIndex}-${table.columns[cellIndex] ?? cellIndex}`"
              class="max-w-sm whitespace-normal break-words py-2 align-top text-xs leading-6"
            >
              {{ cell }}
            </TableCell>
          </TableRow>
          <TableRow v-if="visibleRows.length === 0">
            <TableCell
              :colspan="Math.max(table.columns.length, 1)"
              class="py-4 text-center text-xs text-muted-foreground"
            >
              无数据
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
      <div
        v-if="hiddenRowCount > 0"
        class="border-t px-3 py-2 text-xs text-muted-foreground"
      >
        仅显示前 {{ MAX_VISIBLE_ROWS }} 行，另有 {{ hiddenRowCount }} 行未展开。
      </div>
    </div>

    <CodeBlock
      v-else-if="showFallback"
      :code="fallbackCode"
      :language="fallbackLanguage"
    >
      <CodeBlockHeader class="px-2 py-1">
        <CodeBlockTitle>{{ typeof displayValue === "string" ? "Text" : "JSON" }}</CodeBlockTitle>
        <CodeBlockActions>
          <ChatCodeBlockCopyButton :code="fallbackCode" />
        </CodeBlockActions>
      </CodeBlockHeader>
    </CodeBlock>
  </div>
</template>
