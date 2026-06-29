<script setup lang="ts">
import type { BundledLanguage } from "shiki"
import { computed } from "vue"
import { Badge } from "@/components/ui/badge"
import {
  CodeBlock,
  CodeBlockActions,
  CodeBlockCopyButton,
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
import {
  displayValueForTool,
  sqlFromToolValue,
  sqlKeys,
  summarizeValue,
  tableFromToolValue,
} from "@/lib/tool-display"

const MAX_VISIBLE_ROWS = 50

const props = defineProps<{
  mode: "input" | "output"
  toolName: string
  value?: unknown
  errorText?: string
}>()

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

function formatCode(value: unknown): string {
  if (typeof value === "string") return value
  return JSON.stringify(value, null, 2)
}

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value)
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
      <CodeBlockHeader>
        <CodeBlockTitle>SQL</CodeBlockTitle>
        <CodeBlockActions>
          <CodeBlockCopyButton />
        </CodeBlockActions>
      </CodeBlockHeader>
    </CodeBlock>

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
      <CodeBlockHeader>
        <CodeBlockTitle>{{ typeof displayValue === "string" ? "Text" : "JSON" }}</CodeBlockTitle>
        <CodeBlockActions>
          <CodeBlockCopyButton />
        </CodeBlockActions>
      </CodeBlockHeader>
    </CodeBlock>
  </div>
</template>
