<script setup lang="ts">
import { WrenchIcon } from "@lucide/vue"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { PermissionRequestDisplay } from "@/lib/interaction-display"

defineProps<{
  request: PermissionRequestDisplay
}>()
</script>

<template>
  <div class="flex flex-col gap-3 rounded-md border bg-background p-3">
    <div class="flex min-w-0 flex-wrap items-center gap-2">
      <Badge variant="secondary">
        <WrenchIcon data-icon="inline-start" />
        工具权限
      </Badge>
      <span class="min-w-0 truncate text-sm font-medium text-foreground">
        {{ request.operationName ?? request.toolName }}
      </span>
      <span
        v-if="request.serverName"
        class="text-xs text-muted-foreground"
      >
        来自 {{ request.serverName }}
      </span>
    </div>

    <div class="flex min-w-0 flex-col gap-1">
      <span class="text-xs font-medium text-muted-foreground">完整工具名</span>
      <code class="block truncate rounded-md bg-muted px-2 py-1 font-mono text-xs text-foreground">
        {{ request.toolName }}
      </code>
    </div>

    <div
      v-if="request.argsRows.length > 0"
      class="max-h-48 overflow-auto rounded-md border"
    >
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead class="h-8 text-xs">参数</TableHead>
            <TableHead class="h-8 text-xs">值</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow
            v-for="row in request.argsRows"
            :key="row.key"
          >
            <TableCell class="py-2 align-top font-mono text-xs">
              {{ row.key }}
            </TableCell>
            <TableCell class="max-w-sm whitespace-normal break-words py-2 align-top text-xs leading-6">
              {{ row.value }}
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>
  </div>
</template>
