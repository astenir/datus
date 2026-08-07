<script setup lang="ts">
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { Spinner } from "@/components/ui/spinner"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { McpServerDetailModel, McpToolView } from "@/features/mcp/types"
import PanelCardHeader from "@/features/shared/PanelCardHeader.vue"

withDefaults(defineProps<{
  server: McpServerDetailModel | null
  tools: readonly McpToolView[]
  toolsLoading: boolean
  canViewTools: boolean
  toolsEmptyLabel: string
  showHeader?: boolean
}>(), {
  showHeader: true,
})
</script>

<template>
  <div
    class="flex min-h-0 flex-1 flex-col gap-4"
    :class="!showHeader && 'p-6'"
  >
    <PanelCardHeader
      v-if="showHeader"
      :title="server?.name || 'MCP Server 详情'"
      :description="server?.target || '未选择 Server'"
    >
      <template #meta>
        <Badge
          v-for="badge in server?.badges ?? []"
          :key="badge"
          variant="outline"
        >
          {{ badge }}
        </Badge>
      </template>
    </PanelCardHeader>

    <template v-if="server">
      <dl
        class="grid shrink-0 gap-3 text-sm sm:grid-cols-2"
        :class="showHeader && 'px-6'"
      >
        <div
          v-for="field in server.fields"
          :key="field.label"
          class="min-w-0"
        >
          <dt class="text-xs text-muted-foreground">{{ field.label }}</dt>
          <dd
            class="mt-1 break-words"
            :class="field.monospace ? 'font-mono text-xs' : ''"
          >
            {{ field.value }}
          </dd>
        </div>
      </dl>

      <Separator />
    </template>

    <div
      class="flex min-h-0 flex-1 flex-col gap-2"
      :class="showHeader && 'px-6'"
    >
      <div
        v-if="server && toolsLoading"
        class="flex shrink-0 justify-end"
      >
        <Spinner />
      </div>

      <div
        v-if="!server"
        class="rounded-lg border p-4 text-sm text-muted-foreground"
      >
        选择一个 MCP Server 查看详情。
      </div>

      <template v-else>
        <p
          v-if="!canViewTools"
          class="text-sm text-muted-foreground"
        >
          当前角色没有查看 MCP 工具的权限。
        </p>
        <p
          v-else-if="toolsLoading"
          class="text-sm text-muted-foreground"
        >
          正在加载工具...
        </p>
        <p
          v-else-if="tools.length === 0"
          class="text-sm text-muted-foreground"
        >
          {{ toolsEmptyLabel }}
        </p>
        <ScrollArea
          v-else-if="canViewTools && !toolsLoading"
          class="min-h-0 flex-1"
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>工具</TableHead>
                <TableHead>说明</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow
                v-for="tool in tools"
                :key="tool.name"
              >
                <TableCell class="font-mono text-xs font-medium">{{ tool.name }}</TableCell>
                <TableCell class="whitespace-normal">{{ tool.description || "-" }}</TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </ScrollArea>
      </template>
    </div>
  </div>
</template>
