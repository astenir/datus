<script setup lang="ts">
import { DatabaseIcon, PencilIcon, PlugZapIcon, Trash2Icon } from "@lucide/vue"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableEmpty,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { PersonalDatasourceSummary } from "@/types/profile"

defineProps<{
  datasources: PersonalDatasourceSummary[]
  testingId: string | null
  saving: boolean
}>()

const emit = defineEmits<{
  edit: [datasource: PersonalDatasourceSummary]
  delete: [id: string]
  test: [id: string]
}>()

function labelFor(datasource: PersonalDatasourceSummary): string {
  return datasource.display_name || `${datasource.type}/${datasource.database}`
}
</script>

<template>
  <div class="rounded-md border">
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>名称</TableHead>
          <TableHead>连接</TableHead>
          <TableHead>凭据</TableHead>
          <TableHead>状态</TableHead>
          <TableHead class="w-[13rem] text-right">操作</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow
          v-for="datasource in datasources"
          :key="datasource.id"
        >
          <TableCell class="font-medium">
            <div class="flex min-w-0 items-center gap-2">
              <DatabaseIcon class="text-muted-foreground" />
              <span class="truncate">{{ labelFor(datasource) }}</span>
            </div>
          </TableCell>
          <TableCell>
            <div class="min-w-0">
              <div class="truncate text-sm">{{ datasource.host }}:{{ datasource.port }}</div>
              <div class="truncate text-xs text-muted-foreground">{{ datasource.type }} / {{ datasource.database }}</div>
            </div>
          </TableCell>
          <TableCell>
            <div class="min-w-0">
              <div class="truncate text-sm">{{ datasource.username }}</div>
              <div class="truncate font-mono text-xs text-muted-foreground">{{ datasource.password_hint }}</div>
            </div>
          </TableCell>
          <TableCell>
            <Badge :variant="datasource.enabled ? 'secondary' : 'outline'">
              {{ datasource.enabled ? "启用" : "停用" }}
            </Badge>
          </TableCell>
          <TableCell>
            <div class="flex justify-end gap-1.5">
              <Button
                variant="outline"
                size="sm"
                :disabled="testingId === datasource.id || saving"
                @click="emit('test', datasource.id)"
              >
                <PlugZapIcon data-icon="inline-start" />
                测试
              </Button>
              <Button
                variant="ghost"
                size="icon-sm"
                :disabled="saving"
                title="编辑"
                @click="emit('edit', datasource)"
              >
                <PencilIcon />
              </Button>
              <Button
                variant="ghost"
                size="icon-sm"
                :disabled="saving"
                title="删除"
                @click="emit('delete', datasource.id)"
              >
                <Trash2Icon />
              </Button>
            </div>
          </TableCell>
        </TableRow>
        <TableEmpty
          v-if="datasources.length === 0"
          :colspan="5"
        >
          还没有个人数据源。
        </TableEmpty>
      </TableBody>
    </Table>
  </div>
</template>
