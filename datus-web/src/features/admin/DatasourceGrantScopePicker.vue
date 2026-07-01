<script setup lang="ts">
import { computed } from "vue"
import { RefreshCwIcon } from "@lucide/vue"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import DatasourceGrantScopeTreeNode from "@/features/admin/DatasourceGrantScopeTreeNode.vue"
import type { RoleDatasourceTreeNode } from "@/lib/role-permissions"

const props = defineProps<{
  nodes: readonly RoleDatasourceTreeNode[]
  selectedNodeIds: readonly string[]
  loading: boolean
  error: string | null
  disabled?: boolean
}>()

const emit = defineEmits<{
  toggleNode: [nodeId: string]
  reload: []
}>()

const visibleNodes = computed(() => {
  if (props.nodes.length === 1 && props.nodes[0]?.id.startsWith("ds:")) {
    return props.nodes[0]?.children ?? []
  }
  return props.nodes
})

const selectedCount = computed(() => props.selectedNodeIds.length)
</script>

<template>
  <div class="rounded-md border">
    <div class="flex items-center justify-between gap-3 border-b p-3">
      <div class="min-w-0">
        <div class="text-sm font-medium">库、Schema 与表</div>
        <div class="text-xs text-muted-foreground">
          已选择 {{ selectedCount }} 项；展开库或 Schema 后选择具体表
        </div>
      </div>
      <Button
        type="button"
        variant="outline"
        size="sm"
        :disabled="disabled || loading"
        @click="emit('reload')"
      >
        <RefreshCwIcon data-icon="inline-start" />
        刷新
      </Button>
    </div>

    <div
      v-if="loading"
      class="p-4 text-sm text-muted-foreground"
    >
      正在加载数据源目录...
    </div>
    <div
      v-else-if="error"
      class="flex items-center justify-between gap-3 p-4 text-sm text-muted-foreground"
    >
      <span>{{ error }}</span>
      <Button
        type="button"
        variant="outline"
        size="sm"
        :disabled="disabled"
        @click="emit('reload')"
      >
        重试
      </Button>
    </div>
    <div
      v-else-if="!visibleNodes.length"
      class="p-4 text-sm text-muted-foreground"
    >
      当前数据源没有可选目录。请确认后端 catalog 是否可用。
    </div>
    <ScrollArea
      v-else
      class="h-72"
    >
      <ul class="flex flex-col gap-1 p-2">
        <DatasourceGrantScopeTreeNode
          v-for="node in visibleNodes"
          :key="node.id"
          :node="node"
          :selected-node-ids="selectedNodeIds"
          :disabled="disabled"
          @toggle-node="emit('toggleNode', $event)"
        />
      </ul>
    </ScrollArea>
  </div>
</template>
