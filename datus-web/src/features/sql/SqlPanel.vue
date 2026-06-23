<script setup lang="ts">
import { computed, ref, shallowRef } from "vue"
import { PlayIcon } from "@lucide/vue"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { sqlApi } from "@/lib/api"
import { displaySqlCellValue, parseSqlReturnRows } from "@/lib/sql-results"
import { useConnection } from "@/composables/useConnection"
import type { ChatWorkspace } from "@/composables/useChatWorkspace"

const props = defineProps<{
  workspace: ChatWorkspace
}>()

const { effectiveBase } = useConnection()
const sql = ref("")
const running = shallowRef(false)
const error = shallowRef("")
const rawResult = shallowRef("")

const rows = computed(() => parseSqlReturnRows(rawResult.value))
const columns = computed(() => {
  const keys = new Set<string>()
  for (const row of rows.value.slice(0, 20)) {
    Object.keys(row).forEach((key) => keys.add(key))
  }
  return Array.from(keys)
})

async function execute() {
  const query = sql.value.trim()
  if (!query) return
  running.value = true
  error.value = ""
  try {
    const result = await sqlApi.execute(effectiveBase(), query, {
      database_name: props.workspace.database.value || undefined,
      result_format: "json",
    })
    rawResult.value = result?.sql_return ?? ""
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    running.value = false
  }
}
</script>

<template>
  <section class="grid min-h-0 flex-1 gap-4 overflow-y-auto p-4 xl:grid-cols-[minmax(360px,520px)_1fr]">
    <Card>
      <CardHeader>
        <CardTitle>SQL 控制台</CardTitle>
      </CardHeader>
      <CardContent class="flex flex-col gap-3">
        <Textarea
          v-model="sql"
          class="min-h-72 font-mono"
          placeholder="select * from ..."
        />
        <Button
          :disabled="running || !sql.trim()"
          @click="execute"
        >
          <PlayIcon data-icon="inline-start" />
          执行
        </Button>
        <p
          v-if="error"
          class="text-sm text-destructive"
        >
          {{ error }}
        </p>
      </CardContent>
    </Card>

    <Card>
      <CardHeader>
        <CardTitle>结果</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead
                v-for="column in columns"
                :key="column"
              >
                {{ column }}
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow
              v-for="(row, rowIndex) in rows"
              :key="rowIndex"
            >
              <TableCell
                v-for="column in columns"
                :key="column"
              >
                {{ displaySqlCellValue(row[column]) }}
              </TableCell>
            </TableRow>
            <TableRow v-if="rows.length === 0">
              <TableCell
                class="h-24 text-center text-muted-foreground"
                :colspan="Math.max(columns.length, 1)"
              >
                暂无结果
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  </section>
</template>
