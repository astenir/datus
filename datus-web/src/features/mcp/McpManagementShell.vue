<script setup lang="ts">
import McpManagementToolbar from "@/features/mcp/McpManagementToolbar.vue"
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
  canList: boolean
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
  <section class="flex min-h-0 flex-1 overflow-hidden p-4">
    <div class="flex min-h-0 flex-1 flex-col gap-4">
      <McpManagementToolbar
        :scope="scope"
        :can-view-public="canViewPublic"
        :can-view-personal="canViewPersonal"
        :description="description"
        :count-label="countLabel"
        :loading="loading"
        :can-refresh="canRefresh"
        :can-create="canCreate"
        :create-disabled="createDisabled"
        @refresh="emit('refresh')"
        @add="emit('add')"
        @update:scope="updateScope"
      />

      <slot name="notice" />

      <template v-if="canList">
        <div class="grid min-h-0 flex-1 gap-4 xl:grid-cols-[minmax(22rem,0.9fr)_minmax(28rem,1.1fr)]">
          <slot name="list" />
          <slot name="detail" />
        </div>
      </template>
      <slot
        v-else
        name="access"
      />
    </div>

    <slot name="mobile-detail" />
    <slot />
  </section>
</template>
