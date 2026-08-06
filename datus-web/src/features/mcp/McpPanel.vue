<script setup lang="ts">
import { computed, onMounted, shallowRef, watch } from "vue"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { usePermission } from "@/composables/usePermission"
import PersonalMcpPanel from "@/features/mcp/PersonalMcpPanel.vue"
import PublicMcpPanel from "@/features/mcp/PublicMcpPanel.vue"
import { mcpScopeAccessFromPermission } from "@/features/mcp/access"
import type { McpScope } from "@/features/mcp/types"

const permission = usePermission()
const activeScope = shallowRef<McpScope>("public")
const scopeAccess = computed(() => mcpScopeAccessFromPermission(permission))
const canViewPublic = computed(() => scopeAccess.value.canViewPublic)
const canViewPersonal = computed(() => scopeAccess.value.canViewPersonal)
const hasAnyScope = computed(() => scopeAccess.value.hasAnyScope)

watch(
  [canViewPublic, canViewPersonal],
  ([publicAllowed, personalAllowed]) => {
    if (activeScope.value === "public" && !publicAllowed && personalAllowed) {
      activeScope.value = "personal"
    }
    if (activeScope.value === "personal" && !personalAllowed && publicAllowed) {
      activeScope.value = "public"
    }
  },
  { immediate: true },
)

function updateScope(scope: McpScope): void {
  if (scope === "public" && canViewPublic.value) {
    activeScope.value = scope
    return
  }
  if (scope === "personal" && canViewPersonal.value) {
    activeScope.value = scope
  }
}

onMounted(() => {
  if (!permission.isLoaded.value) void permission.fetchPermissions()
})
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col">
    <PublicMcpPanel
      v-if="activeScope === 'public' && canViewPublic"
      :scope="activeScope"
      :can-view-public="canViewPublic"
      :can-view-personal="canViewPersonal"
      @update:scope="updateScope"
    />
    <PersonalMcpPanel
      v-else-if="activeScope === 'personal' && canViewPersonal"
      :scope="activeScope"
      :can-view-public="canViewPublic"
      :can-view-personal="canViewPersonal"
      @update:scope="updateScope"
    />

    <div
      v-else-if="permission.isLoaded && !hasAnyScope"
      class="p-4"
    >
      <Alert>
        <AlertTitle>没有 MCP 访问权限</AlertTitle>
        <AlertDescription>请联系管理员开通企业 MCP 或个人 MCP 权限。</AlertDescription>
      </Alert>
    </div>
  </div>
</template>
