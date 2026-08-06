<script setup lang="ts">
import { PlusIcon, RefreshCwIcon } from "@lucide/vue"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import McpScopeSwitcher from "@/features/mcp/McpScopeSwitcher.vue"
import type { McpScope } from "@/features/mcp/types"

defineProps<{
  scope: McpScope
  canViewPublic: boolean
  canViewPersonal: boolean
  description: string
  countLabel: string
  loading: boolean
  canRefresh: boolean
  canCreate: boolean
  createDisabled?: boolean
}>()

const emit = defineEmits<{
  refresh: []
  add: []
  "update:scope": [value: McpScope]
}>()

function updateScope(scope: McpScope): void {
  emit("update:scope", scope)
}
</script>

<template>
  <div
    role="toolbar"
    aria-label="MCP 管理页头工具栏"
    class="flex shrink-0 flex-wrap items-center gap-2 rounded-md border bg-muted/30 px-3 py-2 text-sm"
  >
    <div class="flex min-w-0 flex-1 flex-wrap items-center gap-2">
      <McpScopeSwitcher
        :model-value="scope"
        :can-view-public="canViewPublic"
        :can-view-personal="canViewPersonal"
        @update:model-value="updateScope"
      />
      <span class="min-w-0 truncate text-sm text-muted-foreground">{{ description }}</span>
      <Badge variant="secondary">{{ countLabel }}</Badge>
    </div>
    <div class="ml-auto flex shrink-0 items-center gap-2">
      <Button
        variant="outline"
        size="sm"
        :disabled="loading || !canRefresh"
        @click="emit('refresh')"
      >
        <RefreshCwIcon data-icon="inline-start" />
        刷新
      </Button>
      <Button
        v-if="canCreate"
        size="sm"
        :disabled="createDisabled"
        @click="emit('add')"
      >
        <PlusIcon data-icon="inline-start" />
        添加
      </Button>
    </div>
  </div>
</template>
