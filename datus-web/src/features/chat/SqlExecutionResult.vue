<script setup lang="ts">
import { AlertCircleIcon, Loader2Icon } from "@lucide/vue"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

const props = defineProps<{
  running: boolean
  error: string
  contextLabel: string
  columns: readonly string[]
  rows: readonly (readonly string[])[]
  rawResult: string
  hasResult: boolean
  rowCountLabel: string
  executionTimeLabel: string
}>()
</script>

<template>
  <section class="flex min-w-0 flex-col gap-3" aria-labelledby="sql-execution-result-title">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <h3 id="sql-execution-result-title" class="text-sm font-medium">
        执行结果
      </h3>
      <div class="flex flex-wrap items-center gap-2">
        <Badge v-if="props.running" variant="secondary">
          <Loader2Icon data-icon="inline-start" class="animate-spin" />
          执行中
        </Badge>
        <span
          v-else-if="props.hasResult"
          class="text-xs text-muted-foreground"
        >
          {{ props.rowCountLabel }}<template v-if="props.executionTimeLabel"> · {{ props.executionTimeLabel }}</template>
        </span>
      </div>
    </div>

    <Alert v-if="props.error" variant="destructive">
      <AlertCircleIcon />
      <AlertTitle>执行失败</AlertTitle>
      <AlertDescription class="flex flex-col gap-1">
        <span>{{ props.error }}</span>
        <span class="text-xs opacity-90">执行上下文：{{ props.contextLabel }}</span>
      </AlertDescription>
    </Alert>

    <div
      v-else-if="props.columns.length > 0"
      class="max-h-[40vh] min-w-0 overflow-auto rounded-md border bg-background [&_[data-slot=table-container]]:overflow-visible"
    >
      <Table class="min-w-max">
        <TableHeader class="sticky top-0 bg-muted">
          <TableRow>
            <TableHead
              v-for="column in props.columns"
              :key="column"
              class="h-9 text-xs"
            >
              {{ column }}
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow
            v-for="(row, rowIndex) in props.rows"
            :key="`${rowIndex}-${row.join('|')}`"
          >
            <TableCell
              v-for="(cell, cellIndex) in row"
              :key="`${rowIndex}-${props.columns[cellIndex] ?? cellIndex}`"
              class="max-w-sm whitespace-normal break-words py-2 align-top text-xs leading-6"
            >
              {{ cell }}
            </TableCell>
          </TableRow>
          <TableRow v-if="props.rows.length === 0">
            <TableCell
              :colspan="Math.max(props.columns.length, 1)"
              class="h-20 text-center text-xs text-muted-foreground"
            >
              执行完成，无数据
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>

    <pre
      v-else-if="props.rawResult"
      class="max-h-[40vh] max-w-full overflow-auto rounded-md bg-muted p-3 font-mono text-xs leading-6 text-muted-foreground"
    >{{ props.rawResult }}</pre>

    <p
      v-else-if="props.hasResult"
      class="rounded-md border bg-background p-3 text-sm text-muted-foreground"
    >
      执行完成，后端没有返回可展示的结果。
    </p>
  </section>
</template>
