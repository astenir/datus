<script setup lang="ts">
import { computed, onMounted, shallowRef, watch } from "vue"
import { Building2Icon, UserRoundIcon } from "@lucide/vue"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { usePermission } from "@/composables/usePermission"
import PersonalMcpPanel from "@/features/mcp/PersonalMcpPanel.vue"
import PublicMcpPanel from "@/features/mcp/PublicMcpPanel.vue"

type McpScope = "public" | "personal"

const permission = usePermission()
const activeScope = shallowRef<McpScope>("public")
const canViewPublic = computed(() => permission.isAdmin() || permission.hasPermission("module.mcp"))
const canViewPersonal = computed(() =>
  permission.isAdmin()
  || permission.hasPermission("module.mcp.personal")
  || permission.hasFeaturePermission("mcp_personal")
)
const hasAnyScope = computed(() => canViewPublic.value || canViewPersonal.value)

watch([canViewPublic, canViewPersonal], ([publicAllowed, personalAllowed]) => {
  if (activeScope.value === "public" && !publicAllowed && personalAllowed) activeScope.value = "personal"
  if (activeScope.value === "personal" && !personalAllowed && publicAllowed) activeScope.value = "public"
}, { immediate: true })

onMounted(() => {
  if (!permission.isLoaded.value) void permission.fetchPermissions()
})
</script>

<template>
  <Tabs
    v-model="activeScope"
    class="flex min-h-0 flex-1 flex-col"
  >
    <div class="shrink-0 px-4 pt-4">
      <TabsList aria-label="MCP 范围">
        <TabsTrigger
          v-if="canViewPublic"
          value="public"
        >
          <Building2Icon data-icon="inline-start" />
          企业 MCP
        </TabsTrigger>
        <TabsTrigger
          v-if="canViewPersonal"
          value="personal"
        >
          <UserRoundIcon data-icon="inline-start" />
          我的 MCP
        </TabsTrigger>
      </TabsList>
    </div>

    <TabsContent
      v-if="canViewPublic"
      value="public"
      class="mt-0 min-h-0 flex-1"
    >
      <PublicMcpPanel />
    </TabsContent>
    <TabsContent
      v-if="canViewPersonal"
      value="personal"
      class="mt-0 min-h-0 flex-1"
    >
      <PersonalMcpPanel />
    </TabsContent>

    <div
      v-if="permission.isLoaded.value && !hasAnyScope"
      class="p-4"
    >
      <Alert>
        <AlertTitle>没有 MCP 访问权限</AlertTitle>
        <AlertDescription>请联系管理员开通企业 MCP 或个人 MCP 权限。</AlertDescription>
      </Alert>
    </div>
  </Tabs>
</template>
