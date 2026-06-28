<script setup lang="ts">
import { computed, ref, shallowRef } from "vue"
import { DatabaseIcon, PlayIcon } from "@lucide/vue"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs"
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
import { useContextInspector, type ContextInspectorCommandId } from "@/composables/useContextInspector"
import type { ChatWorkspace } from "@/composables/useChatWorkspace"

const props = defineProps<{
  workspace: ChatWorkspace
}>()

const { effectiveBase } = useConnection()
const sql = ref("")
const running = shallowRef(false)
const error = shallowRef("")
const rawResult = shallowRef("")
const contextInspector = useContextInspector()

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

async function runContextCommand(commandId: ContextInspectorCommandId) {
  await contextInspector.runCommand(commandId, {
    databaseName: props.workspace.database.value || undefined,
    schemaName: props.workspace.schema.value || undefined,
  })
}
</script>

<template>
  <section class="grid min-h-0 flex-1 auto-rows-min items-start gap-4 overflow-y-auto p-4 xl:grid-cols-[minmax(360px,520px)_1fr]">
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

    <Card class="min-h-0">
      <CardHeader>
        <CardTitle>结果与上下文</CardTitle>
        <CardDescription>
          SQL 查询结果与只读数据源元数据检查。
        </CardDescription>
      </CardHeader>
      <CardContent class="min-h-0">
        <Tabs
          default-value="query"
          class="min-h-0"
        >
          <TabsList>
            <TabsTrigger value="query">SQL 结果</TabsTrigger>
            <TabsTrigger value="context">元数据上下文</TabsTrigger>
          </TabsList>

          <TabsContent
            value="query"
            class="min-h-0"
          >
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
          </TabsContent>

          <TabsContent
            value="context"
            class="flex min-h-0 flex-col gap-4"
          >
            <div class="grid gap-3 md:grid-cols-2">
              <div
                v-for="command in contextInspector.commands"
                :key="command.id"
                class="rounded-lg border bg-background p-3"
              >
                <Button
                  variant="outline"
                  size="sm"
                  class="w-full justify-start"
                  :disabled="contextInspector.isLoading.value"
                  @click="runContextCommand(command.id)"
                >
                  <DatabaseIcon data-icon="inline-start" />
                  {{ command.label }}
                </Button>
                <p class="mt-2 text-xs leading-5 text-muted-foreground">
                  {{ command.description }}
                </p>
              </div>
            </div>

            <Separator />

            <div class="flex flex-wrap items-center gap-2">
              <Badge variant="outline">{{ contextInspector.selectedCommand.value.label }}</Badge>
              <Badge
                v-if="contextInspector.tableRows.value.length > 0"
                variant="secondary"
              >
                {{ contextInspector.tableRows.value.length }} 项
              </Badge>
              <Badge
                v-if="contextInspector.isLoading.value"
                variant="secondary"
              >
                读取中
              </Badge>
            </div>

            <p
              v-if="contextInspector.error.value"
              class="text-sm text-destructive"
            >
              {{ contextInspector.error.value }}
            </p>
            <p class="text-sm leading-6 text-muted-foreground">
              {{ contextInspector.outputText.value }}
            </p>

            <Table v-if="contextInspector.tableRows.value.length > 0">
              <TableHeader>
                <TableRow>
                  <TableHead>名称</TableHead>
                  <TableHead>类型</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow
                  v-for="row in contextInspector.tableRows.value"
                  :key="`${row.type}:${row.name}`"
                >
                  <TableCell>{{ row.name }}</TableCell>
                  <TableCell>{{ row.type }}</TableCell>
                </TableRow>
              </TableBody>
            </Table>

            <pre
              v-if="contextInspector.result.value"
              class="max-h-72 overflow-auto rounded-md bg-muted p-3 font-mono text-xs leading-6 text-muted-foreground"
            >
{{ contextInspector.resultJson.value }}
            </pre>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  </section>
</template>
