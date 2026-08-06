<script setup lang="ts">
import { Building2Icon, UserRoundIcon } from "@lucide/vue"

import { Badge } from "@/components/ui/badge"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
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
  <Tabs
    v-if="canViewPublic && canViewPersonal"
    :model-value="modelValue"
    class="shrink-0"
    @update:model-value="updateScope"
  >
    <TabsList
      aria-label="选择 MCP 范围"
      class="flex h-auto max-w-full !flex-row flex-nowrap justify-start"
    >
      <TabsTrigger value="public">
        <Building2Icon data-icon="inline-start" />
        企业 MCP
      </TabsTrigger>
      <TabsTrigger value="personal">
        <UserRoundIcon data-icon="inline-start" />
        我的 MCP
      </TabsTrigger>
    </TabsList>
  </Tabs>
  <Badge
    v-else-if="canViewPublic || canViewPersonal"
    variant="outline"
    class="shrink-0"
  >
    {{ canViewPublic ? "企业 MCP" : "我的 MCP" }}
  </Badge>
</template>
