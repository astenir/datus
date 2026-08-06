<script setup lang="ts">
import { Building2Icon, UserRoundIcon } from "@lucide/vue"

import { Badge } from "@/components/ui/badge"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import type { McpScope } from "@/features/mcp/types"

const props = defineProps<{
  modelValue: McpScope
  canViewPublic: boolean
  canViewPersonal: boolean
}>()

const emit = defineEmits<{
  "update:modelValue": [value: McpScope]
}>()

function updateScope(value: unknown): void {
  if (value === "public" && props.canViewPublic) {
    emit("update:modelValue", "public")
    return
  }

  if (value === "personal" && props.canViewPersonal) {
    emit("update:modelValue", "personal")
  }
}
</script>

<template>
  <ToggleGroup
    v-if="canViewPublic && canViewPersonal"
    type="single"
    variant="outline"
    size="sm"
    :model-value="modelValue"
    aria-label="选择 MCP 范围"
    class="shrink-0"
    @update:model-value="updateScope"
  >
    <ToggleGroupItem value="public">
      <Building2Icon data-icon="inline-start" />
      企业 MCP
    </ToggleGroupItem>
    <ToggleGroupItem value="personal">
      <UserRoundIcon data-icon="inline-start" />
      我的 MCP
    </ToggleGroupItem>
  </ToggleGroup>
  <Badge
    v-else-if="canViewPublic || canViewPersonal"
    variant="outline"
    class="shrink-0"
  >
    {{ canViewPublic ? "企业 MCP" : "我的 MCP" }}
  </Badge>
</template>
