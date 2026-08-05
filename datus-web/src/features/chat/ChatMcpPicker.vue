<script setup lang="ts">
import { computed, shallowRef } from "vue"
import { CheckIcon, ChevronDownIcon, LockKeyholeIcon, PlugZapIcon, RefreshCwIcon } from "@lucide/vue"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Popover,
  PopoverContent,
  PopoverDescription,
  PopoverHeader,
  PopoverTitle,
  PopoverTrigger,
} from "@/components/ui/popover"
import { Separator } from "@/components/ui/separator"
import { Spinner } from "@/components/ui/spinner"
import type { PersonalMcpSummary } from "@/types/profile"

const props = defineProps<{
  servers: readonly PersonalMcpSummary[]
  selectedIds: readonly string[]
  locked: boolean
  loading: boolean
  disabled: boolean
  maxSelected: number
  agentAllowsPersonalMcp: boolean
  organizationAvailable: boolean
  enterpriseMcpCount?: number
}>()

const emit = defineEmits<{
  toggle: [mcpId: string]
  refresh: []
}>()

const open = shallowRef(false)
const enabledServers = computed(() => props.servers.filter(server => server.enabled))
const selectedSet = computed(() => new Set(props.selectedIds))
const selectedCount = computed(() => props.selectedIds.length)
const triggerLabel = computed(() => {
  if (props.locked) return selectedCount.value ? `个人 MCP ${selectedCount.value}（已锁定）` : "个人 MCP（已锁定）"
  return selectedCount.value ? `个人 MCP ${selectedCount.value}` : "个人 MCP"
})
const disabledReason = computed(() => {
  if (!props.organizationAvailable) return "组织尚未启用个人 MCP 或未配置允许域名。"
  if (!props.agentAllowsPersonalMcp) return "当前 Agent 不允许使用个人 MCP。"
  if (props.locked) return "会话建立后个人 MCP 选择已锁定。"
  return ""
})

function isSelected(id: string): boolean {
  return selectedSet.value.has(id)
}
</script>

<template>
  <Popover v-model:open="open">
    <PopoverTrigger as-child>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        class="max-w-52 rounded-full"
        :disabled="disabled"
        aria-label="选择个人 MCP"
      >
        <Spinner v-if="loading" data-icon="inline-start" />
        <LockKeyholeIcon v-else-if="locked" data-icon="inline-start" />
        <PlugZapIcon v-else data-icon="inline-start" />
        <span class="truncate">{{ triggerLabel }}</span>
        <ChevronDownIcon data-icon="inline-end" />
      </Button>
    </PopoverTrigger>
    <PopoverContent align="start" class="w-80 p-0">
      <PopoverHeader class="p-3 pb-2">
        <div class="flex items-start justify-between gap-2">
          <div>
            <PopoverTitle>新会话个人 MCP</PopoverTitle>
            <PopoverDescription>
              最多选择 {{ maxSelected }} 个；会话建立后不可切换。
            </PopoverDescription>
          </div>
          <Button
            variant="ghost"
            size="icon-sm"
            :disabled="loading"
            aria-label="刷新个人 MCP"
            title="刷新"
            @click="emit('refresh')"
          >
            <RefreshCwIcon :class="loading ? 'animate-spin' : ''" />
          </Button>
        </div>
      </PopoverHeader>
      <Separator />

      <div v-if="disabledReason" class="px-3 py-3 text-sm text-muted-foreground">
        {{ disabledReason }}
      </div>
      <div v-else-if="enabledServers.length === 0" class="px-3 py-5 text-center text-sm text-muted-foreground">
        还没有可选择的个人 MCP。
      </div>
      <div v-else class="max-h-64 overflow-y-auto p-1.5">
        <Button
          v-for="server in enabledServers"
          :key="server.id"
          type="button"
          variant="ghost"
          class="h-auto w-full justify-start gap-2 px-2.5 py-2 text-left"
          :disabled="locked"
          @click="emit('toggle', server.id)"
        >
          <span
            class="flex size-4 shrink-0 items-center justify-center rounded-sm border"
            :class="isSelected(server.id) ? 'border-primary bg-primary text-primary-foreground' : 'border-input'"
          >
            <CheckIcon v-if="isSelected(server.id)" class="size-3" />
          </span>
          <span class="min-w-0 flex-1">
            <span class="block truncate text-sm font-medium">{{ server.display_name }}</span>
            <span class="block truncate text-xs text-muted-foreground">
              {{ server.transport.toUpperCase() }} · {{ server.url }}
            </span>
          </span>
        </Button>
      </div>

      <template v-if="enterpriseMcpCount !== undefined">
        <Separator />
        <div class="flex items-center gap-2 px-3 py-2 text-xs text-muted-foreground">
          <Badge variant="outline">企业 MCP {{ enterpriseMcpCount }}</Badge>
          <span>由 Agent 提供，不在这里选择。</span>
        </div>
      </template>
    </PopoverContent>
  </Popover>
</template>
