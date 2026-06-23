<script setup lang="ts">
import { computed } from "vue"
import { RefreshCwIcon } from "@lucide/vue"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { ChatWorkspace } from "@/composables/useChatWorkspace"
import { databaseNameFromCatalog } from "@/lib/chat"

const props = defineProps<{
  workspace: ChatWorkspace
}>()

const rows = computed(() =>
  props.workspace.catalogEntries.value.map((entry) => ({
    database: databaseNameFromCatalog(entry),
    type: String(entry.type ?? ""),
    schema: String(entry.schema_name ?? entry.catalog_name ?? ""),
    tables: Array.isArray(entry.tables) ? entry.tables.length : 0,
  })),
)
</script>

<template>
  <section class="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4">
    <Card>
      <CardHeader class="flex-row items-center justify-between">
        <CardTitle>知识与目录</CardTitle>
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
              v-for="row in rows"
              :key="`${row.database}-${row.schema}`"
            >
              <TableCell class="font-medium">{{ row.database }}</TableCell>
              <TableCell>{{ row.schema || "-" }}</TableCell>
              <TableCell>{{ row.type || "-" }}</TableCell>
              <TableCell class="text-right">{{ row.tables }}</TableCell>
            </TableRow>
            <TableRow v-if="rows.length === 0">
              <TableCell
                class="h-24 text-center text-muted-foreground"
                colspan="4"
              >
                暂无目录数据
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  </section>
</template>
