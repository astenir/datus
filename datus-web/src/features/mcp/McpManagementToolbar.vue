<script setup lang="ts">
import { PlusIcon, RefreshCwIcon, ServerIcon } from "@lucide/vue"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import McpScopeSwitcher from "@/features/mcp/McpScopeSwitcher.vue"
import PageHeaderToolbar from "@/features/shared/PageHeaderToolbar.vue"
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
  <PageHeaderToolbar
    title="MCP 管理"
    :description="description"
    aria-label="MCP 管理页头工具栏"
  >
    <template #leading>
      <ServerIcon />
    </template>

    <template #meta>
      <Badge variant="secondary">{{ countLabel }}</Badge>
    </template>

    <template #navigation>
      <McpScopeSwitcher
        :model-value="scope"
        :can-view-public="canViewPublic"
        :can-view-personal="canViewPersonal"
        @update:model-value="updateScope"
      />
    </template>

    <template #actions>
      <Button
        variant="outline"
        size="sm"
        :disabled="loading || !canRefresh"
        @click="emit('refresh')"
      >
        <RefreshCwIcon
          data-icon="inline-start"
          :class="loading && 'animate-spin'"
        />
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
    </template>
  </PageHeaderToolbar>
</template>
