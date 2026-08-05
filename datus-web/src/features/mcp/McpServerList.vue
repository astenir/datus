<script setup lang="ts">
import { ActivityIcon, PencilIcon, ServerIcon, Trash2Icon } from "@lucide/vue"

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
import type { PersonalMcpSummary } from "@/types/profile"

defineProps<{
  servers: readonly PersonalMcpSummary[]
  selectedId: string
  loading: boolean
  checkingId: string | null
  canEdit: boolean
  canRemove: boolean
  canTest: boolean
}>()

const emit = defineEmits<{
  select: [id: string]
  edit: [server: PersonalMcpSummary]
  remove: [server: PersonalMcpSummary]
  test: [id: string]
}>()
</script>

<template>
  <div class="overflow-x-auto rounded-md border">
    <Table class="min-w-3xl">
      <TableHeader>
        <TableRow>
          <TableHead>名称</TableHead>
          <TableHead>连接</TableHead>
          <TableHead>凭据</TableHead>
          <TableHead>状态</TableHead>
          <TableHead class="w-[12rem] text-right">操作</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow
          v-for="server in servers"
          :key="server.id"
          class="cursor-pointer"
          :data-state="server.id === selectedId ? 'selected' : undefined"
          @click="emit('select', server.id)"
        >
          <TableCell>
            <div class="flex min-w-0 items-center gap-2">
              <ServerIcon class="shrink-0 text-muted-foreground" />
              <div class="min-w-0">
                <div class="truncate text-sm font-medium">{{ server.display_name }}</div>
                <div class="truncate font-mono text-xs text-muted-foreground">{{ server.id }}</div>
              </div>
            </div>
          </TableCell>
          <TableCell>
            <div class="min-w-0">
              <Badge variant="outline">{{ server.transport.toUpperCase() }}</Badge>
              <div class="mt-1 max-w-64 truncate text-xs text-muted-foreground">{{ server.url }}</div>
            </div>
          </TableCell>
          <TableCell>
            <span class="text-sm">{{ server.credential_configured ? server.token_hint || "已配置" : "无认证" }}</span>
          </TableCell>
          <TableCell>
            <Badge :variant="server.enabled ? 'secondary' : 'outline'">
              {{ server.enabled ? "启用" : "停用" }}
            </Badge>
          </TableCell>
          <TableCell @click.stop>
            <div class="flex justify-end gap-1.5">
              <Button
                v-if="canTest"
                variant="outline"
                size="sm"
                :disabled="checkingId === server.id || loading"
                @click="emit('test', server.id)"
              >
                <ActivityIcon data-icon="inline-start" />
                {{ checkingId === server.id ? "测试中" : "测试" }}
              </Button>
              <Button
                v-if="canEdit"
                variant="ghost"
                size="icon-sm"
                :disabled="loading"
                title="编辑"
                aria-label="编辑个人 MCP"
                @click="emit('edit', server)"
              >
                <PencilIcon />
              </Button>
              <Button
                v-if="canRemove"
                variant="ghost"
                size="icon-sm"
                class="text-destructive hover:text-destructive"
                :disabled="loading"
                title="删除"
                aria-label="删除个人 MCP"
                @click="emit('remove', server)"
              >
                <Trash2Icon />
              </Button>
            </div>
          </TableCell>
        </TableRow>
        <TableEmpty
          v-if="servers.length === 0"
          :colspan="5"
        >
          {{ loading ? "正在加载个人 MCP..." : "还没有个人 MCP。" }}
        </TableEmpty>
      </TableBody>
    </Table>
  </div>
</template>
